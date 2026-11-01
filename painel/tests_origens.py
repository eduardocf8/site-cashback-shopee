"""Origem das vendas (painel/origens.py) e o mapa de horários na aba Resultados (painel/por_origem.py)."""

from datetime import date, datetime, time
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from bot_whatsapp import shopee_ofertas
from bot_whatsapp.models import ConfiguracaoOfertas
from meusite.models import SiteAfiliado

from . import origens, por_origem, resultados
from .models import VendaItem
from .tests import BasePainel

SP = ZoneInfo("America/Sao_Paulo")


class TestMarca(BasePainel):
    def test_marca_no_link_e_fora_do_sub_id(self):
        self.assertEqual(origens.com_marca(["grupo1"], "bot"), ["grupo1", "apbot"])
        self.assertEqual(origens.com_marca([], "conversor"), ["apconv"])
        self.assertEqual(origens.com_marca(["a", "b", "c", "d", "e"], "bot"), ["a", "b", "c", "d", "e"])  # sem espaço
        self.assertEqual(origens.com_marca(["x"], ""), ["x"])
        self.assertEqual(origens.separar_marca(["grupo1", "apbot"]), (["grupo1"], origens.BOT))
        self.assertEqual(resultados.sub_id_e_marca({"utmContent": "grupo1-apbot---"}), ("grupo1", origens.BOT))
        self.assertEqual(resultados.sub_id_e_marca({"utmContent": "apsite----"}), (resultados.SEM_SUB_ID, origens.SITE))

    def test_gerar_link_poe_a_marca(self):
        with mock.patch.object(shopee_ofertas, "executar_graphql_com_credenciais",
                               return_value={"generateShortLink": {"shortLink": "https://s.shopee.com.br/x"}}) as api:
            shopee_ofertas.gerar_link_afiliado("1", "s", "https://shopee.com.br/p", ["grupo1"], "bot")
        self.assertIn('subIds:["grupo1", "apbot"]', api.call_args.args[2])

    def test_sem_marca_a_origem_sai_do_sub_id(self):
        ConfiguracaoOfertas.objects.create(conta=self.conta, sub_ids="bot", sub_ids_por_grupo={"a@g.us": "achadinhos, g1"})
        SiteAfiliado.objects.create(conta=self.conta, endereco="bia", sub_id="site", sub_id_vitrine="vitrine")
        c = origens.classificador_da_conta(self.conta)
        self.assertEqual([c.origem(r) for r in ("bot", "achadinhos-g1", "site", "vitrine", "conversor", "radar", "instagram",
                                                "outro", resultados.SEM_SUB_ID)],
                         ["bot", "bot", "site", "site", "conversor", "outras", "outras", "fora", "fora"])
        self.assertEqual(c.origem("outro", origens.BOT), "bot")  # a marca manda

    def test_venda_guardada_com_a_origem(self):
        conversao = {"conversionId": "1", "purchaseTime": int(datetime(2026, 10, 3, 12, tzinfo=SP).timestamp()),
                     "utmContent": "promo-apconv---",
                     "orders": [{"orderId": "P", "orderStatus": "PENDING", "items": [{"itemPrice": "10", "qty": 1}]}]}
        item = resultados.itens_vendidos(self.conta, [conversao])[0]
        self.assertEqual((item.sub_id, item.origem), ("promo", origens.CONVERSOR))


