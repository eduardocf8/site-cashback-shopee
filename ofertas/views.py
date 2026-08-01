import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from links.models import Click
from links.services import gerar_click
from links.shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

from .models import Oferta
from .services import carregar_categorias_nivel1

ITENS_POR_PAGINA = 24


def lista(request):
    categoria_id = request.GET.get("categoria", "")
    ofertas = Oferta.objects.all()
    if categoria_id.isdigit():
        ofertas = ofertas.filter(categoria_id=int(categoria_id))

    pagina_ofertas = Paginator(ofertas, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))
    categorias = sorted(carregar_categorias_nivel1().items(), key=lambda item: item[1])

    contexto = {
        "ofertas": pagina_ofertas,
        "categorias": categorias,
        "categoria_selecionada": categoria_id,
    }
    return render(request, "ofertas/lista.html", contexto)


@login_required
def ir_para_oferta(request, oferta_id):
    oferta = get_object_or_404(Oferta, pk=oferta_id)

    try:
        click = gerar_click(request.user, Click.TIPO_PRODUTO, oferta.product_link)
    except ShopeeConfigError as erro:
        messages.error(request, str(erro))
        return redirect("ofertas_lista")
    except SubIdInvalidoError as erro:
        messages.error(request, str(erro))
        return redirect("ofertas_lista")
    except ShopeeAPIError as erro:
        messages.error(request, f"A Shopee recusou o pedido: {erro}")
        return redirect("ofertas_lista")
    except requests.RequestException:
        messages.error(request, "Não foi possível abrir essa oferta agora. Tenta de novo em instantes.")
        return redirect("ofertas_lista")

    return redirect(click.link_gerado)
