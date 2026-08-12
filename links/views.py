from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from ofertas.services import categorias_mais_vendidas, selecionar_top_ofertas_sem_duplicar

from .forms import LinkProdutoForm
from .models import Click
from .services import gerar_click
from .shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

NUMERO_OFERTAS_EM_ALTA = 8
NUMERO_CATEGORIAS_HOME = 6


def home(request):
    link_convertido = None

    if request.method == "POST":
        if not request.user.is_authenticated:
            proximo = f"{reverse('home')}?{urlencode({'url_produto': request.POST.get('url_produto', '')})}"
            return redirect(f"{reverse('login')}?{urlencode({'next': proximo})}")

        form = LinkProdutoForm(request.POST)
        if form.is_valid():
            click = _criar_click_e_avisar(
                request, Click.TIPO_PRODUTO, form.cleaned_data["url_produto"], mensagem_sucesso=None
            )
            link_convertido = click.link_gerado if click else None
            form = LinkProdutoForm()
    else:
        inicial = {}
        if request.GET.get("url_produto"):
            inicial["url_produto"] = request.GET["url_produto"]
        form = LinkProdutoForm(initial=inicial)

    # A oferta em destaque é a mais vendida do momento; "em alta" são as próximas,
    # sem repetir o mesmo produto (ver selecionar_top_ofertas_sem_duplicar).
    top_ofertas = selecionar_top_ofertas_sem_duplicar(1 + NUMERO_OFERTAS_EM_ALTA)
    oferta_destaque = top_ofertas[0] if top_ofertas else None
    ofertas_em_alta = top_ofertas[1:]
    categorias_home = categorias_mais_vendidas(NUMERO_CATEGORIAS_HOME)

    contexto = {
        "form": form,
        "link_convertido": link_convertido,
        "cashback_maximo_anunciado": settings.CASHBACK_MAXIMO_ANUNCIADO,
        "saque_valor_minimo": settings.SAQUE_VALOR_MINIMO,
        "oferta_destaque": oferta_destaque,
        "ofertas_em_alta": ofertas_em_alta,
        "categorias_home": categorias_home,
    }
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