class TestResultadosPorOrigem(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_app_id = "123"
        self.conta.shopee_validado_em = datetime(2026, 9, 1, tzinfo=SP)
        self.conta.save()
        from .models import SincronizacaoResultados

        SincronizacaoResultados.objects.create(conta=self.conta, vendas_desde=datetime(2026, 9, 1, tzinfo=SP),
                                               concluida_em=datetime(2026, 10, 20, tzinfo=SP))
        self.n = 0

    def venda(self, dia, hora, origem, comissao, situacao=VendaItem.PENDENTE, nome="Fone", sub_id="x"):
        self.n += 1
        return VendaItem.objects.create(conta=self.conta, conversao_id=f"c{self.n}", pedido_id=f"p{self.n}", item_id=nome,
                                        nome=nome, valor=Decimal(100), comissao=Decimal(comissao), situacao=situacao,
                                        origem=origem, sub_id=sub_id, comprado_em=datetime(2026, 10, dia, hora, tzinfo=SP))

    def test_filtro_de_origem_na_aba_toda(self):
        self.venda(5, 20, "bot", "10", nome="Fone", sub_id="grupo1")  # segunda 20h
        self.venda(5, 20, "bot", "6", nome="Fone", sub_id="grupo1")
        self.venda(6, 9, "site", "4", nome="Copo", sub_id="site")
        self.venda(7, 21, "fora", "30", nome="Mop", sub_id="sem_subid")
        self.venda(8, 21, "bot", "99", situacao=VendaItem.CANCELADO)  # fora das contas
        with mock.patch("painel.telas.hoje", return_value=date(2026, 10, 20)):
            resposta = self.client.get("/resultados/", {"periodo": "mes"})
            html = resposta.content.decode()
            self.assertIn("De onde vieram as vendas", html)
            resumo = {o["chave"]: o for o in resposta.context["resumo_origens"]["linhas"]}
            self.assertEqual((resumo["bot"]["comissao"], resumo["bot"]["percentual"], resumo["fora"]["percentual"]),
                             (Decimal(16), 32, 60))

            resposta = self.client.get("/resultados/", {"periodo": "mes", "origem": "bot"})
        self.assertEqual((resposta.context["totais"]["pedidos"], resposta.context["totais"]["comissao_estimada"]), (2, Decimal(16)))
        self.assertEqual([p["nome"] for p in resposta.context["ranking"]], ["Fone"])
        self.assertEqual([v.nome for v in resposta.context["pagina_vendas"]], ["Fone", "Fone", "Fone"])  # com a cancelada
        self.assertEqual(resposta.context["sub_ids"][0]["sub_id"], "grupo1")
        self.assertContains(resposta, 'name="origem" value="bot"')  # o período escolhido mantém a origem
        self.assertContains(resposta, "Mostrando só <strong>Bot de WhatsApp</strong>")
        planilha = self.client.get("/resultados/vendas.xlsx", {"periodo": "mes", "origem": "site"})
        self.assertEqual(planilha.status_code, 200)

    def test_mapa_de_horarios_e_dica_do_bot(self):
        for _ in range(3):
            self.venda(5, 20, "bot", "10")  # segunda 20h
        self.venda(6, 9, "bot", "4")  # terça 9h
        config = ConfiguracaoOfertas(conta=self.conta, horario_inicio=time(8), horario_fim=time(20))
        mapa = por_origem.mapa_de_horarios(self.conta, date(2026, 10, 1), date(2026, 10, 31), "", "pedidos", config)
        self.assertEqual(mapa["pedidos"], 4)
        segunda = mapa["linhas"][0]["celulas"]
        self.assertEqual((segunda[20]["valor"], segunda[20]["nivel"], segunda[20]["forte"]), (3, 4, True))
        self.assertEqual(mapa["por_hora"][20]["altura"], 100)
        self.assertTrue(mapa["por_hora"][20]["melhor"])
        self.assertEqual(mapa["destaques"][0]["titulo"], "Segunda, 20h–21h")
        self.assertEqual(mapa["destaques"][-1]["titulo"], "Todo dia, 20h–21h")
        dica = mapa["dica_bot"]
        self.assertFalse(dica["ok"])
        self.assertEqual(dica["bot"], "8h às 20h")
        self.assertIn("para antes do fim", dica["situacao"])
        config.horario_fim = time(23, 59)
        self.assertTrue(por_origem.mapa_de_horarios(self.conta, date(2026, 10, 1), date(2026, 10, 31), "", "pedidos",
                                                    config)["dica_bot"]["ok"])
        so_site = por_origem.mapa_de_horarios(self.conta, date(2026, 10, 1), date(2026, 10, 31), "site")
        self.assertEqual(so_site["total"], 0)

    def test_cartao_de_horarios_na_tela(self):
        for dia in range(5, 30):
            self.venda(dia, 21, "bot", "5")
        with mock.patch("painel.telas.hoje", return_value=date(2026, 10, 31)):
            html = self.client.get("/resultados/", {"periodo": "mes", "mapa": "comissao"}).content.decode()
        self.assertIn("Quando suas vendas acontecem", html)
        self.assertIn("horários mais fortes", html)
        self.assertIn("Todo dia, 21h–22h", html)
        self.assertIn("comissão por hora", html)
