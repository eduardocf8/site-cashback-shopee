import logging

from django.core import signing
from django.core.mail import EmailMessage
from django.urls import reverse

logger = logging.getLogger(__name__)

SALT_VERIFICAR_EMAIL = "accounts.verificar-email"
IDADE_MAXIMA_TOKEN = 60 * 60 * 24 * 3  # 3 dias


def gerar_token_verificacao(usuario) -> str:
    return signing.dumps({"user_id": usuario.pk, "email": usuario.email}, salt=SALT_VERIFICAR_EMAIL)


def validar_token_verificacao(token: str) -> dict | None:
    try:
        return signing.loads(token, salt=SALT_VERIFICAR_EMAIL, max_age=IDADE_MAXIMA_TOKEN)
    except signing.BadSignature:
        return None


def enviar_email_verificacao(usuario, request) -> None:
    token = gerar_token_verificacao(usuario)
    link = request.build_absolute_uri(reverse("verificar_email", args=[token]))
    corpo = (
        f"Olá, {usuario.username}!\n\n"
        "Confirme seu e-mail clicando no link abaixo (vale por 3 dias):\n"
        f"{link}\n\n"
        "Se você não criou uma conta na cash-b, pode ignorar este e-mail.\n\n"
        "Equipe cash-b"
    )
    try:
        EmailMessage(subject="cash-b — confirme seu e-mail", body=corpo, to=[usuario.email]).send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de verificação pro usuário %s", usuario.pk)
