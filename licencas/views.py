import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import EventoWebhookKiwify, Licenca
from .services import aplicar_evento_webhook

logger = logging.getLogger(__name__)


def _assinatura_valida(request) -> bool:
    """A Kiwify manda `?signature=<hmac>` na própria URL do webhook - hex de
    HMAC-SHA1(chave=Token configurado no painel do webhook, mensagem=corpo bruto da
    requisição). Confirmado batendo contra um payload de teste real; não documentado
    publicamente, então não mude sem novo teste."""
    token = settings.KIWIFY_WEBHOOK_TOKEN
    assinatura_recebida = request.GET.get("signature", "")
    if not token or not assinatura_recebida:
        return False
    assinatura_esperada = hmac.new(token.encode(), request.body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(assinatura_recebida, assinatura_esperada)


@csrf_exempt
@require_POST
def webhook_kiwify(request):
    assinatura_ok = _assinatura_valida(request)

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        payload = {}

    evento = EventoWebhookKiwify(
        webhook_event_type=payload.get("webhook_event_type", ""),
        order_status=payload.get("order_status", ""),
        subscription_status=(payload.get("Subscription") or {}).get("status", ""),
        kiwify_subscription_id=(payload.get("Subscription") or {}).get("id", ""),
        email=(payload.get("Customer") or {}).get("email", ""),
        corpo_bruto=request.body.decode("utf-8", errors="replace"),
        assinatura_valida=assinatura_ok,
    )

    if not assinatura_ok:
        evento.erro = "Assinatura inválida ou token não configurado."
        evento.save()
        logger.warning("Licencas: webhook da Kiwify com assinatura inválida, recusado.")
        return HttpResponseForbidden("Assinatura inválida.")

    if not payload:
        evento.erro = "Payload não é um JSON válido."
        evento.save()
        return JsonResponse({"ok": False, "erro": "payload inválido"}, status=400)

    try:
        aplicar_evento_webhook(payload)
        evento.processado_com_sucesso = True
    except Exception as erro:
        evento.erro = str(erro)
        logger.exception("Licencas: falha ao processar webhook da Kiwify.")
    finally:
        evento.save()

    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def validar_licenca(request):
    """Contrato documentado em bot_whatsapp_ofertas_generico/LICENCA.md - não mude a
    forma da resposta sem atualizar o bot também."""
    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"valido": False, "motivo": "Requisição inválida."}, status=400)

    chave = (payload.get("chave") or "").strip()
    if not chave:
        return JsonResponse({"valido": False, "motivo": "Chave de licença não informada."}, status=400)

    try:
        licenca = Licenca.objects.get(chave=chave)
    except Licenca.DoesNotExist:
        return JsonResponse({"valido": False, "motivo": "Chave de licença não encontrada."})

    return JsonResponse(
        {
            "valido": licenca.ativa,
            "motivo": "" if licenca.ativa else (licenca.motivo or "Assinatura não está ativa."),
            "plano": licenca.plano,
            "expira_em": licenca.expira_em.isoformat() if licenca.expira_em else "",
        }
    )
