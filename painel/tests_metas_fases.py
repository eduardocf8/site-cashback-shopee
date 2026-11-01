"""Metas em três fases: prévia (mês atual), em fechamento (mês passado, até o último dia do mês
atual) e fechada (depois disso, só o validado)."""

from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from . import telas
from .models import MetaMensal, ResultadoDiario, SincronizacaoResultados, VendaItem
from .tests import BasePainel


def _aware(*partes) -> datetime:
    return datetime(*partes, tzinfo=timezone.get_current_timezone())


FAIXAS = [{"percentual": 100, "faturamento": 52000, "bonus": 300}, {"percentual": 125, "faturamento": 65000, "bonus": 500}]


class BaseFases(BasePainel):
    def setUp(self):
        super().setUp()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        SincronizacaoResultados.objects.create(conta=self.conta, vendas_desde=_aware(2026, 8, 1))
        self.n = 0

    def venda(self, dia: date, valor: str, situacao: str):
        self.n += 1
        VendaItem.objects.create(conta=self.conta, conversao_id=str(self.n), pedido_id=str(self.n), valor=Decimal(valor),
                                 situacao=situacao, comprado_em=_aware(dia.year, dia.month, dia.day, 12))


class TestFases(BaseFases):
    def test_o_resultado_fecha_30_dias_depois_do_ultimo_dia(self):
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 10, 31)), (telas.PREVIA, date(2026, 11, 30)))
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 11, 1)), (telas.FECHAMENTO, date(2026, 11, 30)))
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 11, 30))[0], telas.FECHAMENTO)  # fecha às 11h
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 12, 1))[0], telas.FECHADA)
        self.assertEqual(telas.fase_da_meta(2026, 9, date(2026, 10, 31)), (telas.FECHADA, date(2026, 10, 30)))
        self.assertEqual(telas.fase_da_meta(2026, 12, date(2027, 1, 5)), (telas.FECHAMENTO, date(2027, 1, 30)))  # virada do ano
        self.assertEqual(telas.fase_da_meta(2027, 1, date(2027, 2, 5))[1], date(2027, 3, 2))

    def test_em_fechamento_separa_validado_pendente_e_cancelado(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=FAIXAS)
        self.venda(date(2026, 10, 5), "41230", VendaItem.CONCLUIDO)
        self.venda(date(2026, 10, 20), "11920", VendaItem.PENDENTE)
        self.venda(date(2026, 10, 25), "753.30", VendaItem.CANCELADO)
        self.venda(date(2026, 11, 2), "9999", VendaItem.CONCLUIDO)  # de novembro: não entra em outubro
        m = telas.situacao_meta(self.conta, 2026, 10, date(2026, 11, 10))
        self.assertTrue(m["em_fechamento"])
        self.assertEqual((m["faturamento"], m["pendente"], m["cancelado"], m["possivel"]), (41230.0, 11920.0, 753.3, 53150.0))
        self.assertEqual([f["estado"] for f in m["faixas_tela"]], ["possivel", "fora"])
        self.assertEqual((m["faixa_em_jogo"]["nome"], m["falta_validar"], m["pode_perder"]), ("100%", 10770.0, 1150.0))
        self.assertEqual(m["bonus_garantido"], 0)  # nada garantido ainda
        self.assertEqual(m["frase_possivel"], "Se todo o pendente for validado, outubro chega a R$ 53.150,00 e bate a "
                                              "faixa 100% (bônus R$ 300). A faixa 125% ficaria a R$ 11.850,00.")

    def test_frase_quando_nao_chega_ou_ja_esta_garantida(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=FAIXAS)
        self.venda(date(2026, 10, 5), "30000", VendaItem.CONCLUIDO)
        self.venda(date(2026, 10, 6), "5000", VendaItem.PENDENTE)
        m = telas.situacao_meta(self.conta, 2026, 10, date(2026, 11, 10))
        self.assertEqual(m["frase_possivel"], "Se todo o pendente for validado, outubro chega a R$ 35.000,00, ainda abaixo "
                                              "da primeira faixa (faltariam R$ 17.000,00 para a 100%).")
        self.venda(date(2026, 10, 7), "25000", VendaItem.CONCLUIDO)  # validado 55.000: a 100% já está garantida
        m = telas.situacao_meta(self.conta, 2026, 10, date(2026, 11, 10))
        self.assertEqual(m["frase_possivel"], "Se todo o pendente for validado, outubro chega a R$ 60.000,00 e continua "
                                              "na faixa 100% (bônus R$ 300), que já está garantida. A faixa 125% ficaria a R$ 5.000,00.")

    def test_fechada_conta_so_o_validado(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=9, faixas=FAIXAS)
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 9, 10), faturamento=Decimal(60000))  # estimado
        self.venda(date(2026, 9, 10), "52430", VendaItem.CONCLUIDO)
        self.venda(date(2026, 9, 11), "7570", VendaItem.CANCELADO)
        m = telas.situacao_meta(self.conta, 2026, 9, date(2026, 11, 3))
        self.assertTrue(m["fechada"])
        self.assertEqual((m["faturamento"], m["cancelado"], m["bonus_garantido"]), (52430.0, 7570.0, 300))
        self.assertEqual([f["estado"] for f in m["faixas_tela"]], ["batida", "fora"])

    def test_previa_usa_o_estimado(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=11, faixas=FAIXAS)
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 11, 2), faturamento=Decimal(53000))
        m = telas.situacao_meta(self.conta, 2026, 11, date(2026, 11, 10))
        self.assertTrue(m["previa"])
        self.assertEqual((m["faturamento"], m["fecha_em"]), (53000.0, date(2026, 12, 30)))
        self.assertEqual(m["faixas_tela"][0]["estado"], "batida")

    def test_sem_os_pedidos_desde_o_comeco_do_mes_avisa(self):
        SincronizacaoResultados.objects.filter(conta=self.conta).update(vendas_desde=_aware(2026, 10, 15))
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=FAIXAS)
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 2), faturamento=Decimal(50000))
        m = telas.situacao_meta(self.conta, 2026, 10, date(2026, 11, 10))
        self.assertEqual((m["sem_pedidos_guardados"], m["em_fechamento"], m["faturamento"]), (True, False, 50000.0))


