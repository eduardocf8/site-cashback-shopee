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
