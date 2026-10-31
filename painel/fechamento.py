"""Fechamento da meta do mês: 30 dias depois do último dia do mês, às 11h (horário de Brasília).

É quando a Shopee manda o e-mail da meta mensal (setembro/2026 chegou em 30/10 às 11h35), contando
os pedidos comprados no mês e validados até ali, pelo valor pago menos reembolsos. Nesse momento o
worker (sincronizar_painel) busca o mês direto na Shopee e guarda em FechamentoMes - depois disso o
resultado da meta não muda mais, mesmo que algum pedido seja validado ou reembolsado mais tarde."""

import logging
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from . import cripto, periodos
from .models import FechamentoMes

logger = logging.getLogger(__name__)

DIAS_ATE_FECHAR = 30
HORA_DO_FECHAMENTO = 11
# Meses que fecharam há mais tempo que isso não são fechados de novo (contas novas, worker parado):
# a meta deles usa os pedidos guardados.
DIAS_PARA_FECHAR_ATRASADO = 7
# Se a Shopee falhar, tenta de novo depois disso.
ESPERA_DEPOIS_DE_ERRO = timedelta(minutes=30)
_ultimo_erro: dict[tuple[int, int, int], datetime] = {}


def dia_do_fechamento(ano: int, mes: int) -> date:
    return periodos.ultimo_dia_do_mes(date(ano, mes, 1)) + timedelta(days=DIAS_ATE_FECHAR)


def momento_do_fechamento(ano: int, mes: int) -> datetime:
    return timezone.make_aware(datetime.combine(dia_do_fechamento(ano, mes), time(HORA_DO_FECHAMENTO)))


def meses_para_fechar(agora: datetime) -> list[tuple[int, int]]:
    """Os meses cujo fechamento já chegou (e não faz mais de DIAS_PARA_FECHAR_ATRASADO dias)."""
    hoje = timezone.localtime(agora).date()
    meses, d = [], hoje.replace(day=1)
    for _ in range(3):
        d = (d - timedelta(days=1)).replace(day=1)
        momento = momento_do_fechamento(d.year, d.month)
        if momento <= agora < momento + timedelta(days=DIAS_PARA_FECHAR_ATRASADO):
            meses.append((d.year, d.month))
    return meses


def fechar(conta, ano: int, mes: int, agora: datetime | None = None) -> FechamentoMes:
    """Busca o mês na Shopee e guarda o fechamento (se já existir, devolve o que está guardado)."""
    from .resultados import _limites, somar_mes_na_shopee

    existente = FechamentoMes.objects.filter(conta=conta, ano=ano, mes=mes).first()
    if existente:
        return existente
    inicio = date(ano, mes, 1)
    de, ate = _limites(inicio, periodos.ultimo_dia_do_mes(inicio))
    soma = somar_mes_na_shopee(conta, cripto.decifrar(conta.shopee_secret_cifrado), de, ate, "purchaseTime")
    fechamento, _ = FechamentoMes.objects.get_or_create(conta=conta, ano=ano, mes=mes, defaults={
        "validado": soma["validados"]["pago_sem_reembolso"], "pendente": soma["pendentes"]["pago_sem_reembolso"],
        "cancelado": soma["cancelados"]["pago_sem_reembolso"], "pedidos": soma["validados"]["pedidos"],
        "fechado_em": agora or timezone.now(),
    })
    return fechamento


def uma_volta(agora: datetime | None = None) -> list[str]:
    """Fecha os meses que chegaram no fechamento, para cada conta com a Shopee conectada."""
    from licencas.models import ContaAppfiliado

    agora = agora or timezone.now()
    meses = meses_para_fechar(agora)
    if not meses:
        return []
    linhas = []
    contas = (ContaAppfiliado.objects.exclude(shopee_app_id="").exclude(shopee_secret_cifrado="")
              .filter(shopee_validado_em__isnull=False))
    for ano, mes in meses:
        ja_fechadas = set(FechamentoMes.objects.filter(ano=ano, mes=mes).values_list("conta_id", flat=True))
        for conta in contas.exclude(pk__in=ja_fechadas):
            chave = (conta.pk, ano, mes)
            if chave in _ultimo_erro and agora - _ultimo_erro[chave] < ESPERA_DEPOIS_DE_ERRO:
                continue
            try:
                fechamento = fechar(conta, ano, mes, agora)
            except Exception as erro:  # noqa: BLE001 - Shopee fora do ar, credencial trocada: tenta mais tarde
                _ultimo_erro[chave] = agora
                logger.warning("Fechamento de %02d/%s da conta %s falhou: %s", mes, ano, conta.pk, erro)
                linhas.append(f"{conta.email}: fechamento de {mes:02d}/{ano} falhou - {erro}")
                continue
            _ultimo_erro.pop(chave, None)
            linhas.append(f"{conta.email}: {mes:02d}/{ano} fechado em R$ {fechamento.validado:.2f}")
    return linhas
