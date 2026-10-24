import hashlib
import json
import re
import time

import requests
from django.conf import settings

PADRAO_SUB_ID_VALIDO = re.compile(r"[A-Za-z0-9]{1,100}")


class ShopeeAPIError(Exception):
    """Erro retornado pela API de afiliados da Shopee (bloco 'errors' da resposta GraphQL)."""


class ShopeeConfigError(Exception):
    """As credenciais da API Shopee não estão configuradas no .env."""


class SubIdInvalidoError(Exception):
    """O subId informado não segue o formato aceito pela API Shopee (só letras e números)."""


def validar_sub_ids(sub_ids: list[str]) -> list[str]:
    if len(sub_ids) > 5:
        raise SubIdInvalidoError("A API Shopee aceita no máximo 5 Sub IDs.")

    invalidos = [sub_id for sub_id in sub_ids if not PADRAO_SUB_ID_VALIDO.fullmatch(sub_id)]
    if invalidos:
        raise SubIdInvalidoError(
            "Sub ID inválido (use apenas letras sem acento e números): " + ", ".join(invalidos)
        )
    return sub_ids


def _assinar(app_id: str, secret: str, timestamp: int, payload: str) -> str:
    base = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def executar_graphql(query: str) -> dict:
    """Envia uma query/mutation (já montada, com os valores embutidos) para a API Shopee."""
    app_id = settings.SHOPEE_AFFILIATE_APP_ID
    secret = settings.SHOPEE_AFFILIATE_SECRET

    if not app_id or not secret:
        raise ShopeeConfigError(
            "Configure SHOPEE_AFFILIATE_APP_ID e SHOPEE_AFFILIATE_SECRET no arquivo .env "
            "com as credenciais da sua conta de afiliado Shopee."
        )
    return executar_graphql_com_credenciais(app_id, secret, query)


def executar_graphql_com_credenciais(app_id: str, secret: str, query: str) -> dict:
    """Igual executar_graphql, mas com as credenciais de outra conta de afiliado
    (usado pelo painel do Appfiliado, com as credenciais de cada cliente)."""
    payload = json.dumps({"query": query}, ensure_ascii=False, separators=(",", ":"))
    timestamp = int(time.time())
    assinatura = _assinar(app_id, secret, timestamp, payload)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={assinatura}",
    }

    resposta = requests.post(
        settings.SHOPEE_AFFILIATE_API_URL,
        data=payload,
        headers=headers,
        timeout=15,
    )
    resposta.raise_for_status()
    corpo_resposta = resposta.json()

    if corpo_resposta.get("errors"):
        mensagens = "; ".join(erro.get("message", str(erro)) for erro in corpo_resposta["errors"])
        raise ShopeeAPIError(mensagens)

    return corpo_resposta.get("data", {})


def gerar_link_curto(origin_url: str, sub_ids: list[str]) -> str:
    sub_ids = validar_sub_ids(sub_ids)
    sub_ids_graphql = f",subIds:{json.dumps(sub_ids, ensure_ascii=False)}" if sub_ids else ""

    query = (
        "mutation{"
        "generateShortLink(input:{"
        f"originUrl:{json.dumps(origin_url, ensure_ascii=False)}"
        f"{sub_ids_graphql}"
        "}){"
        "shortLink"
        "}"
        "}"
    )
    dados = executar_graphql(query)
    return dados["generateShortLink"]["shortLink"]