@mock.patch("painel.telas.hoje", return_value=date(2026, 11, 10))
class TestTelasComTresMeses(BaseFases):
    def setUp(self):
        super().setUp()
        self.entrar()
        for mes in (9, 10, 11):
            MetaMensal.objects.create(conta=self.conta, ano=2026, mes=mes, faixas=FAIXAS)
        self.venda(date(2026, 9, 5), "52430", VendaItem.CONCLUIDO)
        self.venda(date(2026, 10, 5), "41230", VendaItem.CONCLUIDO)
        self.venda(date(2026, 10, 6), "11920", VendaItem.PENDENTE)
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 11, 2), faturamento=Decimal(8450))

    def test_metas_detalha_os_tres_meses(self, _):
        html = self.client.get("/metas/").content.decode()
        for texto in ("Setembro/2026", "Fechada em 30/10", "Outubro/2026", "Em fechamento até 30/11", "Novembro/2026",
                      "Prévia", "possível: depende dos pendentes", "Bônus de Setembro/2026"):
            self.assertIn(texto, html)
        self.assertEqual(html.count('class="selo-fase'), 3)

    def test_inicio_mostra_os_outros_meses_em_linhas(self, _):
        html = self.client.get("/").content.decode()
        self.assertIn("Outubro/2026 em fechamento até 30/11:", html)
        self.assertIn("Setembro/2026 fechada:", html)

    def test_email_diario_com_as_fases(self, _):
        from . import relatorio

        dados = relatorio.montar(self.conta, date(2026, 11, 10))
        self.assertTrue(dados["meta"]["previa"])
        self.assertEqual([m["nome_mes"] for m in dados["outros_meses"]], ["Outubro/2026", "Setembro/2026"])
        from django.template.loader import render_to_string

        texto = render_to_string("painel/email_relatorio.txt", dados)
        self.assertIn("Outubro/2026 em fechamento até 30/11: garantido", texto)
        self.assertIn("É uma prévia: o resultado oficial de Novembro/2026 fecha em 30/12 às 11h", texto)


