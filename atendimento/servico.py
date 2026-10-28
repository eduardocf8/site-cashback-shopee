"""Lado do worker do WhatsApp: guarda as mensagens privadas do número de vendas e responde com o
agente. O gerenciador do bot (bot_whatsapp/gerenciador.py) chama `deve_ouvir` na thread da
sessão, `registrar` quando a mensagem chega e `uma_volta` a cada volta do laço."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from . import agente, aprendizado, comandos
from .models import Conversa, Mensagem

logger = logging.getLogger(__name__)

# Espera a pessoa terminar de digitar (muita gente manda 3 mensagens seguidas) antes de responder.
ESPERA_ANTES_DE_RESPONDER = timedelta(seconds=7)
# Sem nenhuma mensagem sua por esse tempo, a conversa pausada volta pro agente.
VOLTA_PRO_AGENTE = timedelta(hours=12)
RESPOSTAS_POR_DIA = 60  # por conversa: corta abuso e loop com outro robô
HISTORICO = 40  # últimas mensagens que o agente lê
MAXIMO_DO_TEXTO = 2000
COMANDO_VOLTAR = "#ia"  # você digita na conversa, pelo celular, pra devolver ao agente
AVISO_SO_TEXTO = "Por aqui eu só consigo ler mensagens de texto 🙏 Pode me escrever a sua dúvida?"

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="atendimento")
_em_andamento: set = set()  # conversas sendo respondidas (pk) ou analisadas ("aprender", pk)
_enviando: set[tuple[str, str]] = set()  # (chat, texto) saindo agora: o eco não é mensagem sua
_trava = threading.Lock()


def ligado() -> bool:
    return bool(settings.ATENDIMENTO_CONTA_ID and settings.ANTHROPIC_API_KEY)


def deve_ouvir(conta_id: int, ev) -> bool:
    """Filtro rápido, na thread da sessão: só conversas privadas do número de vendas."""
    if not ligado() or conta_id != settings.ATENDIMENTO_CONTA_ID:
        return False
    fonte = ev.Info.MessageSource
    return not fonte.IsGroup and fonte.Chat.Server in ("s.whatsapp.net", "lid")


def _telefone(ev) -> str:
    fonte = ev.Info.MessageSource
    for jid in (fonte.Chat, fonte.Sender, fonte.SenderAlt, fonte.RecipientAlt):
        if jid.Server == "s.whatsapp.net" and jid.User:
            return jid.User
    return ""


def _citada(ev) -> str:
    """Id da mensagem que você respondeu com "Responder" (citação), ou ""."""
    try:
        from bot_whatsapp import copia

        mensagem = copia.desembrulhar(ev.Message)
        if mensagem.HasField("extendedTextMessage"):
            return str(getattr(mensagem.extendedTextMessage.contextInfo, "stanzaID", "") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def registrar(ev, texto: str, tem_midia: bool) -> None:
    """Guarda a mensagem que chegou (da pessoa ou sua, digitada no celular)."""
    fonte = ev.Info.MessageSource
    chat = f"{fonte.Chat.User}@{fonte.Chat.Server}"
    msg_id = ev.Info.ID
    if Mensagem.objects.filter(whatsapp_id=msg_id).exists():
        return  # o próprio agente mandou (ou a mensagem chegou duas vezes)
    conversa, _ = Conversa.objects.get_or_create(chat=chat)
    agora = timezone.now()
    if not fonte.IsFromMe and aprendizado.eh_o_dono(_telefone(ev)):
        # Você, do seu número pessoal, respondendo uma sugestão de resposta aprendida.
        confirmacao = aprendizado.tratar_resposta_do_dono(texto, _citada(ev))
        if confirmacao:
            Mensagem.objects.create(conversa=conversa, autor=Mensagem.AGENTE, texto=confirmacao, respondida=True)
            return
    if fonte.IsFromMe:
        with _trava:
            eco = (chat, texto) in _enviando
        if eco or Mensagem.objects.filter(conversa=conversa, autor=Mensagem.AGENTE, texto=texto,
                                          criada_em__gte=agora - timedelta(minutes=2)).exists():
            return
        if texto.strip().lower() == COMANDO_VOLTAR:
            conversa.estado, conversa.motivo_humano, conversa.humano_desde = Conversa.IA, "", None
            conversa.save()
            return
        if not texto:
            return
        Mensagem.objects.create(conversa=conversa, autor=Mensagem.VOCE, texto=texto[:MAXIMO_DO_TEXTO],
                                whatsapp_id=msg_id, respondida=True)
        # Você respondeu pelo celular: o agente sai da frente nesta conversa e não responde depois o
        # que você já respondeu.
        conversa.mensagens.filter(autor=Mensagem.CLIENTE, respondida=False).update(respondida=True)
        conversa.estado, conversa.humano_desde = Conversa.HUMANO, agora
        conversa.motivo_humano = conversa.motivo_humano or "Você respondeu pelo celular."
        conversa.save()
        return
    conversa.telefone = conversa.telefone or _telefone(ev)
    conversa.nome = (ev.Info.Pushname or conversa.nome)[:120]
    conversa.ultima_recebida_em = agora
    conversa.save()
    if texto:
        resposta = comandos.tratar(conversa, texto)
        if resposta is not None:
            # Comando do assinante (resultados, metas...): resposta fixa, sem passar pelo agente. Sai
            # na próxima volta, pelo mesmo caminho dos avisos prontos.
            Mensagem.objects.create(conversa=conversa, autor=Mensagem.CLIENTE, texto=texto[:MAXIMO_DO_TEXTO],
                                    whatsapp_id=msg_id, respondida=True)
            if resposta:
                Mensagem.objects.create(conversa=conversa, autor=Mensagem.AGENTE, texto=resposta, respondida=True)
            return
        # Com a conversa com você, a mensagem já nasce tratada: ao voltar (#ia ou depois de 12 h), o agente
        # responde só o que chegar dali pra frente, e não o que você já respondeu.
        Mensagem.objects.create(conversa=conversa, autor=Mensagem.CLIENTE, texto=texto[:MAXIMO_DO_TEXTO], whatsapp_id=msg_id,
                                respondida=conversa.estado == Conversa.HUMANO)
    elif tem_midia:
        # Áudio, foto sem legenda, figurinha: responde na hora, sem gastar a IA.
        Mensagem.objects.create(conversa=conversa, autor=Mensagem.CLIENTE, texto="[mídia sem texto]",
                                whatsapp_id=msg_id, respondida=True)
        if conversa.estado == Conversa.IA:
            Mensagem.objects.create(conversa=conversa, autor=Mensagem.AGENTE, texto=AVISO_SO_TEXTO, respondida=True)


def uma_volta(sessoes: dict) -> None:
    if not ligado():
        return
    sessao = sessoes.get(settings.ATENDIMENTO_CONTA_ID)
    if not sessao or not sessao.conectada:
        return
    agora = timezone.now()
    Conversa.objects.filter(estado=Conversa.HUMANO, humano_desde__lt=agora - VOLTA_PRO_AGENTE).exclude(
        mensagens__autor=Mensagem.VOCE, mensagens__criada_em__gte=agora - VOLTA_PRO_AGENTE,
    ).update(estado=Conversa.IA, motivo_humano="", humano_desde=None)
    _enviar_avisos_prontos(sessao)
    _enviar_sugestoes(sessao)
    for pk in aprendizado.conversas_prontas(agora):
        with _trava:
            if ("aprender", pk) in _em_andamento:
                continue
            _em_andamento.add(("aprender", pk))
        _executor.submit(_aprender, pk)
    pendentes = (Conversa.objects.filter(estado=Conversa.IA, mensagens__autor=Mensagem.CLIENTE, mensagens__respondida=False,
                                         ultima_recebida_em__lte=agora - ESPERA_ANTES_DE_RESPONDER)
                 .distinct().values_list("pk", flat=True)[:10])
    for pk in pendentes:
        with _trava:
            if pk in _em_andamento:
                continue
            _em_andamento.add(pk)
        _executor.submit(_atender, pk, sessao)


def _enviar_avisos_prontos(sessao) -> None:
    """Respostas fixas (ex: o aviso de 'só leio texto') que ainda não saíram."""
    for msg in Mensagem.objects.filter(autor=Mensagem.AGENTE, whatsapp_id="", criada_em__gte=timezone.now() - timedelta(hours=1)
                                       ).select_related("conversa")[:5]:
        msg.whatsapp_id = _enviar(sessao, msg.conversa.chat, msg.texto) or "falhou"
        msg.save(update_fields=["whatsapp_id"])


def _enviar_sugestoes(sessao) -> None:
    """Sugestões de resposta aprendida que ainda não foram pro seu WhatsApp."""
    for r in aprendizado.para_enviar():
        r.whatsapp_id = _enviar(sessao, f"{aprendizado._digitos(settings.ATENDIMENTO_AVISAR)}@s.whatsapp.net",
                                aprendizado.texto_da_sugestao(r))
        r.enviada_em = timezone.now()
        r.save(update_fields=["whatsapp_id", "enviada_em", "atualizada_em"])


def _aprender(pk: int) -> None:
    close_old_connections()
    try:
        aprendizado.analisar(pk)
    except Exception:  # noqa: BLE001 - sem sugestão desta vez; a conversa já ficou marcada
        logger.exception("Atendimento: falha ao montar a sugestão de resposta da conversa %s", pk)
    finally:
        with _trava:
            _em_andamento.discard(("aprender", pk))


def _atender(pk: int, sessao) -> None:
    close_old_connections()
    try:
        conversa = Conversa.objects.get(pk=pk)
        novas = list(conversa.mensagens.filter(autor=Mensagem.CLIENTE, respondida=False).values_list("pk", flat=True))
        Mensagem.objects.filter(pk__in=novas).update(respondida=True)
        if not novas or conversa.estado != Conversa.IA:
            return
        hoje = timezone.localdate()
        if conversa.dia_das_respostas != hoje:
            conversa.dia_das_respostas, conversa.respostas_no_dia = hoje, 0
        if conversa.respostas_no_dia >= RESPOSTAS_POR_DIA:
            _passar_pra_voce(sessao, conversa, {"motivo": "Passou do limite de respostas do agente no dia.", "resumo": ""})
            return
        _digitando(sessao, conversa.chat)
        try:
            resposta = agente.responder(historico(conversa), nome=conversa.nome)
        except Exception:  # noqa: BLE001 - sem a IA, a pessoa não fica sem resposta
            logger.exception("Atendimento: falha ao chamar o agente na conversa %s", pk)
            resposta = agente.Resposta(agente.RESPOSTA_DE_FALHA, {"motivo": "Falha ao chamar a IA.", "resumo": ""})
        enviado = _enviar(sessao, conversa.chat, resposta.texto)
        Mensagem.objects.create(conversa=conversa, autor=Mensagem.AGENTE, texto=resposta.texto,
                                whatsapp_id=enviado or "falhou", respondida=True)
        conversa.respostas_no_dia += 1
        conversa.save(update_fields=["dia_das_respostas", "respostas_no_dia", "atualizada_em"])
        if resposta.humano:
            _passar_pra_voce(sessao, conversa, resposta.humano)
    except Exception:  # noqa: BLE001 - a thread não pode morrer
        logger.exception("Atendimento: erro na conversa %s", pk)
    finally:
        with _trava:
            _em_andamento.discard(pk)


def historico(conversa) -> list[dict]:
    """A conversa no formato da API: a pessoa é "user"; o agente e você são "assistant"."""
    ultimas = list(conversa.mensagens.exclude(texto="[mídia sem texto]").order_by("-criada_em", "-id")[:HISTORICO])[::-1]
    saida: list[dict] = []
    for msg in ultimas:
        papel = "user" if msg.autor == Mensagem.CLIENTE else "assistant"
        if saida and saida[-1]["role"] == papel:
            saida[-1]["content"] += "\n\n" + msg.texto
        else:
            saida.append({"role": papel, "content": msg.texto})
    while saida and saida[0]["role"] != "user":
        saida.pop(0)
    return saida


def _passar_pra_voce(sessao, conversa, humano: dict) -> None:
    conversa.estado, conversa.humano_desde = Conversa.HUMANO, timezone.now()
    conversa.motivo_humano = humano.get("motivo", "")[:500]
    conversa.save(update_fields=["estado", "humano_desde", "motivo_humano", "atualizada_em"])
    if not settings.ATENDIMENTO_AVISAR:
        return
    quem = conversa.nome or "Alguém"
    contato = conversa.link_whatsapp or "(sem número visível; veja no WhatsApp do Appfiliado)"
    aviso = (f"🔔 *Atendimento Appfiliado*\n{quem} precisa de você: {conversa.motivo_humano}\n{contato}\n\n"
             + (f"Resumo: {humano['resumo']}\n\n" if humano.get("resumo") else "")
             + f"O agente pausou nessa conversa. Para devolver, mande {COMANDO_VOLTAR} na conversa pelo celular.")
    _enviar(sessao, f"{settings.ATENDIMENTO_AVISAR}@s.whatsapp.net", aviso)


def _jid(texto: str):
    from neonize.utils.jid import build_jid

    usuario, _, servidor = texto.partition("@")
    return build_jid(usuario, servidor)


def _digitando(sessao, chat: str) -> None:
    try:
        from neonize.utils.enum import ChatPresence, ChatPresenceMedia

        sessao.cliente.send_chat_presence(_jid(chat), ChatPresence.CHAT_PRESENCE_COMPOSING,
                                          ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
    except Exception:  # noqa: BLE001 - "digitando..." é só enfeite
        pass


def _enviar(sessao, chat: str, texto: str) -> str:
    """Manda e devolve o id da mensagem (pra não tratar como mensagem sua quando ela voltar)."""
    with _trava:
        _enviando.add((chat, texto))
    try:
        resposta = sessao.cliente.send_message(_jid(chat), texto)
        return resposta.ID or "enviada"
    except Exception:  # noqa: BLE001
        logger.exception("Atendimento: não consegui enviar a mensagem pra %s", chat)
        return ""
    finally:
        threading.Timer(30, lambda: _enviando.discard((chat, texto))).start()
