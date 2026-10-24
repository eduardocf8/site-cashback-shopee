"""Notas fiscais das assinaturas do Appfiliado.

Cada pagamento confirmado pela Zouti (assinatura ativada ou renovada) vira uma NFS-e emitida pela
empresa cadastrada no Emissor da conta NOTAS_ASSINATURAS_CONTA_ID, com o serviço próprio dessas
notas (NOTAS_ASSINATURAS_CODIGO etc.). A nota entra na mesma fila das outras (notas/fila.py) e,
autorizada, vai por e-mail pro cliente. Estorno ou chargeback cancelam a nota.

Chamado pelo webhook da Zouti (licencas/services.py). Nunca levanta exceção: um problema aqui não
pode impedir a liberação da assinatura; o resumo volta pro registro do evento."""

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from . import dps
from .models import AMBIENTE_PRODUCAO, EmpresaNotas, NotaFiscal

logger = logging.getLogger(__name__)

EVENTOS_DE_PAGAMENTO = {"SUBSCRIPTION_ACTIVATED", "SUBSCRIPTION_RENEWED"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ligado() -> bool:
    return bool(settings.NOTAS_ASSINATURAS_CONTA_ID)


def empresa() -> EmpresaNotas | None:
    return EmpresaNotas.objects.filter(conta_id=settings.NOTAS_ASSINATURAS_CONTA_ID).order_by("criada_em").first()


def _tomador(cliente: dict) -> dps.Tomador | None:
    documento = re.sub(r"\D", "", str(cliente.get("document") or ""))
    tipo = {11: "cpf", 14: "cnpj"}.get(len(documento))
    nome = " ".join(str(cliente.get("name") or "").split())
    if not tipo or not nome:
        return None
    return dps.Tomador(tipo, documento, nome, str(cliente.get("email") or "").strip().lower()[:254])


def _valor(payload: dict) -> Decimal:
    """Valor pago, em reais (a Zouti manda em centavos): a soma dos itens, ou o do plano."""
    itens = payload.get("line_items") or []
    centavos = sum(int(i.get("amount") or 0) for i in itens) if itens else int((payload.get("plan") or {}).get("amount") or 0)
    return (Decimal(centavos) / 100).quantize(Decimal("0.01"))


def _descricao(payload: dict) -> str:
    itens = [str(i.get("name") or "").strip() for i in payload.get("line_items") or []]
    produtos = " + ".join(i for i in itens if i) or str((payload.get("plan") or {}).get("name") or "").strip()
    inicio = str(payload.get("current_period_start") or "")[:10]
    referencia = f" (ref. {inicio[5:7]}/{inicio[:4]})" if len(inicio) == 10 else ""
    plano = " anual" if str((payload.get("plan") or {}).get("interval") or "").upper() in ("YEARLY", "ANNUALLY", "YEAR") else ""
    base = settings.NOTAS_ASSINATURAS_DESCRICAO
    return f"{base}{plano} - {produtos}{referencia}" if produtos else f"{base}{plano}{referencia}"


def registrar_pagamento(tipo_evento: str, payload: dict) -> str:
    """Põe na fila a nota de um pagamento confirmado. Devolve um resumo (vazio = nada a fazer)."""
    if not ligado() or tipo_evento not in EVENTOS_DE_PAGAMENTO:
        return ""
    if str(payload.get("status") or "").upper() != "ACTIVE":
        return f"Nota: não emitida (assinatura com status {payload.get('status') or '?'})."
    try:
        return _registrar(payload)
    except Exception:  # noqa: BLE001 - a nota não pode atrapalhar a liberação da assinatura
        logger.exception("Notas das assinaturas: falha ao registrar a nota da assinatura %s", payload.get("id"))
        return "Nota: erro ao registrar (ver o log)."


def _registrar(payload: dict) -> str:
    emissora = empresa()
    if not emissora:
        logger.warning("Notas das assinaturas: a conta %s não tem empresa cadastrada no Emissor.",
                       settings.NOTAS_ASSINATURAS_CONTA_ID)
        return "Nota: não emitida (sem empresa cadastrada no Emissor da conta configurada)."
    sub_id = str(payload.get("id") or "")
    inicio = str(payload.get("current_period_start") or "")[:10]
    tomador = _tomador(payload.get("customer") or {})
    valor = _valor(payload)
    if not sub_id or not inicio:
        return "Nota: não emitida (evento sem id da assinatura ou sem o início do período)."
    if not tomador:
        logger.warning("Notas das assinaturas: cliente sem CPF/CNPJ ou nome válido na assinatura %s.", sub_id)
        return "Nota: não emitida (cliente sem CPF/CNPJ ou nome válido)."
    if valor <= 0:
        return "Nota: não emitida (valor zero)."
    ambiente = settings.NOTAS_ASSINATURAS_AMBIENTE
    # Um ciclo = uma nota: o mesmo evento repetido (ou ativação e renovação do mesmo período) não duplica.
    referencia = f"zouti:{sub_id}:{inicio}"
    nota, criada = NotaFiscal.objects.get_or_create(
        empresa=emissora, ambiente=ambiente, referencia=referencia,
        defaults={
            "tipo": NotaFiscal.TIPO_ASSINATURA, "competencia": timezone.localdate(), "situacao": NotaFiscal.FILA,
            "tomador_tipo": tomador.tipo, "tomador_documento": tomador.documento, "tomador_nome": tomador.nome[:300],
            "tomador_email": tomador.email, "valor": valor,
            "servico_codigo": settings.NOTAS_ASSINATURAS_CODIGO,
            "servico_codigo_municipal": settings.NOTAS_ASSINATURAS_CODIGO_MUNICIPAL,
            "servico_nbs": settings.NOTAS_ASSINATURAS_NBS,
            "servico_descricao": _descricao(payload)[:2000],
            # Só nota de verdade vai pro cliente; a do ambiente de testes não tem valor fiscal.
            "email_situacao": (NotaFiscal.EMAIL_NAO if ambiente != AMBIENTE_PRODUCAO
                               else NotaFiscal.EMAIL_PENDENTE if tomador.email else NotaFiscal.EMAIL_SEM),
        },
    )
    if not criada:
        return f"Nota: já registrada antes para este período (nota {nota.pk})."
    return f"Nota: na fila de emissão (nota {nota.pk}, R$ {valor})."


def cancelar_por_estorno(sub_ids: list[str], estorno: bool) -> str:
    """Estorno ou chargeback: cancela a nota mais recente de cada assinatura. A que ainda não saiu
    sai da fila. Devolve um resumo; nunca levanta exceção."""
    if not ligado() or not sub_ids:
        return ""
    from . import servicos

    resumo = []
    for sub_id in sub_ids:
        nota = (NotaFiscal.objects.filter(tipo=NotaFiscal.TIPO_ASSINATURA, referencia__startswith=f"zouti:{sub_id}:")
                .exclude(situacao=NotaFiscal.CANCELADA).order_by("-criada_em").first())
        if not nota:
            continue
        try:
            if nota.situacao in (NotaFiscal.FILA, NotaFiscal.RECUSADA, NotaFiscal.PREVIA) and not nota.chave:
                nota.delete()
                resumo.append(f"nota de {sub_id} tirada da fila")
            elif nota.situacao == NotaFiscal.AUTORIZADA:
                motivo = "Assinatura reembolsada ao cliente." if estorno else "Pagamento contestado (chargeback)."
                servicos.cancelar(nota, "2", motivo)
                resumo.append(f"nota {nota.numero_nfse or nota.pk} cancelada")
            else:  # enviando ou sem resposta do governo: alguém precisa conferir
                logger.warning("Notas das assinaturas: estorno de %s com a nota %s em '%s': cancele à mão.",
                               sub_id, nota.pk, nota.situacao)
                resumo.append(f"nota {nota.pk} em '{nota.get_situacao_display()}': cancelar à mão")
        except Exception as erro:  # noqa: BLE001 - ex: passou do prazo de cancelamento do governo
            logger.exception("Notas das assinaturas: não deu pra cancelar a nota %s", nota.pk)
            resumo.append(f"nota {nota.pk}: não cancelou ({str(erro)[:80]}), cancelar à mão")
    return ("Nota: " + "; ".join(resumo) + ".") if resumo else ""
