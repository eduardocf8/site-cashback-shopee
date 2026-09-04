import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.utils.formats import number_format
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Saque
from .services import ChavePixNaoConfiguradaError, ValorAbaixoDoMinimoError, solicitar_saque

logger = logging.getLogger(__name__)


@login_required
def pedir_saque(request):
    if request.method == "POST":
        if not request.user.email_verificado:
            messages.error(request, "Confirme seu e-mail antes de solicitar um saque.")
            return redirect("dashboard")
        try:
            saque = solicitar_saque(request.user)
            valor_formatado = number_format(saque.valor, decimal_pos=2)
            messages.success(
                request,
                f"Saque de R$ {valor_formatado} solicitado! Assim que for aprovado, o Pix cai na sua chave cadastrada.",
            )
        except ChavePixNaoConfiguradaError as erro:
            messages.error(request, str(erro))
        except ValorAbaixoDoMinimoError as erro:
            messages.error(request, str(erro))

    return redirect("dashboard")


@csrf_exempt
@require_POST
def webhook_validacao_asaas(request):
    """Mecanismo de segurança da Asaas alternativo ao código por SMS: a Asaas chama essa
    URL uns segundos depois de criar uma transferência Pix e espera de volta "APPROVED" ou
    "REFUSED". O payload vem aninhado - {"type": "TRANSFER", "transfer": {"id": ..., ...}}
    - por isso o id não está na raiz. Só autoriza transferências cujo id já está gravado
    num Saque (ou seja, que a gente mesmo criou via processar_saque_asaas, depois de uma
    aprovação manual no admin) - qualquer id desconhecido é recusado."""
    token_esperado = settings.ASAAS_WEBHOOK_TOKEN
    if not token_esperado or request.headers.get("asaas-access-token") != token_esperado:
        return HttpResponseForbidden("Token inválido.")

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"status": "REFUSED", "refuseReason": "Payload inválido."}, status=400)

    transferencia = payload.get("transfer") or payload
    transfer_id = str(transferencia.get("id", ""))
    if transfer_id and Saque.objects.filter(asaas_transfer_id=transfer_id).exists():
        logger.info("Webhook Asaas: transferência %s autorizada.", transfer_id)
        return JsonResponse({"status": "APPROVED"})

    logger.warning("Webhook Asaas: transferência %s não reconhecida, recusando.", transfer_id)
    return JsonResponse({"status": "REFUSED", "refuseReason": "Transferência não reconhecida."})
