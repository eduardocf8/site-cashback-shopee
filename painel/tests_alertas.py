"""Tela do alerta de preço (aba do Bot de WhatsApp)."""

from decimal import Decimal
from unittest import mock

from django.utils import timezone

from bot_whatsapp import alertas, shopee_ofertas
from bot_whatsapp.models import AlertaDisparado, AlertaPreco, ConexaoWhatsApp, EnvioWhatsApp, ProdutoAcompanhado
from bot_whatsapp.tests_ofertas import GRUPOS, produto

from .cripto import cifrar
from .tests import BasePainel


class TestTelaDoAlerta(BasePainel):
    def setUp(self):
        super().setUp()
        self.conta.shopee_app_id, self.conta.shopee_secret_cifrado = "123", cifrar("s")
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        self.entrar()

    def test_abre_vazia(self):
        resposta = self.client.get("/whatsapp/alertas/")
        self.assertContains(resposta, "Alerta de preço pausado")
        self.assertContains(resposta, "0 de 10")  # plano Standard
        self.assertContains(resposta, 'href="/whatsapp/alertas/"')  # a aba

    @mock.patch("bot_whatsapp.copia.identificar_produto", side_effect=lambda link: link[-1])
    def test_adicionar_por_link_e_remover(self, _):
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item",
                               side_effect=lambda a, s, item: produto(item, preco=99.9) if item != "9" else None):
            resposta = self.client.post("/whatsapp/alertas/", {
                "acao": "adicionar_links",
                "links": "https://shopee.com.br/a-i.1.1\nhttps://s.shopee.com.br/x2\nhttps://shopee.com.br/z-i.1.9",
            }, follow=True)
        self.assertContains(resposta, "2 produtos adicionados")
        self.assertContains(resposta, "Não achei 1 produto")
        self.assertContains(resposta, "R$ 99,90")
        p = ProdutoAcompanhado.objects.get(item_id="1")
        self.client.post("/whatsapp/alertas/", {"acao": "remover", "produto": p.pk})
        self.assertEqual(ProdutoAcompanhado.objects.count(), 1)

    def test_vitrine_e_ofertas_do_bot(self):
        EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", origem="oferta", item_id="77", produto="Air fryer")
        with mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(5, nome="Fone JBL")], False)) as busca:
            resposta = self.client.get("/whatsapp/alertas/?q=fone")
            self.client.get("/whatsapp/alertas/?q=fone")
        self.assertEqual(busca.call_count, 1)  # a mesma busca fica guardada por 10 minutos
        self.assertContains(resposta, "Fone JBL")
        self.assertContains(resposta, "Air fryer")
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=produto(5, nome="Fone JBL")):
            resposta = self.client.post("/whatsapp/alertas/", {"acao": "adicionar_item", "item_id": "5", "q": "fone"}, follow=True)
        self.assertEqual(resposta.redirect_chain[0][0], "/whatsapp/alertas/?q=fone#vitrine")  # a busca continua na tela
        self.assertContains(resposta, "“Fone JBL” entrou no alerta")
        self.assertContains(resposta, "✓ Acompanhando")

    def test_limite_do_plano_na_tela(self):
        for i in range(10):
            alertas.adicionar(self.conta, produto(i))
        resposta = self.client.get("/whatsapp/alertas/")
        self.assertContains(resposta, "chegou ao limite de 10 produtos")
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=produto(50)):
            resposta = self.client.post("/whatsapp/alertas/", {"acao": "adicionar_item", "item_id": "50"}, follow=True)
        self.assertContains(resposta, "Seu plano acompanha até 10 produtos")

    def test_salvar_configuracao(self):
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        base = {"acao": "salvar", "intervalo_minutos": "60", "queda_minima": "15", "avisar_email": "on",
                "modelo_mensagem": "{produto} {link}"}
        resposta = self.client.post("/whatsapp/alertas/", {**base, "intervalo_minutos": "15"})
        self.assertContains(resposta, "Faça uma escolha válida")  # 15 min é do Premium
        resposta = self.client.post("/whatsapp/alertas/", {**base, "enviar_grupos": "on"})
        self.assertContains(resposta, "Escolha pelo menos um grupo")
        resposta = self.client.post("/whatsapp/alertas/", {**base, "enviar_grupos": "on", "grupos": ["1@g.us"]}, follow=True)
        self.assertContains(resposta, "Alerta de preço salvo")
        alerta = AlertaPreco.objects.get(conta=self.conta)
        self.assertEqual((alerta.queda_minima, alerta.enviar_grupos, alerta.grupos),
                         (15, True, [{"jid": "1@g.us", "nome": "Ofertas VIP"}]))

    def test_premium_pode_15_minutos(self):
        self.conta.modulos_cortesia = "whatsapp_premium"
        self.conta.save()
        self.client.post("/whatsapp/alertas/", {"acao": "salvar", "intervalo_minutos": "15", "queda_minima": "10"})
        self.assertEqual(AlertaPreco.objects.get(conta=self.conta).intervalo_minutos, 15)

    def test_ligar_conferir_e_aviso_na_inicio(self):
        self.client.post("/whatsapp/alertas/", {"acao": "ligar"})
        self.assertTrue(AlertaPreco.objects.get(conta=self.conta).ativo)
        p, _ = alertas.adicionar(self.conta, produto(1, preco=100.0, nome="Fone"))
        AlertaDisparado.objects.create(conta=self.conta, produto=p, nome="Fone", preco_antes=Decimal("100"),
                                       preco_agora=Decimal("80"), queda=Decimal("20"))
        self.assertContains(self.client.get("/"), "Um produto que você acompanha baixou de preço")
        resposta = self.client.get("/whatsapp/alertas/")
        self.assertContains(resposta, "−20%")
        self.assertNotContains(self.client.get("/"), "baixou de preço")  # abriu a aba: já viu
        self.client.post("/whatsapp/alertas/", {"acao": "conferir"})
        self.assertIsNotNone(AlertaPreco.objects.get(conta=self.conta).pedido_conferir_em)

    def test_sem_o_bot_nao_abre(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertContains(self.client.get("/whatsapp/alertas/"), "Não incluso no seu plano")
