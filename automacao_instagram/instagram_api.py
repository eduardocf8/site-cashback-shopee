import json

import requests
from django.conf import settings

API_VERSAO = "v21.0"


class InstagramAPIError(Exception):
    """Erro retornado pela Instagram Graph API."""


def _url(caminho: str) -> str:
    return f"{settings.INSTAGRAM_GRAPH_API_URL}/{API_VERSAO}/{caminho}"


def _chamar(metodo: str, caminho: str, access_token: str, **params) -> dict:
    params["access_token"] = access_token
    resposta = requests.request(metodo, _url(caminho), params=params, timeout=30)
    dados = resposta.json()
    if "error" in dados:
        erro = dados["error"]
        mensagem = erro.get("message", str(erro))
        detalhes = ", ".join(
            f"{chave}={erro[chave]}" for chave in ("code", "error_subcode", "type", "fbtrace_id") if chave in erro
        )
        raise InstagramAPIError(f"{mensagem} [{detalhes}]" if detalhes else mensagem)
    resposta.raise_for_status()
    return dados


def listar_midias_recentes(instagram_business_account_id: str, access_token: str, limite: int = 25) -> list[dict]:
    """Últimos posts da conta, pra escolher qual receberá a automação (sem precisar
    digitar o ID do post na mão). Retorna [{id, caption, permalink, timestamp}, ...]."""
    dados = _chamar(
        "GET", f"{instagram_business_account_id}/media", access_token,
        fields="id,caption,permalink,timestamp", limit=limite,
    )
    return dados.get("data", [])


def listar_comentarios(media_id: str, access_token: str) -> list[dict]:
    """Comentários de nível 1 (não conta resposta de resposta) do post. Retorna
    [{id, text, username, timestamp, from: {id, username}}, ...]."""
    dados = _chamar(
        "GET", f"{media_id}/comments", access_token,
        fields="id,text,username,timestamp,from",
    )
    return dados.get("data", [])


def responder_comentario(comment_id: str, texto: str, access_token: str) -> str:
    """Responde publicamente um comentário (fica visível pra qualquer um, como
    resposta do post). Retorna o id da resposta criada."""
    dados = _chamar("POST", f"{comment_id}/replies", access_token, message=texto)
    return dados["id"]


def enviar_resposta_privada(instagram_business_account_id: str, comment_id: str, texto: str, access_token: str) -> str:
    """Manda a "resposta privada" (DM) associada a um comentário - só funciona até 7
    dias após o comentário e uma vez por comentário (regra da própria API)."""
    dados = _chamar(
        "POST", f"{instagram_business_account_id}/messages", access_token,
        recipient=json.dumps({"comment_id": comment_id}),
        message=json.dumps({"text": texto}),
    )
    return dados.get("message_id", "")


def listar_conversas(instagram_business_account_id: str, access_token: str) -> list[dict]:
    """Conversas recentes no direto da conta - usado só pra checar se alguém
    respondeu uma DM enviada pela automação (ver services.verificar_dms_respondidas)."""
    dados = _chamar(
        "GET", f"{instagram_business_account_id}/conversations", access_token,
        platform="instagram", fields="participants,messages{id,from,created_time}",
    )
    return dados.get("data", [])
