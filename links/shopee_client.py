import hashlib
import json
import time

import requests
from django.conf import settings


class ShopeeAPIError(Exception):
    """Erro retornado pela API de afiliados da Shopee (bloco 'errors' da resposta GraphQL)."""


class ShopeeConfigError(Exception):
    """As credenciais da API Shopee não estão configuradas no .env."""


def _assinar(app_id: str, secret: str, timestamp: int, payload: str) -> str:
    base = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def executar_graphql(query: str, variables: dict | None = None) -> dict:
    """Envia uma query/mutation para a API de afiliados Shopee e retorna o campo 'data'."""
    app_id = settings.SHOPEE_AFFILIATE_APP_ID
    secret = settings.SHOPEE_AFFILIATE_SECRET

    if not app_id or not secret:
        raise ShopeeConfigError(
            "Configure SHOPEE_AFFILIATE_APP_ID e SHOPEE_AFFILIATE_SECRET no arquivo .env "
            "com as credenciais da sua conta de afiliado Shopee."
        )

    corpo = {"query": query, "variables": variables or {}}
    payload = json.dumps(corpo, separators=(",", ":"))
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
    query = """
        mutation gerarLink($input: ShortLinkInput!) {
            generateShortLink(input: $input) {
                shortLink
            }
        }
    """
    dados = executar_graphql(query, {"input": {"originUrl": origin_url, "subIds": sub_ids}})
    return dados["generateShortLink"]["shortLink"]
