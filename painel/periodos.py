# -*- coding: utf-8 -*-
"""Períodos prontos (hoje, esta semana, este mês...) e agrupamento dos
resultados diários por dia, semana ou mês."""

from datetime import date, timedelta

PRESETS = [
    ("hoje", "Hoje"),
    ("ontem", "Ontem"),
    ("7dias", "Últimos 7 dias"),
    ("semana", "Esta semana"),
    ("semana_passada", "Semana passada"),
    ("mes", "Este mês"),
    ("mes_passado", "Mês passado"),
    ("30dias", "Últimos 30 dias"),
    ("personalizado", "Personalizado"),
]

AGRUPAMENTOS = [("dia", "Por dia"), ("semana", "Por semana"), ("mes", "Por mês")]

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

CAMPOS_SOMADOS = ("pedidos", "faturamento", "comissao_estimada", "comissao_validada")


def primeiro_dia_do_mes(dia: date) -> date:
    return dia.replace(day=1)


def ultimo_dia_do_mes(dia: date) -> date:
    proximo = (dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return proximo - timedelta(days=1)


def intervalo_do_preset(chave: str, hoje: date) -> tuple[date, date]:
    """(início, fim) do período pronto. Semana começa na segunda-feira."""
    if chave == "hoje":
        return hoje, hoje
    if chave == "ontem":
        ontem = hoje - timedelta(days=1)
        return ontem, ontem
    if chave == "7dias":
        return hoje - timedelta(days=6), hoje
    if chave == "30dias":
        return hoje - timedelta(days=29), hoje
    if chave == "semana":
        return inicio_da_semana(hoje), hoje
    if chave == "semana_passada":
        fim = inicio_da_semana(hoje) - timedelta(days=1)  # o sábado da semana passada
        return fim - timedelta(days=6), fim
    if chave == "mes_passado":
        fim = primeiro_dia_do_mes(hoje) - timedelta(days=1)
        return primeiro_dia_do_mes(fim), fim
    # "mes" e qualquer chave desconhecida
    return primeiro_dia_do_mes(hoje), hoje


def inicio_da_semana(dia: date) -> date:
    """Domingo da semana do dia (no Brasil a semana começa no domingo, como no calendário)."""
    return dia - timedelta(days=(dia.weekday() + 1) % 7)


def agrupamento_sugerido(inicio: date, fim: date) -> str:
    dias = (fim - inicio).days + 1
    if dias <= 31:
        return "dia"
    if dias <= 120:
        return "semana"
    return "mes"


def _rotulo_dia(dia: date) -> str:
    return dia.strftime("%d/%m")


def agrupar(linhas_diarias, modo: str):
    """Soma as linhas diárias (com a chave "dia") em grupos.

    Devolve [{"inicio", "fim", "rotulo", "rotulo_curto", pedidos,
    faturamento, comissao_estimada, comissao_validada}], na ordem."""
    grupos = {}
    for linha in linhas_diarias:
        dia = linha["dia"]
        if modo == "semana":
            chave = inicio_da_semana(dia)
        elif modo == "mes":
            chave = primeiro_dia_do_mes(dia)
        else:
            chave = dia
        grupo = grupos.setdefault(chave, {"inicio": dia, "fim": dia, **{c: 0 for c in CAMPOS_SOMADOS}})
        grupo["inicio"] = min(grupo["inicio"], dia)
        grupo["fim"] = max(grupo["fim"], dia)
        for campo in CAMPOS_SOMADOS:
            grupo[campo] += linha.get(campo) or 0

    resultado = []
    for chave in sorted(grupos):
        grupo = grupos[chave]
        if modo == "semana":
            grupo["rotulo"] = f"{_rotulo_dia(grupo['inicio'])} a {_rotulo_dia(grupo['fim'])}"
            grupo["rotulo_curto"] = _rotulo_dia(grupo["inicio"])
        elif modo == "mes":
            grupo["rotulo"] = f"{MESES[chave.month - 1].capitalize()}/{chave.year}"
            grupo["rotulo_curto"] = MESES[chave.month - 1][:3]
        else:
            grupo["rotulo"] = chave.strftime("%d/%m/%Y")
            grupo["rotulo_curto"] = chave.strftime("%d")
        resultado.append(grupo)
    return resultado


def descrever_periodo(inicio: date, fim: date) -> str:
    if inicio == fim:
        return inicio.strftime("%d/%m/%Y")
    return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
