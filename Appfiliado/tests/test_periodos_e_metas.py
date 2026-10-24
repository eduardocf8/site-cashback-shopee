from datetime import date, datetime, timedelta

import pytest

import metas
import periodos
from afiliados import ConversorAfiliados


# --- periodos ---------------------------------------------------------------------

HOJE = date(2026, 10, 18)  # domingo


@pytest.mark.parametrize(
    "chave, esperado",
    [
        ("hoje", (date(2026, 10, 18), date(2026, 10, 18))),
        ("ontem", (date(2026, 10, 17), date(2026, 10, 17))),
        ("7dias", (date(2026, 10, 12), date(2026, 10, 18))),
        ("semana", (date(2026, 10, 12), date(2026, 10, 18))),
        ("semana_passada", (date(2026, 10, 5), date(2026, 10, 11))),
        ("mes", (date(2026, 10, 1), date(2026, 10, 18))),
        ("mes_passado", (date(2026, 9, 1), date(2026, 9, 30))),
        ("30dias", (date(2026, 9, 19), date(2026, 10, 18))),
    ],
)
def test_intervalo_do_preset(chave, esperado):
    assert periodos.intervalo_do_preset(chave, HOJE) == esperado


def test_mes_passado_em_janeiro_volta_pra_dezembro():
    assert periodos.intervalo_do_preset("mes_passado", date(2027, 1, 10)) == (date(2026, 12, 1), date(2026, 12, 31))


def _linhas(inicio, dias):
    return [
        {"dia": inicio + timedelta(days=i), "pedidos": 1, "faturamento": 10.0,
         "comissao_estimada": 1.0, "comissao_validada": 0.5}
        for i in range(dias)
    ]


def test_agrupar_por_semana_comeca_na_segunda():
    grupos = periodos.agrupar(_linhas(date(2026, 10, 1), 18), "semana")  # qui 01 a dom 18
    assert [g["inicio"] for g in grupos] == [date(2026, 10, 1), date(2026, 10, 5), date(2026, 10, 12)]
    assert grupos[0]["pedidos"] == 4  # qui, sex, sáb, dom
    assert grupos[1]["faturamento"] == 70.0
    assert grupos[1]["rotulo"] == "05/10 a 11/10"


def test_agrupar_por_mes():
    grupos = periodos.agrupar(_linhas(date(2026, 9, 29), 4), "mes")
    assert [g["rotulo"] for g in grupos] == ["Setembro/2026", "Outubro/2026"]
    assert grupos[0]["comissao_validada"] == 1.0


def test_agrupamento_sugerido():
    assert periodos.agrupamento_sugerido(date(2026, 10, 1), date(2026, 10, 31)) == "dia"
    assert periodos.agrupamento_sugerido(date(2026, 8, 1), date(2026, 10, 18)) == "semana"


# --- metas ------------------------------------------------------------------------

FAIXAS = [
    {"percentual": 125, "faturamento": 37500, "bonus": 500},
    {"percentual": 100, "faturamento": 30000, "bonus": 300},
    {"percentual": 150, "faturamento": 45000, "bonus": 800},
    {"percentual": 0, "faturamento": 0, "bonus": 0},  # linha vazia do formulário
]


def test_normalizar_ordena_e_tira_vazias():
    assert [m["percentual"] for m in metas.normalizar(FAIXAS)] == [100, 125, 150]


def test_situacao_no_meio_do_mes():
    s = metas.situacao(31000, FAIXAS, date(2026, 10, 18), 2026, 10)
    assert [m["percentual"] for m in s["batidas"]] == [100]
    assert s["bonus_garantido"] == 300
    assert s["proxima"]["percentual"] == 125
    assert s["falta"] == 6500
    # 31.000 em 17 dias com dados (hoje a Shopee ainda não mostrou) -> ~56.529
    # em 31 dias: passa da faixa de 150%
    assert s["projecao"] == pytest.approx(31000 / 17 * 31)
    assert s["faixa_projetada"]["percentual"] == 150
    assert s["dias_restantes"] == 14  # 18 a 31, contando hoje
    assert s["por_dia"] == pytest.approx(6500 / 14)


