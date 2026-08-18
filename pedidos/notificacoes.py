import logging

from django.core.mail import EmailMessage
from django.utils.formats import number_format

from accounts.push import enviar_push

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
    enviar_push(
        pedido.usuario,
        "Pedido validado!",
        f'"{produto}" — R$ {valor} de cashback, liberado pra saque em {prazo}.',
        url="/dashboard/#pedidos",
    )


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
    enviar_push(
        pedido.usuario,
        "Cashback liberado!",
        f'R$ {valor} de "{produto}" já pode ser sacado via PIX.',
        url="/dashboard/#saques",
    )


def notificar_indicador_bonus_pendente(indicacao):
    """Avisa quem indicou que a 1ª compra do indicado acabou de validar - o próximo
    pedido validado do indicador vem com o dobro de cashback (ver
    services.py::_selecionar_bonus_indicacao). Dispara só uma vez, no momento em que
    esse vínculo é decidido pela primeira vez - não a cada resync do mesmo pedido."""
    indicador = indicacao.indicador
    corpo = (
        f"Olá, {indicador.username}!\n\n"
        f"A pessoa que você indicou (@{indicacao.indicado.username}) teve a 1ª compra "
        "validada! 🎉\n\n"
        "Isso significa que o SEU próximo pedido validado vai vir com o dobro de "
        "cashback. Aproveite!\n\n"
        "Se estiver rolando uma campanha de cashback extra, seu pedido já vem com o "
        "valor aumentado da campanha e o bônus da indicação fica guardado para o "
        "pedido seguinte, depois que ela terminar.\n\n"
        "Equipe cash-b"
    )
    _enviar(indicador, "cash-b — sua indicação validou! seu próximo pedido vem em dobro", corpo)
    enviar_push(
        indicador,
        "Sua indicação validou!",
        f"@{indicacao.indicado.username} teve a 1ª compra validada — seu próximo pedido vem em dobro.",
        url="/dashboard/#indicacoes",
    )
