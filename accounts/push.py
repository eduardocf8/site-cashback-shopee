import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


def enviar_push(usuario, titulo, corpo, url="/"):
    """Manda uma notificação push pra todos os dispositivos inscritos do usuário.

    Sem falhar o fluxo que chamou (validação de pedido, liberação de saldo etc.) se
    o push não sair - assim como o e-mail (ver pedidos/notificacoes.py), notificação é
    um extra, nunca pode travar a operação principal. Inscrições que o navegador já
    invalidou (404/410 - usuário desinstalou o app, limpou o site, etc.) são apagadas
    na hora, pra não ficar tentando mandar pra elas pra sempre."""
    if not settings.VAPID_PRIVATE_KEY or not usuario:
        return

    dados = json.dumps({"titulo": titulo, "corpo": corpo, "url": url})
    for inscricao in usuario.push_subscriptions.all():
        try:
            webpush(
                subscription_info={
                    "endpoint": inscricao.endpoint,
                    "keys": {"p256dh": inscricao.chave_p256dh, "auth": inscricao.chave_auth},
                },
                data=dados,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
            )
        except WebPushException as erro:
            if erro.response is not None and erro.response.status_code in (404, 410):
                inscricao.delete()
            else:
                logger.exception("Falha ao enviar push pro usuário %s", usuario.pk)
