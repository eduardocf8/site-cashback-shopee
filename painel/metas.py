# -*- coding: utf-8 -*-
"""Metas mensais de faturamento da Shopee - mesma lógica de Appfiliado/metas.py.

A Shopee costuma dar até 3 faixas por mês (ex: 100%, 125% e 150% de uma meta
base), cada uma com um bônus. Como elas mudam todo mês e não vêm pela API, a
pessoa cadastra à mão no painel (painel.models.MetaMensal):

    [{"percentual": 100, "faturamento": 30000.0, "bonus": 300.0}, ...]
"""

from datetime import date

from .periodos import ultimo_dia_do_mes


def chave_mes(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def normalizar(metas) -> list[dict]:
    """Só as faixas com faturamento > 0, da menor para a maior."""
    limpas = []
    for meta in metas or []:
        try:
            faturamento = float(meta.get("faturamento") or 0)
            bonus = float(meta.get("bonus") or 0)
            percentual = float(meta.get("percentual") or 0)
        except (AttributeError, TypeError, ValueError):
            continue
        if faturamento > 0:
            limpas.append({"percentual": percentual, "faturamento": faturamento, "bonus": bonus})
    return sorted(limpas, key=lambda m: m["faturamento"])


def nome_faixa(meta: dict) -> str:
    percentual = meta.get("percentual") or 0
    if percentual:
        return f"{percentual:g}%"
    return "Meta"


def situacao(faturamento: float, metas: list[dict], hoje: date, ano: int, mes: int) -> dict:
    """Onde o faturamento do mês está em relação às faixas.

    - batidas: faixas já alcançadas; bonus_garantido = bônus da maior delas.
    - proxima / falta: próxima faixa e quanto falta para ela.
    - projecao: faturamento no fim do mês mantendo o ritmo diário até hoje;
      faixa_projetada = maior faixa que essa projeção alcança.
    - por_dia: quanto precisa faturar por dia, nos dias que restam (contando
      hoje), para chegar na próxima faixa.
    - fracao: faturamento / maior faixa (para a barra de progresso)."""
    metas = normalizar(metas)
    inicio_mes = date(ano, mes, 1)
    fim_mes = ultimo_dia_do_mes(inicio_mes)
    dias_no_mes = fim_mes.day

    if hoje < inicio_mes:
        dias_passados = 0
    elif hoje > fim_mes:
        dias_passados = dias_no_mes
    else:
        dias_passados = hoje.day
    dias_restantes = dias_no_mes - dias_passados + (1 if inicio_mes <= hoje <= fim_mes else 0)

    if dias_passados and dias_passados < dias_no_mes:
        projecao = faturamento / dias_passados * dias_no_mes
    else:
        projecao = faturamento

    batidas = [m for m in metas if faturamento >= m["faturamento"]]
    pendentes = [m for m in metas if faturamento < m["faturamento"]]
    proxima = pendentes[0] if pendentes else None
    falta = (proxima["faturamento"] - faturamento) if proxima else 0.0
    projetadas = [m for m in metas if projecao >= m["faturamento"]]
    maior = metas[-1]["faturamento"] if metas else 0.0

    return {
        "metas": metas,
        "batidas": batidas,
        "bonus_garantido": batidas[-1]["bonus"] if batidas else 0.0,
        "proxima": proxima,
        "falta": falta,
        "projecao": projecao,
        "faixa_projetada": projetadas[-1] if projetadas else None,
        "por_dia": (falta / dias_restantes) if (proxima and dias_restantes > 0) else 0.0,
        "dias_restantes": dias_restantes,
        "fracao": (faturamento / maior) if maior else 0.0,
    }