def buscar_ofertas_produtos(pagina: int, limite: int = 50, categoria: int | None = None) -> dict:
    """Consulta a query productOfferV2 para montar a página de ofertas: o feed geral
    (listType ALL) ou, com `categoria`, os produtos de uma categoria (productCatId) - cada
    categoria traz uma lista própria (ver ofertas/catalogo.py).

    Usa commissionRate (= shopeeCommissionRate + sellerCommissionRate), não só
    shopeeCommissionRate. sellerCommissionRate é um bônus de campanha do vendedor,
    instável e por produto - mas confirmamos comparando com o painel oficial de
    afiliados da Shopee que ele já entra de fato no itemTotalCommission pago em vendas
    diretas reais (ver pedidos/services.py), então escondê-lo aqui só faria o site
    prometer menos do que o usuário realmente recebe.
    """
    query = (
        "query{"
        "productOfferV2("
        + (f"productCatId:{int(categoria)}," if categoria else "listType:0,")
        + f"page:{pagina},limit:{limite}"
        "){"
        "nodes{"
        "itemId commissionRate sellerCommissionRate sales priceMax priceMin productCatIds ratingStar "
        "priceDiscountRate imageUrl productName shopName productLink offerLink"
        "}"
        "pageInfo{page limit hasNextPage}"
        "}"
        "}"
    )
    dados = executar_graphql(query)
    return dados["productOfferV2"]


def listar_ids_de_ofertas(pagina: int, limite: int = 50, *, ordem: int | None = None, palavra: str = "",
                          categoria: int | None = None, loja: int | None = None) -> dict:
    """Uma página da productOfferV2 só com os itemId - para medir quantos produtos cada
    busca traz (ver ofertas/management/commands/explorar_limite_catalogo.py). Sem palavra-
    chave, categoria ou loja, é o mesmo feed geral (listType ALL) da sincronização."""
    argumentos = [f"page:{int(pagina)}", f"limit:{int(limite)}"]
    if palavra:
        argumentos.append(f"keyword:{json.dumps(palavra, ensure_ascii=False)}")
    elif categoria:
        argumentos.append(f"productCatId:{int(categoria)}")
    elif loja:
        argumentos.append(f"shopId:{int(loja)}")
    else:
        argumentos.append("listType:0")
    if ordem:
        argumentos.append(f"sortType:{int(ordem)}")
    query = f"query{{productOfferV2({','.join(argumentos)}){{nodes{{itemId}}pageInfo{{page limit hasNextPage}}}}}}"
    return executar_graphql(query)["productOfferV2"]


def buscar_oferta_por_item_id(item_id: int) -> dict | None:
    """Busca os dados de UM produto específico (mesmos campos de buscar_ofertas_produtos)
    - usado pra postar uma oferta escolhida na mão a partir de um link, fora da
    sincronização em lote (ver ofertas/services.py, buscar_oferta_por_link). None se a
    Shopee não retornar nenhum node pra esse item_id (ex: sem comissão de afiliado
    ativa no momento)."""
    query = (
        "query{"
        "productOfferV2("
        f"listType:0,itemId:{item_id},page:1,limit:1"
        "){"
        "nodes{"
        "itemId commissionRate sellerCommissionRate sales priceMax priceMin productCatIds ratingStar "
        "priceDiscountRate imageUrl productName shopName productLink offerLink"
        "}"
        "}"
        "}"
    )
    dados = executar_graphql(query)
    nodes = dados["productOfferV2"]["nodes"]
    return nodes[0] if nodes else None


def buscar_conversoes(purchase_time_start: int, purchase_time_end: int, scroll_id: str | None = None, limit: int = 500) -> dict:
    """Consulta a query conversionReport da Shopee para um período, com paginação por scrollId."""
    query = (
        "query{"
        "conversionReport("
        f"purchaseTimeStart:{purchase_time_start},"
        f"purchaseTimeEnd:{purchase_time_end},"
        f"limit:{limit},"
        f"scrollId:{json.dumps(scroll_id or '', ensure_ascii=False)}"
        "){"
        "nodes{"
        "conversionId purchaseTime utmContent "
        "orders{orderId orderStatus items{itemId completeTime itemTotalCommission actualAmount itemName imageUrl fraudReason}}"
        "}"
        "pageInfo{scrollId hasNextPage}"
        "}"
        "}"
    )
    dados = executar_graphql(query)
    return dados["conversionReport"]
