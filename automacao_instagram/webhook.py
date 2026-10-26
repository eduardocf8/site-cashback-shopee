import hashlib
import hmac
import logging

from django.conf import settings
from django.urls import reverse

from instagram_bot.models import RegistroPublicacao

from . import instagram_api
from .models import AutomacaoStory, RespostaStoryProcessada

logger = logging.getLogger(__name__)


def verificar_assinatura(corpo: bytes, assinatura_header: str | None) -> bool:
    """Confere o cabeçalho X-Hub-Signature-256 que a Meta manda em toda entrega de
    webhook, calculado com o INSTAGRAM_APP_SECRET (mesmo App usado pelo instagram_bot
    - ver marketing/instagram/README.md) - sem essa checagem, qualquer um que
    descobrisse a URL do webhook poderia forjar "resposta a story" nossa."""
    if not assinatura_header or not settings.INSTAGRAM_APP_SECRET:
        return False
    esperado = "sha256=" + hmac.new(
        settings.INSTAGRAM_APP_SECRET.encode(), corpo, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, assinatura_header)


def _extrair_eventos_de_mensagem(payload: dict) -> list[dict]:
    """Achata o payload do webhook numa lista de "eventos de mensagem" (cada um com
    sender/message). A Graph API entrega mensagem do Instagram tanto em
    `entry[].messaging[]` (formato herdado do Messenger) quanto em `entry[].changes[]`
    com field="messages" (formato "cru" que outros webhooks da Graph API usam) - sem
    ter testado contra tráfego real ainda pra saber qual essa conta recebe, aceita as
    duas."""
    eventos = []
    for entry in payload.get("entry", []):
        eventos.extend(entry.get("messaging", []) or [])
        for change in entry.get("changes", []) or []:
            if change.get("field") == "messages" and isinstance(change.get("value"), dict):
                eventos.append(change["value"])
    return eventos


def _link_do_produto(story_media_id: str, request) -> str:
    """Link rastreado (com cashback) do produto daquele story - só existe quando o
    story foi publicado pelo instagram_bot (ver RegistroPublicacao.link_produto_original).
    Vazio quando não achou (ex: story postado fora do bot, ou já fora da janela)."""
    registro = RegistroPublicacao.objects.filter(
        instagram_media_id=story_media_id,
    ).exclude(link_produto_original="").first()
    if not registro:
        return ""
    return request.build_absolute_uri(reverse("instagram_story_ir", args=[registro.pk]))


def _ja_respondido(automacao: AutomacaoStory, sender_id: str) -> bool:
    """True se essa pessoa já recebeu uma DM dessa automação antes - 1 DM por pessoa
    por automação de story, senão cada resposta nova (reação, "obrigada" etc.) manda
    de novo."""
    return automacao.respostas.filter(instagram_autor_id=sender_id, dm_enviada=True).exists()


def _processar_um_evento(evento: dict, request) -> None:
    mensagem = evento.get("message") or {}
    if mensagem.get("is_echo"):
        # Mensagem que a própria conta mandou (inclusive as DMs que essa automação
        # manda) também chega como evento - ignora, senão o bot reagiria à própria DM.
        return

    story = (mensagem.get("reply_to") or {}).get("story") or {}
    story_media_id = story.get("id", "")
    if not story_media_id:
        return  # não é resposta a story (DM comum, reação a mensagem, etc.) - fora do escopo daqui.

    automacao = AutomacaoStory.objects.filter(
        instagram_story_media_id=story_media_id, ativa=True,
    ).select_related("conta").first()
    if not automacao:
        return  # sem automação configurada pra esse story - igual comentário sem palavra-chave, ignora.

    sender_id = (evento.get("sender") or {}).get("id", "")
    if not sender_id or _ja_respondido(automacao, sender_id):
        return

    if automacao.modo_resposta == AutomacaoStory.MODO_LINK_PRODUTO:
        link = _link_do_produto(story_media_id, request)
        if not link:
            logger.warning(
                "[automacao_instagram] automação %s está em modo link_produto, mas o story %s não "
                "tem link_produto_original gravado (não foi publicado pelo instagram_bot?) - ignorando.",
                automacao.pk, story_media_id,
            )
            return
        texto_dm = f"Aqui está o link com o cashback garantido: {link}"
    else:
        texto_dm = automacao.texto_personalizado

    registro = RespostaStoryProcessada(
        automacao=automacao, instagram_autor_id=sender_id, texto_recebido=mensagem.get("text", ""),
    )
    try:
        instagram_api.enviar_mensagem_direta(
            automacao.conta.instagram_business_account_id, sender_id, texto_dm, automacao.conta.access_token,
        )
        registro.dm_enviada = True
    except instagram_api.InstagramAPIError as erro:
        logger.exception("[automacao_instagram] falha ao enviar DM de resposta a story pra %s", sender_id)
        registro.dm_erro = str(erro)
    registro.save()


def processar_evento_webhook(payload: dict, request) -> None:
    """Chamado pela view do webhook (ver views.py) a cada entrega da Meta. Por
    evento: se for resposta a um story com AutomacaoStory ativa, manda a DM
    configurada (link do produto detectado ou mensagem personalizada) - no máximo 1
    por pessoa por automação (ver _ja_respondido)."""
    for evento in _extrair_eventos_de_mensagem(payload):
        try:
            _processar_um_evento(evento, request)
        except Exception:
            logger.exception("[automacao_instagram] falha ao processar evento do webhook: %s", evento)
