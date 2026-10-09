import hmac
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import cache_control

from accounts.comunicacoes import (
    enviar_lembrete_primeira_compra_7_dias,
    enviar_lembrete_primeira_compra_30_dias,
    enviar_lembrete_venda_indireta_semanal,
)
from accounts.tokens import enviar_lembretes_verificacao_pendente
from instagram_bot.lembrete_token import verificar_validade_token
from instagram_bot.services import executar_publicacoes_do_dia, publicar_story_oferta_do_momento
from links.services import resolver_item_id_alvo_pendentes
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


@cache_control(max_age=0, no_cache=True)
def service_worker(request):
    """Serve o arquivo em /sw.js (raiz do site), não em /static/sw.js.

    Escopo de um service worker é limitado à pasta de onde ele é servido - registrado
    em /static/sw.js ele só enxergaria páginas dentro de /static/. Servido na raiz,
    cobre o site inteiro, que é o que a notificação push precisa (o evento "push"
    chega no service worker mesmo com o site fechado, então ele não pode estar restrito
    a uma rota específica). "no-cache" evita o navegador prender numa versão antiga do
    arquivo depois de um deploy - sem isso, dá pra levar até 24h pra pegar uma atualização.
    """
    caminho = settings.BASE_DIR / "static" / "sw.js"
    return HttpResponse(caminho.read_text(), content_type="application/javascript")


def _token_valido(request) -> bool:
    token_esperado = settings.TAREFAS_TOKEN
    token_recebido = request.GET.get("token", "")
    return bool(token_esperado) and hmac.compare_digest(token_esperado, token_recebido)


# Janela da sincronização diária com a Shopee - só precisa cobrir o atraso normal da
# Shopee pra reportar conversões (girando em torno de 1 dia, mas com folga pra atrasos
# maiores) - não o histórico inteiro. Rodar com 60 dias TODO dia (como era antes)
# reprocessava um volume que só cresce com o tempo, deixando a tarefa cada vez mais
# perto do timeout de 120s do gunicorn - arriscado rodando num horário de tráfego real
# (ver DIAS_SINCRONIZACAO_RECONCILIACAO, abaixo, pra reconciliação).
DIAS_SINCRONIZACAO_DIARIA = 10

# Janela da sincronização semanal de reconciliação (executar_sincronizacao_semanal) -
# cobre o mesmo histórico de 60 dias que a sincronização diária cobria antes,
# recapturando status que mudou tarde (cancelamento/devolução reportado bem depois da
# compra) e que a janela curta da diária não pegaria. Roda só 1x por semana, de
# madrugada (baixo tráfego), já que é a parte mais pesada.
DIAS_SINCRONIZACAO_RECONCILIACAO = 60


