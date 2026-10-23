import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PROMPT = (
    "Você edita nomes de produtos de e-commerce para um site de cashback. Reescreva cada "
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


# Cada modelo tem a sua própria cota no plano gratuito. Quando um estoura (429), ele descansa
# um tempo e o próximo da lista assume; passado o descanso, o primeiro volta a ser usado.
DESCANSO_SEM_COTA_SEGUNDOS = 30 * 60
DESCANSO_MODELO_INEXISTENTE_SEGUNDOS = 6 * 3600
_descansa_ate: dict[str, float] = {}


def modelos() -> list[str]:
    """GEMINI_MODELS (separados por vírgula, em ordem de preferência); sem ela, só GEMINI_MODEL."""
    lista = [m.strip() for m in (getattr(settings, "GEMINI_MODELS", "") or "").split(",") if m.strip()]
    return lista or [settings.GEMINI_MODEL]


def _modelos_na_ordem() -> list[str]:
    agora = time.monotonic()
    todos = modelos()
    livres = [m for m in todos if _descansa_ate.get(m, 0) <= agora]
    return livres or todos  # todos descansando: tenta mesmo assim, na ordem de preferência


def _url(modelo: str) -> str:
    return f"{settings.GEMINI_API_URL}/models/{modelo}:generateContent"


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
    ultimo_erro = None
    for modelo in _modelos_na_ordem():
        resposta = requests.post(
            _url(modelo),
            headers={"x-goog-api-key": settings.GEMINI_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        dados = resposta.json()
        if resposta.status_code in (429, 404):
            descanso = DESCANSO_SEM_COTA_SEGUNDOS if resposta.status_code == 429 else DESCANSO_MODELO_INEXISTENTE_SEGUNDOS
            _descansa_ate[modelo] = time.monotonic() + descanso
            ultimo_erro = GeminiAPIError((dados.get("error") or {}).get("message", f"HTTP {resposta.status_code} em {modelo}"))
            logger.warning("[ofertas] %s sem resposta (HTTP %s), tentando o próximo modelo", modelo, resposta.status_code)
            continue
        break
    else:
        raise ultimo_erro
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
