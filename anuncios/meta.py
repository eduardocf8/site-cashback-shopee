"""Chamadas à API de Marketing da Meta (só leitura, permissão ads_read) e ao Login do Facebook para
Empresas. Endereços conferidos na documentação da Meta (out/2026): marketing-api (insights,
authorization) e facebook-login-for-business."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import requests
from django.conf import settings

VERSAO = "v26.0"
GRAPH = f"https://graph.facebook.com/{VERSAO}"
DIALOGO = f"https://www.facebook.com/{VERSAO}/dialog/oauth"
TEMPO = 30
TOKEN_INVALIDO = 190  # código da Meta: acesso expirado ou retirado


class ErroMeta(Exception):
    def __init__(self, mensagem: str, codigo: int | None = None):
        super().__init__(mensagem)
        self.codigo = codigo


def app_id() -> str:
    return settings.APPFILIADO_META_ADS_APP_ID


def app_secret() -> str:
    return settings.APPFILIADO_META_ADS_APP_SECRET


def configurado() -> bool:
    return bool(app_id() and app_secret() and settings.APPFILIADO_META_ADS_CONFIG_ID)


def _prova(token: str) -> str:
    """appsecret_proof: a Meta confere que a chamada veio do servidor do app."""
    return hmac.new(app_secret().encode(), token.encode(), hashlib.sha256).hexdigest()


def _resposta(r: requests.Response) -> dict:
    try:
        dados = r.json()
    except ValueError as erro:
        raise ErroMeta(f"Resposta inválida da Meta (HTTP {r.status_code}).") from erro
    if isinstance(dados, dict) and dados.get("error"):
        e = dados["error"] if isinstance(dados["error"], dict) else {"message": str(dados["error"])}
        raise ErroMeta(f"{e.get('message', 'erro')} (código {e.get('code', '?')})", e.get("code"))
    if r.status_code >= 400:
        raise ErroMeta(f"HTTP {r.status_code}")
    return dados


def _get(caminho: str, token: str | None = None, params: dict | None = None) -> dict:
    url = caminho if caminho.startswith("http") else f"{GRAPH}/{caminho}"
    params = dict(params or {})
    if token and not caminho.startswith("http"):
        params.update(access_token=token, appsecret_proof=_prova(token))
    try:
        return _resposta(requests.get(url, params=params, timeout=TEMPO))
    except requests.RequestException as erro:
        raise ErroMeta(f"Sem conexão com a Meta: {erro.__class__.__name__}") from erro


def _todas_as_paginas(caminho: str, token: str, params: dict, limite_paginas: int = 20) -> list[dict]:
    dados, itens = _get(caminho, token, params), []
    for _ in range(limite_paginas):
        itens += dados.get("data") or []
        proxima = (dados.get("paging") or {}).get("next")
        if not proxima:
            break
        dados = _get(proxima)  # o "next" já traz o token e a prova
    return itens


# --- login -------------------------------------------------------------------------------------

def url_de_login(redirect_uri: str, state: str) -> str:
    return DIALOGO + "?" + urlencode({
        "client_id": app_id(), "redirect_uri": redirect_uri, "state": state, "response_type": "code",
        "config_id": settings.APPFILIADO_META_ADS_CONFIG_ID, "override_default_response_type": "true",
    })


def trocar_codigo(codigo: str, redirect_uri: str) -> dict:
    """Código da volta do login -> {access_token, expires_in}."""
    return _get("oauth/access_token", params={
        "client_id": app_id(), "client_secret": app_secret(), "redirect_uri": redirect_uri, "code": codigo})


def token_longo(token: str) -> dict:
    """Token curto -> token de 60 dias. {access_token, expires_in}."""
    return _get("oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id(), "client_secret": app_secret(), "fb_exchange_token": token})


def eu(token: str) -> dict:
    return _get("me", token, {"fields": "id,name"})


# --- anúncios (ads_read) -------------------------------------------------------------------------

def contas_de_anuncios(token: str) -> list[dict]:
    """[{account_id, name, currency, account_status}] das contas que a pessoa liberou."""
    return _todas_as_paginas("me/adaccounts", token, {"fields": "account_id,name,currency,account_status", "limit": 200})


def campanhas(token: str, account_id: str) -> list[dict]:
    return _todas_as_paginas(f"act_{account_id}/campaigns", token,
                             {"fields": "id,name,effective_status,created_time", "limit": 500})


def gastos_por_dia(token: str, account_id: str, desde, ate) -> list[dict]:
    """Uma linha por campanha e por dia: campaign_id, campaign_name, date_start, spend, impressions,
    inline_link_clicks (Insights, nível de campanha)."""
    return _todas_as_paginas(f"act_{account_id}/insights", token, {
        "level": "campaign", "time_increment": 1, "limit": 500,
        "fields": "campaign_id,campaign_name,spend,impressions,inline_link_clicks",
        "time_range": json.dumps({"since": desde.isoformat(), "until": ate.isoformat()}),
    })