def executar_tarefas_agendadas(request):
    """Roda a sincronização diária (janela curta) com a Shopee, a liberação de saldo e
    a checagem de saques.

    Protegido por um token (TAREFAS_TOKEN) em vez de exigir login, porque quem chama
    esse endereço é o agendamento automático (GitHub Actions), não uma pessoa logada.

    Roda às 10h (Brasília) - depois da Shopee atualizar os pedidos do dia anterior
    (por volta das 7h-8h), pra eles aparecerem no site em D+1 em vez de D+2. Mudou de
    madrugada pra esse horário só depois de encolher a janela de sincronização pra 10
    dias (ver DIAS_SINCRONIZACAO_DIARIA) - o site roda com 1 worker gunicorn só (ver
    README.md), então uma tarefa pesada demais nesse horário de tráfego real arriscava
    tirar o site do ar (timeout de 120s matando o único worker). A reconciliação de 60
    dias continua rodando de madrugada, mas numa tarefa separada e semanal (ver
    executar_sincronizacao_semanal).

    Separado de propósito dos posts do Instagram (executar_publicacoes_instagram) -
    essa tarefa mexe com dinheiro de gente de verdade (saldo, saques).
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    agora = datetime.now(tz=dt_timezone.utc)
    inicio = agora - timedelta(days=DIAS_SINCRONIZACAO_DIARIA)

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

    return JsonResponse(resultado)


def executar_sincronizacao_semanal(request):
    """Reconciliação semanal: reprocessa os últimos 60 dias de conversões da Shopee,
    pra recapturar status que mudou tarde (cancelamento/devolução reportado bem depois
    da compra original) e que a janela curta da sincronização diária (10 dias, ver
    executar_tarefas_agendadas) não pegaria.

    Separada da diária de propósito - é a parte pesada (reprocessa um volume bem maior
    de pedidos), então fica de madrugada, 1x por semana, longe de qualquer horário de
    tráfego real (ver README.md sobre o único worker gunicorn do site)."""
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    agora = datetime.now(tz=dt_timezone.utc)
    inicio = agora - timedelta(days=DIAS_SINCRONIZACAO_RECONCILIACAO)

    resultado = {}
    try:
        resultado["sincronizacao"] = sincronizar(int(inicio.timestamp()), int(agora.timestamp()))
    except (ShopeeConfigError, ShopeeAPIError) as erro:
        resultado["sincronizacao_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_publicacoes_instagram(request):
    """Posta o(s) conteúdo(s) do dia no Instagram e confere a validade do token de
    acesso. Separado de executar_tarefas_agendadas de propósito - ver o comentário lá:
    esse aqui precisa rodar num horário de bom alcance (11h), não de madrugada."""
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
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


def executar_resolucao_item_id_alvo(request):
    """Tenta resolver, seguindo redirecionamento de verdade, o item_id_alvo dos
    cliques que a resolução rápida (na hora do clique) não conseguiu - tipicamente
    links curtos (ver links/services.py::resolver_item_id_alvo_pendentes e
    ROADMAP.md, Fase 41/42).

    Tarefa agendada separada de propósito, mesmo motivo de executar_encurtamento_nomes:
    seguir redirecionamento pode levar até 10s por clique, e isso não cabe no
    orçamento de 120s junto com a sincronização de pedidos/saques.
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        resultado["item_id_alvo_resolvido"] = resolver_item_id_alvo_pendentes()
    except Exception as erro:
        resultado["item_id_alvo_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_lembrete_verificacao_email(request):
    """Manda um lembrete (novo link) pra quem se cadastrou entre 24h e 48h atrás e
    ainda não confirmou o e-mail (ver accounts/tokens.py::enviar_lembretes_verificacao_pendente).

    Cron Job dedicado de propósito, mesmo motivo de executar_encurtamento_nomes/
    executar_resolucao_item_id_alvo: manda 1 e-mail por pessoa em série (BCC não dá,
    cada um carrega um token diferente), então roda de madrugada, fora do horário de
    pico - não cabe dividir o orçamento com executar_tarefas_agendadas.
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        resultado["lembretes_verificacao_enviados"] = enviar_lembretes_verificacao_pendente(request)
    except Exception as erro:
        resultado["lembretes_verificacao_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_lembrete_primeira_compra(request):
    """Manda um lembrete pra quem se cadastrou há 7 dias ou 30 dias e ainda não fez
    nenhum pedido (ver accounts/comunicacoes.py::enviar_lembrete_primeira_compra_7_dias/
    30_dias) - textos diferentes em cada janela, mesmo Cron Job chama os dois porque é
    rápido (BCC em lote, não 1 e-mail por pessoa).

    Cron Job dedicado, mesmo motivo dos outros: roda de madrugada, fora do horário de
    pico.
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        resultado["lembrete_7_dias_enviados"] = enviar_lembrete_primeira_compra_7_dias(request)
    except Exception as erro:
        resultado["lembrete_7_dias_erro"] = str(erro)

    try:
        resultado["lembrete_30_dias_enviados"] = enviar_lembrete_primeira_compra_30_dias(request)
    except Exception as erro:
        resultado["lembrete_30_dias_erro"] = str(erro)

    return JsonResponse(resultado)


def executar_lembrete_venda_indireta(request):
    """Lembrete semanal (todo sábado de manhã) pra quem comprou por venda indireta
    nos últimos 7 dias, explicando a venda direta (ver
    accounts/comunicacoes.py::enviar_lembrete_venda_indireta_semanal).

    Cron Job próprio: roda 1x/semana, num horário diferente dos lembretes diários.
    """
    if not _token_valido(request):
        return HttpResponseForbidden("Token inválido ou não configurado.")

    resultado = {}
    try:
        resultado["lembrete_venda_indireta_enviados"] = enviar_lembrete_venda_indireta_semanal(request)
    except Exception as erro:
        resultado["lembrete_venda_indireta_erro"] = str(erro)

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
