import logging

from django.core.mail import EmailMessage
from django.utils.formats import number_format

logger = logging.getLogger(__name__)


def notificar_saque_pago(saque):
    if not saque.usuario or not saque.usuario.email:
        return
    valor_formatado = number_format(saque.valor, decimal_pos=2)
    corpo = (
        f"Olá, {saque.usuario.username}!\n\n"
        f"Seu saque de R$ {valor_formatado} foi pago via PIX na chave cadastrada.\n\n"
        "Equipe cash-b"
    )
    try:
        EmailMessage(subject="cash-b — seu saque foi pago", body=corpo, to=[saque.usuario.email]).send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de saque pago pro usuário %s", saque.usuario_id)
