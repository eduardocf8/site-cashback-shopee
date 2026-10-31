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
    def test_o_resultado_fecha_no_ultimo_dia_do_mes_seguinte(self):
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 10, 31)), (telas.PREVIA, date(2026, 11, 30)))
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 11, 1)), (telas.FECHAMENTO, date(2026, 11, 30)))
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 11, 30))[0], telas.FECHAMENTO)
        self.assertEqual(telas.fase_da_meta(2026, 10, date(2026, 12, 1))[0], telas.FECHADA)
        self.assertEqual(telas.fase_da_meta(2026, 12, date(2027, 1, 5)), (telas.FECHAMENTO, date(2027, 1, 31)))  # virada do ano

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
        self.assertEqual((m["faturamento"], m["fecha_em"]), (53000.0, date(2026, 12, 31)))
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
        for texto in ("Setembro/2026", "Fechada em 31/10", "Outubro/2026", "Em fechamento até 30/11", "Novembro/2026",
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
        self.assertIn("É uma prévia: o resultado oficial de Novembro/2026 fecha em 31/12", texto)


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
        with mock.patch("painel.telas.hoje", return_value=date(2026, 11, 3)):
            html = self.client.get("/resultados/conferir/?mes=2026-09").content.decode()
        self.assertIn("3. Pedidos validados em Setembro/2026", html)
        self.assertIn("R$ 3.000,00", html)
