import hmac
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse

from links.shopee_client import ShopeeAPIError, ShopeeConfigError
from pedidos.services import liberar_saldo, sincronizar
from saques.services import verificar_saques_pendentes


def executar_tarefas_agendadas(request):
    """Roda a sincronização diária com a Shopee, a liberação de saldo e a checagem de saques.

    Protegido por um token (TAREFAS_TOKEN) em vez de exigir login, porque quem chama
    esse endereço é o agendamento automático (GitHub Actions), não uma pessoa logada.
    """
    token_esperado = settings.TAREFAS_TOKEN
    token_recebido = request.GET.get("token", "")
    if not token_esperado or not hmac.compare_digest(token_esperado, token_recebido):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    agora = datetime.now(tz=dt_timezone.utc)
    inicio = agora - timedelta(days=60)

    resultado = {}
    try:
        resultado["sincronizacao"] = sincronizar(int(inicio.timestamp()), int(agora.timestamp()))
    except (ShopeeConfigError, ShopeeAPIError) as erro:
        resultado["sincronizacao_erro"] = str(erro)

    resultado["saldos_liberados"] = liberar_saldo()
    resultado["saques_verificados"] = verificar_saques_pendentes()

    return JsonResponse(resultado)
