import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ofertas.services import (
    LinkProdutoInvalidoError,
    SemComissaoError,
    buscar_oferta_por_link,
    categorias_mais_vendidas,
    obter_cashback_maximo_anunciado,
    selecionar_carrossel_home,
)
from saques.services import calcular_resumo_saldo_nav

from .forms import LinkProdutoForm
from .models import Click
from .services import gerar_click
from .shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

logger = logging.getLogger(__name__)

NUMERO_OFERTAS_EM_ALTA = 8
NUMERO_CATEGORIAS_HOME = 12


def home(request):
    link_convertido = None
    oferta_convertida = None
    sem_comissao_convertida = False
    click_id_pendente = None

    if request.method == "POST":
        if not request.user.is_authenticated:
            proximo = f"{reverse('home')}?{urlencode({'url_produto': request.POST.get('url_produto', '')})}"
            return redirect(f"{reverse('login')}?{urlencode({'next': proximo})}")

        form = LinkProdutoForm(request.POST)
        if form.is_valid():
            url_produto = form.cleaned_data["url_produto"]
            click = _criar_click_e_avisar(request, Click.TIPO_PRODUTO, url_produto, mensagem_sucesso=None)
            if click:
                link_convertido = click.link_gerado
                oferta_convertida, sem_comissao_convertida, precisa_navegador = _buscar_cashback_real(url_produto)
                if precisa_navegador:
                    click_id_pendente = click.id
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
        "click_id_pendente": click_id_pendente,
        "cashback_percentual_maximo": cashback_percentual_maximo,
        "saque_valor_minimo": settings.SAQUE_VALOR_MINIMO,
        "oferta_destaque": oferta_destaque,
        "ofertas_em_alta": ofertas_em_alta,
        "categorias_home": categorias_home,
    }
    if request.user.is_authenticated:
        contexto.update(calcular_resumo_saldo_nav(request.user))
    return render(request, "links/home.html", contexto)


@login_required
def ir_para_shopee(request):
    click = _criar_click_e_avisar(request, Click.TIPO_HOME, None, mensagem_sucesso=None)
    if click is None:
        return redirect("home")
    return redirect(click.link_gerado)


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
    link. Só tenta a resolução rápida (sem navegador headless, ver
    cashback_real_pendente pra isso) - é chamada síncrona, dentro da resposta da
    conversão do link, então não pode demorar. Retorna (oferta, sem_comissao,
    precisa_navegador) - o terceiro valor indica se vale tentar de novo em segundo
    plano com o navegador headless (ver Fase 37 no ROADMAP.md)."""
    try:
        return buscar_oferta_por_link(url_produto), False, False
    except SemComissaoError:
        return None, True, False
    except (LinkProdutoInvalidoError, ShopeeConfigError, ShopeeAPIError, requests.RequestException) as erro:
        logger.warning("[links] não consegui buscar o cashback real de %s: %s", url_produto, erro)
        return None, False, True


@login_required
def cashback_real_pendente(request, click_id):
    """Endpoint chamado via JS depois que a home já carregou (ver home.html) - só
    existe pra não travar a conversão do link esperando o navegador headless, que é
    bem mais lento que a resolução rápida (ver _buscar_cashback_real). Filtra por
    usuario=request.user pra ninguém conseguir consultar o click de outra pessoa."""
    click = get_object_or_404(Click, pk=click_id, usuario=request.user)
    try:
        oferta = buscar_oferta_por_link(click.url_original, usar_navegador=True)
        return JsonResponse(
            {
                "status": "ok",
                "percentual": str(oferta.percentual_cashback),
                "valor": f"{oferta.valor_cashback_estimado:.2f}",
            }
        )
    except SemComissaoError:
        return JsonResponse({"status": "sem_comissao"})
    except (LinkProdutoInvalidoError, ShopeeConfigError, ShopeeAPIError, requests.RequestException) as erro:
        logger.warning("[links] navegador headless também não resolveu %s: %s", click.url_original, erro)
        return JsonResponse({"status": "falhou"})


def _criar_click_e_avisar(request, tipo, url_produto, mensagem_sucesso="Link gerado com sucesso!"):
    try:
        click = gerar_click(request.user, tipo, url_produto)
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
