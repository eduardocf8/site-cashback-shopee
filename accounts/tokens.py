import logging
from datetime import timedelta

from django.core import signing
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone

from .models import User

logger = logging.getLogger(__name__)

SALT_VERIFICAR_EMAIL = "accounts.verificar-email"
IDADE_MAXIMA_TOKEN = 60 * 60 * 24 * 3  # 3 dias

# Janela do lembrete automático (ver enviar_lembretes_verificacao_pendente) - pega quem
# se cadastrou entre 24h e 48h atrás. Rodando 1x/dia, cada pessoa cai nessa janela uma
# vez só; não é o mesmo prazo do token (3 dias) de propósito - o lembrete é cedo o
# bastante pra pegar gente que já esqueceu do e-mail original, mas o token que ele manda
# de novo ainda vale por mais 3 dias a partir daí.
LEMBRETE_JANELA_INICIO_HORAS = 24
LEMBRETE_JANELA_FIM_HORAS = 48


def gerar_token_verificacao(usuario) -> str:
    return signing.dumps({"user_id": usuario.pk, "email": usuario.email}, salt=SALT_VERIFICAR_EMAIL)


def validar_token_verificacao(token: str) -> dict | None:
    """Payload do token só quando a assinatura é válida E ainda está dentro da
    validade - é o que realmente confirma o e-mail (ver accounts/views.py::verificar_email).
    Pra saber quem era o dono de um token só vencido (assinatura ainda válida), ver
    decodificar_token_verificacao_mesmo_vencido."""
    try:
        return signing.loads(token, salt=SALT_VERIFICAR_EMAIL, max_age=IDADE_MAXIMA_TOKEN)
    except signing.BadSignature:
        return None


def decodificar_token_verificacao_mesmo_vencido(token: str) -> dict | None:
    """Igual validar_token_verificacao, mas sem checar a validade (max_age=None) - só
    serve pra descobrir de quem era um link expirado, pra poder mandar um novo (ver
    accounts/views.py::verificar_email). Nunca usar isso pra confirmar o e-mail de
    verdade: um token com assinatura válida mas vencido ainda passa aqui."""
    try:
        return signing.loads(token, salt=SALT_VERIFICAR_EMAIL, max_age=None)
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


def enviar_lembretes_verificacao_pendente(request) -> int:
    """Reenvia o e-mail de verificação pra quem se cadastrou entre 24h e 48h atrás e
    ainda não verificou - chamado 1x/dia por um Cron Job do Render (ver
    /tarefas/lembrete-verificacao-email/ em cashback_shopee/views.py e "Cron Jobs do
    Render" em marketing/instagram/README.md). Manda 1 e-mail por pessoa em série (não
    dá pra mandar em BCC lote como accounts/comunicacoes.py - cada um carrega um token
    de verificação diferente) - por isso roda de madrugada, mesmo horário de baixo
    tráfego dos outros Cron Jobs."""
    agora = timezone.now()
    usuarios = User.objects.filter(
        email_verificado=False,
        date_joined__lt=agora - timedelta(hours=LEMBRETE_JANELA_INICIO_HORAS),
        date_joined__gte=agora - timedelta(hours=LEMBRETE_JANELA_FIM_HORAS),
    ).exclude(email="")

    total = 0
    for usuario in usuarios:
        enviar_email_verificacao(usuario, request)
        total += 1
    return total
