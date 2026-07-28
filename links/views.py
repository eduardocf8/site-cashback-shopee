import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LinkProdutoForm
from .models import Click
from .services import gerar_click
from .shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError


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


def _criar_click_e_avisar(request, tipo, url_produto):
    try:
        gerar_click(request.user, tipo, url_produto)
        messages.success(request, "Link gerado com sucesso!")
    except ShopeeConfigError as erro:
        messages.error(request, str(erro))
    except SubIdInvalidoError as erro:
        messages.error(request, str(erro))
    except ShopeeAPIError as erro:
        messages.error(request, f"A Shopee recusou o pedido: {erro}")
    except (requests.RequestException, KeyError):
        messages.error(request, "Não foi possível gerar o link agora. Tente novamente em instantes.")
