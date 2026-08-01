from decimal import Decimal

import requests
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from django.utils.formats import number_format

from pedidos.models import Pedido

from .asaas_client import AsaasAPIError, AsaasConfigError, consultar_transferencia, criar_transferencia_pix
from .models import Saque
from .notificacoes import notificar_saque_pago

STATUS_QUE_RESERVAM_SALDO = [Saque.STATUS_SOLICITADO, Saque.STATUS_PROCESSANDO, Saque.STATUS_PAGO]

TERMOS_PAGO = ("DONE",)
TERMOS_FALHOU = ("FAILED", "CANCELLED", "BLOCKED")


class ChavePixNaoConfiguradaError(Exception):
    """O usuário ainda não cadastrou uma chave PIX."""


class ValorAbaixoDoMinimoError(Exception):
    """O saldo disponível é menor que o valor mínimo de saque."""


def calcular_saldo_disponivel(usuario) -> Decimal:
    liberado = Pedido.objects.filter(usuario=usuario, status=Pedido.STATUS_LIBERADO).aggregate(
        total=Sum("valor_cashback")
    )["total"] or Decimal("0")
    reservado = Saque.objects.filter(usuario=usuario, status__in=STATUS_QUE_RESERVAM_SALDO).aggregate(
        total=Sum("valor")
    )["total"] or Decimal("0")
    return liberado - reservado


def solicitar_saque(usuario) -> Saque:
    """Cria uma solicitação de saque do saldo disponível total do usuário."""
    if not usuario.chave_pix or not usuario.tipo_chave_pix:
        raise ChavePixNaoConfiguradaError("Cadastre sua chave PIX antes de solicitar um saque.")

    saldo_disponivel = calcular_saldo_disponivel(usuario)
    if saldo_disponivel < settings.SAQUE_VALOR_MINIMO:
        raise ValorAbaixoDoMinimoError(
            f"O saldo mínimo para saque é R$ {number_format(settings.SAQUE_VALOR_MINIMO, decimal_pos=2)}."
        )

    return Saque.objects.create(
        usuario=usuario,
        valor=saldo_disponivel,
        chave_pix=usuario.chave_pix,
        tipo_chave_pix=usuario.tipo_chave_pix,
    )


def _mapear_status_transferencia(status_bruto: str) -> str:
    valor = (status_bruto or "").upper()
    if any(termo in valor for termo in TERMOS_PAGO):
        return Saque.STATUS_PAGO
    if any(termo in valor for termo in TERMOS_FALHOU):
        return Saque.STATUS_FALHOU
    return Saque.STATUS_PROCESSANDO


def processar_saque(saque: Saque) -> Saque:
    """Chama a Asaas para efetivar o pagamento PIX do saque e atualiza o status conforme o resultado."""
    descricao = f"Cashback Shopee - saque #{saque.pk}"
    try:
        resposta = criar_transferencia_pix(saque.valor, saque.chave_pix, saque.tipo_chave_pix, descricao)
    except (AsaasConfigError, AsaasAPIError) as erro:
        saque.status = Saque.STATUS_FALHOU
        saque.resposta_asaas = str(erro)
        saque.save(update_fields=["status", "resposta_asaas", "atualizado_em"])
        return saque
    except requests.RequestException as erro:
        saque.status = Saque.STATUS_FALHOU
        saque.resposta_asaas = f"Falha de conexão com a Asaas: {erro}"
        saque.save(update_fields=["status", "resposta_asaas", "atualizado_em"])
        return saque

    status_antes = saque.status
    saque.status = _mapear_status_transferencia(resposta.get("status"))
    saque.asaas_transfer_id = str(resposta.get("id", ""))
    saque.resposta_asaas = str(resposta)
    if saque.status == Saque.STATUS_PAGO:
        saque.pago_em = timezone.now()
    saque.save(update_fields=["status", "asaas_transfer_id", "resposta_asaas", "pago_em", "atualizado_em"])
    if saque.status == Saque.STATUS_PAGO and status_antes != Saque.STATUS_PAGO:
        notificar_saque_pago(saque)
    return saque


def atualizar_status_saque(saque: Saque) -> Saque:
    """Reconsulta na Asaas um saque que ficou 'processando' e atualiza o status final."""
    if not saque.asaas_transfer_id:
        return saque

    try:
        resposta = consultar_transferencia(saque.asaas_transfer_id)
    except (AsaasConfigError, AsaasAPIError, requests.RequestException):
        return saque

    status_antes = saque.status
    saque.status = _mapear_status_transferencia(resposta.get("status"))
    saque.resposta_asaas = str(resposta)
    if saque.status == Saque.STATUS_PAGO and not saque.pago_em:
        saque.pago_em = timezone.now()
    saque.save(update_fields=["status", "resposta_asaas", "pago_em", "atualizado_em"])
    if saque.status == Saque.STATUS_PAGO and status_antes != Saque.STATUS_PAGO:
        notificar_saque_pago(saque)
    return saque


def verificar_saques_pendentes() -> dict:
    """Reconsulta na Asaas todos os saques 'processando' e retorna um resumo do resultado."""
    pendentes = Saque.objects.filter(status=Saque.STATUS_PROCESSANDO)
    total = pendentes.count()
    atualizados = 0
    for saque in pendentes:
        status_antes = saque.status
        atualizar_status_saque(saque)
        if saque.status != status_antes:
            atualizados += 1
    return {"verificados": total, "atualizados": atualizados}
