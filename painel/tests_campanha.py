"""Modo campanha do bot: calendário, datas próprias, tela e aviso da Início."""

from datetime import date
from unittest import mock

from bot_whatsapp import campanhas
from bot_whatsapp.models import CampanhaBot, ConfiguracaoOfertas

from .tests import BasePainel

HOJE = date(2026, 10, 21)


class TestCalendario(BasePainel):
    def test_black_friday(self):
        self.assertEqual([campanhas.black_friday(a) for a in (2025, 2026, 2027)],
                         [date(2025, 11, 28), date(2026, 11, 27), date(2027, 11, 26)])

    def test_lista_anda_sozinha_e_as_datas_valem_todo_ano(self):
        campanha = CampanhaBot(conta=self.conta)  # 9.9, 10.10, 11.11, Black Friday e 12.12 ligadas
        datas = campanhas.proximas_datas(campanha, HOJE)
        self.assertEqual(datas[0]["chave"], "11.11")  # o 10.10 já passou e saiu da lista
        self.assertEqual(datas[-1]["data"], date(2027, 10, 10))  # e voltou no ano que vem, ligado
        self.assertTrue(datas[-1]["ligada"])
        self.assertEqual(len(datas), 12)  # 11.11, Black Friday, 12.12, 3.3, Consumidor e 4.4 a 10.10
        self.assertEqual(campanhas.proximas_datas(campanha, date(2027, 1, 5))[0]["data"], date(2027, 3, 3))

    def test_datas_proprias(self):
        campanha = CampanhaBot(conta=self.conta, datas_proprias=[
            {"data": "2026-10-24", "nome": "Uma vez"},
            {"data": "2025-10-01", "nome": "Aniversário", "anual": True},
            {"data": "2026-10-01", "nome": "Já passou"},
        ])
        proprias = [d for d in campanhas.proximas_datas(campanha, HOJE) if d["propria"]]
        self.assertEqual([(d["nome"], d["data"]) for d in proprias],
                         [("Uma vez", date(2026, 10, 24)), ("Aniversário", date(2027, 10, 1))])
        self.assertEqual([p["nome"] for p in campanhas.sem_datas_passadas(campanha.datas_proprias, HOJE)],
                         ["Uma vez", "Aniversário"])

    def test_campanha_do_dia_so_com_o_modo_ligado(self):
        campanha = CampanhaBot(conta=self.conta, ativo=False)
        self.assertIsNone(campanhas.campanha_do_dia(campanha, date(2026, 11, 11)))
        campanha.ativo = True
        self.assertEqual(campanhas.campanha_do_dia(campanha, date(2026, 11, 11))["nome"], "11.11")
        self.assertIsNone(campanhas.campanha_do_dia(campanha, date(2026, 11, 12)))
        campanha.datas_ligadas = ["12.12"]
        self.assertIsNone(campanhas.campanha_do_dia(campanha, date(2026, 11, 11)))


