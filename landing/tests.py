"""Página de vendas do Appfiliado (appfiliado.com.br): preços, links do checkout e roteamento por domínio."""

from django.test import SimpleTestCase, TestCase, override_settings

from . import planos

DOMINIO = dict(APPFILIADO_SITES_DOMINIO="appfiliado.com.br", ALLOWED_HOSTS=[".appfiliado.com.br", "testserver"],
               APPFILIADO_LANDING_HOSTS=["appfiliado.com.br", "www.appfiliado.com.br"])


class TestPlanos(SimpleTestCase):
    def test_todas_as_26_combinacoes_tem_link_unico_do_checkout(self):
        combos = planos.todos_os_combos()
        self.assertEqual(len(combos), 26)
        links = [c["link"] for c in combos.values()] + list(planos.LINKS_NOTAS.values())
        self.assertEqual(len(links), len(set(links)))
        self.assertTrue(all(l.startswith("https://pay.zouti.com.br/checkout?poi=prod_offer_") for l in links))
        self.assertEqual(len(planos.LINKS_NOTAS), len(planos.NOTAS))

    def test_precos_batem_com_o_guia_da_zouti(self):
        combos = planos.todos_os_combos()
        esperado = {"bot0": 49.90, "bot1": 89.90, "site0": 22.90, "carrosseis1": 35.90,
                    "bot0+site0+carrosseis0": 73.90, "bot1+site1+carrosseis1": 128.90,
                    "bot0+site0": 64.90, "bot1+site1": 112.90, "site0+carrosseis0": 37.90, "bot1+site0+carrosseis1": 118.90,
                    "bot0+site1+carrosseis0": 83.90}
        for chave, preco in esperado.items():
            self.assertEqual(combos[chave]["preco"], preco, chave)

    def test_combo_nunca_custa_mais_que_separado(self):
        for chave, c in planos.todos_os_combos().items():
            self.assertLessEqual(c["preco"], c["separado"], chave)

    def test_formatacao_em_reais(self):
        self.assertEqual(planos.brl(1234.5), "R$ 1.234,50")


@override_settings(**DOMINIO)
class TestPagina(TestCase):
    def abrir(self, host="appfiliado.com.br", caminho="/"):
        return self.client.get(caminho, HTTP_HOST=host)

    def test_a_raiz_e_o_www_mostram_a_pagina_de_vendas(self):
        for host in ("appfiliado.com.br", "www.appfiliado.com.br"):
            resposta = self.abrir(host)
            self.assertContains(resposta, "Tudo o que o afiliado da Shopee precisa em um só lugar")
            self.assertContains(resposta, "https://cdn1.zouti.com.br/scripts/params/persistence.min.js")
            self.assertContains(resposta, planos.LINKS["bot1"])
            self.assertContains(resposta, planos.LINKS_NOTAS["ilimitada"])
            self.assertContains(resposta, "R$ 49,90")

    def test_outros_enderecos_do_dominio_continuam_como_antes(self):
        self.assertEqual(self.abrir("admin.appfiliado.com.br").status_code, 404)  # reservado
        self.assertEqual(self.abrir("a.b.appfiliado.com.br").status_code, 404)

    def test_robots_e_sitemap_so_da_landing(self):
        self.assertContains(self.abrir(caminho="/robots.txt"), "Sitemap: https://appfiliado.com.br/sitemap.xml")
        self.assertContains(self.abrir(caminho="/sitemap.xml"), "https://appfiliado.com.br/")
        self.assertEqual(self.abrir(caminho="/dashboard/").status_code, 404)  # nada da cash-b nesse domínio
        self.assertEqual(self.abrir(caminho="/admin/").status_code, 404)

    def test_contato_so_aparece_quando_configurado(self):
        self.assertNotContains(self.abrir(), "wa.me")
        with override_settings(APPFILIADO_WHATSAPP_SUPORTE="+55 (11) 91234-5678", APPFILIADO_EMAIL_SUPORTE="ajuda@appfiliado.com.br"):
            resposta = self.abrir()
        self.assertContains(resposta, "https://wa.me/5511912345678")
        self.assertContains(resposta, "mailto:ajuda@appfiliado.com.br")

    def test_dados_do_montador_vao_para_a_pagina(self):
        self.assertContains(self.abrir(), 'id="dados-montador"')


class TestSemDominioConfigurado(TestCase):
    def test_sem_hosts_da_landing_o_site_da_cashb_segue_normal(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotContains(self.client.get("/"), "Tudo o que o afiliado da Shopee precisa em um só lugar")
