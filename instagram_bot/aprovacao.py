import logging

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage
from django.urls import reverse

from . import instagram_client
from .models import RegistroPublicacao

logger = logging.getLogger(__name__)

SALT_APROVACAO = "instagram_bot.aprovacao"
IDADE_MAXIMA_TOKEN = 60 * 60 * 36  # 36h - dá tempo de ver no celular sem ficar pendente pra sempre


def _gerar_token(registro_id: int, acao: str) -> str:
    return signing.dumps({"id": registro_id, "acao": acao}, salt=SALT_APROVACAO)


def _validar_token(token: str) -> dict | None:
    try:
        return signing.loads(token, salt=SALT_APROVACAO, max_age=IDADE_MAXIMA_TOKEN)
    except signing.BadSignature:
        return None


def enviar_email_aprovacao(
    registro: RegistroPublicacao,
    imagens_bytes: list[bytes],
    request,
    posicao: tuple[int, int] | None = None,
) -> None:
    """imagens_bytes tem 1 item pra story/post normal, ou N itens (na ordem dos slides) pra carrossel.

    posicao é (qual, total) e só vale pra conteúdo que sai em mais de um e-mail no mesmo
    dia - hoje, o combo diário de stories. Sem ela, os três e-mails chegavam com assunto
    idêntico e sem ordem garantida (a entrega não respeita a ordem de envio), e a única
    forma de saber qual era qual era abrindo os três. O número vem antes do resto do
    assunto de propósito: assim a ordem aparece na lista da caixa de entrada, sem abrir
    nada.
    """
    destinatario = settings.INSTAGRAM_APROVADOR_EMAIL
    if not destinatario:
        logger.warning("[instagram_bot] INSTAGRAM_APROVADOR_EMAIL não configurado - não dá pra pedir aprovação")
        return

    link_aprovar = request.build_absolute_uri(reverse("instagram_aprovar", args=[_gerar_token(registro.pk, "aprovar")]))
    link_rejeitar = request.build_absolute_uri(reverse("instagram_aprovar", args=[_gerar_token(registro.pk, "rejeitar")]))
    linha_imagens = (
        f"Carrossel com {len(imagens_bytes)} imagens (anexadas, na ordem dos slides)."
        if len(imagens_bytes) > 1
        else f"Ver imagem: {registro.imagem_url}"
    )
    ordem = f"{posicao[0]}/{posicao[1]} " if posicao else ""
    corpo = (
        f"{registro.get_tipo_display()} - {registro.get_conteudo_tipo_display()} ({registro.data})\n\n"
        + (f"Story {posicao[0]} de {posicao[1]} da sequência do dia.\n\n" if posicao else "")
        + f"Legenda:\n{registro.legenda}\n\n"
        f"{linha_imagens}\n\n"
        f"Aprovar e publicar: {link_aprovar}\n\n"
        f"Rejeitar (não publicar): {link_rejeitar}\n\n"
        "Esse link vale por 36h."
    )
    email = EmailMessage(
        subject=f"cash-b — {ordem}aprovar {registro.get_conteudo_tipo_display().lower()}?",
        body=corpo,
        to=[destinatario],
    )
    for indice, imagem_bytes in enumerate(imagens_bytes, start=1):
        email.attach(f"cash-b-{registro.pk}-{indice}.jpg", imagem_bytes, "image/jpeg")
    email.send()


def processar_decisao(token: str) -> tuple[RegistroPublicacao | None, str]:
    """Chamado pela view que o link do e-mail abre. Retorna (registro, mensagem) pra
    exibir uma resposta simples de confirmação."""
    dados = _validar_token(token)
    if not dados:
        return None, "Link inválido ou expirado."

    try:
        registro = RegistroPublicacao.objects.get(pk=dados["id"])
    except RegistroPublicacao.DoesNotExist:
        return None, "Publicação não encontrada."

    if registro.status != RegistroPublicacao.STATUS_PENDENTE_APROVACAO:
        return registro, f"Essa publicação já foi processada antes (status atual: {registro.get_status_display()})."

    if dados["acao"] == "rejeitar":
        registro.status = RegistroPublicacao.STATUS_REJEITADO
        registro.save(update_fields=["status"])
        return registro, "Rejeitado - essa arte não vai ser publicada no Instagram."

    try:
        if registro.imagem_urls:
            media_id = instagram_client.publicar_carrossel(
                registro.imagem_urls.splitlines(), legenda=registro.legenda,
            )
        else:
            story = registro.tipo == RegistroPublicacao.TIPO_STORY
            media_id = instagram_client.publicar_imagem(registro.imagem_url, legenda=registro.legenda, story=story)
        registro.status = RegistroPublicacao.STATUS_PUBLICADO
        registro.sucesso = True
        registro.instagram_media_id = media_id
        registro.save(update_fields=["status", "sucesso", "instagram_media_id"])
        return registro, "Aprovado e publicado no Instagram!"
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar após aprovação (registro %s)", registro.pk)
        registro.status = RegistroPublicacao.STATUS_ERRO
        registro.erro = str(erro)
        registro.save(update_fields=["status", "erro"])
        return registro, f"Aprovado, mas falhou ao publicar no Instagram: {erro}"
