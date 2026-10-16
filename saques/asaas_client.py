import json
from decimal import Decimal

import requests
from django.conf import settings


class AsaasAPIError(Exception):
    """Erro retornado pela API da Asaas."""


class AsaasConfigError(Exception):
    """A credencial da API Asaas não está configurada no .env."""


def _headers() -> dict:
    api_key = settings.ASAAS_API_KEY
    if not api_key:
        raise AsaasConfigError(
            "Configure ASAAS_API_KEY no arquivo .env com a chave de API da sua conta Asaas."
        )
    return {
        "Content-Type": "application/json",
        "access_token": api_key,
        "User-Agent": "CashbackShopee",
    }


def _tratar_resposta(resposta: requests.Response) -> dict:
    corpo = resposta.json()
    if resposta.status_code >= 400 or corpo.get("errors"):
        mensagens = "; ".join(
            erro.get("description", str(erro)) for erro in corpo.get("errors", [])
        ) or f"HTTP {resposta.status_code}"
        raise AsaasAPIError(mensagens)
    return corpo


def criar_transferencia_pix(valor: Decimal, chave_pix: str, tipo_chave_pix: str, descricao: str) -> dict:
    """Cria uma transferência Pix na Asaas (POST /transfers) e retorna a resposta bruta."""
    payload = {
        "value": float(valor),
        "pixAddressKey": chave_pix,
        "pixAddressKeyType": tipo_chave_pix,
        "description": descricao,
    }
    resposta = requests.post(
        f"{settings.ASAAS_API_URL}/transfers",
        headers=_headers(),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=30,
    )
    return _tratar_resposta(resposta)


def consultar_transferencia(transfer_id: str) -> dict:
    """Consulta o status atual de uma transferência (GET /transfers/{id})."""
    resposta = requests.get(
        f"{settings.ASAAS_API_URL}/transfers/{transfer_id}",
        headers=_headers(),
        timeout=15,
    )
    return _tratar_resposta(resposta)


class AsaasIndisponivelError(AsaasAPIError):
    """Falha que não diz nada sobre a chave em si - rede, Asaas fora do ar, limite de
    consultas (429) ou fichas esgotadas no Token Bucket. Quem chama deve tentar de
    novo depois, não recusar a chave."""


def consultar_chave_pix(tipo_chave_pix: str, chave_pix: str) -> dict:
    """Consulta o titular de uma chave Pix externa (GET /pix/addressKeys/external) -
    devolve {"owner": {"name", "cpfCnpj"}, ...}; o cpfCnpj vem mascarado
    ("***.202.745-**").

    Limites da Asaas (docs.asaas.com/docs/consultar-chave-pix): 5 consultas/minuto
    por conta e um Token Bucket de 300 fichas (PJ) que repõe 2/minuto - consulta
    válida gasta 1 ficha, chave inexistente gasta 15. Por isso o site limita as
    tentativas por usuário (accounts/verificacao_pix.py).

    AsaasAPIError = a Asaas respondeu que a chave não existe/é inválida (recusar);
    AsaasIndisponivelError = não deu pra saber agora (tentar de novo depois)."""
    try:
        resposta = requests.get(
            f"{settings.ASAAS_API_URL}/pix/addressKeys/external",
            headers=_headers(),
            params={"type": tipo_chave_pix, "key": chave_pix},
            timeout=8,
        )
    except requests.RequestException as erro:
        raise AsaasIndisponivelError(f"Falha de rede ao consultar a chave Pix: {erro}") from erro
    if resposta.status_code == 429 or resposta.status_code >= 500:
        raise AsaasIndisponivelError(f"Asaas indisponível para consulta de chave (HTTP {resposta.status_code}).")
    try:
        return _tratar_resposta(resposta)
    except ValueError as erro:  # corpo que não é JSON
        raise AsaasIndisponivelError(f"Resposta inesperada da Asaas (HTTP {resposta.status_code}).") from erro
