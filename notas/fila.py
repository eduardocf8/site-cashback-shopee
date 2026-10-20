"""Fila de emissão, rodada pelo worker (painel/management/commands/sincronizar_painel.py).

A cada volta: envia as notas da fila (uma por vez, por ordem de chegada), confere as que
ficaram sem resposta, manda os e-mails das autorizadas e fecha os lotes terminados.
Cada volta tem um tempo máximo, para não travar as outras tarefas do worker."""

import logging
import time
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from . import certificado, email, servicos
from .models import LoteNotas, NotaFiscal
from .sefin import ClienteSefin

logger = logging.getLogger(__name__)

TENTATIVAS_MAXIMAS = 12  # com 10 minutos entre elas: aguenta umas 2 horas de instabilidade
ESPERA_ENTRE_TENTATIVAS = timedelta(minutes=10)
ENVIANDO_TRAVADA = timedelta(minutes=15)  # worker caiu no meio do envio
EMAILS_POR_VOLTA = 60


def _pegar(nota_id: int) -> bool:
    """Marca a nota como "enviando" se ninguém pegou antes (evita envio em dobro)."""
    return bool(NotaFiscal.objects.filter(pk=nota_id, situacao__in=[NotaFiscal.FILA, NotaFiscal.ERRO])
                .update(situacao=NotaFiscal.ENVIANDO))


def _a_enviar():
    agora = timezone.now()
    # Quem ficou "enviando" demais (worker reiniciou) volta como "sem resposta" e é conferido.
    NotaFiscal.objects.filter(situacao=NotaFiscal.ENVIANDO, atualizada_em__lt=agora - ENVIANDO_TRAVADA).update(
        situacao=NotaFiscal.ERRO)
    return (NotaFiscal.objects.filter(
        Q(situacao=NotaFiscal.FILA)
        | Q(situacao=NotaFiscal.ERRO, tentativas__lt=TENTATIVAS_MAXIMAS, atualizada_em__lt=agora - ESPERA_ENTRE_TENTATIVAS))
        .exclude(empresa__emissao_pausada__gt="")
        .order_by("criada_em").values_list("pk", "empresa_id"))


def _acesso_negado(nota) -> bool:
    return nota.situacao == NotaFiscal.RECUSADA and any(m.get("codigo") in ("401", "403") for m in nota.mensagens)


def emitir(limite_segundos: float = 45) -> int:
    inicio, feitas, clientes, pausadas = time.monotonic(), 0, {}, set()
    for nota_id, empresa_id in _a_enviar()[:500]:
        if time.monotonic() - inicio > limite_segundos:
            break
        if empresa_id in pausadas or not _pegar(nota_id):
            continue
        nota = NotaFiscal.objects.select_related("empresa", "empresa__conta").get(pk=nota_id)
        if nota.empresa.emissao_pausada:
            NotaFiscal.objects.filter(pk=nota_id).update(situacao=NotaFiscal.FILA)
            pausadas.add(empresa_id)
            continue
        chave = (nota.empresa_id, nota.ambiente)
        if chave not in clientes:  # um certificado e uma conexão por empresa, reaproveitados
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
            nota.empresa.emissao_pausada = str(conexao)[:300]
            nota.empresa.save(update_fields=["emissao_pausada", "atualizada_em"])
            pausadas.add(empresa_id)
            continue
        servicos.processar(nota, cert=conexao[0], cliente=conexao[1])
        feitas += 1
        if nota.situacao == NotaFiscal.ERRO:
            break  # governo fora do ar ou instável: para a volta e tenta de novo daqui a pouco
        if _acesso_negado(nota):
            nota.empresa.emissao_pausada = nota.mensagens[0]["descricao"][:300]
            nota.empresa.save(update_fields=["emissao_pausada", "atualizada_em"])
            pausadas.add(empresa_id)
    return feitas


def enviar_emails(limite: int = EMAILS_POR_VOLTA) -> int:
    enviados = 0
    pendentes = (NotaFiscal.objects.filter(situacao=NotaFiscal.AUTORIZADA, email_situacao=NotaFiscal.EMAIL_PENDENTE)
                 .select_related("empresa", "empresa__conta", "lote").order_by("autorizada_em")[:limite])
    for nota in pendentes:
        if not nota.tomador_email:
            nota.email_situacao = NotaFiscal.EMAIL_SEM
        elif not nota.xml_nfse:
            continue  # ainda sem o XML da nota: tenta de novo depois
        else:
            try:
                email.montar(nota).send()
                nota.email_situacao, nota.email_enviado_em, nota.email_erro = NotaFiscal.EMAIL_ENVIADO, timezone.now(), ""
                enviados += 1
            except Exception as erro:  # noqa: BLE001 - um e-mail com problema não para os outros
                logger.warning("Notas: e-mail da nota %s falhou: %s", nota.pk, erro)
                nota.email_situacao, nota.email_erro = NotaFiscal.EMAIL_FALHOU, str(erro)[:300]
        nota.save(update_fields=["email_situacao", "email_enviado_em", "email_erro", "atualizada_em"])
    return enviados


def fechar_lotes():
    abertas = [NotaFiscal.FILA, NotaFiscal.ENVIANDO, NotaFiscal.ERRO]
    for lote in LoteNotas.objects.filter(estado=LoteNotas.EMITINDO):
        if not lote.notas.filter(situacao__in=abertas).exclude(
                situacao=NotaFiscal.ERRO, tentativas__gte=TENTATIVAS_MAXIMAS).exists():
            lote.estado = LoteNotas.CONCLUIDO
            lote.save(update_fields=["estado"])


def uma_volta(limite_segundos: float = 45) -> list[str]:
    """Chamado pelo worker a cada volta. Devolve linhas para o log."""
    linhas = []
    notas = emitir(limite_segundos)
    if notas:
        linhas.append(f"Notas fiscais: {notas} processada(s).")
    emails = enviar_emails()
    if emails:
        linhas.append(f"Notas fiscais: {emails} e-mail(s) enviado(s).")
    fechar_lotes()
    return linhas
