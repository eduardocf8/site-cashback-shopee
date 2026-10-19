"""Busca de produtos (productOfferV2) e link de afiliado (generateShortLink) na API
de afiliados da Shopee, com as credenciais de cada conta. Mesmas regras do app de
Windows (Appfiliado/afiliados.py: normalizar_oferta_shopee e filtros locais)."""

import json
import re

from links.shopee_client import PADRAO_SUB_ID_VALIDO, ShopeeAPIError, executar_graphql_com_credenciais
from painel.resultados import para_numero
from painel.shopee import _campo_invalido

from .categorias import produto_pertence_as_categorias

POR_PAGINA = 50
CAMPOS_PRODUTO = [
    "itemId", "shopId", "productName", "price", "priceMin", "priceMax", "priceDiscountRate",
    "commissionRate", "sellerCommissionRate", "ratingStar", "imageUrl", "productLink", "offerLink",
    "sales", "shopName",
]
# sortType da productOfferV2: 1 relevância (só com palavra-chave), 2 mais vendidos,
# 5 maior comissão. Não existe "maior desconto": busca por mais vendidos e reordena.
SORT_TYPE = {"mais_vendidos": 2, "maior_comissao": 5, "maior_desconto": 2}


class SubIdInvalido(ValueError):
    pass


def extrair_id_da_loja(texto: str) -> str:
    """Número da loja a partir do que a pessoa colou: o número, o link da loja
    (/shop/123) ou o link de um produto dela (-i.LOJA.ITEM). "" se não achar."""
    texto = str(texto or "").strip()
    if texto.isdigit():
        return texto
    if re.search(r"/collections?/", texto, re.I):
        return ""
    for padrao in (r"/shop/(\d{3,})", r"-i\.(\d+)\.\d+", r"[?&](?:shopid|shop_id)=(\d+)", r"/product/(\d+)/\d+"):
        achado = re.search(padrao, texto, re.I)
        if achado:
            return achado.group(1)
    return ""


def _percentual(valor) -> float:
    numero = para_numero(valor)
    return numero * 100 if 0 < numero < 1 else numero


def normalizar_produto(no: dict) -> dict:
    preco = para_numero(no.get("priceMin")) or para_numero(no.get("price"))
    return {
        "item_id": str(no.get("itemId") or ""),
        "shop_id": str(no.get("shopId") or ""),
        "nome": str(no.get("productName") or "").strip(),
        "link": str(no.get("productLink") or no.get("offerLink") or "").strip(),
        "imagem": str(no.get("imageUrl") or "").strip(),
        "preco": preco,
        "comissao": _percentual(no.get("commissionRate") or no.get("sellerCommissionRate")),
        "desconto": _percentual(no.get("priceDiscountRate")),
        "vendas": int(para_numero(no.get("sales"))),
        "avaliacao": para_numero(no.get("ratingStar")),
        "loja": str(no.get("shopName") or "").strip(),
    }


def buscar_produtos(app_id: str, secret: str, config, pagina: int) -> tuple[list[dict], bool]:
    """(produtos da página já normalizados, tem próxima página). Os filtros de
    número (comissão, preço...) são aplicados depois, em passa_nos_filtros."""
    argumentos = [f"limit:{POR_PAGINA}", f"page:{int(pagina)}"]
    if config.tipo_busca == config.BUSCA_PALAVRA and config.palavra_chave.strip():
        argumentos.append(f"keyword:{json.dumps(config.palavra_chave.strip(), ensure_ascii=False)}")
    if config.tipo_busca == config.BUSCA_LOJA:
        loja = extrair_id_da_loja(config.loja)
        if not loja:
            raise ValueError("Não consegui achar o número da loja no link informado.")
        argumentos.append(f"shopId:{int(loja)}")
    argumentos.append(f"sortType:{SORT_TYPE.get(config.ordenacao, 2)}")

    campos = list(CAMPOS_PRODUTO)
    while True:
        query = (
            f"query{{productOfferV2({','.join(argumentos)}){{nodes{{{' '.join(campos)}}}"
            "pageInfo{page limit hasNextPage}}}"
        )
        try:
            dados = executar_graphql_com_credenciais(app_id, secret, query)
            break
        except ShopeeAPIError as erro:
            invalido = _campo_invalido(str(erro))
            if not invalido or invalido not in campos:
                raise
            campos.remove(invalido)

    relatorio = dados.get("productOfferV2") or {}
    nos = [no for no in relatorio.get("nodes") or [] if isinstance(no, dict)]
    produtos = [p for p in (normalizar_produto(no) for no in nos) if p["nome"] and p["link"] and p["item_id"]]
    info = relatorio.get("pageInfo") or {}
    tem_proxima = bool(info.get("hasNextPage")) if "hasNextPage" in info else len(nos) >= POR_PAGINA
    if config.ordenacao == "maior_desconto":
        produtos.sort(key=lambda p: p["desconto"], reverse=True)
    return produtos, tem_proxima