@mock.patch("django.utils.timezone.localdate", return_value=HOJE)
class TestTela(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_abre_com_as_datas_e_sem_erros(self, _):
        resposta = self.client.get("/whatsapp/campanhas/")
        self.assertContains(resposta, "Modo campanha desligado")
        self.assertContains(resposta, "Black Friday")
        self.assertNotContains(resposta, "obrigatório")
        self.assertContains(resposta, 'value="00:00"')

    def test_salvar_ligar_e_previa(self, _):
        self.client.post("/whatsapp/campanhas/", {"acao": "ligar"})
        resposta = self.client.post("/whatsapp/campanhas/", {
            "acao": "salvar", "datas_ligadas": ["11.11"], "horario_inicio": "00:00", "horario_fim": "23:59",
            "intervalo_minutos": "20", "mensagem_ativa": "on", "frase_abertura": "🔥 11.11!", "cupom": "SHOPEE1111",
            "link_campanha": "https://shopee.com.br/m/11-11", "link_campanha_a_cada": "10",
        }, follow=True)
        self.assertContains(resposta, "Modo campanha salvo")
        campanha = CampanhaBot.objects.get(conta=self.conta)
        self.assertTrue(campanha.ativo)
        self.assertEqual((campanha.datas_ligadas, campanha.intervalo_minutos, campanha.cupom), (["11.11"], 20, "SHOPEE1111"))
        self.assertContains(resposta, "🔥 11.11!\n\n")  # a prévia começa pela frase
        self.assertContains(resposta, "Cupom: SHOPEE1111")
        self.assertContains(resposta, "Próxima campanha: <strong>11.11</strong>")

    def test_pagina_da_campanha_precisa_do_link_e_tem_previa_propria(self, _):
        base = {"acao": "salvar", "horario_inicio": "00:00", "horario_fim": "23:59", "link_campanha_a_cada": "5",
                "pagina_ativa": "on"}
        resposta = self.client.post("/whatsapp/campanhas/", base)
        self.assertContains(resposta, "Cole o link da página da campanha para enviar a mensagem.")
        resposta = self.client.post("/whatsapp/campanhas/", {**base, "link_campanha": "https://shopee.com.br/m/11-11",
                                                            "texto_pagina": "Tudo do 11.11 aqui", "cupom": "C1"}, follow=True)
        self.assertContains(resposta, "Mensagem da página da campanha")
        self.assertContains(resposta, "a cada 5 ofertas")
        self.assertContains(resposta, "Tudo do 11.11 aqui\nhttps://s.shopee.com.br/sua-pagina\n\n🎟️ Cupom: C1")
        self.assertTrue(CampanhaBot.objects.get(conta=self.conta).pagina_ativa)

    def test_mensagem_desligada_guarda_o_texto_e_a_previa_fica_normal(self, _):
        resposta = self.client.post("/whatsapp/campanhas/", {
            "acao": "salvar", "horario_inicio": "00:00", "horario_fim": "23:59", "frase_abertura": "🔥 11.11!",
            "cupom": "SHOPEE1111", "link_campanha_a_cada": "10",
        }, follow=True)
        campanha = CampanhaBot.objects.get(conta=self.conta)
        self.assertFalse(campanha.mensagem_ativa)
        self.assertEqual(campanha.cupom, "SHOPEE1111")
        self.assertNotContains(resposta, "Cupom: SHOPEE1111")

    def test_recusa_link_de_fora_e_intervalo_abaixo_do_plano(self, _):
        resposta = self.client.post("/whatsapp/campanhas/", {
            "acao": "salvar", "horario_inicio": "00:00", "horario_fim": "23:59", "intervalo_minutos": "3",
            "link_campanha": "https://golpe.com/11-11", "link_campanha_a_cada": "10",
        })
        self.assertContains(resposta, "Cole um link da Shopee")
        self.assertContains(resposta, "maior ou igual a 15")

    def test_marcar_data_salva_na_hora(self, _):
        resposta = self.client.post("/whatsapp/campanhas/", {"acao": "marcar_data", "chave": "3.3", "ligada": "1"})
        self.assertEqual(resposta.json()["texto"], "3.3 ligada no modo campanha.")
        self.client.post("/whatsapp/campanhas/", {"acao": "marcar_data", "chave": "11.11", "ligada": "0"})
        ligadas = CampanhaBot.objects.get(conta=self.conta).datas_ligadas
        self.assertIn("3.3", ligadas)
        self.assertNotIn("11.11", ligadas)
        self.assertEqual(self.client.post("/whatsapp/campanhas/", {"acao": "marcar_data", "chave": "x"}).status_code, 400)

    def test_datas_proprias(self, _):
        self.client.post("/whatsapp/campanhas/", {"acao": "adicionar_data", "nome": "Aniversário", "data": "2026-10-24", "anual": "1"})
        self.client.post("/whatsapp/campanhas/", {"acao": "adicionar_data", "nome": "Velha", "data": "2026-10-01"})
        campanha = CampanhaBot.objects.get(conta=self.conta)
        self.assertEqual(campanha.datas_proprias, [{"data": "2026-10-24", "nome": "Aniversário", "anual": True}])
        self.assertContains(self.client.get("/whatsapp/campanhas/"), "Sua data · todo ano")
        self.client.post("/whatsapp/campanhas/", {"acao": "remover_data", "data": "2026-10-24"})
        self.assertEqual(CampanhaBot.objects.get(conta=self.conta).datas_proprias, [])

    def test_data_que_passou_some_sozinha(self, _):
        CampanhaBot.objects.create(conta=self.conta, datas_proprias=[{"data": "2026-10-01", "nome": "Velha"}])
        self.client.get("/whatsapp/campanhas/")
        self.assertEqual(CampanhaBot.objects.get(conta=self.conta).datas_proprias, [])

    def test_aviso_na_inicio(self, _):
        self.assertIsNone(campanhas.aviso_da_inicio(self.conta, HOJE))  # modo campanha desligado
        CampanhaBot.objects.create(conta=self.conta, ativo=True, datas_proprias=[{"data": "2026-10-24", "nome": "Aniversário"}])
        self.assertIn("Faltam 3 dias", campanhas.aviso_da_inicio(self.conta, HOJE)["texto"])
        self.assertIn("pausadas", campanhas.aviso_da_inicio(self.conta, date(2026, 10, 23))["texto"])
        ConfiguracaoOfertas.objects.create(conta=self.conta, ativo=True)
        self.assertIn("é amanhã", campanhas.aviso_da_inicio(self.conta, date(2026, 10, 23))["texto"])
        self.assertIn("Hoje é Aniversário", campanhas.aviso_da_inicio(self.conta, date(2026, 10, 24))["texto"])
        self.assertContains(self.client.get("/"), "Ver modo campanha")

    def test_sem_o_bot_nao_abre(self, _):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertContains(self.client.get("/whatsapp/campanhas/"), "Não incluso no seu plano")


class TestAutomacaoNoDia(BasePainel):
    def test_aba_automacao_avisa_que_a_campanha_esta_valendo(self):
        CampanhaBot.objects.create(conta=self.conta, ativo=True, datas_ligadas=["11.11"])
        self.entrar()
        with mock.patch("django.utils.timezone.localdate", return_value=date(2026, 11, 11)):
            self.assertContains(self.client.get("/whatsapp/ofertas/"), "Hoje é 11.11: o bot está usando a configuração")
        with mock.patch("django.utils.timezone.localdate", return_value=date(2026, 11, 12)):
            self.assertNotContains(self.client.get("/whatsapp/ofertas/"), "Hoje é 11.11")
