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


def enviar_email_aprovacao(registro: RegistroPublicacao, imagem_bytes: bytes, request) -> None:
    destinatario = settings.INSTAGRAM_APROVADOR_EMAIL
    if not destinatario:
        logger.warning("[instagram_bot] INSTAGRAM_APROVADOR_EMAIL não configurado - não dá pra pedir aprovação")
        return

    link_aprovar = request.build_absolute_uri(reverse("instagram_aprovar", args=[_gerar_token(registro.pk, "aprovar")]))
    link_rejeitar = request.build_absolute_uri(reverse("instagram_aprovar", args=[_gerar_token(registro.pk, "rejeitar")]))
    corpo = (
        f"{registro.get_tipo_display()} - {registro.get_conteudo_tipo_display()} ({registro.data})\n\n"
        f"Legenda:\n{registro.legenda}\n\n"
        f"Ver imagem: {registro.imagem_url}\n\n"
        f"Aprovar e publicar: {link_aprovar}\n\n"
        f"Rejeitar (não publicar): {link_rejeitar}\n\n"
        "Esse link vale por 36h."
    )
    email = EmailMessage(
        subject=f"cash-b — aprovar {registro.get_conteudo_tipo_display().lower()}?",
        body=corpo,
        to=[destinatario],
    )
    email.attach(f"cash-b-{registro.pk}.png", imagem_bytes, "image/png")
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

    story = registro.tipo == RegistroPublicacao.TIPO_STORY
    try:
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
