import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import EstadoTokenInstagram

logger = logging.getLogger(__name__)

DIAS_VALIDADE_TOKEN = 60
DIAS_ANTES_DE_AVISAR = 10  # começa a avisar faltando 10 dias (~aos 50 dias de uso)
DIAS_ENTRE_LEMBRETES = 3  # depois do primeiro aviso, reforça a cada 3 dias até renovar


def _obter_estado() -> EstadoTokenInstagram:
    """Não fixa pk=1: se a linha (singleton) for apagada e recriada, o Postgres não
    reutiliza o mesmo ID, então é mais seguro só pegar a mais recente que existir."""
    estado = EstadoTokenInstagram.objects.order_by("-pk").first()
    return estado or EstadoTokenInstagram.objects.create()


def verificar_validade_token() -> dict:
    """Confere se o INSTAGRAM_ACCESS_TOKEN está perto de vencer (dura 60 dias, ver
    instagram_client.py) e manda um e-mail de lembrete pro INSTAGRAM_APROVADOR_EMAIL quando
    estiver perto. Não renova o token sozinho - ver README, seção "Renovação do token de
    acesso", pro motivo de a renovação continuar manual."""
    estado = _obter_estado()
    hoje = timezone.localdate()
    dias_restantes = DIAS_VALIDADE_TOKEN - (hoje - estado.renovado_em).days

    if dias_restantes > DIAS_ANTES_DE_AVISAR:
        return {"dias_restantes": dias_restantes, "lembrete_enviado": False}

    if estado.ultimo_lembrete_em and (hoje - estado.ultimo_lembrete_em).days < DIAS_ENTRE_LEMBRETES:
        return {"dias_restantes": dias_restantes, "lembrete_enviado": False}

    destinatario = settings.INSTAGRAM_APROVADOR_EMAIL
    if not destinatario:
        logger.warning("[instagram_bot] INSTAGRAM_APROVADOR_EMAIL não configurado - não dá pra avisar sobre o token")
        return {"dias_restantes": dias_restantes, "lembrete_enviado": False}

    vencido = dias_restantes <= 0
    assunto = "cash-b: token do Instagram VENCEU" if vencido else "cash-b: token do Instagram vence em breve"
    situacao = (
        f"o token já venceu há {-dias_restantes} dia(s)!"
        if vencido
        else f"o token vence em {dias_restantes} dia(s)."
    )
    corpo = (
        f"Fica ligado: {situacao}\n\n"
        "Enquanto o token está vencido, o bot não consegue publicar nada no Instagram.\n\n"
        "Pra renovar:\n"
        "1. Gere um novo token de longa duração no painel da Meta for Developers "
        "(mesmo processo da configuração inicial - ver marketing/instagram/README.md).\n"
        "2. Atualize INSTAGRAM_ACCESS_TOKEN no Render (Environment).\n"
        "3. No Django Admin (Instagram_bot > Estado do token do Instagram), selecione a "
        "linha e rode a ação \"Marcar token como renovado hoje\" - senão esse lembrete "
        "continua chegando."
    )
    EmailMessage(subject=assunto, body=corpo, to=[destinatario]).send()

    estado.ultimo_lembrete_em = hoje
    estado.save(update_fields=["ultimo_lembrete_em"])
    return {"dias_restantes": dias_restantes, "lembrete_enviado": True}
