import logging
from datetime import date, datetime

from django.conf import settings
from django.core.mail import EmailMessage

from .models import Licenca

logger = logging.getLogger(__name__)


def _data_de_iso(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        # Kiwify manda algo como "2026-09-30T01:44:17.150Z"
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def interpretar_evento(payload: dict) -> dict:
    """Decide o status da licença a partir de um payload de webhook da Kiwify já
    verificado (assinatura conferida em views.webhook_kiwify).

    Prioriza sinais fortes e explícitos (reembolso, chargeback, recusa) sobre o status
    geral da assinatura, porque esses eventos podem chegar antes da Kiwify atualizar
    Subscription.status. Quando nada bate com o que a gente já viu em produção, bloqueia
    por padrão em vez de arriscar liberar - ver Licenca.STATUS_QUE_LIBERAM."""

    webhook_event_type = (payload.get("webhook_event_type") or "").lower()
    order_status = (payload.get("order_status") or "").lower()
    subscription = payload.get("Subscription") or {}
    sub_status = (subscription.get("status") or "").lower()

    plano = ""
    plano_info = subscription.get("plan") or {}
    if plano_info.get("name"):
        plano = plano_info["name"]
    elif plano_info.get("frequency"):
        plano = plano_info["frequency"]

    expira_em = _data_de_iso(subscription.get("next_payment"))

    if "refund" in webhook_event_type or order_status == "refunded":
        return {
            "status": Licenca.STATUS_REEMBOLSADA,
            "motivo": "Compra reembolsada.",
            "plano": plano,
            "expira_em": expira_em,
        }

    if "chargeback" in webhook_event_type or order_status in ("chargeback", "chargedback"):
        return {
            "status": Licenca.STATUS_CHARGEBACK,
            "motivo": "Chargeback registrado nesta compra.",
            "plano": plano,
            "expira_em": expira_em,
        }

    if "refus" in webhook_event_type or order_status in ("refused", "recused"):
        return {
            "status": Licenca.STATUS_RECUSADA,
            "motivo": "Pagamento recusado.",
            "plano": plano,
            "expira_em": expira_em,
        }

    if sub_status:
        if sub_status == "active":
            return {"status": Licenca.STATUS_ATIVA, "motivo": "", "plano": plano, "expira_em": expira_em}
        if sub_status in ("late", "overdue", "past_due"):
            return {
                "status": Licenca.STATUS_ATRASADA,
                "motivo": "Pagamento da assinatura está atrasado.",
                "plano": plano,
                "expira_em": expira_em,
            }
        if sub_status in ("canceled", "cancelled", "expired", "inactive"):
            return {
                "status": Licenca.STATUS_CANCELADA,
                "motivo": "Assinatura cancelada.",
                "plano": plano,
                "expira_em": expira_em,
            }
        logger.warning("Licencas: Subscription.status desconhecido da Kiwify: %r", sub_status)
        return {
            "status": Licenca.STATUS_CANCELADA,
            "motivo": "Status da assinatura não reconhecido - verifique manualmente.",
            "plano": plano,
            "expira_em": expira_em,
        }

    if order_status == "paid":
        return {"status": Licenca.STATUS_ATIVA, "motivo": "", "plano": plano, "expira_em": expira_em}

    logger.warning(
        "Licencas: evento sem Subscription e sem order_status=paid (webhook_event_type=%r, order_status=%r)",
        webhook_event_type, order_status,
    )
    return {
        "status": Licenca.STATUS_CANCELADA,
        "motivo": "Evento não reconhecido - verifique manualmente.",
        "plano": plano,
        "expira_em": expira_em,
    }


def aplicar_evento_webhook(payload: dict) -> Licenca:
    """Aplica um evento já verificado (assinatura conferida) a uma Licenca, criando-a
    (e enviando a chave por e-mail) se ainda não existir."""

    customer = payload.get("Customer") or {}
    email = (customer.get("email") or "").strip().lower()
    nome = customer.get("full_name") or ""
    subscription = payload.get("Subscription") or {}
    subscription_id = subscription.get("id") or payload.get("subscription_id") or ""

    interpretado = interpretar_evento(payload)

    if subscription_id:
        licenca, criada = Licenca.objects.get_or_create(
            kiwify_subscription_id=subscription_id,
            defaults={"email": email, "nome": nome},
        )
    else:
        licenca, criada = Licenca.objects.get_or_create(
            email=email,
            kiwify_subscription_id="",
            defaults={"nome": nome},
        )

    licenca.email = email or licenca.email
    licenca.kiwify_customer_email = email or licenca.kiwify_customer_email
    licenca.nome = nome or licenca.nome
    licenca.status = interpretado["status"]
    licenca.motivo = interpretado["motivo"]
    licenca.plano = interpretado["plano"]
    licenca.expira_em = interpretado["expira_em"]
    licenca.save()

    if criada:
        enviar_email_licenca(licenca)

    return licenca


def enviar_email_licenca(licenca: Licenca) -> None:
    if not licenca.email:
        logger.warning("Licencas: licenca %s sem e-mail, não foi possível enviar a chave.", licenca.pk)
        return

    corpo = (
        f"Olá{', ' + licenca.nome if licenca.nome else ''}!\n\n"
        "Sua assinatura do Appfiliado foi confirmada. Essa é a sua chave de licença - "
        "cole ela na tela de ativação do aplicativo:\n\n"
        f"{licenca.chave}\n\n"
        "Guarde esse e-mail: se precisar reinstalar o app ou trocar de computador, "
        "é só usar a mesma chave de novo.\n\n"
        "Equipe Appfiliado"
    )
    try:
        EmailMessage(
            subject="Appfiliado — sua chave de licença",
            body=corpo,
            to=[licenca.email],
            from_email=settings.APPFILIADO_EMAIL_REMETENTE,
        ).send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de licença pra %s", licenca.email)