def test_situacao_sem_metas():
    s = metas.situacao(1000, [], date(2026, 10, 18), 2026, 10)
    assert s["proxima"] is None
    assert s["fracao"] == 0


def test_primeiro_dia_do_mes_nao_projeta():
    s = metas.situacao(0, FAIXAS, date(2026, 10, 1), 2026, 10)
    assert s["projecao"] == 0
    assert s["dias_restantes"] == 31


def test_mes_fechado_nao_projeta():
    s = metas.situacao(40000, FAIXAS, date(2026, 11, 2), 2026, 10)
    assert s["projecao"] == 40000
    assert s["dias_restantes"] == 0
    assert s["por_dia"] == 0


def test_metas_do_mes_pela_chave():
    salvas = {"2026-10": FAIXAS}
    assert len(metas.metas_do_mes(salvas, 2026, 10)) == 3
    assert metas.metas_do_mes(salvas, 2026, 11) == []


# --- resultados por periodo (API) -------------------------------------------------

def _ts(ano, mes, dia, hora=12):
    return int(datetime(ano, mes, dia, hora).timestamp())


def test_resultados_periodo_separa_estimada_validada_e_faturamento(monkeypatch):
    conversor = ConversorAfiliados()
    nodes = [
        {   # comprado e validado dentro do período
            "purchaseTime": _ts(2026, 10, 5), "utmContent": "grupo", "netCommission": "5,00",
            "orders": [{"orderId": "A", "orderStatus": "COMPLETED", "items": [
                {"itemPrice": "50,00", "qty": 1, "itemTotalCommission": "5,00", "completeTime": _ts(2026, 10, 9)}]}],
        },
        {   # pendente: entra no faturamento e na estimada, não na validada
            "purchaseTime": _ts(2026, 10, 6), "utmContent": "canal", "netCommission": "3,00",
            "orders": [{"orderId": "B", "orderStatus": "PENDING", "items": [
                {"itemPrice": "30,00", "qty": 2, "itemTotalCommission": "3,00"}]}],
        },
        {   # comprado antes, validado dentro: só a validada
            "purchaseTime": _ts(2026, 9, 20), "utmContent": "grupo", "netCommission": "2,00",
            "orders": [{"orderId": "C", "orderStatus": "COMPLETED", "items": [
                {"itemPrice": "20,00", "qty": 1, "itemTotalCommission": "2,00", "completeTime": _ts(2026, 10, 7)}]}],
        },
        {   # cancelado: não conta em nada
            "purchaseTime": _ts(2026, 10, 8), "utmContent": "grupo", "netCommission": "9,00",
            "orders": [{"orderId": "D", "orderStatus": "CANCELLED", "items": [
                {"itemPrice": "90,00", "qty": 1, "itemTotalCommission": "9,00"}]}],
        },
    ]
    monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

    r = conversor.obter_resultados_periodo(date(2026, 10, 5), date(2026, 10, 11))

    assert r["resumo"]["faturamento"] == 110.0
    assert r["resumo"]["pedidos"] == 2
    assert r["resumo"]["comissao_estimada"] == 8.0
    assert r["resumo"]["comissao_validada"] == 7.0
    assert len(r["diario"]) == 7
    por_dia = {l["dia"]: l for l in r["diario"]}
    assert por_dia[date(2026, 10, 9)]["comissao_validada"] == 5.0
    assert por_dia[date(2026, 10, 6)]["comissao_estimada"] == 3.0
    sub_ids = {l["sub_id"]: l["comissao"] for l in r["sub_ids"]}
    # O pedido cancelado entra no Sub ID "grupo" com comissão zerada.
    assert sub_ids == {"grupo": 5.0, "canal": 3.0}
