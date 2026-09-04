import logging

from django.core.mail import EmailMessage
from django.utils.formats import number_format

from accounts.push import enviar_push

logger = logging.getLogger(__name__)


def notificar_saque_pago(saque):
    valor_formatado = number_format(saque.valor, decimal_pos=2)

    if saque.usuario and saque.usuario.email:
        corpo = (
            f"Olá, {saque.usuario.username}!\n\n"
            f"Seu saque de R$ {valor_formatado} foi pago via Pix na chave cadastrada.\n\n"
            "Equipe cash-b"
        )
        try:
            EmailMessage(subject="cash-b — seu saque foi pago", body=corpo, to=[saque.usuario.email]).send()
        except Exception:
            logger.exception("Falha ao enviar e-mail de saque pago pro usuário %s", saque.usuario_id)

    enviar_push(
        saque.usuario,
        "Saque pago!",
        f"Seu saque de R$ {valor_formatado} caiu via Pix na chave cadastrada.",
        url="/dashboard/#saques",
    )
