"""Fila de emissão, rodada pelo worker (painel/management/commands/sincronizar_painel.py).

A cada volta: envia as notas da fila (várias ao mesmo tempo, por ordem de chegada), confere as que
ficaram sem resposta, manda os e-mails das autorizadas e fecha os lotes terminados.
Cada volta tem um tempo máximo, para não travar as outras tarefas do worker."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db import connection, connections
from django.db.models import Q
from django.utils import timezone

from cashback_shopee.ses_email_backend import LimiteDeEnvio

from . import certificado, email, servicos
from .models import LoteNotas, NotaFiscal
from .sefin import ClienteSefin

logger = logging.getLogger(__name__)

TENTATIVAS_MAXIMAS = 12  # com 10 minutos entre elas: aguenta umas 2 horas de instabilidade
ESPERA_ENTRE_TENTATIVAS = timedelta(minutes=10)
ENVIANDO_TRAVADA = timedelta(minutes=15)  # worker caiu no meio do envio
EMAILS_POR_VOLTA = 600


def _pegar(nota_id: int) -> bool:
    """Marca a nota como "enviando" se ninguém pegou antes (evita envio em dobro)."""
    return bool(NotaFiscal.objects.filter(pk=nota_id, situacao__in=[NotaFiscal.FILA, NotaFiscal.ERRO])
                .update(situacao=NotaFiscal.ENVIANDO, atualizada_em=timezone.now()))


def _a_enviar():
    agora = timezone.now()
    # Quem ficou "enviando" demais (worker reiniciou) volta como "sem resposta" e é conferido.
    NotaFiscal.objects.filter(situacao=NotaFiscal.ENVIANDO, atualizada_em__lt=agora - ENVIANDO_TRAVADA).update(
        situacao=NotaFiscal.ERRO)
    return (NotaFiscal.objects.filter(
        Q(situacao=NotaFiscal.FILA)
        | Q(situacao=NotaFiscal.ERRO, tentativas__lt=TENTATIVAS_MAXIMAS, atualizada_em__lt=agora - ESPERA_ENTRE_TENTATIVAS))
        .exclude(empresa__emissao_pausada__gt="")
        # Notas de verdade antes das de teste: um lote grande no ambiente de testes não
        # atrasa a emissão real de ninguém.
        .order_by("ambiente", "criada_em").values_list("pk", "empresa_id"))


def _acesso_negado(nota) -> bool:
    return nota.situacao == NotaFiscal.RECUSADA and any(m.get("codigo") in ("401", "403") for m in nota.mensagens)


class _Rodada:
    """Itens de uma volta da fila, repartidos entre os envios simultâneos (threads)."""

    def __init__(self, itens, limite_segundos: float):
        self._itens = iter(itens)
        self._fim = time.monotonic() + limite_segundos
        self.trava = threading.Lock()
        self.parar = False
        self.pausadas = set()
        self.feitas = 0

    def proximo(self):
        with self.trava:
            if self.parar or time.monotonic() > self._fim:
                return None
            return next(self._itens, None)

    def contar(self):
        with self.trava:
            self.feitas += 1


def _simultaneos(configurado: int) -> int:
    # Um por vez no SQLite (testes e desenvolvimento: não aguenta escrita em paralelo) e dentro de
    # uma transação aberta (as outras threads, com outra conexão, não enxergariam os dados dela).
    if connection.vendor == "sqlite" or connection.in_atomic_block:
        return 1
    return max(1, configurado)


def _rodar(trabalho, rodada: _Rodada, quantos: int):
    if quantos <= 1:
        trabalho(rodada)
        return

    def na_thread(r):
        try:
            trabalho(r)
        finally:
            connections.close_all()  # cada thread tem a própria conexão com o banco

    with ThreadPoolExecutor(max_workers=quantos, thread_name_prefix="notas") as grupo:
        for futuro in [grupo.submit(na_thread, rodada) for _ in range(quantos)]:
            futuro.result()


def _pausar(empresa, motivo: str):
    empresa.emissao_pausada = motivo[:300]
    empresa.save(update_fields=["emissao_pausada", "atualizada_em"])


def _trabalhar_notas(rodada: _Rodada):
    clientes = {}  # um certificado e uma conexão por empresa, reaproveitados (um jogo por thread)
    while (item := rodada.proximo()) is not None:
        nota_id, empresa_id = item
        with rodada.trava:
            pausada = empresa_id in rodada.pausadas
        if pausada or not _pegar(nota_id):
            continue
        nota = NotaFiscal.objects.select_related("empresa", "empresa__conta").get(pk=nota_id)
        if nota.empresa.emissao_pausada:
            NotaFiscal.objects.filter(pk=nota_id).update(situacao=NotaFiscal.FILA)
            with rodada.trava:
                rodada.pausadas.add(empresa_id)
            continue
        chave = (nota.empresa_id, nota.ambiente)
        if chave not in clientes:
            try:
                cert = certificado.da_empresa(nota.empresa)
                clientes[chave] = (cert, ClienteSefin(nota.ambiente, cert))
            except Exception as erro:  # noqa: BLE001 - certificado vencido/ilegível
                clientes[chave] = erro
        conexao = clientes[chave]
        if isinstance(conexao, Exception):
            # Certificado vencido ou ilegível: vale para todas as notas da empresa. Pausa e
            # deixa todas na fila, em vez de recusar uma a uma.
            NotaFiscal.objects.filter(pk=nota_id).update(situacao=NotaFiscal.FILA)
            _pausar(nota.empresa, str(conexao))
            with rodada.trava:
                rodada.pausadas.add(empresa_id)
            continue
        servicos.processar(nota, cert=conexao[0], cliente=conexao[1])
        rodada.contar()
        if nota.situacao == NotaFiscal.ERRO and not getattr(nota, "erro_inesperado", False):
            # (um erro só desta nota, do nosso lado, não para a volta das outras empresas)
            rodada.parar = True  # governo fora do ar ou instável: para a volta e tenta daqui a pouco
        elif _acesso_negado(nota):
            _pausar(nota.empresa, nota.mensagens[0]["descricao"])
            with rodada.trava:
                rodada.pausadas.add(empresa_id)


def emitir(limite_segundos: float = 45) -> int:
    """Manda as notas da fila, várias ao mesmo tempo (NOTAS_ENVIOS_SIMULTANEOS), até o
    tempo da volta acabar. Cada nota é "pega" antes de enviar, então nenhuma sai duas vezes."""
    itens = list(_a_enviar()[:3000])
    if not itens:
        return 0
    rodada = _Rodada(itens, limite_segundos)
    _rodar(_trabalhar_notas, rodada, _simultaneos(settings.NOTAS_ENVIOS_SIMULTANEOS))
    return rodada.feitas


def _limite_do_servico(erro) -> bool:
    """O serviço de e-mail pediu para esperar (cota por segundo/dia ou créditos)?"""
    if isinstance(erro, LimiteDeEnvio):
        return True
    resposta = getattr(erro, "response", None)
    return getattr(resposta, "status_code", None) in (402, 429)


def _mandar_um_email(nota, conexao) -> bool:
    """Manda o e-mail de uma nota. False = o serviço pediu para esperar (parar a volta)."""
    if not nota.tomador_email:
        nota.email_situacao = NotaFiscal.EMAIL_SEM
    elif not nota.xml_nfse:
        return True  # ainda sem o XML da nota: tenta de novo depois
    else:
        try:
            email.montar(nota, connection=conexao).send()
            nota.email_situacao, nota.email_enviado_em, nota.email_erro = NotaFiscal.EMAIL_ENVIADO, timezone.now(), ""
        except Exception as erro:  # noqa: BLE001 - um e-mail com problema não para os outros
            if _limite_do_servico(erro):
                logger.info("Notas: serviço de e-mail pediu para esperar (%s). Continua depois.", erro)
                return False  # fica "a enviar" e sai na próxima volta
            logger.warning("Notas: e-mail da nota %s falhou: %s", nota.pk, erro)
            nota.email_situacao, nota.email_erro = NotaFiscal.EMAIL_FALHOU, str(erro)[:300]
    nota.save(update_fields=["email_situacao", "email_enviado_em", "email_erro", "atualizada_em"])
    return True


def enviar_emails(limite: int = EMAILS_POR_VOLTA, limite_segundos: float = 40) -> int:
    if settings.NOTAS_EMAILS_POR_DIA:
        hoje = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        ja = NotaFiscal.objects.filter(email_enviado_em__gte=hoje).count()
        limite = min(limite, max(0, settings.NOTAS_EMAILS_POR_DIA - ja))
        if not limite:
            return 0  # teto do dia atingido: o resto sai amanhã
    agora = timezone.now()
    pendentes = list(NotaFiscal.objects.filter(situacao=NotaFiscal.AUTORIZADA, email_situacao=NotaFiscal.EMAIL_PENDENTE)
                     .filter(Q(email_enviar_em__isnull=True) | Q(email_enviar_em__lte=agora))  # agendados esperam a hora
                     .select_related("empresa", "empresa__conta", "lote").order_by("autorizada_em")[:limite])
    if not pendentes:
        return 0
    rodada = _Rodada(pendentes, limite_segundos)

    def trabalhar(r):
        conexao = email.conexao()
        while (nota := r.proximo()) is not None:
            if not _mandar_um_email(nota, conexao):
                r.parar = True
            elif nota.email_situacao == NotaFiscal.EMAIL_ENVIADO:
                r.contar()

    _rodar(trabalhar, rodada, _simultaneos(settings.NOTAS_EMAILS_SIMULTANEOS))
    return rodada.feitas


def fechar_lotes():
    abertas = [NotaFiscal.FILA, NotaFiscal.ENVIANDO, NotaFiscal.ERRO]
    for lote in LoteNotas.objects.filter(estado=LoteNotas.EMITINDO):
        if not lote.notas.filter(situacao__in=abertas).exclude(
                situacao=NotaFiscal.ERRO, tentativas__gte=TENTATIVAS_MAXIMAS).exists():
            lote.estado = LoteNotas.CONCLUIDO
            lote.save(update_fields=["estado"])


def tem_fila() -> bool:
    try:
        return NotaFiscal.objects.filter(situacao__in=[NotaFiscal.FILA, NotaFiscal.ENVIANDO]).exclude(
            empresa__emissao_pausada__gt="").exists()
    except Exception:  # noqa: BLE001 - banco fora do ar: espera o normal
        return False


def uma_volta(limite_segundos: float = 45) -> list[str]:
    """Chamado pelo worker a cada volta. Devolve linhas para o log."""
    linhas = []
    notas = emitir(limite_segundos)
    if notas:
        linhas.append(f"Notas fiscais: {notas} processada(s).")
    # Enquanto houver notas na fila, a volta é toda da emissão (a barra não para); os e-mails
    # saem logo que a fila esvaziar.
    emails = 0 if tem_fila() else enviar_emails()
    if emails:
        linhas.append(f"Notas fiscais: {emails} e-mail(s) enviado(s).")
    fechar_lotes()
    enviados = _contabilidade()
    if enviados:
        linhas.append(f"Notas fiscais: notas do mês enviadas a {enviados} contabilidade(s).")
    return linhas


_proxima_contabilidade = 0.0


def _contabilidade() -> int:
    """No começo de cada mês, manda o mês anterior pras contabilidades cadastradas (uma vez por hora
    confere se falta alguma; só depois das 7h, pra não mandar de madrugada)."""
    global _proxima_contabilidade
    if time.monotonic() < _proxima_contabilidade or timezone.localtime().hour < 7:
        return 0
    _proxima_contabilidade = time.monotonic() + 3600
    from . import contabilidade

    try:
        return contabilidade.enviar_mes_anterior()
    except Exception:  # noqa: BLE001 - não pode parar a emissão
        logger.exception("Notas: envio mensal à contabilidade")
        return 0
