from datetime import datetime, timedelta

import pytest

from afiliados import ConversorAfiliados


@pytest.fixture
def conversor():
    return ConversorAfiliados()


def _ts(ano, mes, dia, hora=12):
    return int(datetime(ano, mes, dia, hora, 0, 0).timestamp())


class TestObterFaturamentoValidado:
    def test_pedido_completed_comprado_no_mes_conta_faturamento_e_comissao(self, conversor, monkeypatch):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 5),
                "orders": [
                    {
                        "orderId": "ORD-1",
                        "orderStatus": "COMPLETED",
                        "items": [
                            {
                                "itemPrice": "100,00",
                                "qty": 2,
                                "itemTotalCommission": "10,00",
                                "completeTime": _ts(2026, 9, 10),
                            }
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 1
        assert resultado["resumo"]["faturamento"] == 200.0
        assert resultado["resumo"]["comissao"] == 10.0

    def test_pedido_pending_conta_no_faturamento_mas_nao_na_comissao(self, conversor, monkeypatch):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 5),
                "orders": [
                    {
                        "orderId": "ORD-2",
                        "orderStatus": "PENDING",
                        "items": [
                            {
                                "itemPrice": "50,00",
                                "qty": 1,
                                "itemTotalCommission": "5,00",
                                "completeTime": None,
                            }
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 1
        assert resultado["resumo"]["faturamento"] == 50.0
        # PENDING nunca e COMPLETED, entao nao entra na comissao validada -
        # mesmo que (por erro de dado) tivesse um completeTime preenchido.
        assert resultado["resumo"]["comissao"] == 0.0

    def test_pedido_cancelled_nao_conta_em_nada(self, conversor, monkeypatch):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 5),
                "orders": [
                    {
                        "orderId": "ORD-3",
                        "orderStatus": "CANCELLED",
                        "items": [
                            {"itemPrice": "999,00", "qty": 1, "itemTotalCommission": "99,00"}
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 0
        assert resultado["resumo"]["faturamento"] == 0.0
        assert resultado["resumo"]["comissao"] == 0.0

    def test_pedido_comprado_antes_do_mes_mas_validado_dentro_so_conta_comissao(
        self, conversor, monkeypatch
    ):
        # Comprado em agosto, mas validou (completeTime) em setembro: nao
        # deve entrar no faturamento de setembro (foi comprado em agosto),
        # mas a comissao validada de setembro deve incluir esse pedido.
        nodes = [
            {
                "purchaseTime": _ts(2026, 8, 20),
                "orders": [
                    {
                        "orderId": "ORD-4",
                        "orderStatus": "COMPLETED",
                        "items": [
                            {
                                "itemPrice": "300,00",
                                "qty": 1,
                                "itemTotalCommission": "30,00",
                                "completeTime": _ts(2026, 9, 2),
                            }
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 0
        assert resultado["resumo"]["faturamento"] == 0.0
        assert resultado["resumo"]["comissao"] == 30.0

    def test_pedido_comprado_no_mes_mas_ainda_nao_validou_so_conta_faturamento(
        self, conversor, monkeypatch
    ):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 28),
                "orders": [
                    {
                        "orderId": "ORD-5",
                        "orderStatus": "COMPLETED",
                        "items": [
                            {
                                "itemPrice": "80,00",
                                "qty": 1,
                                "itemTotalCommission": "8,00",
                                "completeTime": _ts(2026, 10, 5),
                            }
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 1
        assert resultado["resumo"]["faturamento"] == 80.0
        assert resultado["resumo"]["comissao"] == 0.0

    def test_relatorio_diario_agrupa_pelo_dia_certo(self, conversor, monkeypatch):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 3),
                "orders": [
                    {
                        "orderId": "ORD-6",
                        "orderStatus": "COMPLETED",
                        "items": [
                            {
                                "itemPrice": "100,00",
                                "qty": 1,
                                "itemTotalCommission": "10,00",
                                "completeTime": _ts(2026, 9, 7),
                            }
                        ],
                    }
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)
        diario_por_dia = {linha["dia"]: linha for linha in resultado["diario"]}

        dia_compra = datetime(2026, 9, 3).date()
        dia_validacao = datetime(2026, 9, 7).date()

        assert diario_por_dia[dia_compra]["pedidos"] == 1
        assert diario_por_dia[dia_compra]["faturamento"] == 100.0
        assert diario_por_dia[dia_compra]["comissao"] == 0.0

        assert diario_por_dia[dia_validacao]["pedidos"] == 0
        assert diario_por_dia[dia_validacao]["faturamento"] == 0.0
        assert diario_por_dia[dia_validacao]["comissao"] == 10.0

        # Todos os dias do mes devem aparecer no relatorio, mesmo sem atividade.
        assert len(resultado["diario"]) == 30

    def test_mes_totalmente_fora_da_janela_da_api_levanta_excecao(self, conversor, monkeypatch):
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: [])
        with pytest.raises(Exception):
            conversor.obter_faturamento_validado(2020, 1)

    def test_multiplos_pedidos_mesma_conversao_somam_faturamento(self, conversor, monkeypatch):
        nodes = [
            {
                "purchaseTime": _ts(2026, 9, 1),
                "orders": [
                    {
                        "orderId": "ORD-7",
                        "orderStatus": "COMPLETED",
                        "items": [{"itemPrice": "10,00", "qty": 1, "itemTotalCommission": "1,00"}],
                    },
                    {
                        "orderId": "ORD-8",
                        "orderStatus": "COMPLETED",
                        "items": [{"itemPrice": "20,00", "qty": 1, "itemTotalCommission": "2,00"}],
                    },
                ],
            }
        ]
        monkeypatch.setattr(conversor, "executar_relatorio_paginado", lambda *a, **k: nodes)

        resultado = conversor.obter_faturamento_validado(2026, 9)

        assert resultado["resumo"]["pedidos"] == 2
        assert resultado["resumo"]["faturamento"] == 30.0
