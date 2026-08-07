import time
import uuid
from decimal import Decimal

import requests
from django.conf import settings

ESCOPO = "pagamento-pix.write pagamento-pix.read"

# Cache do token em memória do processo - o token dura 60 minutos e a doc do Inter
# pede pra reutilizar nas requisições em vez de gerar um novo a cada chamada.
_token_cache = {"token": "", "expira_em": 0.0}


class InterConfigError(Exception):
    """Credenciais ou certificado do Inter não configurados no .env."""


class InterAPIError(Exception):
    """Erro retornado pela API do Inter."""


def _certificado() -> tuple[str, str]:
    if not settings.INTER_CERT_PATH or not settings.INTER_KEY_PATH:
        raise InterConfigError(
            "Configure INTER_CERT_PATH e INTER_KEY_PATH com os certificados baixados no Internet Banking."
        )
    return (settings.INTER_CERT_PATH, settings.INTER_KEY_PATH)


def _obter_token() -> str:
    agora = time.time()
    if _token_cache["token"] and agora < _token_cache["expira_em"]:
        return _token_cache["token"]

    if not settings.INTER_CLIENT_ID or not settings.INTER_CLIENT_SECRET:
        raise InterConfigError("Configure INTER_CLIENT_ID e INTER_CLIENT_SECRET.")

    resposta = requests.post(
        f"{settings.INTER_API_URL}/oauth/v2/token",
        cert=_certificado(),
        data={
            "client_id": settings.INTER_CLIENT_ID,
            "client_secret": settings.INTER_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": ESCOPO,
        },
        timeout=30,
    )
    dados = resposta.json()
    if resposta.status_code >= 400:
        raise InterAPIError(dados.get("error_description") or dados.get("error") or f"HTTP {resposta.status_code}")

    _token_cache["token"] = dados["access_token"]
    # Renova 60s antes de expirar de verdade, de folga.
    _token_cache["expira_em"] = agora + dados.get("expires_in", 3600) - 60
    return _token_cache["token"]


def _headers() -> dict:
    headers = {
        "Authorization": f"Bearer {_obter_token()}",
        "Content-Type": "application/json",
        "x-id-idempotente": str(uuid.uuid4()),
    }
    if settings.INTER_CONTA_CORRENTE:
        headers["x-conta-corrente"] = settings.INTER_CONTA_CORRENTE
    return headers


def _tratar_resposta(resposta: requests.Response) -> dict:
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    if resposta.status_code >= 400:
        mensagem = corpo.get("detail") or corpo.get("title") or corpo.get("message") or f"HTTP {resposta.status_code}"
        raise InterAPIError(str(mensagem))
    return corpo


def criar_pagamento_pix(valor: Decimal, chave_pix: str, descricao: str) -> dict:
    """Cria um pagamento/transferência Pix (POST /banking/v2/pix) e retorna a resposta bruta.

    NOTA: o formato exato do campo "destinatario" pra pagamento via chave Pix não veio
    detalhado na documentação oficial - o formato abaixo foi inferido a partir do
    exemplo de callback do webhook (que mostra um campo "chave"). Validar contra o
    sandbox do Inter antes de usar em produção.
    """
    payload = {
        "valor": float(valor),
        "descricao": descricao[:140],
        "destinatario": {"tipo": "CHAVE", "chave": chave_pix},
    }
    resposta = requests.post(
        f"{settings.INTER_API_URL}/banking/v2/pix",
        headers=_headers(),
        json=payload,
        cert=_certificado(),
        timeout=30,
    )
    return _tratar_resposta(resposta)


def consultar_pagamento_pix(codigo_solicitacao: str) -> dict:
    """Consulta um pagamento Pix pelo código de solicitação (GET /banking/v2/pix/{codigoSolicitacao})."""
    resposta = requests.get(
        f"{settings.INTER_API_URL}/banking/v2/pix/{codigo_solicitacao}",
        headers=_headers(),
        cert=_certificado(),
        timeout=15,
    )
    return _tratar_resposta(resposta)
