import hashlib
import logging
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.urls import reverse

from accounts.cliques_anonimos import salvar_click_anonimo
from accounts.funil import (
    clique_anonimo_permitido,
    exigir_login_ou_pagina_de_escolha,
    registrar_clique_sem_conta,
    registrar_primeiro_link,
    registrar_tentativa,
)
from accounts.ratelimit import limitar_por_ip
from ofertas.services import (
    LinkProdutoInvalidoError,
    SemComissaoError,
    buscar_oferta_por_item,
    buscar_oferta_por_link,
    categorias_mais_vendidas,
    obter_cashback_maximo_anunciado,
    resolver_item_id_com_rede,
    resolver_item_id_sem_rede,
    selecionar_carrossel_home,
)
from paginas.prova_social import frases_prova_social
from saques.services import calcular_resumo_saldo_nav

from cashback_shopee.meta_capi import enviar_evento, gerar_event_id

from .forms import LinkProdutoForm
from .models import Click
from .services import gerar_click
from .shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

logger = logging.getLogger(__name__)

NUMERO_OFERTAS_EM_ALTA = 8
NUMERO_CATEGORIAS_HOME = 12

# Estimativa ao vivo do conversor (cashback_estimado): a comissão de um produto não muda
# de minuto em minuto, então guarda por item_id e evita chamar a API da Shopee a cada
# tecla/colagem repetida do mesmo link.
CACHE_ESTIMATIVA_SEGUNDOS = 10 * 60
DOMINIOS_LINK_CURTO = ("s.shopee.com.br", "shp.ee")
# Abrir o link curto leva menos de 1s normalmente; o teto curto protege o único worker
# do gunicorn se a Shopee ficar lenta.
TIMEOUT_LINK_CURTO_SEGUNDOS = 4


def home(request):
    link_convertido = None
    oferta_convertida = None
    sem_comissao_convertida = False
    click_gerado = None

    if request.method == "POST":
        if not request.user.is_authenticated:
            registrar_tentativa(request, "conversor")
            # Página de escolha em vez de ir direto pro cadastro (ROADMAP 13.11,
            # decisão de 24/10/2026): "Cadastrar e continuar" volta pra cá com o link
            # preservado (ver accounts/views.py::registrar, parâmetro "next");
            # "Continuar sem cadastro" também volta pra cá, como GET (ver o elif abaixo).
            proximo = f"{reverse('home')}?{urlencode({'url_produto': request.POST.get('url_produto', '')})}"
            return redirect(
                f"{reverse('continuar_sem_cadastro')}?{urlencode({'next': proximo, 'origem': 'conversor'})}"
            )

        form = LinkProdutoForm(request.POST)
        if form.is_valid():
            url_produto = form.cleaned_data["url_produto"]
            click_gerado = _criar_click_e_avisar(request, Click.TIPO_PRODUTO, url_produto, mensagem_sucesso=None)
            if click_gerado:
                link_convertido = click_gerado.link_gerado
                oferta_convertida, sem_comissao_convertida = _buscar_cashback_real(url_produto)
            form = LinkProdutoForm()
    elif (
        not request.user.is_authenticated
        and request.GET.get("continuar") == "sem_cadastro"
        and request.GET.get("url_produto")
    ):
        # "Continuar sem cadastro" escolhido na página de escolha - mesmo fluxo do
        # POST acima, mas o clique fica anônimo (ver accounts/cliques_anonimos.py).
        if not clique_anonimo_permitido(request):
            return HttpResponse("Muitas tentativas sem cadastro. Crie uma conta para continuar.", status=429)
        registrar_tentativa(request, "conversor")
        registrar_clique_sem_conta(request, "conversor")
        form = LinkProdutoForm({"url_produto": request.GET["url_produto"]})
        if form.is_valid():
            url_produto = form.cleaned_data["url_produto"]
            click_gerado = _criar_click_e_avisar(request, Click.TIPO_PRODUTO, url_produto, mensagem_sucesso=None)
            if click_gerado:
                link_convertido = click_gerado.link_gerado
                oferta_convertida, sem_comissao_convertida = _buscar_cashback_real(url_produto)
        form = LinkProdutoForm()
    else:
        inicial = {}
        if request.GET.get("url_produto"):
            inicial["url_produto"] = request.GET["url_produto"]
        form = LinkProdutoForm(initial=inicial)

    # A oferta em destaque é a mais vendida do momento; "em alta" prioriza as ofertas
    # manuais cadastradas no admin, completando o resto com as mais vendidas do
    # catálogo sincronizado - ver selecionar_carrossel_home.
    oferta_destaque, ofertas_em_alta = selecionar_carrossel_home(NUMERO_OFERTAS_EM_ALTA)
    categorias_home = categorias_mais_vendidas(NUMERO_CATEGORIAS_HOME)
    cashback_percentual_maximo = obter_cashback_maximo_anunciado()

    contexto = {
        "form": form,
        "link_convertido": link_convertido,
        "oferta_convertida": oferta_convertida,
        "sem_comissao_convertida": sem_comissao_convertida,
        "cashback_percentual_maximo": cashback_percentual_maximo,
        "prova_social": frases_prova_social(),
        "cashback_minimo_direta": settings.CASHBACK_MINIMO_VENDA_DIRETA,
        "cashback_minimo_indireta": settings.CASHBACK_MINIMO_VENDA_INDIRETA,
        "saque_valor_minimo": settings.SAQUE_VALOR_MINIMO,
        "oferta_destaque": oferta_destaque,
        "ofertas_em_alta": ofertas_em_alta,
        "categorias_home": categorias_home,
        "url_instagram": settings.URL_INSTAGRAM,
        "url_whatsapp_canal": settings.URL_WHATSAPP_CANAL,
    }
    if request.user.is_authenticated:
        contexto.update(calcular_resumo_saldo_nav(request.user))
    resposta = render(request, "links/home.html", contexto)
    if click_gerado and not request.user.is_authenticated:
        # Clique anônimo (ROADMAP 13.11) - guarda no navegador pra ligar à conta se a
        # pessoa se cadastrar dentro de 7 dias (ver accounts/cliques_anonimos.py).
        salvar_click_anonimo(request, resposta, click_gerado.id.hex)
    return resposta


