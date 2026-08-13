import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from links.models import Click
from links.services import gerar_click
from links.shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError
from saques.services import calcular_resumo_saldo_nav

from .models import Oferta
from .services import carregar_categorias_nivel1

ITENS_POR_PAGINA = 24

ORDENACOES = {
    "vendidos": "-vendas",
    "maior_cashback": "-percentual_comissao",
    "menor_preco": "preco_min",
    "maior_preco": "-preco_min",
    "maior_desconto": "-percentual_desconto",
}
ORDENACOES_ROTULOS = {
    "vendidos": "Mais vendidos",
    "maior_cashback": "Maior cashback",
    "menor_preco": "Menor preço",
    "maior_preco": "Maior preço",
    "maior_desconto": "Maior desconto",
}


def lista(request):
    categoria_id = request.GET.get("categoria", "")
    busca = request.GET.get("q", "").strip()
    ordenacao = request.GET.get("ordenar", "vendidos")
    if ordenacao not in ORDENACOES:
        ordenacao = "vendidos"

    ofertas = Oferta.objects.all()
    if categoria_id.isdigit():
        ofertas = ofertas.filter(categoria_id=int(categoria_id))
    if busca:
        ofertas = ofertas.filter(nome__icontains=busca)
    ofertas = ofertas.order_by(ORDENACOES[ordenacao])

    pagina_ofertas = Paginator(ofertas, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))
    categorias = sorted(carregar_categorias_nivel1().items(), key=lambda item: item[1])

    contexto = {
        "ofertas": pagina_ofertas,
        "categorias": categorias,
        "categoria_selecionada": categoria_id,
        "busca": busca,
        "ordenacao_selecionada": ordenacao,
        "ordenacoes": ORDENACOES_ROTULOS.items(),
        "cashback_maximo_por_produto": settings.CASHBACK_MAXIMO_POR_PRODUTO,
    }
    if request.user.is_authenticated:
        contexto.update(calcular_resumo_saldo_nav(request.user))
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
