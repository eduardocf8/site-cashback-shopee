"""Mensagens avulsas (aba Mensagens do Bot de WhatsApp): textos que a pessoa escreve pra mandar
nos grupos agora, num dia e hora marcados ou toda semana. Roda numa thread do worker: na hora,
troca os links da Shopee pelos links de afiliado (com os Sub IDs de cada grupo) e põe uma
mensagem por grupo na fila do gerenciador, que manda no ritmo normal (uma a cada 3 s).

Não conta no limite de ofertas nem no intervalo das ofertas automáticas, e sai mesmo com elas
desligadas ou no modo simulação. Com o WhatsApp desconectado na hora, espera até ATRASO_MAXIMO;
depois disso fica como "não enviada" (melhor do que chegar fora de hora)."""

import logging
import threading
import time
from datetime import datetime, timedelta

from django.db import close_old_connections
from django.utils import timezone

from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, MensagemAvulsa

logger = logging.getLogger(__name__)

INTERVALO = 10  # segundos entre uma conferência e outra
ATRASO_MAXIMO = timedelta(hours=1)
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def proxima_semanal(dias: list[int], hora, depois) -> datetime | None:
    """A próxima vez (estritamente depois de `depois`) num dos dias da semana, na hora local."""
    if not dias or hora is None:
        return None
    local = timezone.localtime(depois)
    for avanco in range(8):
        dia = (local + timedelta(days=avanco)).date()
        if dia.weekday() not in dias:
            continue
        quando = timezone.make_aware(datetime.combine(dia, hora))
        if quando > depois:
            return quando
    return None


def calcular_proxima(mensagem, agora) -> datetime | None:
    if mensagem.quando == MensagemAvulsa.QUANDO_AGORA:
        return agora
    if mensagem.quando == MensagemAvulsa.QUANDO_AGENDAR:
        return mensagem.agendada_para
    return proxima_semanal(mensagem.dias_semana, mensagem.hora, agora)


def descrever_quando(mensagem) -> str:
    if mensagem.quando == MensagemAvulsa.QUANDO_SEMANAL and mensagem.hora:
        dias = [DIAS[d] for d in sorted(mensagem.dias_semana or [])]
        lista = "todo dia" if len(dias) == 7 else ("toda " + ", ".join(dias[:-1]) + (" e " if len(dias) > 1 else "") + dias[-1])
        return f"{lista[0].upper()}{lista[1:]} às {mensagem.hora:%H:%M}"
    if mensagem.quando == MensagemAvulsa.QUANDO_AGENDAR and mensagem.agendada_para:
        return f"{timezone.localtime(mensagem.agendada_para):%d/%m às %H:%M}"
    return "Agora"


def destinos(mensagem, config=None, conexao=None) -> list[dict]:
    """Os grupos ({"jid", "nome"}) que recebem esta mensagem, dentro do limite do plano."""
    from . import ofertas, servico

    config = config if config is not None else ConfiguracaoOfertas.objects.filter(conta=mensagem.conta).first()
    if mensagem.destino == MensagemAvulsa.DESTINO_GRUPOS:
        conexao = conexao if conexao is not None else ConexaoWhatsApp.objects.filter(conta=mensagem.conta).first()
        possiveis = {g["jid"]: g for g in (servico.destinos_possiveis(conexao) if conexao else []) if g.get("jid")}
        if config:  # os grupos escolhidos na Automação, mesmo se sumiram da lista
            for g in config.grupos or []:
                possiveis.setdefault(g.get("jid"), g)
        maximo = ofertas.regras_do_plano(config)["grupos"] if config else len(mensagem.grupos)
        return [{"jid": jid, "nome": possiveis[jid].get("nome", "")} for jid in mensagem.grupos if jid in possiveis][:maximo]
    if not config:
        return []
    if mensagem.destino == MensagemAvulsa.DESTINO_NICHO:
        return next((grupos for nicho, grupos in ofertas.nichos_do_plano(config) if nicho["id"] == mensagem.nicho), [])
    return ofertas.grupos_do_plano(config)


