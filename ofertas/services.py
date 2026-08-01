import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from links.shopee_client import buscar_ofertas_produtos

from .models import Oferta

CAMINHO_CATEGORIAS_NIVEL1 = Path(__file__).resolve().parent / "data" / "shopee_categorias_nivel1.json"

_categorias_nivel1_cache: dict[int, str] | None = None


def carregar_categorias_nivel1() -> dict[int, str]:
    global _categorias_nivel1_cache
    if _categorias_nivel1_cache is None:
        with open(CAMINHO_CATEGORIAS_NIVEL1, encoding="utf-8") as f:
            lista = json.load(f)
        _categorias_nivel1_cache = {item["id"]: item["nome"] for item in lista}
    return _categorias_nivel1_cache


def _decimal_seguro(valor, padrao=Decimal("0")):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        return padrao


def _montar_oferta(node: dict, categorias_nivel1: dict[int, str]) -> Oferta:
    categoria_ids = node.get("productCatIds") or []
    categoria_id = categoria_ids[0] if categoria_ids else 0
    avaliacao_bruta = node.get("ratingStar")
    avaliacao = _decimal_seguro(avaliacao_bruta) if avaliacao_bruta else None

    return Oferta(
        item_id=node["itemId"],
        nome=(node.get("productName") or "")[:255],
        imagem_url=node.get("imageUrl") or "",
        preco_min=_decimal_seguro(node.get("priceMin")),
        preco_max=_decimal_seguro(node.get("priceMax")),
        percentual_desconto=int(node.get("priceDiscountRate") or 0),
        percentual_comissao=_decimal_seguro(node.get("commissionRate")),
        avaliacao=avaliacao,
        vendas=int(node.get("sales") or 0),
        categoria_id=categoria_id,
        categoria_nome=categorias_nivel1.get(categoria_id, ""),
        loja_nome=(node.get("shopName") or "")[:255],
        product_link=node.get("productLink") or "",
    )


def sincronizar_ofertas(limite_por_pagina: int = 50, max_paginas: int = 40) -> dict:
    """Busca as ofertas de produtos (productOfferV2, listType ALL) e substitui a lista atual.

    Full-replace (não incremental): uma "oferta" é só uma foto do que a Shopee está
    oferecendo hoje, sem status a preservar entre sincronizações (diferente de Pedido/Saque).
    """
    categorias_nivel1 = carregar_categorias_nivel1()

    ofertas_novas = []
    pagina = 1
    while pagina <= max_paginas:
        resultado = buscar_ofertas_produtos(pagina, limite_por_pagina)
        for node in resultado["nodes"]:
            ofertas_novas.append(_montar_oferta(node, categorias_nivel1))
        if not resultado["pageInfo"].get("hasNextPage"):
            break
        pagina += 1

    # Dedup por item_id (a Shopee pode repetir um item entre páginas se o feed
    # for atualizado no meio da sincronização).
    por_item_id = {oferta.item_id: oferta for oferta in ofertas_novas}

    with transaction.atomic():
        Oferta.objects.all().delete()
        Oferta.objects.bulk_create(por_item_id.values())

    return {"total": len(por_item_id), "paginas_percorridas": pagina}
