"""Chamadas ao Instagram com o Login do Instagram para empresas (graph.instagram.com).

Endereços conferidos na documentação da Meta (out/2026): instagram-platform/instagram-api-with-instagram-login
(business-login, messaging-api) e instagram-platform/webhooks (setup, examples)."""

import json
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERSAO = "v26.0"
GRAPH = "https://graph.instagram.com"
AUTORIZAR = "https://www.instagram.com/oauth/authorize"
TROCAR_CODIGO = "https://api.instagram.com/oauth/access_token"
PERMISSOES = [
    "instagram_business_basic",
    "instagram_business_manage_comments",
    "instagram_business_manage_messages",
    "instagram_business_content_publish",
]
CAMPOS_WEBHOOK = "comments,messages"
TEMPO = 15  # segundos: o webhook responde a Meta depois destas chamadas


class ErroInstagram(Exception):
    """Mensagem do Instagram (ou da conexão), pronta para o log e para a tela."""


def app_id() -> str:
    return settings.APPFILIADO_INSTAGRAM_APP_ID


def app_secret() -> str:
    return settings.APPFILIADO_INSTAGRAM_APP_SECRET


def _resposta(r: requests.Response) -> dict:
    try:
        dados = r.json()
    except ValueError as erro:
        raise ErroInstagram(f"Resposta inválida do Instagram (HTTP {r.status_code}).") from erro
    if isinstance(dados, dict) and dados.get("error"):
        e = dados["error"]
        if isinstance(e, dict):
            raise ErroInstagram(f"{e.get('message', 'erro')} (código {e.get('code', '?')})")
        raise ErroInstagram(str(dados.get("error_message") or e))
    if r.status_code >= 400:
        raise ErroInstagram(f"HTTP {r.status_code}")
    return dados


def _chamar(metodo: str, caminho: str, token: str, params: dict | None = None, corpo: dict | None = None,
            tempo: int = TEMPO) -> dict:
    url = caminho if caminho.startswith("http") else f"{GRAPH}/{VERSAO}/{caminho}"
    try:
        r = requests.request(metodo, url, params=params, json=corpo, timeout=tempo,
                             headers={"Authorization": f"Bearer {token}"})
    except requests.RequestException as erro:
        raise ErroInstagram(f"Sem conexão com o Instagram: {erro.__class__.__name__}") from erro
    return _resposta(r)


# --- login ------------------------------------------------------------------------------------

def url_de_autorizacao(redirect_uri: str, state: str) -> str:
    return AUTORIZAR + "?" + urlencode({
        "client_id": app_id(), "redirect_uri": redirect_uri, "response_type": "code",
        "scope": ",".join(PERMISSOES), "state": state, "enable_fb_login": "0", "force_reauth": "true",
    })


def trocar_codigo(codigo: str, redirect_uri: str) -> dict:
    """Código da volta do login -> {access_token, user_id, permissions} (token curto, 1 hora)."""
    try:
        r = requests.post(TROCAR_CODIGO, timeout=TEMPO, data={
            "client_id": app_id(), "client_secret": app_secret(), "grant_type": "authorization_code",
            "redirect_uri": redirect_uri, "code": codigo})
    except requests.RequestException as erro:
        raise ErroInstagram("Sem conexão com o Instagram.") from erro
    dados = _resposta(r)
    if isinstance(dados.get("data"), list) and dados["data"]:  # formato atual: {"data": [{...}]}
        dados = dados["data"][0]
    if not dados.get("access_token"):
        raise ErroInstagram("O Instagram não devolveu o acesso.")
    return dados


def token_longo(token_curto: str) -> dict:
    """Token curto -> token de 60 dias. {access_token, expires_in}."""
    try:
        r = requests.get(f"{GRAPH}/access_token", timeout=TEMPO, params={
            "grant_type": "ig_exchange_token", "client_secret": app_secret(), "access_token": token_curto})
    except requests.RequestException as erro:
        raise ErroInstagram("Sem conexão com o Instagram.") from erro
    return _resposta(r)


def renovar_token(token: str) -> dict:
    """Mais 60 dias (o token precisa ter pelo menos 24 horas e estar válido)."""
    try:
        r = requests.get(f"{GRAPH}/refresh_access_token", timeout=TEMPO,
                         params={"grant_type": "ig_refresh_token", "access_token": token})
    except requests.RequestException as erro:
        raise ErroInstagram("Sem conexão com o Instagram.") from erro
    return _resposta(r)


