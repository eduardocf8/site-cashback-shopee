"""Login com Google via OAuth 2.0 / OpenID Connect (ROADMAP 13.15), sem biblioteca
extra: redireciona pro Google, troca o código pelo token e lê o perfil (nome, e-mail
verificado e o "sub", identificador estável da conta Google)."""
from urllib.parse import urlencode

import requests
from django.conf import settings

URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_PERFIL = "https://openidconnect.googleapis.com/v1/userinfo"
TIMEOUT_SEGUNDOS = 10


class GoogleOAuthError(Exception):
    pass


def configurado() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def url_autorizacao(redirect_uri: str, state: str) -> str:
    parametros = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{URL_AUTORIZACAO}?{urlencode(parametros)}"


def obter_perfil(code: str, redirect_uri: str) -> dict:
    """Troca o código de autorização pelo access token e devolve o perfil:
    {"sub", "email", "email_verified", "name", ...}."""
    try:
        resposta_token = requests.post(
            URL_TOKEN,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        token = resposta_token.json()
        if resposta_token.status_code >= 400 or "access_token" not in token:
            raise GoogleOAuthError(f"Google recusou o código: {token.get('error', resposta_token.status_code)}")
        resposta_perfil = requests.get(
            URL_PERFIL,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=TIMEOUT_SEGUNDOS,
        )
        perfil = resposta_perfil.json()
    except (requests.RequestException, ValueError) as erro:
        raise GoogleOAuthError(f"Falha ao falar com o Google: {erro}") from erro
    if resposta_perfil.status_code >= 400 or not perfil.get("sub") or not perfil.get("email"):
        raise GoogleOAuthError(f"Perfil do Google incompleto (HTTP {resposta_perfil.status_code}).")
    return perfil