def _textos_por_grupo(mensagem, grupos, config) -> dict[str, str]:
    """O texto de cada grupo: os links da Shopee viram o link de afiliado com os Sub IDs do grupo
    (um texto por combinação de Sub IDs). Sem link da Shopee, vai o texto como foi escrito."""
    from painel import conversor

    if not conversor.tem_link_da_shopee(mensagem.texto):
        return {g["jid"]: mensagem.texto for g in grupos}
    por_sub_ids: dict[tuple, str] = {}
    textos = {}
    for grupo in grupos:
        sub_ids = tuple(config.lista_sub_ids(grupo["jid"]) if config else [])
        if sub_ids not in por_sub_ids:
            resultado = conversor.converter(mensagem.conta, mensagem.texto, conversor.MODO_TEXTO,
                                            sub_ids=list(sub_ids), manter_outros_links=True)
            por_sub_ids[sub_ids] = resultado["texto"]
        textos[grupo["jid"]] = por_sub_ids[sub_ids]
    return textos


def _registrar(mensagem, grupos, agora, textos=None, erro=""):
    EnvioWhatsApp.objects.bulk_create([
        EnvioWhatsApp(
            conta=mensagem.conta, destino=g["jid"], destino_nome=g.get("nome", ""), origem=EnvioWhatsApp.MENSAGEM,
            texto=(textos or {}).get(g["jid"], mensagem.texto), mensagem=mensagem, disparo_em=agora,
            produto=mensagem.texto.strip().splitlines()[0][:300] if mensagem.texto.strip() else "",
            estado=EnvioWhatsApp.ERRO if erro else EnvioWhatsApp.PENDENTE, erro=erro[:500],
        )
        for g in grupos
    ])


def disparar(mensagem, agora) -> str:
    """Põe a mensagem na fila de cada grupo (ou registra por que não foi). Devolve um resumo."""
    from licencas.models import MODULO_WHATSAPP
    from painel.conversor import ErroConversor

    config = ConfiguracaoOfertas.objects.filter(conta=mensagem.conta).first()
    conexao = ConexaoWhatsApp.objects.filter(conta=mensagem.conta).first()
    grupos = destinos(mensagem, config, conexao)
    if not grupos:
        return "sem grupos"
    if MODULO_WHATSAPP not in mensagem.conta.modulos_liberados():
        _registrar(mensagem, grupos, agora, erro="Não enviada: o Bot de WhatsApp não está mais no seu plano.")
        return "fora do plano"
    if not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO:
        _registrar(mensagem, grupos, agora, erro="Não enviada: o WhatsApp ficou desconectado por mais de 1 hora "
                                                 "depois do horário marcado.")
        return "WhatsApp desconectado"
    try:
        textos = _textos_por_grupo(mensagem, grupos, config)
    except ErroConversor as erro:
        _registrar(mensagem, grupos, agora, erro=f"Não enviada: {erro}")
        return f"erro nos links: {erro}"
    _registrar(mensagem, grupos, agora, textos)
    return f"na fila de {len(grupos)} grupo(s)"


def uma_volta(agora=None) -> list[str]:
    agora = agora or timezone.now()
    linhas = []
    vencidas = (MensagemAvulsa.objects.filter(proxima_em__lte=agora, pausada=False)
                .select_related("conta").order_by("proxima_em")[:50])
    for mensagem in vencidas:
        marcada = mensagem.proxima_em
        conexao = ConexaoWhatsApp.objects.filter(conta=mensagem.conta).first()
        conectado = conexao and conexao.estado == ConexaoWhatsApp.CONECTADO
        if not conectado and agora - marcada <= ATRASO_MAXIMO:
            continue  # espera reconectar (a faixa e o e-mail de bot parado já avisam a pessoa)
        proxima = (proxima_semanal(mensagem.dias_semana, mensagem.hora, max(agora, marcada))
                   if mensagem.quando == MensagemAvulsa.QUANDO_SEMANAL else None)
        # Só um processo leva esta vez: quem conseguir trocar a próxima vez primeiro.
        if not MensagemAvulsa.objects.filter(pk=mensagem.pk, proxima_em=marcada).update(
                proxima_em=proxima, ultimo_envio_em=agora):
            continue
        try:
            resumo = disparar(mensagem, agora)
        except Exception:  # noqa: BLE001 - uma mensagem com problema não trava as outras
            logger.exception("Mensagens: erro ao disparar a mensagem %s", mensagem.pk)
            resumo = "erro"
        linhas.append(f"Mensagem {mensagem.pk} de {mensagem.conta.email}: {resumo}.")
    return linhas


def rodar():
    while True:
        close_old_connections()
        try:
            for linha in uma_volta():
                logger.info(linha)
        except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
            logger.exception("Mensagens: erro na volta")
        time.sleep(INTERVALO)


def iniciar_em_segundo_plano():
    threading.Thread(target=rodar, name="mensagens-avulsas", daemon=True).start()
