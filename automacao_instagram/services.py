import logging

from django.utils import timezone

from . import instagram_api
from .models import AutomacaoComentario, ComentarioProcessado, ContaInstagramConectada

logger = logging.getLogger(__name__)


def processar_ciclo() -> None:
    """Chamado a cada intervalo pelo worker (ver management/commands). Percorre
    todas as automações ativas, processa comentários novos e depois confere se
    alguma DM enviada anteriormente já foi respondida."""
    for automacao in AutomacaoComentario.objects.filter(ativa=True).select_related("conta"):
        _processar_automacao(automacao)
    _verificar_dms_respondidas()


def _processar_automacao(automacao: AutomacaoComentario) -> None:
    conta = automacao.conta
    try:
        comentarios = instagram_api.listar_comentarios(automacao.instagram_media_id, conta.access_token)
    except instagram_api.InstagramAPIError:
        logger.exception("[automacao_instagram] falha ao listar comentários da automação %s", automacao.pk)
        return

    ids_ja_processados = set(automacao.comentarios.values_list("instagram_comment_id", flat=True))
    for comentario in comentarios:
        comment_id = comentario.get("id")
        if not comment_id or comment_id in ids_ja_processados:
            continue
        palavra = automacao.encontra_palavra_chave(comentario.get("text", ""))
        if not palavra:
            continue
        _processar_comentario_correspondido(automacao, comentario, palavra)


def _processar_comentario_correspondido(automacao: AutomacaoComentario, comentario: dict, palavra: str) -> None:
    conta = automacao.conta
    autor = comentario.get("from") or {}
    registro = ComentarioProcessado(
        automacao=automacao,
        instagram_comment_id=comentario["id"],
        instagram_autor_id=autor.get("id", ""),
        autor_username=autor.get("username") or comentario.get("username", ""),
        texto_comentario=comentario.get("text", ""),
        palavra_chave_encontrada=palavra,
    )

    if automacao.responder_comentario and automacao.texto_resposta:
        try:
            instagram_api.responder_comentario(comentario["id"], automacao.texto_resposta, conta.access_token)
            registro.resposta_publica_enviada = True
        except instagram_api.InstagramAPIError as erro:
            logger.exception("[automacao_instagram] falha ao responder comentário %s", comentario["id"])
            registro.resposta_publica_erro = str(erro)

    if automacao.enviar_dm and automacao.texto_dm:
        try:
            instagram_api.enviar_resposta_privada(
                conta.instagram_business_account_id, comentario["id"], automacao.texto_dm, conta.access_token,
            )
            registro.dm_enviada = True
        except instagram_api.InstagramAPIError as erro:
            logger.exception("[automacao_instagram] falha ao enviar DM pro comentário %s", comentario["id"])
            registro.dm_erro = str(erro)

    registro.save()


def _verificar_dms_respondidas() -> None:
    """Pra cada conta com DM pendente de resposta, busca as conversas recentes do
    direto e marca como respondida se o autor mandou alguma mensagem depois da DM."""
    contas_pendentes = ContaInstagramConectada.objects.filter(
        automacoes__comentarios__dm_enviada=True,
        automacoes__comentarios__dm_respondida=False,
    ).distinct()

    for conta in contas_pendentes:
        pendentes = ComentarioProcessado.objects.filter(
            automacao__conta=conta, dm_enviada=True, dm_respondida=False,
        ).exclude(instagram_autor_id="")
        pendentes_por_autor = {p.instagram_autor_id: p for p in pendentes}
        if not pendentes_por_autor:
            continue

        try:
            conversas = instagram_api.listar_conversas(conta.instagram_business_account_id, conta.access_token)
        except instagram_api.InstagramAPIError:
            logger.exception("[automacao_instagram] falha ao listar conversas da conta %s", conta.pk)
            continue

        for conversa in conversas:
            participantes = {p.get("id") for p in conversa.get("participants", {}).get("data", [])}
            autor_id = next((pid for pid in participantes if pid in pendentes_por_autor), None)
            if not autor_id:
                continue

            mensagens = conversa.get("messages", {}).get("data", [])
            respondeu = any((m.get("from") or {}).get("id") == autor_id for m in mensagens)
            if respondeu:
                pendente = pendentes_por_autor[autor_id]
                pendente.dm_respondida = True
                pendente.dm_respondida_em = timezone.now()
                pendente.save(update_fields=["dm_respondida", "dm_respondida_em"])
