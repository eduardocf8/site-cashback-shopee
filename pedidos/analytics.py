from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet, Sum

from accounts.models import Indicacao
from saques.models import Saque

from .models import Pedido


def _no_periodo(queryset: QuerySet, campo_data: str, data_inicio, data_fim) -> QuerySet:
    if data_inicio:
        queryset = queryset.filter(**{f"{campo_data}__date__gte": data_inicio})
    if data_fim:
        queryset = queryset.filter(**{f"{campo_data}__date__lte": data_fim})
    return queryset


def obter_pedidos_filtrados(data_inicio=None, data_fim=None, status=None) -> QuerySet:
    """Pedidos filtrados por período (via data_compra) e status - base compartilhada
    entre a tela de analytics e a exportação em CSV, pra manter os dois sempre batendo."""
    pedidos = _no_periodo(Pedido.objects.all(), "data_compra", data_inicio, data_fim)
    if status:
        pedidos = pedidos.filter(status=status)
    return pedidos


def obter_analytics(data_inicio=None, data_fim=None, status=None) -> dict:
    """Agrega os números do negócio pro período/status informado - usado pela tela
    /admin/pedidos/pedido/analytics/. Cada bloco filtra pela sua própria data "natural"
    (pedido por data_compra, saque por criado_em, indicação por criado_em, usuário por
    date_joined), porque não faz sentido contar, por exemplo, um saque solicitado fora
    do período só porque o pedido que originou aquele cashback foi comprado dentro dele.
    """
    pedidos = obter_pedidos_filtrados(data_inicio, data_fim, status)

    totais_pedidos = pedidos.aggregate(
        total_comissao=Sum("valor_comissao"), total_cashback=Sum("valor_cashback"), total=Count("id")
    )
    total_comissao = totais_pedidos["total_comissao"] or Decimal("0")
    total_cashback = totais_pedidos["total_cashback"] or Decimal("0")
    total_pedidos = totais_pedidos["total"] or 0

    por_status_bruto = {
        linha["status"]: linha
        for linha in pedidos.values("status").annotate(
            total=Count("id"), comissao=Sum("valor_comissao"), cashback=Sum("valor_cashback")
        )
    }
    resumo_status = [
        {
            "status": chave,
            "status_label": label,
            "total": (por_status_bruto.get(chave) or {}).get("total") or 0,
            "comissao": (por_status_bruto.get(chave) or {}).get("comissao") or Decimal("0"),
            "cashback": (por_status_bruto.get(chave) or {}).get("cashback") or Decimal("0"),
        }
        for chave, label in Pedido.STATUS_CHOICES
    ]
    cashback_por_status = {linha["status"]: linha["cashback"] for linha in resumo_status}

    saques = _no_periodo(Saque.objects.all(), "criado_em", data_inicio, data_fim)
    totais_saques = saques.aggregate(total_valor=Sum("valor"), total=Count("id"))
    saques_por_status_bruto = {
        linha["status"]: linha
        for linha in saques.values("status").annotate(total=Count("id"), valor=Sum("valor"))
    }
    saques_por_status = [
        {
            "status": chave,
            "status_label": label,
            "total": (saques_por_status_bruto.get(chave) or {}).get("total") or 0,
            "valor": (saques_por_status_bruto.get(chave) or {}).get("valor") or Decimal("0"),
        }
        for chave, label in Saque.STATUS_CHOICES
    ]

    indicacoes = _no_periodo(Indicacao.objects.all(), "criado_em", data_inicio, data_fim)
    total_indicacoes = indicacoes.count()
    indicacoes_concluidas = indicacoes.filter(pedido_bonus_indicador__isnull=False).count()
    ranking_indicadores = list(
        indicacoes.values("indicador__username")
        .annotate(
            total_indicacoes=Count("id"),
            concluidas=Count("id", filter=Q(pedido_bonus_indicador__isnull=False)),
        )
        .order_by("-total_indicacoes", "-concluidas")[:20]
    )

    novos_usuarios = _no_periodo(get_user_model().objects.all(), "date_joined", data_inicio, data_fim).count()

    return {
        "total_comissao": total_comissao,
        "total_cashback": total_cashback,
        "total_pedidos": total_pedidos,
        "margem_retida": total_comissao - total_cashback,
        "percentual_repassado": (total_cashback / total_comissao * 100) if total_comissao else Decimal("0"),
        "ticket_medio_cashback": (total_cashback / total_pedidos) if total_pedidos else Decimal("0"),
        "resumo_status": resumo_status,
        "saldo_a_liberar": cashback_por_status.get(Pedido.STATUS_PENDENTE, Decimal("0"))
        + cashback_por_status.get(Pedido.STATUS_VALIDADO, Decimal("0")),
        "saldo_liberado": cashback_por_status.get(Pedido.STATUS_LIBERADO, Decimal("0")),
        "total_saques_valor": totais_saques["total_valor"] or Decimal("0"),
        "total_saques": totais_saques["total"] or 0,
        "saques_por_status": saques_por_status,
        "total_indicacoes": total_indicacoes,
        "indicacoes_concluidas": indicacoes_concluidas,
        "ranking_indicadores": ranking_indicadores,
        "novos_usuarios": novos_usuarios,
    }