class TestConferenciaDoFaturamento(BaseFases):
    def item(self, compra: date, valor: int, situacao: str, validado: date | None = None):
        self.n += 1
        VendaItem.objects.create(conta=self.conta, conversao_id=f"c{self.n}", pedido_id=f"p{self.n}", valor=Decimal(valor),
                                 situacao=situacao, comprado_em=_aware(compra.year, compra.month, compra.day, 12),
                                 concluido_em=_aware(validado.year, validado.month, validado.day, 12) if validado else None)

    def test_tres_jeitos_de_contar_o_mes(self):
        self.item(date(2026, 8, 25), 1000, VendaItem.CONCLUIDO, date(2026, 9, 5))  # comprado em agosto, validado em setembro
        self.item(date(2026, 9, 3), 2000, VendaItem.CONCLUIDO, date(2026, 9, 20))
        self.item(date(2026, 9, 25), 4000, VendaItem.CONCLUIDO, date(2026, 10, 8))  # comprado em setembro, validado em outubro
        self.item(date(2026, 9, 28), 500, VendaItem.PENDENTE)
        self.item(date(2026, 9, 29), 300, VendaItem.CANCELADO)
        c = telas.conferencia_faturamento(self.conta, 2026, 9)
        self.assertEqual(c["feitos"]["valor"], 6500)  # 2.000 + 4.000 + 500
        self.assertEqual(c["feitos_validados"]["valor"], 6000)
        self.assertEqual(c["feitos_cancelados"]["valor"], 300)
        self.assertEqual((c["validados_no_mes"]["valor"], c["validados_no_mes"]["pedidos"]), (3000, 2))  # 1.000 + 2.000
        self.assertEqual(c["validados_no_mes_comprados_antes"]["valor"], 1000)

        self.entrar()
        self.assertEqual(self.client.get("/resultados/conferir/?mes=2026-09").status_code, 404)  # escondida
        self.conta.beta_conferir_faturamento = True
        self.conta.save()
        with mock.patch("painel.telas.hoje", return_value=date(2026, 11, 3)):
            html = self.client.get("/resultados/conferir/?mes=2026-09").content.decode()
        self.assertIn("3. Pedidos validados em Setembro/2026", html)
        self.assertIn("R$ 3.000,00", html)

    def test_busca_direto_na_shopee_pela_data_de_validacao(self):
        from . import cripto, resultados

        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("segredo")
        self.conta.beta_conferir_faturamento = True
        self.conta.save()

        def ts(*partes):
            return int(_aware(*partes).timestamp())

        def item(preco, pago, validado=None, reembolso=0, canal="Social Media"):
            return {"itemPrice": str(preco), "qty": 1, "actualAmount": str(pago), "refundAmount": str(reembolso),
                    "completeTime": ts(*validado) if validado else None, "channelType": canal}

        validados = [  # comprado em julho, validado em setembro; e um validado em outubro (fora)
            {"purchaseTime": ts(2026, 7, 20), "orders": [{"orderId": "A", "orderStatus": "COMPLETED", "items": [
                item(1000, 900, (2026, 9, 2)), item(500, 450, (2026, 10, 1))]}]},
            {"purchaseTime": ts(2026, 9, 1), "orders": [{"orderId": "B", "orderStatus": "COMPLETED", "items": [
                item(200, 200, (2026, 9, 15), reembolso=50)]}]},
        ]
        feitos = [
            {"purchaseTime": ts(2026, 9, 1), "orders": [
                {"orderId": "B", "orderStatus": "COMPLETED", "items": [item(200, 200, (2026, 9, 15), reembolso=50)]},
                {"orderId": "E", "orderStatus": "COMPLETED", "items": [item(100, 80, (2026, 10, 2), canal="Shopee Video")]},
                {"orderId": "C", "orderStatus": "PENDING", "items": [item(300, 280)]},
                {"orderId": "D", "orderStatus": "CANCELLED", "items": [item(90, 90)]}]},
        ]

        def paginas(app_id, secret, inicio, fim, data="purchaseTime", itens_extras=()):
            self.assertEqual((app_id, secret, inicio, fim), ("123", "segredo", ts(2026, 9, 1, 0), ts(2026, 10, 1, 0) - 1))
            self.assertIn("channelType", itens_extras)
            yield validados if data == "completeTime" else feitos

        with mock.patch.object(resultados, "paginas_de_conversoes", side_effect=paginas):
            r = resultados.conferencia_na_shopee(self.conta, date(2026, 9, 1), date(2026, 9, 30))
            v, f = r["por_validacao"], r["por_compra"]
            self.assertEqual((v["total"]["preco"], v["total"]["pago"], v["total"]["pago_sem_reembolso"], v["total"]["pedidos"]),
                             (Decimal(1200), Decimal(1100), Decimal(1050), 2))
            self.assertEqual(v["compra_mais_antiga"], date(2026, 7, 20))
            # o jeito da meta da Shopee: comprados no mês e validados (mesmo que a validação seja em outubro)
            self.assertEqual((f["validados"]["pago"], f["validados"]["pago_sem_reembolso"], f["validados"]["pedidos"]),
                             (Decimal(280), Decimal(230), 2))
            self.assertEqual([(canal, g["pago"]) for canal, g in f["canais"]],
                             [("Social Media", Decimal(200)), ("Shopee Video", Decimal(80))])
            self.assertEqual((f["pendentes"]["pago"], f["cancelados"]["preco"], f["total"]["pago"], f["total"]["pedidos"]),
                             (Decimal(280), Decimal(90), Decimal(560), 3))

            self.entrar()
            with mock.patch("painel.telas.hoje", return_value=date(2026, 10, 31)):
                html = self.client.get("/resultados/conferir/?mes=2026-09").content.decode()
                self.assertIn("Buscar Setembro/2026 na Shopee", html)
                html = self.client.get("/resultados/conferir/?mes=2026-09&shopee=1").content.decode()
        self.assertIn("Feitos em Setembro/2026 e validados", html)
        self.assertIn("<strong>R$ 280,00</strong>", html)
        self.assertIn("canal: Shopee Video", html)
        self.assertIn("compra mais antiga: 20/07/2026", html)

    def test_erro_da_shopee_aparece_na_pagina(self):
        from links.shopee_client import ShopeeAPIError

        from . import cripto, resultados

        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("segredo")
        self.conta.save()
        with mock.patch.object(resultados, "paginas_de_conversoes", side_effect=ShopeeAPIError("Unknown argument completeTimeStart")):
            r = resultados.conferencia_na_shopee(self.conta, date(2026, 9, 1), date(2026, 9, 30))
        self.assertIn("completeTimeStart", r["por_validacao"]["erro"])


