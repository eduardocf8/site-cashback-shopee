"""Resultados das ofertas do bot (bot_whatsapp/desempenho.py e a aba Resultados)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from painel.models import VendaItem
from painel.tests import BasePainel

from . import desempenho
from .models import ConfiguracaoOfertas, EnvioWhatsApp

SP = ZoneInfo("America/Sao_Paulo")


def momento(dia, hora=12, minuto=0):
    return datetime(2026, 10, dia, hora, minuto, tzinfo=SP)


class BaseDesempenho(BasePainel):
    def setUp(self):
        super().setUp()
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, sub_ids="", sub_ids_por_grupo={"a@g.us": "achadinhos1", "b@g.us": "achadinhos2"})
        self.n = 0

    def oferta(self, item, quando, grupos=("a@g.us", "b@g.us"), nome="Copo Térmico", origem=EnvioWhatsApp.OFERTA):
        """Um produto posto na fila de uma vez: um envio por grupo, criados juntos."""
        for jid in grupos:
            envio = EnvioWhatsApp.objects.create(conta=self.conta, destino=jid, destino_nome=f"Grupo {jid[0].upper()}",
                                                 item_id=item, produto=nome, origem=origem, estado=EnvioWhatsApp.ENVIADO,
                                                 enviado_em=quando + timedelta(seconds=30))
            EnvioWhatsApp.objects.filter(pk=envio.pk).update(criado_em=quando)

    def venda(self, item, quando, sub_id, comissao="10", situacao=VendaItem.PENDENTE, pedido=None):
        self.n += 1
        VendaItem.objects.create(conta=self.conta, conversao_id=str(self.n), pedido_id=pedido or f"p{self.n}", item_id=item,
                                 valor=Decimal(100), comissao=Decimal(comissao), situacao=situacao, sub_id=sub_id,
                                 comprado_em=quando, nome="Copo Térmico")


class TestCalculo(BaseDesempenho):
    def test_liga_a_venda_a_oferta_e_ao_grupo_pelo_sub_id(self):
        self.oferta("1", momento(10, 19))
        self.oferta("2", momento(11, 8))
        self.venda("1", momento(12, 9), "achadinhos1", "12")  # 2 dias depois, grupo A
        self.venda("1", momento(16, 9), "achadinhos2", "8")  # 6 dias depois, grupo B
        self.venda("1", momento(18, 9), "achadinhos1", "99")  # 8 dias depois: fora da janela
        self.venda("1", momento(12, 10), "instagram", "50")  # outro Sub ID: veio de outro lugar
        self.venda("1", momento(12, 11), "achadinhos1", "70", situacao=VendaItem.CANCELADO)  # cancelada
        self.venda("2", momento(11, 7), "achadinhos1", "30")  # comprado antes do envio
        d = desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 11))
        self.assertEqual((d["ofertas"], d["envios"], d["grupos"]), (2, 4, 2))
        self.assertEqual((d["venderam"], d["percentual_venderam"], d["pedidos"], d["comissao"]), (1, 50, 2, Decimal(20)))
        self.assertEqual(d["por_oferta"], Decimal(10))
        grupos = {g["jid"]: g for g in d["por_grupo"]}
        self.assertEqual((grupos["a@g.us"]["comissao"], grupos["b@g.us"]["comissao"]), (Decimal(12), Decimal(8)))
        self.assertEqual((grupos["a@g.us"]["ofertas"], grupos["a@g.us"]["venderam"]), (2, 50))
        self.assertTrue(grupos["a@g.us"]["separavel"])
        campea = d["campeas"][0]
        self.assertEqual((campea["item_id"], campea["vezes"], campea["pedidos"], campea["comissao"]), ("1", 1, 2, Decimal(20)))
        self.assertFalse(d["sem_sub_id"] or d["sub_id_repetido"])
        dias = {p["dia"]: p["comissao"] for p in d["por_dia"]}
        self.assertEqual((dias[date(2026, 10, 10)], dias[date(2026, 10, 11)]), (Decimal(20), Decimal(0)))
        horario = {f["nome"]: f for f in d["por_horario"]["faixas"]}
        self.assertEqual((horario["18h–21h"]["por_oferta"], horario["7h–9h"]["por_oferta"]), (Decimal(20), Decimal(0)))

    def test_a_venda_fica_com_o_envio_mais_recente(self):
        self.oferta("1", momento(10))
        self.oferta("1", momento(13))
        self.venda("1", momento(14), "achadinhos1", "10")
        d = desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 10))
        self.assertEqual((d["ofertas"], d["comissao"]), (1, Decimal(0)))  # quem vendeu foi o envio do dia 13
        d = desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 13))
        self.assertEqual((d["ofertas"], d["venderam"], d["comissao"]), (2, 1, Decimal(10)))
        self.assertEqual((d["campeas"][0]["vezes"], d["campeas"][0]["por_envio"]), (2, Decimal(5)))

    def test_mesmo_sub_id_em_varios_grupos_conta_a_oferta_sem_separar_o_grupo(self):
        self.config.sub_ids, self.config.sub_ids_por_grupo = "bot", {}
        self.config.save()
        self.oferta("1", momento(10))
        self.venda("1", momento(11), "bot", "15")
        d = desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 10))
        self.assertEqual(d["comissao"], Decimal(15))
        self.assertTrue(d["sub_id_repetido"])
        self.assertFalse(any(g["separavel"] for g in d["por_grupo"]))
        self.assertEqual(sum(g["comissao"] for g in d["por_grupo"]), 0)

    def test_sem_sub_id_conta_qualquer_venda_do_produto(self):
        self.config.sub_ids_por_grupo = {}
        self.config.save()
        self.oferta("1", momento(10))
        self.venda("1", momento(11), "instagram", "15")
        d = desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 10))
        self.assertEqual(d["comissao"], Decimal(15))
        self.assertTrue(d["sem_sub_id"])

    def test_teste_simulado_e_mensagem_nao_contam(self):
        self.oferta("1", momento(10), origem=EnvioWhatsApp.TESTE)
        EnvioWhatsApp.objects.create(conta=self.conta, destino="a@g.us", item_id="2", origem=EnvioWhatsApp.OFERTA,
                                     estado=EnvioWhatsApp.SIMULADO, enviado_em=momento(10))
        self.assertEqual(desempenho.calcular(self.conta, date(2026, 10, 10), date(2026, 10, 10))["ofertas"], 0)


@mock.patch("django.utils.timezone.localdate", return_value=date(2026, 10, 20))
class TestTela(BaseDesempenho):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_aba_resultados(self, _):
        self.oferta("1", momento(10, 19), nome="Copo Térmico 1,2L")
        self.venda("1", momento(12, 9), "achadinhos1", "12.50")
        html = self.client.get("/whatsapp/resultados/?periodo=personalizado&de=2026-10-01&ate=2026-10-19").content.decode()
        for texto in ("Ofertas campeãs", "Copo Térmico 1,2L", "R$ 12,50", "Por grupo", "Por horário de envio",
                      'aria-current="page">Resultados', "até <strong>7 dias</strong>"):
            self.assertIn(texto, html)
        self.assertNotIn("Grupo sem Sub ID próprio", html)
        html = self.client.get("/whatsapp/resultados/?periodo=ontem").content.decode()
        self.assertIn("Nenhuma oferta enviada pelo bot em 19/10/2026.", html)

    def test_sem_sub_id_avisa(self, _):
        self.config.sub_ids_por_grupo = {}
        self.config.save()
        self.oferta("1", momento(10))
        html = self.client.get("/whatsapp/resultados/?periodo=mes").content.decode()
        self.assertIn("Grupo sem Sub ID próprio", html)
        self.assertIn("não têm como separar as vendas", html)