def perfil(token: str) -> dict:
    """{id (o ID por app), user_id (o ID da conta profissional), username, name, profile_picture_url}."""
    return _chamar("GET", "me", token, params={"fields": "id,user_id,username,name,profile_picture_url"})


def ligar_avisos(token: str) -> None:
    """Liga os avisos (webhook) de comentários e mensagens para esta conta."""
    _chamar("POST", "me/subscribed_apps", token, params={"subscribed_fields": CAMPOS_WEBHOOK})


# --- posts e stories ---------------------------------------------------------------------------

def posts_recentes(token: str, limite: int = 45) -> list[dict]:
    dados = _chamar("GET", "me/media", token, params={
        "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp", "limit": limite})
    return dados.get("data", [])


def stories_no_ar(token: str) -> list[dict]:
    dados = _chamar("GET", "me/stories", token, params={"fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp"})
    return dados.get("data", [])


# --- respostas ---------------------------------------------------------------------------------

def responder_comentario(token: str, comentario_id: str, texto: str) -> str:
    return _chamar("POST", f"{comentario_id}/replies", token, params={"message": texto}).get("id", "")


def _corpo_da_mensagem(texto: str, botao: tuple[str, str] | None) -> dict:
    """Texto simples, ou o texto com um botão que abre o link (modelo de botão: até 640 caracteres)."""
    if not botao:
        return {"text": texto}
    titulo, url = botao
    return {"attachment": {"type": "template", "payload": {
        "template_type": "button", "text": texto[:640], "buttons": [{"type": "web_url", "url": url, "title": titulo[:20]}]}}}


def resposta_privada(token: str, ig_id: str, comentario_id: str, texto: str, botao: tuple[str, str] | None = None) -> str:
    """A DM ligada a um comentário: uma vez por comentário e até 7 dias depois dele."""
    corpo = {"recipient": {"comment_id": comentario_id}, "message": _corpo_da_mensagem(texto, botao)}
    return _chamar("POST", f"{ig_id}/messages", token, corpo=corpo).get("message_id", "")


def mensagem(token: str, ig_id: str, destinatario: str, texto: str, botao: tuple[str, str] | None = None) -> str:
    """DM para quem mandou mensagem ou respondeu um story (dentro da janela de 24 horas)."""
    corpo = {"recipient": {"id": destinatario}, "message": _corpo_da_mensagem(texto, botao)}
    return _chamar("POST", f"{ig_id}/messages", token, corpo=corpo).get("message_id", "")


# --- publicar (instagram_business_content_publish) ----------------------------------------------
# A Meta baixa cada imagem pelo endereço (JPEG, endereço público). Um "container" por imagem; no
# carrossel, um container a mais juntando os filhos; no story, um container por story.

TEMPO_PUBLICAR = 60  # a Meta baixa a imagem antes de responder


def criar_container(token: str, ig_id: str, **campos) -> str:
    """campos: image_url, caption, media_type (CAROUSEL ou STORIES), is_carousel_item, children."""
    corpo = {k: v for k, v in campos.items() if v not in (None, "")}
    dados = _chamar("POST", f"{ig_id}/media", token, corpo=corpo, tempo=TEMPO_PUBLICAR)
    if not dados.get("id"):
        raise ErroInstagram("O Instagram não preparou a imagem.")
    return str(dados["id"])


def estado_container(token: str, container_id: str) -> str:
    """FINISHED, IN_PROGRESS, ERROR, EXPIRED ou PUBLISHED."""
    return str(_chamar("GET", container_id, token, params={"fields": "status_code"}).get("status_code") or "")


def publicar_container(token: str, ig_id: str, container_id: str) -> str:
    dados = _chamar("POST", f"{ig_id}/media_publish", token, corpo={"creation_id": container_id}, tempo=TEMPO_PUBLICAR)
    if not dados.get("id"):
        raise ErroInstagram("O Instagram não confirmou a publicação.")
    return str(dados["id"])


def link_da_midia(token: str, midia_id: str) -> str:
    return str(_chamar("GET", midia_id, token, params={"fields": "permalink"}).get("permalink") or "")


def corpo_json(dados) -> str:
    return json.dumps(dados, ensure_ascii=False)[:2000]
