import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.urls import reverse

from . import instagram_client
from .models import RegistroPublicacao, RespostaStoryEnviada

logger = logging.getLogger(__name__)

MENSAGEM_LINK_NAO_ENCONTRADO = (
    "Oi! Não consegui achar o link desse story agora (talvez ele já tenha saído do ar) - "
    "mas dá pra ver essa e outras ofertas com cashback direto em cash-b.com 🛍️💸"
)


def verificar_assinatura(corpo: bytes, assinatura_header: str | None) -> bool:
    """Confere o cabeçalho X-Hub-Signature-256 que a Meta manda em toda entrega de
    webhook, calculado com o INSTAGRAM_APP_SECRET - sem essa checagem, qualquer um que
    descobrisse a URL do webhook poderia forjar "resposta a story" e receber, de
    graça, o link de cashback sem ter respondido nada de verdade."""
    if not assinatura_header or not settings.INSTAGRAM_APP_SECRET:
        return False
    esperado = "sha256=" + hmac.new(
        settings.INSTAGRAM_APP_SECRET.encode(), corpo, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, assinatura_header)


def _extrair_eventos_de_mensagem(payload: dict) -> list[dict]:
    """Achata o payload do webhook numa lista de "eventos de mensagem" (cada um com
    sender/message). A Graph API entrega mensagem do Instagram tanto em
    `entry[].messaging[]` (formato herdado do Messenger) quanto em `entry[].changes[]`
    com field="messages" (formato "cru" que outros webhooks da Graph API usam) - sem
    ter testado contra tráfego real ainda pra saber qual essa conta recebe, aceita as
    duas (ver payload_bruto em RespostaStoryEnviada pra ajuste fino se nenhuma bater)."""
    eventos = []
    for entry in payload.get("entry", []):
        eventos.extend(entry.get("messaging", []) or [])
        for change in entry.get("changes", []) or []:
            if change.get("field") == "messages" and isinstance(change.get("value"), dict):
                eventos.append(change["value"])
    return eventos


def _link_absoluto(registro: RegistroPublicacao, request) -> str:
    return request.build_absolute_uri(reverse("instagram_story_ir", args=[registro.pk]))


def _processar_um_evento(evento: dict, request) -> None:
    mensagem = evento.get("message") or {}
    if mensagem.get("is_echo"):
        # Mensagem que a própria conta mandou (inclusive as DMs que essa automação
        # manda) também chega como evento - ignora, senão o bot reagiria à própria DM.
        return

    story = (mensagem.get("reply_to") or {}).get("story") or {}
    story_media_id = story.get("id", "")
    if not story_media_id:
        return  # não é resposta a story (DM comum, reação a mensagem, etc.) - fora do escopo daqui.

    sender_id = (evento.get("sender") or {}).get("id", "")
    resposta = RespostaStoryEnviada(
        instagram_story_media_id=story_media_id,
        sender_instagram_id=sender_id,
        texto_recebido=mensagem.get("text", ""),
        payload_bruto=json.dumps(evento, ensure_ascii=False),
    )

    registro = RegistroPublicacao.objects.filter(
        instagram_media_id=story_media_id,
        conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
    ).exclude(link_produto_original="").first()
    resposta.registro_publicacao = registro

    texto_dm = MENSAGEM_LINK_NAO_ENCONTRADO
    if registro:
        resposta.link_enviado = _link_absoluto(registro, request)
        texto_dm = f"Aqui está o link com o cashback garantido: {resposta.link_enviado}"

    if not sender_id:
        resposta.dm_erro = "Payload sem sender.id - não deu pra responder."
        resposta.save()
        return

    try:
        instagram_client.enviar_mensagem_direta(sender_id, texto_dm)
        resposta.dm_enviada = True
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao enviar DM de resposta a story pra %s", sender_id)
        resposta.dm_erro = str(erro)
    resposta.save()


def processar_evento_webhook(payload: dict, request) -> None:
    """Chamado pela view do webhook (ver views.py) a cada entrega da Meta. Por
    evento: se for resposta a um story de oferta nosso, manda por DM o link (com
    cashback rastreado) daquele produto específico - ver
    instagram_bot/views.py::ir_para_story_de_oferta. Sempre grava um
    RespostaStoryEnviada quando é resposta a story, ache o registro ou não."""
    for evento in _extrair_eventos_de_mensagem(payload):
        try:
            _processar_um_evento(evento, request)
        except Exception:
            logger.exception("[instagram_bot] falha ao processar evento do webhook: %s", evento)
