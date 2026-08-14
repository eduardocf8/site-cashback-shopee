import hmac
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone

from instagram_bot.lembrete_token import verificar_validade_token
from instagram_bot.services import executar_publicacoes_do_dia, publicar_story_oferta_do_momento
from links.shopee_client import ShopeeAPIError, ShopeeConfigError
from ofertas.services import encurtar_nomes_pendentes, sincronizar_ofertas
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
Disallow: /healthz/

Sitemap: {scheme}://{host}/sitemap.xml
"""


def healthcheck(request):
    """Endpoint pra configurar como "Health Check Path" no serviço web da Render.

    Sem um health check configurado, a Render só confere se a porta está aberta antes
    de considerar a instância nova pronta e desligar a antiga - isso pode achar a
    instância "pronta" antes do banco estar de fato acessível, deixando os primeiros
    usuários depois de cada deploy verem um 502/500 por alguns segundos. Consultando o
    banco aqui garante que só vira "pronta" quando estiver mesmo.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("unhealthy", status=503)
    return HttpResponse("ok")


def robots_txt(request):
    conteudo = ROBOTS_TXT.format(scheme="https" if request.is_secure() else "http", host=request.get_host())
    return HttpResponse(conteudo, content_type="text/plain")


def _token_valido(request) -> bool:
    token_esperado = settings.TAREFAS_TOKEN
    token_recebido = request.GET.get("token", "")
    return bool(token_esperado) and hmac.compare_digest(token_esperado, token_recebido)


def executar_tarefas_agendadas(request):
    """Roda a sincronização diária com a Shopee, a liberação de saldo e a checagem de saques.

    Protegido por um token (TAREFAS_TOKEN) em vez de exigir login, porque quem chama
    esse endereço é o agendamento automático (GitHub Actions), não uma pessoa logada.
    """
    if not _token_valido(request):
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

    try:
        resultado["token_instagram"] = verificar_validade_token()
    except Exception as erro:
        resultado["token_instagram_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_encurtamento_nomes(request):
    """Melhora aos poucos o nome_curto das ofertas via Gemini (ver ofertas/services.py).

    É uma tarefa agendada separada de executar_tarefas_agendadas de propósito: a busca de
    ofertas na Shopee já usa boa parte dos 120s de orçamento antes do timeout do gunicorn
    (--timeout 120), e enfileirar as chamadas ao Gemini atrás dela na mesma requisição
    estourava esse timeout quase toda vez. Assim, essa chamada tem os 120s só pra si.
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        resultado["nomes_encurtados"] = encurtar_nomes_pendentes()
    except Exception as erro:
        resultado["nomes_encurtados_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_story_oferta(request):
    """Posta no máximo 1 story de oferta (ver instagram_bot/services.py,
    publicar_story_oferta_do_momento). Chamado várias vezes ao dia por um cron
    dedicado - separado de executar_tarefas_agendadas de propósito, já que roda numa
    frequência bem diferente (várias vezes ao dia, não uma vez só)."""
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        registro = publicar_story_oferta_do_momento(timezone.localdate(), request)
        resultado["story_oferta"] = (
            {"status": registro.status, "simulado": registro.modo_simulacao, "oferta": registro.oferta_nome}
            if registro else None
        )
    except Exception as erro:
        resultado["story_oferta_erro"] = str(erro)

    return JsonResponse(resultado)
