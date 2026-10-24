"""Envio mensal das notas pra contabilidade: um ZIP com o XML de cada nota de verdade do mês
(autorizadas e canceladas, pela data de competência) e uma planilha-resumo, mandado pro e-mail
cadastrado no Emissor. Sai sozinho todo dia 1 com o mês anterior, ou na hora pelo botão."""

import csv
import io
import logging
import zipfile
from datetime import date

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from painel.exportar import texto_sem_formula

from . import danfse
from .email import MESES, _brl, conexao
from .models import AMBIENTE_PRODUCAO, EmpresaNotas, NotaFiscal

logger = logging.getLogger(__name__)
SITUACOES = [NotaFiscal.AUTORIZADA, NotaFiscal.CANCELADA]


def mes_anterior(hoje: date | None = None) -> date:
    hoje = hoje or timezone.localdate()
    return date(hoje.year - (hoje.month == 1), 12 if hoje.month == 1 else hoje.month - 1, 1)


def notas_do_mes(empresa, mes: date):
    return (NotaFiscal.objects.filter(empresa=empresa, ambiente=AMBIENTE_PRODUCAO, situacao__in=SITUACOES,
                                      competencia__year=mes.year, competencia__month=mes.month)
            .order_by("competencia", "numero"))


def montar_zip(empresa, mes: date) -> tuple[bytes, dict]:
    memoria, resumo = io.BytesIO(), io.StringIO()
    planilha = csv.writer(resumo, delimiter=";")
    planilha.writerow(["Competência", "Número NFS-e", "Tipo", "Tomador", "Documento", "Valor", "Situação",
                       "Cancelada em", "Chave de acesso"])
    totais = {"notas": 0, "canceladas": 0, "valor": 0}
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nota in notas_do_mes(empresa, mes).iterator():
            cancelada = nota.situacao == NotaFiscal.CANCELADA
            planilha.writerow([texto_sem_formula(v) for v in (
                f"{nota.competencia:%d/%m/%Y}", nota.numero_nfse, nota.get_tipo_display(), nota.tomador_nome,
                nota.tomador_documento, str(nota.valor).replace(".", ","), nota.get_situacao_display(),
                f"{timezone.localtime(nota.cancelada_em):%d/%m/%Y}" if nota.cancelada_em else "", nota.chave)])
            if nota.xml_nfse:
                arquivo.writestr(f"xml/{danfse.nome_arquivo(nota, 'xml')}", nota.xml_nfse)
            if nota.xml_cancelamento:
                arquivo.writestr(f"cancelamentos/{danfse.nome_arquivo(nota, 'xml')}", nota.xml_cancelamento)
            totais["notas"] += 1
            totais["canceladas"] += cancelada
            totais["valor"] += 0 if cancelada else nota.valor
        arquivo.writestr("resumo.csv", "﻿" + resumo.getvalue())
    return memoria.getvalue(), totais


def enviar(empresa, mes: date, para: str | None = None) -> dict:
    """Manda o mês pra contabilidade. Devolve os totais. Levanta a exceção do e-mail se falhar."""
    para = para or empresa.contabilidade_email
    conteudo, totais = montar_zip(empresa, mes)
    nome_mes = f"{MESES[mes.month - 1]} de {mes.year}"
    corpo = (
        "Olá!\n\n"
        f"Seguem as notas fiscais de serviço (NFS-e) de {empresa.razao_social} (CNPJ {empresa.cnpj_formatado}) "
        f"com competência em {nome_mes}.\n\n"
        f"Notas: {totais['notas']} (das quais {totais['canceladas']} cancelada{'s' if totais['canceladas'] != 1 else ''})\n"
        f"Valor das notas válidas: {_brl(totais['valor'])}\n\n"
        "No ZIP em anexo: o XML de cada nota (pasta xml), o XML dos cancelamentos (pasta cancelamentos) e a "
        "planilha resumo.csv.\n\n"
        f"Enviado pelo Appfiliado em nome de {empresa.razao_social}. Dúvidas? É só responder este e-mail.\n"
    )
    mensagem = EmailMessage(
        subject=f"Notas fiscais de {nome_mes} - {empresa.razao_social}",
        body=corpo, from_email=settings.NOTAS_EMAIL_REMETENTE or settings.APPFILIADO_EMAIL_REMETENTE,
        to=[para], cc=[empresa.conta.email], reply_to=[empresa.conta.email], connection=conexao(),
    )
    mensagem.attach(f"notas-{empresa.cnpj}-{mes:%Y-%m}.zip", conteudo, "application/zip")
    mensagem.send()
    return totais


def enviar_mes_anterior(hoje: date | None = None) -> int:
    """Chamado pelo worker: no começo de cada mês, manda o mês anterior pra quem cadastrou a contabilidade."""
    mes = mes_anterior(hoje)
    enviados = 0
    pendentes = EmpresaNotas.objects.exclude(contabilidade_email="").exclude(contabilidade_enviado_mes__gte=mes)
    for empresa in pendentes.select_related("conta"):
        # Notas de um mês que ainda estão na fila (ex: lote emitido no último dia) esperam sair.
        if NotaFiscal.objects.filter(empresa=empresa, ambiente=AMBIENTE_PRODUCAO, competencia__gte=mes,
                                     competencia__lt=date(mes.year + (mes.month == 12), mes.month % 12 + 1, 1),
                                     situacao__in=[NotaFiscal.FILA, NotaFiscal.ENVIANDO]).exists():
            continue
        try:
            enviar(empresa, mes)
        except Exception:  # noqa: BLE001 - tenta de novo na próxima volta
            logger.exception("Notas: envio à contabilidade da empresa %s falhou", empresa.pk)
            continue
        empresa.contabilidade_enviado_mes = mes
        empresa.save(update_fields=["contabilidade_enviado_mes", "atualizada_em"])
        enviados += 1
    return enviados
