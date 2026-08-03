import requests
from django.conf import settings

API_VERSAO = "v21.0"


class InstagramConfigError(Exception):
    """As credenciais do Instagram não estão configuradas no .env."""


class InstagramAPIError(Exception):
    """Erro retornado pela Instagram Graph API."""


def _url(caminho: str) -> str:
    return f"{settings.INSTAGRAM_GRAPH_API_URL}/{API_VERSAO}/{caminho}"


def _exigir_config():
    if not settings.INSTAGRAM_ACCESS_TOKEN or not settings.INSTAGRAM_BUSINESS_ACCOUNT_ID:
        raise InstagramConfigError(
            "INSTAGRAM_ACCESS_TOKEN e/ou INSTAGRAM_BUSINESS_ACCOUNT_ID não configurados."
        )


def _chamar(metodo: str, caminho: str, **params) -> dict:
    params["access_token"] = settings.INSTAGRAM_ACCESS_TOKEN
    resposta = requests.request(metodo, _url(caminho), params=params, timeout=30)
    dados = resposta.json()
    if "error" in dados:
        raise InstagramAPIError(dados["error"].get("message", str(dados["error"])))
    resposta.raise_for_status()
    return dados


def criar_container_midia(image_url: str, legenda: str = "", story: bool = False) -> str:
    """Cria o container de mídia (passo 1 de 2 pra publicar). Retorna o creation_id."""
    _exigir_config()
    params = {"image_url": image_url}
    if story:
        params["media_type"] = "STORIES"
    else:
        params["caption"] = legenda
    dados = _chamar("POST", f"{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media", **params)
    return dados["id"]


def publicar_container(creation_id: str) -> str:
    """Publica um container já criado (passo 2 de 2). Retorna o media_id publicado."""
    _exigir_config()
    dados = _chamar(
        "POST", f"{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish", creation_id=creation_id
    )
    return dados["id"]


def publicar_imagem(image_url: str, legenda: str = "", story: bool = False) -> str:
    """Fluxo completo: cria o container e publica. Retorna o media_id publicado."""
    creation_id = criar_container_midia(image_url, legenda=legenda, story=story)
    return publicar_container(creation_id)


def criar_item_carrossel(image_url: str) -> str:
    """Cria um item (uma imagem) de um carrossel - passo 1 de 3 pra publicar. Retorna o creation_id."""
    _exigir_config()
    dados = _chamar(
        "POST", f"{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        image_url=image_url, is_carousel_item="true",
    )
    return dados["id"]


def criar_container_carrossel(item_ids: list[str], legenda: str = "") -> str:
    """Cria o container "pai" do carrossel, agrupando os itens já criados - passo 2 de 3. Retorna o creation_id."""
    _exigir_config()
    dados = _chamar(
        "POST", f"{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        media_type="CAROUSEL", children=",".join(item_ids), caption=legenda,
    )
    return dados["id"]


def publicar_carrossel(image_urls: list[str], legenda: str = "") -> str:
    """Fluxo completo de carrossel: cria um container por imagem, agrupa num container "pai", e
    publica. Retorna o media_id publicado. Máximo de 10 imagens (limite da própria API)."""
    item_ids = [criar_item_carrossel(url) for url in image_urls]
    creation_id = criar_container_carrossel(item_ids, legenda=legenda)
    return publicar_container(creation_id)


def renovar_token_de_longa_duracao(token_atual: str) -> dict:
    """Renova o access token de longa duração antes que ele expire (dura 60 dias).

    Retorna {"access_token": ..., "expires_in": ...} (segundos até expirar de novo).
    """
    resposta = requests.get(
        f"{settings.INSTAGRAM_GRAPH_API_URL}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token_atual},
        timeout=15,
    )
    dados = resposta.json()
    if "error" in dados:
        raise InstagramAPIError(dados["error"].get("message", str(dados["error"])))
    resposta.raise_for_status()
    return dados
