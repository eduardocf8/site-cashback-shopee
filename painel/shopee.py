"""Conversa com a API de afiliados da Shopee usando as credenciais DA CONTA
(não as da cash-b)."""

import requests

from links.shopee_client import ShopeeAPIError, executar_graphql_com_credenciais

CONSULTA_TESTE = "query{productOfferV2(limit:1){nodes{itemId}}}"


def testar_credenciais(app_id: str, secret: str) -> tuple[bool, str]:
    """(funcionou, mensagem para mostrar)."""
    if not app_id or not secret:
        return False, "Preencha o AppID e o Secret."
    try:
        executar_graphql_com_credenciais(app_id, secret, CONSULTA_TESTE)
    except ShopeeAPIError as erro:
        texto = str(erro).lower()
        if any(p in texto for p in ("credential", "signature", "auth", "app_id", "appid")):
            return False, "A Shopee não aceitou esse AppID e Secret. Confira se copiou certinho."
        return False, f"A Shopee respondeu com um erro: {erro}"
    except requests.RequestException:
        return False, "Não consegui falar com a Shopee agora. Tente de novo em alguns minutos."
    return True, "Conexão com a Shopee funcionando."


# --- Relatório de conversões (resultados) ------------------------------------------

import json  # noqa: E402
import re  # noqa: E402

# Campos pedidos ao conversionReport. Os de comissão no nível da conversão
# (netCommission/totalCommission) são a comissão ESTIMADA; se a API de alguma conta
# não tiver um deles, ele é tirado e a consulta tenta de novo (mesma tolerância do
# app do Appfiliado, afiliados.executar_relatorio_com_campos).
CAMPOS_CONVERSOES = [
    "conversionId",
    "purchaseTime",
    "utmContent",
    "netCommission",
    "totalCommission",
    "orders{orderId orderStatus items{itemPrice qty itemTotalCommission completeTime}}",
]
MAXIMO_PAGINAS = 50


def _campo_invalido(mensagem: str) -> str:
    achado = re.search(r'Cannot query field "([^"]+)"', mensagem)
    return achado.group(1) if achado else ""


def _consultar_pagina(app_id, secret, inicio_ts, fim_ts, scroll_id, campos):
    campos_atuais = list(campos)
    while True:
        parametros = (
            f"purchaseTimeStart:{inicio_ts},purchaseTimeEnd:{fim_ts},limit:500,"
            f"scrollId:{json.dumps(scroll_id, ensure_ascii=False)}"
        )
        query = (
            f"query{{conversionReport({parametros}){{nodes{{{' '.join(campos_atuais)}}}"
            "pageInfo{scrollId hasNextPage}}}"
        )
        try:
            return executar_graphql_com_credenciais(app_id, secret, query), campos_atuais
        except ShopeeAPIError as erro:
            invalido = _campo_invalido(str(erro))
            if not invalido or invalido not in campos_atuais:
                raise
            campos_atuais.remove(invalido)


def buscar_conversoes(app_id: str, secret: str, inicio_ts: int, fim_ts: int) -> list[dict]:
    """Todas as conversões com data de compra entre inicio_ts e fim_ts (paginando)."""
    todas = []
    scroll_id = ""
    vistos = set()
    campos = CAMPOS_CONVERSOES
    for _ in range(MAXIMO_PAGINAS):
        if scroll_id in vistos:
            break
        vistos.add(scroll_id)
        dados, campos = _consultar_pagina(app_id, secret, inicio_ts, fim_ts, scroll_id, campos)
        relatorio = dados.get("conversionReport") or {}
        nodes = relatorio.get("nodes") or []
        if isinstance(nodes, list):
            todas.extend(nodes)
        pagina = relatorio.get("pageInfo") or {}
        proximo = str(pagina.get("scrollId") or "").strip()
        if not pagina.get("hasNextPage") or not proximo:
            break
        scroll_id = proximo
    return todas
