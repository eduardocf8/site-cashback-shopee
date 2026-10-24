import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .autenticacao import token_senha

logger = logging.getLogger(__name__)


def url_do_painel(nome_url: str, *args) -> str:
    """URL absoluta no domínio do painel - funciona até numa requisição que
    chegou por outro domínio (ex: o webhook da Zouti, que chega na cash-b)."""
    caminho = reverse(nome_url, args=args, urlconf="painel.urls_dominio")
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + caminho


def link_definir_senha(conta) -> str:
    uid = urlsafe_base64_encode(force_bytes(conta.pk))
    return url_do_painel("painel_definir_senha", uid, token_senha.make_token(conta))


def enviar_email_recuperar_senha(conta) -> bool:
    corpo = (
        f"Olá{', ' + conta.nome if conta.nome else ''}!\n\n"
        "Recebemos um pedido para criar ou trocar a senha do seu painel do Appfiliado. "
        "Use o link abaixo (vale por 3 dias e só uma vez):\n\n"
        f"{link_definir_senha(conta)}\n\n"
        "Se não foi você, pode ignorar este e-mail - sua senha continua a mesma.\n\n"
        "Equipe Appfiliado\nFerramentas para afiliados Shopee"
    )
    try:
        EmailMessage(
            subject="Appfiliado — defina sua senha",
            body=corpo,
            to=[conta.email],
            from_email=settings.APPFILIADO_EMAIL_REMETENTE,
        ).send()
    except Exception:
        logger.exception("Painel: falha ao enviar e-mail de senha pra conta %s", conta.pk)
        return False
    return True