def passa_nos_filtros(produto: dict, config) -> bool:
    if config.comissao_minima and produto["comissao"] < config.comissao_minima:
        return False
    if config.desconto_minimo and produto["desconto"] < config.desconto_minimo:
        return False
    if config.vendas_minimas and produto["vendas"] < config.vendas_minimas:
        return False
    # Vazio ou 0 = sem filtro (preço máximo 0 barrava todos os produtos).
    if config.preco_minimo and produto["preco"] < float(config.preco_minimo):
        return False
    if config.preco_maximo and produto["preco"] > float(config.preco_maximo):
        return False
    if config.avaliacao_minima and produto["avaliacao"] < float(config.avaliacao_minima):
        return False
    if config.tipo_busca == config.BUSCA_CATEGORIA:
        return produto_pertence_as_categorias(produto["nome"], config.categorias)
    return True


def validar_sub_ids(sub_ids: list[str]) -> list[str]:
    if len(sub_ids) > 5:
        raise SubIdInvalido("A Shopee aceita no máximo 5 Sub IDs.")
    invalidos = [s for s in sub_ids if not PADRAO_SUB_ID_VALIDO.fullmatch(s)]
    if invalidos:
        raise SubIdInvalido(f"Sub ID só pode ter letras e números (sem espaço, hífen ou acento): {', '.join(invalidos)}")
    return sub_ids


def gerar_link_afiliado(app_id: str, secret: str, url: str, sub_ids: list[str]) -> str:
    sub_ids = validar_sub_ids(sub_ids)
    extra = f",subIds:{json.dumps(sub_ids, ensure_ascii=False)}" if sub_ids else ""
    query = (
        f"mutation{{generateShortLink(input:{{originUrl:{json.dumps(url, ensure_ascii=False)}{extra}}})"
        "{shortLink}}"
    )
    dados = executar_graphql_com_credenciais(app_id, secret, query)
    link = ((dados or {}).get("generateShortLink") or {}).get("shortLink") or ""
    if not link:
        raise ShopeeAPIError("A Shopee não devolveu o link de afiliado.")
    return link


def _moeda(valor: float) -> str:
    texto = f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def texto_base(produto: dict, cupom: str = "") -> str:
    """O mesmo texto base do app de Windows (bot_runner._montar_texto_base_shopee);
    depois passa pelo formatador, que monta título, preço, "Compre aqui" etc."""
    linhas = [produto["nome"] or "Oferta Shopee"]
    if produto["vendas"]:
        linhas.append(f"Mais de {produto['vendas']} vendidos!")
    if produto["desconto"]:
        linhas.append(f"Desconto: {produto['desconto']:g}%")
    if produto["avaliacao"]:
        linhas.append(f"Avaliação: {produto['avaliacao']:g}/5")
    if produto["preco"]:
        linhas.append(f"Por: {_moeda(produto['preco'])}")
    if cupom.strip():
        linhas.append(f"Cupom: {cupom.strip()}")
    return "\n".join(linhas)
