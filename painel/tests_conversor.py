"""Conversor de links do painel."""

from unittest import mock

from bot_whatsapp.formatador import remover_links
from bot_whatsapp.models import ConexaoWhatsApp, EnvioWhatsApp

from . import conversor
from .cripto import cifrar
from .tests import BasePainel

TEXTO_DA_SHOPEE = (
    "🔥 Ofertas do dia!\n"
    "\n"
    "Fone sem fio por R$ 39,90: https://shopee.com.br/Fone-i.123.456?smtt=0.0.9&utm_source=an_999&sp_atk=x\n"
    "Nota 4.8/5 ⭐\n"
    "Leve também: s.shopee.com.br/AbCdE.\n"
    "Entre no grupo: https://chat.whatsapp.com/Golpe\n"
    "https://bit.ly/outro\n"
    "Fale com fulano@gmail.com"
)


def gerar(app_id, secret, url, sub_ids):
    return f"https://s.shopee.com.br/meu?de={url}&sub={','.join(sub_ids)}"


class TestConversor(BasePainel):
    def setUp(self):
        super().setUp()
        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cifrar("segredo")
        self.conta.save()
        patchers = [
            mock.patch("bot_whatsapp.shopee_ofertas.gerar_link_afiliado", side_effect=gerar),
            mock.patch("bot_whatsapp.copia.identificar_produto", return_value="789"),
            mock.patch("bot_whatsapp.shopee_ofertas.buscar_produto_por_item",
                       return_value={"link": "https://shopee.com.br/product/7/789"}),
        ]
        self.gerar, self.identificar, self.buscar = [p.start() for p in patchers]
        for p in patchers:
            self.addCleanup(p.stop)

    def test_mantem_o_texto_e_troca_so_os_links(self):
        r = conversor.converter(self.conta, TEXTO_DA_SHOPEE, conversor.MODO_TEXTO, "canal")
        linhas = r["texto"].split("\n")
        self.assertEqual(linhas[0], "🔥 Ofertas do dia!")
        self.assertEqual(linhas[1], "")  # a linha em branco do original continua
        # link do produto limpo (sem o rastreio de quem divulgou) e com o Sub ID escolhido
        self.assertEqual(linhas[2], "Fone sem fio por R$ 39,90: https://s.shopee.com.br/meu?de=https://shopee.com.br/product/123/456&sub=canal")
        self.assertEqual(linhas[3], "Nota 4.8/5 ⭐")
        # link curto: abre para achar o produto; a pontuação colada fica
        self.assertEqual(linhas[4], "Leve também: https://s.shopee.com.br/meu?de=https://shopee.com.br/product/7/789&sub=canal.")
        self.assertEqual(linhas[5], "Entre no grupo:")  # o convite de grupo saiu
        self.assertEqual(linhas[6], "Fale com fulano@gmail.com")  # a linha só com o bit.ly sumiu; e-mail fica
        self.assertEqual((r["convertidos"], r["removidos"], r["falharam"]), (2, 2, []))

    def test_so_os_links(self):
        texto = TEXTO_DA_SHOPEE + "\nDe novo: https://shopee.com.br/Fone-i.123.456"
        r = conversor.converter(self.conta, texto, conversor.MODO_LINKS)
        self.assertEqual(r["texto"].split("\n"), [
            "https://s.shopee.com.br/meu?de=https://shopee.com.br/product/123/456&sub=conversor",
            "https://s.shopee.com.br/meu?de=https://shopee.com.br/product/7/789&sub=conversor",
        ])
        self.assertEqual(self.gerar.call_count, 2)  # o mesmo produto repetido converte uma vez só

    def test_pagina_de_campanha_tira_so_o_rastreio(self):
        texto = "11.11: https://shopee.com.br/m/11-11?utm_campaign=x&keyword=fone&af_id=9"
        r = conversor.converter(self.conta, texto, conversor.MODO_LINKS)
        self.assertIn("de=https://shopee.com.br/m/11-11?keyword=fone&", r["texto"])

    def test_link_que_a_shopee_recusa_fica_e_avisa(self):
        def as_vezes(app_id, secret, url, sub_ids):
            if "456" in url:
                raise RuntimeError("recusado")
            return gerar(app_id, secret, url, sub_ids)
        self.gerar.side_effect = as_vezes
        r = conversor.converter(self.conta, TEXTO_DA_SHOPEE, conversor.MODO_TEXTO)
        self.assertIn("R$ 39,90: https://shopee.com.br/Fone-i.123.456", r["texto"])
        self.assertEqual(len(r["falharam"]), 1)

    def test_erros_com_mensagem_clara(self):
        casos = [
            ("", "Cole um texto"),
            ("sem link nenhum aqui https://bit.ly/x", "Não achei nenhum link da Shopee"),
            (" ".join(f"https://shopee.com.br/p-i.1.{i}" for i in range(21)), "Converta até 20"),
        ]
        for texto, mensagem in casos:
            with self.assertRaisesMessage(conversor.ErroConversor, mensagem):
                conversor.converter(self.conta, texto, conversor.MODO_TEXTO)
        with self.assertRaisesMessage(conversor.ErroConversor, "letras e números"):
            conversor.converter(self.conta, "https://shopee.com.br/p-i.1.2", conversor.MODO_TEXTO, "com espaço")
        self.gerar.side_effect = RuntimeError("fora do ar")
        with self.assertRaisesMessage(conversor.ErroConversor, "não converteu nenhum"):
            conversor.converter(self.conta, "https://shopee.com.br/p-i.1.2", conversor.MODO_TEXTO)

    def test_sem_shopee_conectada(self):
        self.conta.shopee_app_id = ""
        self.conta.save()
        with self.assertRaisesMessage(conversor.ErroConversor, "Conecte sua conta da Shopee"):
            conversor.converter(self.conta, "https://shopee.com.br/p-i.1.2", conversor.MODO_TEXTO)

    def test_tela(self):
        self.entrar()
        resposta = self.client.get("/conversor/")
        self.assertContains(resposta, "Conversor de links")
        self.assertContains(resposta, 'href="/conversor/"')  # está no menu
        resposta = self.client.post("/conversor/", {"texto": TEXTO_DA_SHOPEE, "modo": "links", "sub_id": "canal"})
        self.assertContains(resposta, "2 links convertidos")
        self.assertContains(resposta, "sub=canal")
        self.assertContains(resposta, "Conecte o WhatsApp")  # tem o bot, mas não conectou
        self.assertNotContains(resposta, "Assine o Bot de WhatsApp")
        self.assertContains(resposta, 'name="texto" readonly')  # sem enviar no grupo, o resultado só se copia
        # guarda o modo e o Sub ID para a próxima vez
        resposta = self.client.get("/conversor/")
        self.assertContains(resposta, 'value="canal"')
        self.assertContains(resposta, 'value="links" checked')

    def test_tela_sem_o_bot_nao_mostra_enviar(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.entrar()
        resposta = self.client.post("/conversor/", {"texto": TEXTO_DA_SHOPEE, "modo": "texto"})
        self.assertContains(resposta, "2 links convertidos")
        self.assertNotContains(resposta, "Enviar no grupo")
        self.assertContains(resposta, "Assine o Bot de WhatsApp")
        self.assertEqual(self.client.post("/conversor/enviar/", {"destino": "1@g.us", "texto": "x"}).status_code, 302)
        self.assertFalse(EnvioWhatsApp.objects.exists())

    def test_enviar_no_grupo(self):
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=[{"jid": "1@g.us", "nome": "Ofertas"}])
        self.entrar()
        resposta = self.client.post("/conversor/", {"texto": TEXTO_DA_SHOPEE, "modo": "texto"})
        self.assertContains(resposta, "Enviar no grupo")
        self.assertContains(resposta, "Ofertas")
        self.assertNotContains(resposta, 'name="texto" readonly')  # dá para ajustar antes de enviar
        self.client.post("/conversor/enviar/", {"destino": "1@g.us", "texto": "🔥 oferta https://s.shopee.com.br/meu"})
        envio = EnvioWhatsApp.objects.get()
        self.assertEqual((envio.destino, envio.texto), ("1@g.us", "🔥 oferta https://s.shopee.com.br/meu"))

    def test_limite_por_hora(self):
        self.entrar()
        with mock.patch("painel.views_conversor.CONVERSOES_POR_HORA", 1):
            self.client.post("/conversor/", {"texto": "https://shopee.com.br/p-i.1.2"})
            resposta = self.client.post("/conversor/", {"texto": "https://shopee.com.br/p-i.1.2"}, follow=True)
        self.assertContains(resposta, "conversões nesta hora")

    def test_precisa_entrar(self):
        self.assertEqual(self.client.get("/conversor/").status_code, 302)


class TestRemoverLinks(BasePainel):
    def test_nota_e_medida_nao_sao_link(self):
        self.assertEqual(remover_links("Nota 4.8/5 e 1.200/mês bit.ly/x"), "Nota 4.8/5 e 1.200/mês")
