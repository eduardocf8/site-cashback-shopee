import hmac
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse

from instagram_bot.services import executar_publicacoes_do_dia
from links.shopee_client import ShopeeAPIError, ShopeeConfigError
from ofertas.services import sincronizar_ofertas
from pedidos.services import liberar_saldo, sincronizar
from saques.services import verificar_saques_pendentes

ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /dashboard/
Disallow: /chave-pix/
Disallow: /editar-perfil/
Disallow: /trocar-senha/
Disallow: /verificar-email/
Disallow: /reenviar-verificacao/
Disallow: /esqueci-senha/
Disallow: /resetar-senha/
Disallow: /saques/
Disallow: /tarefas/

Sitemap: {scheme}://{host}/sitemap.xml
"""


def robots_txt(request):
    conteudo = ROBOTS_TXT.format(scheme="https" if request.is_secure() else "http", host=request.get_host())
    return HttpResponse(conteudo, content_type="text/plain")


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

    try:
        resultado["ofertas_sincronizadas"] = sincronizar_ofertas()
    except (ShopeeConfigError, ShopeeAPIError) as erro:
        resultado["ofertas_erro"] = str(erro)

    resultado["saldos_liberados"] = liberar_saldo()
    resultado["saques_verificados"] = verificar_saques_pendentes()

    try:
        resultado["instagram"] = executar_publicacoes_do_dia(request)
    except Exception as erro:
        resultado["instagram_erro"] = str(erro)

    return JsonResponse(resultado)
