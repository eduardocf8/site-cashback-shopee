"""O agente aprende com as suas respostas, com a sua aprovação.

1. Quando você responde uma conversa e ela fica ESPERA_DEPOIS_DA_SUA_RESPOSTA sem mensagem nova, a IA relê o
   trecho e escreve uma pergunta e uma resposta genéricas (ou nada, se era um caso pessoal).
2. A sugestão vai pro seu WhatsApp (ATENDIMENTO_AVISAR). Você responde 1 (aprovar), 2 (descartar) ou, usando
   "Responder" na mensagem da sugestão, escreve a resposta do jeito certo, que entra no lugar.
3. Também dá pra aprovar, editar, descartar ou criar no admin (Agente de vendas > Respostas aprendidas).
As aprovadas entram no que o agente sabe (agente.respostas_aprovadas)."""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from .models import Conversa, Mensagem, RespostaAprendida

logger = logging.getLogger(__name__)

ESPERA_DEPOIS_DA_SUA_RESPOSTA = timedelta(minutes=30)
TRECHO = 30  # últimas mensagens da conversa que a IA relê
VALIDADE_DO_1_E_2 = timedelta(hours=48)  # "1"/"2" sem citar a mensagem valem pra última sugestão desse prazo
APROVAR, DESCARTAR = "1", "2"


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def eh_o_dono(telefone: str) -> bool:
    return bool(settings.ATENDIMENTO_AVISAR) and _digitos(telefone) == _digitos(settings.ATENDIMENTO_AVISAR)


def conversas_prontas(agora=None) -> list[int]:
    """Conversas com resposta sua ainda não analisada e paradas há pelo menos 30 minutos."""
    agora = agora or timezone.now()
    limite = agora - ESPERA_DEPOIS_DA_SUA_RESPOSTA
    candidatas = Conversa.objects.filter(mensagens__autor=Mensagem.VOCE,
                                         mensagens__criada_em__gte=agora - timedelta(days=7)).distinct()
    prontas = []
    for conversa in candidatas:
        if eh_o_dono(conversa.telefone):
            continue
        ultima = conversa.mensagens.aggregate(m=Max("criada_em"))["m"]
        sua = conversa.mensagens.filter(autor=Mensagem.VOCE).aggregate(m=Max("criada_em"))["m"]
        if ultima and ultima <= limite and sua and (not conversa.aprendizado_em or sua > conversa.aprendizado_em):
            prontas.append(conversa.pk)
    return prontas


def trecho_da_conversa(conversa) -> str:
    nomes = {Mensagem.CLIENTE: "Cliente", Mensagem.AGENTE: "Assistente", Mensagem.VOCE: "Você (dono)"}
    ultimas = list(conversa.mensagens.exclude(texto="[mídia sem texto]").order_by("-criada_em", "-id")[:TRECHO])[::-1]
    return "\n".join(f"{nomes.get(m.autor, m.autor)}: {m.texto}" for m in ultimas)


def analisar(pk: int, agora=None, cliente=None) -> RespostaAprendida | None:
    """Pede a sugestão à IA (chamado numa thread do worker). Marca a conversa como analisada antes,
    pra não repetir mesmo se a IA falhar."""
    from . import agente

    agora = agora or timezone.now()
    marcou = Conversa.objects.filter(pk=pk).exclude(aprendizado_em__gte=agora).update(aprendizado_em=agora)
    if not marcou:
        return None
    conversa = Conversa.objects.get(pk=pk)
    conhecidas = "\n".join(f"- {r.pergunta}" for r in RespostaAprendida.objects.exclude(estado=RespostaAprendida.DESCARTADA))
    sugestao = agente.sugerir_aprendizado(trecho_da_conversa(conversa), conhecidas, cliente=cliente)
    if not sugestao:
        return None
    return RespostaAprendida.objects.create(conversa=conversa, **sugestao)


def texto_da_sugestao(r: RespostaAprendida) -> str:
    return ("💡 *Aprender esta resposta?*\n"
            f"*Pergunta:* {r.pergunta}\n*Resposta:* {r.resposta}\n\n"
            f"Responda *{APROVAR}* pra aprovar, *{DESCARTAR}* pra descartar, ou use \"Responder\" nesta mensagem e "
            "escreva a resposta do jeito certo, que ela entra no lugar.")


def para_enviar() -> list[RespostaAprendida]:
    """Sugestões que ainda não foram pro seu WhatsApp."""
    if not settings.ATENDIMENTO_AVISAR:
        return []
    return list(RespostaAprendida.objects.filter(estado=RespostaAprendida.SUGERIDA, enviada_em__isnull=True,
                                                 conversa__isnull=False).order_by("criada_em")[:5])


def _decidir(r: RespostaAprendida, texto: str) -> str:
    """Aplica a sua resposta e devolve a confirmação."""
    agora = timezone.now()
    if texto == DESCARTAR:
        r.estado = RespostaAprendida.DESCARTADA
        confirmacao = "🗑️ Descartada. O agente não vai usar essa."
    else:
        if texto != APROVAR:
            r.resposta = texto[:1500]
        r.estado = RespostaAprendida.APROVADA
        confirmacao = f"✅ Aprendido! A partir de agora o agente responde assim:\n*{r.pergunta}*\n{r.resposta}"
    r.decidida_em = agora
    r.save(update_fields=["estado", "resposta", "decidida_em", "atualizada_em"])
    return confirmacao


def tratar_resposta_do_dono(texto: str, citada: str) -> str | None:
    """Mensagem do seu número pessoal pro número de vendas: se for a resposta a uma sugestão, aplica e
    devolve a confirmação; senão None (a mensagem segue como uma conversa normal, pra você poder testar
    o agente pelo seu número)."""
    texto = (texto or "").strip()
    if not texto:
        return None
    pendentes = RespostaAprendida.objects.filter(estado=RespostaAprendida.SUGERIDA, enviada_em__isnull=False)
    if citada:
        r = pendentes.filter(whatsapp_id=citada).first()
        if r:
            return _decidir(r, texto)
    if texto in (APROVAR, DESCARTAR):
        r = pendentes.filter(enviada_em__gte=timezone.now() - VALIDADE_DO_1_E_2).order_by("-enviada_em").first()
        if r:
            return _decidir(r, texto)
    return None