@exigir_login_ou_pagina_de_escolha("ir_shopee")
def ir_para_shopee(request):
    click = _criar_click_e_avisar(request, Click.TIPO_HOME, None, mensagem_sucesso=None)
    if click is None:
        return redirect("home")
    resposta = redirect(click.link_gerado)
    if not request.user.is_authenticated:
        # Clique anônimo (ROADMAP 13.11) - guarda no navegador pra ligar à conta se a
        # pessoa se cadastrar dentro de 7 dias (ver accounts/cliques_anonimos.py).
        salvar_click_anonimo(request, resposta, click.id.hex)
    return resposta


def _navegador_instagram(request) -> bool:
    """O navegador interno do Instagram (abre links de DM/story sem sair do app) tem
    o User-Agent normal do celular com "Instagram" no final (ver NAVEGADOR em
    accounts/tests.py::FunilSemContaTests) - nem sempre mantém cookie entre sessões,
    então "continuar sem cadastro" é menos confiável nele (ver aviso condicional em
    continuar_sem_cadastro.html). Só muda o que é mostrado na tela, não bloqueia nada."""
    return "instagram" in request.META.get("HTTP_USER_AGENT", "").lower()


def continuar_sem_cadastro(request):
    """Página de escolha de quem esbarrou no login ao clicar sem conta (ROADMAP
    13.11, decisão de 24/10/2026): "Cadastrar e continuar" (ganha cashback) ou
    "Continuar sem cadastro" (vai pra Shopee sem cashback, clique fica anônimo).
    Mostrada pelo decorador accounts.funil.exigir_login_ou_pagina_de_escolha, em vez
    de forçar o login de cara. "origem" (conversor/ir_shopee/oferta/story) só serve
    pra registrar a tentativa no funil - ver accounts/funil.py - não é usada aqui."""
    proximo = request.GET.get("next", "")
    if not proximo or not url_has_allowed_host_and_scheme(
        proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect("home")

    separador = "&" if "?" in proximo else "?"
    contexto = {
        "link_cadastrar": f"{reverse('registrar')}?{urlencode({'next': proximo})}",
        "link_continuar": f"{proximo}{separador}{urlencode({'continuar': 'sem_cadastro'})}",
        "navegador_instagram": _navegador_instagram(request),
    }
    return render(request, "links/continuar_sem_cadastro.html", contexto)


@login_required
def gerar_link(request):
    form = LinkProdutoForm()

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "produto":
            form = LinkProdutoForm(request.POST)
            if form.is_valid():
                _criar_click_e_avisar(request, Click.TIPO_PRODUTO, form.cleaned_data["url_produto"])
                return redirect("gerar_link")
        elif acao == "home":
            _criar_click_e_avisar(request, Click.TIPO_HOME, None)
            return redirect("gerar_link")

    clicks = request.user.clicks.all()[:20]
    return render(request, "links/gerar_link.html", {"form": form, "clicks": clicks})


def _buscar_cashback_real(url_produto):
    """Busca a % de comissão real do produto convertido, pra mostrar o cashback de
    verdade em vez do "até X%" genérico do catálogo sincronizado (ver
    ofertas.services.buscar_oferta_por_link) - o link já foi gerado nesse ponto, então
    qualquer falha aqui só significa "sem estimativa exata pra mostrar", nunca desfaz o
    link. Retorna (oferta, sem_comissao).

    Chegou a existir uma segunda tentativa em segundo plano via navegador headless
    (Browserless) pros links que essa busca rápida não consegue resolver - removida
    depois de confirmar em produção que a Shopee bloqueia esse tipo de navegador como
    tráfego suspeito nesse domínio de rastreamento (100% de bloqueio nos testes reais,
    não um caso raro) - ver ROADMAP.md, Fase 37."""
    try:
        return buscar_oferta_por_link(url_produto), False
    except SemComissaoError:
        return None, True
    except (LinkProdutoInvalidoError, ShopeeConfigError, ShopeeAPIError, requests.RequestException) as erro:
        logger.warning("[links] não consegui buscar o cashback real de %s: %s", url_produto, erro)
        return None, False


def _criar_click_e_avisar(request, tipo, url_produto, mensagem_sucesso="Link gerado com sucesso!"):
    try:
        click = gerar_click(request.user, tipo, url_produto)
        # Só via Conversions API (servidor) - ver o mesmo comentário em
        # ofertas/views.py::_ir_com_click_ou_erro (nem todo caminho até aqui
        # renderiza uma página nossa depois, pra disparar o Pixel do navegador).
        enviar_evento("GerouLinkCashback", request, gerar_event_id(), {"tipo_click": tipo})
        registrar_primeiro_link(request)
        if mensagem_sucesso:
            messages.success(request, mensagem_sucesso)
        return click
    except ShopeeConfigError as erro:
        messages.error(request, str(erro))
    except SubIdInvalidoError as erro:
        messages.error(request, str(erro))
    except ShopeeAPIError as erro:
        messages.error(request, f"A Shopee recusou o pedido: {erro}")
    except (requests.RequestException, KeyError):
        messages.error(request, "Não foi possível gerar o link agora. Tente novamente em instantes.")
    return None


@require_GET
@limitar_por_ip("cashback_estimado", limite=30, janela_segundos=60)
def cashback_estimado(request):
    """% e R$ de cashback reais de um produto, consultados ASSIM QUE o link é colado no
    conversor da home (antes de gerar o link) - o "até X%" genérico do catálogo não diz
    nada sobre o produto específico. Pública (quem chega de anúncio ainda não tem
    conta), por isso com limite por IP e cache por item_id.

    Link com o item_id na própria URL resolve sem rede. Link curto (s.shopee.com.br,
    shp.ee) abre a página da Shopee pra achar o produto (ver
    ofertas/services.py::_texto_da_pagina_normalizado) - com timeout curto e o item_id
    guardado em cache por URL, porque a rota é pública e o gunicorn tem 1 worker só. Se
    não der pra identificar, responde "link_curto" e a home explica como ver o valor."""
    url = request.GET.get("url", "").strip()
    item_id = resolver_item_id_sem_rede(url)
    if item_id is None:
        host = urlparse(url).netloc.lower()
        if not any(host == d or host.endswith("." + d) for d in DOMINIOS_LINK_CURTO):
            return JsonResponse({"status": "nao_identificado"})
        chave_url = f"cashback_estimado:url:{hashlib.sha256(url.encode()).hexdigest()}"
        item_id = cache.get(chave_url)
        if item_id is None:
            item_id = resolver_item_id_com_rede(url, timeout=TIMEOUT_LINK_CURTO_SEGUNDOS)
            if item_id is None:
                return JsonResponse({"status": "link_curto"})
            cache.set(chave_url, item_id, CACHE_ESTIMATIVA_SEGUNDOS)

    chave = f"cashback_estimado:{item_id}"
    resultado = cache.get(chave)
    if resultado is None:
        try:
            oferta = buscar_oferta_por_item(item_id)
            resultado = {
                "status": "ok",
                # Mesmo formato do floatformat:"-1" usado no resto da home (9,8 / 12).
                "percentual": f"{oferta.percentual_cashback:.1f}".removesuffix(".0").replace(".", ","),
                "valor": f"{oferta.valor_cashback_estimado:.2f}".replace(".", ","),
            }
        except SemComissaoError:
            resultado = {"status": "sem_comissao"}
        except (ShopeeConfigError, ShopeeAPIError, requests.RequestException, KeyError) as erro:
            logger.warning("[links] estimativa ao vivo falhou pro item %s: %s", item_id, erro)
            return JsonResponse({"status": "indisponivel"})
        cache.set(chave, resultado, CACHE_ESTIMATIVA_SEGUNDOS)
    return JsonResponse(resultado)
