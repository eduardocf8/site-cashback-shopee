import hashlib
import logging
import time
import uuid

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_VERSAO = "v21.0"
TIMEOUT_SEGUNDOS = 5


def gerar_event_id() -> str:
    """ID compartilhado entre o evento mandado pelo Pixel (navegador, ver
    templates/_meta_pixel.html) e pela Conversions API (servidor) do MESMO
    acontecimento - é assim que a Meta deduplica os dois lados de um evento que
    dispara nos dois canais, em vez de contar a mesma conversão 2x."""
    return uuid.uuid4().hex


def _hash(valor: str) -> str:
    """SHA-256 do dado pessoal em minúsculo e sem espaço nas pontas - formato exigido
    pela Meta pra campos de user_data (ex: "em"). Nunca manda e-mail em texto puro."""
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()


def _dados_do_usuario(request) -> dict:
    """Monta o user_data a partir da requisição - quanto mais campos, melhor o "match
    quality" que a Meta consegue entre esse evento e uma conta de anúncio real. fbp/fbc
    só existem se o Pixel já rodou nesse navegador antes (cookies que ele mesmo grava)."""
    dados = {
        "client_ip_address": request.META.get("REMOTE_ADDR", ""),
        "client_user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }
    fbp = request.COOKIES.get("_fbp")
    if fbp:
        dados["fbp"] = fbp
    fbc = request.COOKIES.get("_fbc")
    if fbc:
        dados["fbc"] = fbc
    if request.user.is_authenticated and request.user.email:
        dados["em"] = [_hash(request.user.email)]
    return dados


def enviar_evento(nome_evento: str, request, event_id: str, dados_customizados: dict | None = None) -> None:
    """Manda 1 evento de conversão pra Meta via Conversions API (server-side) - não
    depende do navegador rodar o Pixel nem de cookie de terceiro sobreviver (iOS
    14.5+/Safari ITP/ad blocker derrubam boa parte do rastreamento só-navegador, ver
    ROADMAP.md).

    Silencioso de propósito: sem META_PIXEL_ID/META_CAPI_ACCESS_TOKEN configurados,
    não faz nada (recurso desligado, mesmo padrão de GEMINI_API_KEY e das credenciais
    Shopee); e qualquer erro de rede ou resposta da Meta só vira um log de aviso, nunca
    uma exceção - rastreamento de anúncio não pode derrubar uma ação real do usuário
    (cadastro, gerar link de cashback) se a Meta estiver fora do ar ou lenta. Timeout
    curto (5s) pelo mesmo motivo - isso roda no meio do fluxo normal da pessoa, não faz
    sentido ela esperar muito por uma chamada que nem aparece pra ela."""
    if not settings.META_PIXEL_ID or not settings.META_CAPI_ACCESS_TOKEN:
        return

    payload = {
        "data": [
            {
                "event_name": nome_evento,
                "event_time": int(time.time()),
                "event_id": event_id,
                "action_source": "website",
                "event_source_url": request.build_absolute_uri(),
                "user_data": _dados_do_usuario(request),
                **({"custom_data": dados_customizados} if dados_customizados else {}),
            }
        ],
    }
    # Só preenchido durante o teste no Gerenciador de Eventos da Meta (aba "Testar
    # eventos") - etiqueta os eventos como teste, sem misturar com dado real de
    # campanha. Tirar a variável de ambiente depois de confirmar que está tudo certo.
    if settings.META_CAPI_TEST_EVENT_CODE:
        payload["test_event_code"] = settings.META_CAPI_TEST_EVENT_CODE

    try:
        resposta = requests.post(
            f"https://graph.facebook.com/{API_VERSAO}/{settings.META_PIXEL_ID}/events",
            params={"access_token": settings.META_CAPI_ACCESS_TOKEN},
            json=payload,
            timeout=TIMEOUT_SEGUNDOS,
        )
        dados = resposta.json()
        if "error" in dados:
            logger.warning("[meta_capi] erro ao mandar evento %s: %s", nome_evento, dados["error"])
    except (requests.RequestException, ValueError) as erro:
        logger.warning("[meta_capi] falha ao mandar evento %s: %s", nome_evento, erro)
