import json
import logging

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ContaAppfiliado, EventoWebhookZouti
from .services import assinatura_webhook_valida, processar_evento, resposta_validacao

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook_zouti(request):
    """Recebe os webhooks da Zouti (Integrações > Webhooks no painel dela).

    Só responde 2xx quando o evento foi guardado - se der erro ao processar, responde
    500 pra Zouti tentar de novo (ela reenvia por até 4 dias)."""
    cabecalho = request.headers.get("x-zouti-signature", "")
    assinatura_ok = assinatura_webhook_valida(request.body, cabecalho, settings.ZOUTI_WEBHOOK_SECRET)

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        payload = None

    evento_id = request.headers.get("x-zouti-event-id", "")[:64]
    tipo_evento = request.headers.get("x-zouti-event-type", "")[:60]
    tipo_objeto = request.headers.get("x-zouti-object-name", "")[:30]
    cliente = (payload.get("customer") or {}) if isinstance(payload, dict) else {}
    evento = EventoWebhookZouti(
        zouti_event_id=evento_id,
        tipo_evento=tipo_evento,
        tipo_objeto=tipo_objeto,
        zouti_object_id=request.headers.get("x-zouti-object-id", "")[:64],
        email=str(cliente.get("email") or "")[:254],
        corpo_bruto=request.body.decode("utf-8", errors="replace"),
        assinatura_valida=assinatura_ok,
    )

    if not assinatura_ok:
        evento.erro = "Assinatura inválida ou segredo do webhook não configurado."
        evento.save()
        logger.warning("Licencas: webhook da Zouti com assinatura inválida, recusado.")
        return HttpResponseForbidden("Assinatura inválida.")

    if not isinstance(payload, dict):
        evento.erro = "Payload não é um JSON válido."
        evento.save()
        return JsonResponse({"ok": False, "erro": "payload inválido"}, status=400)

    if evento_id and EventoWebhookZouti.objects.filter(
        zouti_event_id=evento_id, processado_com_sucesso=True,
    ).exists():
        evento.processado_com_sucesso = True
        evento.resultado = "Duplicado: evento já processado antes."
        evento.save()
        return JsonResponse({"ok": True, "duplicado": True})

    try:
        evento.resultado = processar_evento(tipo_evento, tipo_objeto, payload)[:200]
        evento.processado_com_sucesso = True
    except Exception as erro:
        evento.erro = str(erro)
        logger.exception("Licencas: falha ao processar webhook da Zouti.")
    evento.save()

    if not evento.processado_com_sucesso:
        return JsonResponse({"ok": False}, status=500)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def validar_licenca(request):
    """Chamado pelo app do Appfiliado (Appfiliado/licenca.py). Ver
    services.resposta_validacao pro formato da resposta - não tire nem mude o
    significado de um campo sem atualizar o app também."""
    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        return JsonResponse({"valido": False, "motivo": "Requisição inválida."}, status=400)

    chave = str(payload.get("chave") or "").strip()
    if not chave:
        return JsonResponse({"valido": False, "motivo": "Chave de licença não informada."}, status=400)

    conta = ContaAppfiliado.objects.filter(chave=chave).first()
    if not conta:
        return JsonResponse(
            {"valido": False, "motivo": "Chave de licença não encontrada.", "conta_ativa": False, "modulos": []}
        )

    return JsonResponse(resposta_validacao(conta))