class TestValorPago(BaseFases):
    def test_valor_pago_menos_reembolso(self):
        from . import resultados

        self.assertEqual(resultados.valor_do_item({"itemPrice": "100", "qty": 2, "actualAmount": "180.50", "refundAmount": "30"}), 150.5)
        self.assertEqual(resultados.valor_do_item({"itemPrice": "100", "qty": 2}), 200.0)  # sem o valor pago: preço x qtd
        conversao = {"purchaseTime": int(_aware(2026, 9, 3, 12).timestamp()), "conversionId": "1", "orders": [
            {"orderId": "A", "orderStatus": "COMPLETED", "items": [{"itemPrice": "100", "qty": 2, "actualAmount": "180.50",
                                                                     "refundAmount": "30", "itemTotalCommission": "10"}]}]}
        por_dia, _ = resultados.calcular_por_dia([conversao])
        self.assertEqual(por_dia[date(2026, 9, 3)]["faturamento"], 150.5)
        self.assertEqual(resultados.itens_vendidos(self.conta, [conversao])[0].valor, Decimal("150.50"))


class TestFechamento(BaseFases):
    def setUp(self):
        super().setUp()
        from . import cripto, fechamento

        fechamento._ultimo_erro.clear()
        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("segredo")
        self.conta.save()

    def conversoes(self):
        def item(pago, reembolso=0):
            return {"itemPrice": str(pago + 10), "qty": 1, "actualAmount": str(pago), "refundAmount": str(reembolso)}

        return [{"purchaseTime": int(_aware(2026, 9, 10, 12).timestamp()), "orders": [
            {"orderId": "A", "orderStatus": "COMPLETED", "items": [item(50000), item(3000, reembolso=500)]},
            {"orderId": "B", "orderStatus": "PENDING", "items": [item(1200)]},
            {"orderId": "C", "orderStatus": "CANCELLED", "items": [item(700)]}]}]

    def test_meses_que_fecham(self):
        from . import fechamento

        self.assertEqual(fechamento.meses_para_fechar(_aware(2026, 10, 30, 10, 59)), [])
        self.assertEqual(fechamento.meses_para_fechar(_aware(2026, 10, 30, 11, 0)), [(2026, 9)])
        self.assertEqual(fechamento.meses_para_fechar(_aware(2026, 11, 6, 10, 0)), [(2026, 9)])
        self.assertEqual(fechamento.meses_para_fechar(_aware(2026, 11, 7, 11, 0)), [])  # atrasado demais
        self.assertEqual(fechamento.meses_para_fechar(_aware(2026, 11, 30, 11, 5)), [(2026, 10)])

    def test_guarda_o_fechamento_e_ele_nao_muda_mais(self):
        from . import fechamento, resultados
        from .models import FechamentoMes

        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=9, faixas=FAIXAS)
        agora = _aware(2026, 10, 30, 11, 2)
        self.assertEqual(fechamento.uma_volta(_aware(2026, 10, 30, 10, 30)), [])  # antes das 11h
        with mock.patch.object(resultados, "paginas_de_conversoes", return_value=iter([self.conversoes()])) as buscar:
            linhas = fechamento.uma_volta(agora)
            self.assertEqual(fechamento.uma_volta(agora), [])  # já fechado: não busca de novo
        self.assertEqual(buscar.call_count, 1)
        self.assertEqual(buscar.call_args.kwargs["data"], "purchaseTime")
        self.assertIn("09/2026 fechado em R$ 52500.00", linhas[0])
        f = FechamentoMes.objects.get()
        self.assertEqual((f.validado, f.pendente, f.cancelado, f.pedidos), (Decimal(52500), Decimal(1200), Decimal(700), 1))

        # Pedidos validados depois do fechamento não mudam a meta.
        self.venda(date(2026, 9, 12), "9999", VendaItem.CONCLUIDO)
        m = telas.situacao_meta(self.conta, 2026, 9, date(2026, 10, 30))
        self.assertTrue(m["fechada"])
        self.assertEqual((m["faturamento"], m["pendente"], m["bonus_garantido"]), (52500.0, 1200.0, 300))
        self.assertEqual(m["fechado_em"], agora)

    def test_no_dia_do_fechamento_antes_de_guardar_continua_em_fechamento(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=9, faixas=FAIXAS)
        self.venda(date(2026, 9, 12), "40000", VendaItem.CONCLUIDO)
        m = telas.situacao_meta(self.conta, 2026, 9, date(2026, 10, 30))
        self.assertTrue(m["em_fechamento"])

    def test_falha_da_shopee_tenta_de_novo_depois(self):
        from links.shopee_client import ShopeeAPIError

        from . import fechamento, resultados
        from .models import FechamentoMes

        with mock.patch.object(resultados, "paginas_de_conversoes", side_effect=ShopeeAPIError("fora do ar")):
            self.assertIn("falhou", fechamento.uma_volta(_aware(2026, 10, 30, 11, 0))[0])
            self.assertEqual(fechamento.uma_volta(_aware(2026, 10, 30, 11, 10)), [])  # espera 30 min
        self.assertFalse(FechamentoMes.objects.exists())
        with mock.patch.object(resultados, "paginas_de_conversoes", return_value=iter([self.conversoes()])):
            self.assertIn("fechado", fechamento.uma_volta(_aware(2026, 10, 30, 11, 31))[0])
