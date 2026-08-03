import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PROMPT = (
    "Você edita nomes de produtos de e-commerce pra um site de cashback. Reescreva cada "
    "nome abaixo de forma mais enxuta (até uns 60 caracteres), removendo repetição de "
    "palavra-chave, emoji e informação irrelevante (frete, brinde, variações de cor/tamanho "
    "listadas à toa), mas mantendo o essencial: o que é o produto, marca (se houver) e a "
    "característica principal. Responda em português. Devolva um array JSON de strings, na "
    "mesma ordem e na mesma quantidade dos nomes abaixo - não pule nenhum, não junte dois "
    "nomes num só, não adicione nenhum a mais.\n\n"
)


class GeminiConfigError(Exception):
    """GEMINI_API_KEY não configurada no .env."""


class GeminiAPIError(Exception):
    """Erro retornado pela API do Gemini, ou resposta em formato inesperado."""


def _url() -> str:
    return f"{settings.GEMINI_API_URL}/models/{settings.GEMINI_MODEL}:generateContent"


def encurtar_nomes(nomes: list[str]) -> list[str]:
    """Manda até ~50 nomes de produto por vez pro Gemini encurtar, num lote só (mais barato
    e rápido que uma chamada por produto). Retorna a lista encurtada, na mesma ordem.

    Levanta GeminiConfigError/GeminiAPIError se algo falhar - quem chama decide o fallback
    (normalmente: manter o nome original pros itens desse lote)."""
    if not settings.GEMINI_API_KEY:
        raise GeminiConfigError("Configure GEMINI_API_KEY no .env.")
    if not nomes:
        return []

    texto_lista = "\n".join(f"{i + 1}. {nome}" for i, nome in enumerate(nomes))
    payload = {
        "contents": [{"parts": [{"text": PROMPT + texto_lista}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {"type": "array", "items": {"type": "string"}},
        },
    }
    resposta = requests.post(
        _url(),
        headers={"x-goog-api-key": settings.GEMINI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    dados = resposta.json()
    if "error" in dados:
        raise GeminiAPIError(dados["error"].get("message", str(dados["error"])))
    resposta.raise_for_status()

    try:
        texto_resposta = dados["candidates"][0]["content"]["parts"][0]["text"]
        nomes_curtos = json.loads(texto_resposta)
    except (KeyError, IndexError, json.JSONDecodeError) as erro:
        raise GeminiAPIError(f"Resposta em formato inesperado do Gemini: {erro}")

    if len(nomes_curtos) != len(nomes):
        raise GeminiAPIError(
            f"Gemini devolveu {len(nomes_curtos)} nomes, mas o lote tinha {len(nomes)} - descartando o lote."
        )
    return [str(nome).strip() for nome in nomes_curtos]
