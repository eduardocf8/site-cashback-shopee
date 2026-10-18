"""Conversa com a API de afiliados da Shopee usando as credenciais DA CONTA
(não as da cash-b)."""

import requests

from links.shopee_client import ShopeeAPIError, executar_graphql_com_credenciais

CONSULTA_TESTE = "query{productOfferV2(limit:1){nodes{itemId}}}"


def testar_credenciais(app_id: str, secret: str) -> tuple[bool, str]:
    """(funcionou, mensagem pra mostrar)."""
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
