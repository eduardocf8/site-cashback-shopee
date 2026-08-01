import logging

from django.core.mail import EmailMessage
from django.utils.formats import number_format

logger = logging.getLogger(__name__)


def _enviar(usuario, assunto, corpo):
    if not usuario or not usuario.email:
        return
    try:
        EmailMessage(subject=assunto, body=corpo, to=[usuario.email]).send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de notificação de pedido pro usuário %s", usuario.pk)


def notificar_pedido_validado(pedido):
    produto = pedido.produto_nome or f"pedido {pedido.order_id}"
    valor = number_format(pedido.valor_cashback, decimal_pos=2)
    prazo = (
        pedido.data_prevista_liberacao.strftime("%d/%m/%Y")
        if pedido.data_prevista_liberacao
        else "em breve"
    )
    corpo = (
        f"Olá, {pedido.usuario.username}!\n\n"
        f'Seu pedido "{produto}" foi validado pela Shopee.\n'
        f"Cashback: R$ {valor}\n\n"
        f"Esse saldo fica disponível pra saque a partir de {prazo}.\n\n"
        "Equipe cash-b"
    )
    _enviar(pedido.usuario, "cash-b — seu pedido foi validado", corpo)


def notificar_pedido_liberado(pedido):
    produto = pedido.produto_nome or f"pedido {pedido.order_id}"
    valor = number_format(pedido.valor_cashback, decimal_pos=2)
    corpo = (
        f"Olá, {pedido.usuario.username}!\n\n"
        f'O cashback de "{produto}" (R$ {valor}) já está liberado e pode ser '
        "sacado via PIX no seu painel.\n\n"
        "Equipe cash-b"
    )
    _enviar(pedido.usuario, "cash-b — cashback liberado pra saque", corpo)
