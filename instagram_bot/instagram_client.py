import json
import time

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
        erro = dados["error"]
        mensagem = erro.get("message", str(erro))
        # code/error_subcode/fbtrace_id ajudam a identificar a causa exata (a mensagem
        # sozinha costuma ser genérica demais, ex: "Only photo or video can be
        # accepted as media type" cobre várias causas bem diferentes entre si).
        detalhes = ", ".join(
            f"{chave}={erro[chave]}" for chave in ("code", "error_subcode", "type", "fbtrace_id") if chave in erro
        )
        raise InstagramAPIError(f"{mensagem} [{detalhes}]" if detalhes else mensagem)
    resposta.raise_for_status()
    return dados


def _aguardar_processamento(creation_id: str, tentativas: int = 10, intervalo: float = 2.0) -> None:
    """Espera o container terminar de processar (baixar/validar a imagem do lado da
    Meta) antes de publicar. Sem isso, publicar_container logo em seguida à criação às
    vezes devolve "Media ID is not available" [code=9007, error_subcode=2207027] -
    a Meta documenta esse erro como "a mídia ainda não está pronta pra publicar,
    aguarde um momento" (ver marketing/instagram/README.md, troubleshooting)."""
    for _ in range(tentativas):
        dados = _chamar("GET", creation_id, fields="status_code")
        status = dados.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise InstagramAPIError(f"Processamento do container {creation_id} falhou (status_code=ERROR).")
        time.sleep(intervalo)
    raise InstagramAPIError(
        f"Container {creation_id} não terminou de processar a tempo (status_code ainda não é FINISHED)."
    )


def verificar_configuracao() -> None:
    """Confere se o INSTAGRAM_BUSINESS_ACCOUNT_ID configurado bate com o ID de
    verdade associado ao INSTAGRAM_ACCESS_TOKEN antes de publicar. Sem essa checagem,
    um ID errado gera um erro genérico da própria API ("Only photo or video can be
    accepted", ou "code=2, type=OAuthException") que não aponta a causa raiz - já
    aconteceu 2x (ver marketing/instagram/README.md, troubleshooting)."""
    _exigir_config()
    dados = _chamar("GET", "me", fields="id")
    id_do_token = dados["id"]
    if id_do_token != settings.INSTAGRAM_BUSINESS_ACCOUNT_ID:
        raise InstagramConfigError(
            f"INSTAGRAM_BUSINESS_ACCOUNT_ID configurado ({settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}) "
            f"não bate com o ID associado ao INSTAGRAM_ACCESS_TOKEN ({id_do_token}) - "
            "corrija a variável de ambiente no Render."
        )


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
    verificar_configuracao()
    creation_id = criar_container_midia(image_url, legenda=legenda, story=story)
    _aguardar_processamento(creation_id)
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
    verificar_configuracao()
    item_ids = [criar_item_carrossel(url) for url in image_urls]
    for item_id in item_ids:
        _aguardar_processamento(item_id)
    creation_id = criar_container_carrossel(item_ids, legenda=legenda)
    _aguardar_processamento(creation_id)
    return publicar_container(creation_id)


def enviar_mensagem_direta(recipient_id: str, texto: str) -> str:
    """Manda uma DM pra um usuário (identificado pelo IGSID, o "sender.id" que chega
    no webhook de mensagens) - usado pra responder quem respondeu um story de oferta
    com o link do produto (ver webhook.py). Diferente de
    automacao_instagram/instagram_api.py::enviar_resposta_privada, que manda a
    "resposta privada" atrelada a um comment_id: aqui é uma DM avulsa, no recipient.id
    (sem essa restrição de 7 dias/1 vez que a resposta a comentário tem). Retorna o
    id da mensagem criada."""
    _exigir_config()
    dados = _chamar(
        "POST", f"{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages",
        recipient=json.dumps({"id": recipient_id}),
        message=json.dumps({"text": texto}),
    )
    return dados.get("message_id", dados.get("id", ""))


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
