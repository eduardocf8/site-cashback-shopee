"""Tela do alerta de preço (aba do Bot de WhatsApp)."""

from decimal import Decimal
from unittest import mock

from django.utils import timezone

from bot_whatsapp import alertas, shopee_ofertas
from bot_whatsapp.models import (
    AlertaDisparado, AlertaPreco, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, ProdutoAcompanhado,
)
from bot_whatsapp.tests_ofertas import GRUPOS, produto
from ofertas.models import Oferta

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
        Oferta.objects.create(item_id=5, nome="Fone JBL", nome_curto="Fone JBL", preco_min=Decimal("59.90"), preco_max=Decimal("59.90"),
                              categoria_id=100535, vendas=10, product_link="https://shopee.com.br/p-i.1.5", visto_em=timezone.now())
        Oferta.objects.create(item_id=6, nome="Caneca", nome_curto="Caneca", preco_min=Decimal("19.90"), preco_max=Decimal("19.90"),
                              categoria_id=100535, vendas=10, product_link="https://shopee.com.br/p-i.1.6", visto_em=timezone.now())
        with mock.patch.object(shopee_ofertas, "buscar_produtos") as api:
            resposta = self.client.get("/whatsapp/alertas/?q=fone")
        api.assert_not_called()  # a vitrine usa o catálogo da cash-b, não a API da Shopee
        self.assertContains(resposta, "Fone JBL")
        self.assertNotContains(resposta, "Caneca")
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
        base = {"acao": "salvar", "intervalo_minutos": "60", "queda_minima": "15", "avisar_email": "on",
                "modelo_mensagem": "{produto} {link}"}
        resposta = self.client.post("/whatsapp/alertas/", {**base, "intervalo_minutos": "15"})
        self.assertContains(resposta, "Faça uma escolha válida")  # 15 min é do Premium
        resposta = self.client.post("/whatsapp/alertas/", {**base, "enviar_grupos": "on"}, follow=True)
        self.assertContains(resposta, "Alerta de preço salvo")
        alerta = AlertaPreco.objects.get(conta=self.conta)
        self.assertEqual((alerta.queda_minima, alerta.enviar_grupos), (15, True))
        self.assertContains(resposta, "nenhum está escolhido ainda")  # os grupos vêm da Automação
        ConfiguracaoOfertas.objects.filter(conta=self.conta).update(grupos=GRUPOS)
        self.assertContains(self.client.get("/whatsapp/alertas/"), "Vai para os mesmos grupos das ofertas: <strong>Ofertas VIP, Achadinhos</strong>")

    def test_dez_produtos_por_pagina(self):
        self.conta.modulos_cortesia = "whatsapp_premium"
        self.conta.save()
        for i in range(23):
            alertas.adicionar(self.conta, produto(i, nome=f"Produto número {i}"))
        resposta = self.client.get("/whatsapp/alertas/")
        self.assertContains(resposta, "23 de 50")
        self.assertContains(resposta, "Mostrando 1–10 de 23")
        self.assertContains(resposta, "Produto número 22")  # os mais novos primeiro
        self.assertNotContains(resposta, "Produto número 12<")
        resposta = self.client.get("/whatsapp/alertas/?pagina=3")
        self.assertContains(resposta, "Mostrando 21–23 de 23")
        self.assertContains(resposta, 'aria-label="Página anterior"')
        p = ProdutoAcompanhado.objects.get(item_id="0")
        resposta = self.client.post("/whatsapp/alertas/", {"acao": "remover", "produto": p.pk, "pagina": "3"})
        self.assertEqual(resposta["Location"], "/whatsapp/alertas/?pagina=3#produtos")  # volta para a mesma página

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
