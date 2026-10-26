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
            self.assertContains(resposta, "/emissao-de-notas/")  # a landing resume e leva à página das notas
            self.assertContains(resposta, "R$ 49,90")

    def test_outros_enderecos_do_dominio_continuam_como_antes(self):
        self.assertEqual(self.abrir("admin.appfiliado.com.br").status_code, 404)  # reservado
        self.assertEqual(self.abrir("a.b.appfiliado.com.br").status_code, 404)

    def test_health_check_do_render_responde_no_dominio_da_landing(self):
        # O Render confere /healthz/ com o domínio personalizado no Host; sem isso o deploy não termina.
        for host in ("appfiliado.com.br", "www.appfiliado.com.br"):
            self.assertEqual(self.abrir(host, "/healthz/").status_code, 200)

    def test_robots_e_sitemap_so_da_landing(self):
        self.assertContains(self.abrir(caminho="/robots.txt"), "Sitemap: https://appfiliado.com.br/sitemap.xml")
        self.assertContains(self.abrir(caminho="/sitemap.xml"), "https://appfiliado.com.br/")
        self.assertEqual(self.abrir(caminho="/dashboard/").status_code, 404)  # nada da cash-b nesse domínio
        self.assertEqual(self.abrir(caminho="/admin/").status_code, 404)

    def test_politica_de_privacidade_com_a_parte_do_instagram(self):
        # A Meta exige a política no domínio do app, explicando os dados do Instagram e a exclusão.
        pagina = self.abrir(caminho="/privacidade/")
        self.assertContains(pagina, "Dados do Instagram")
        self.assertContains(pagina, "Como pedir a exclusão dos dados")
        self.assertContains(self.abrir(caminho="/sitemap.xml"), "/privacidade/")
        self.assertContains(self.abrir(), 'href="/privacidade/"')

    def test_pagina_de_notas_com_planos_e_aviso_de_pessoa_juridica(self):
        resposta = self.abrir(caminho="/emissao-de-notas/")
        self.assertContains(resposta, "Serviço exclusivo para afiliados pessoa jurídica")
        self.assertContains(resposta, "persistence.min.js")
        for link in planos.LINKS_NOTAS.values():
            self.assertContains(resposta, link)
        self.assertContains(resposta, "R$ 229,90")
        self.assertContains(self.abrir(caminho="/sitemap.xml"), "/emissao-de-notas/")
        self.assertContains(self.abrir(), "Para afiliados pessoa jurídica")  # a landing também avisa

    def test_paginas_de_recursos_de_cada_modulo(self):
        from licencas import planos as plano
        s, p = plano.BOT[False], plano.BOT[True]
        bot = self.abrir(caminho="/bot-de-whatsapp/")
        self.assertContains(bot, "Ofertas da Shopee nos seus grupos de WhatsApp")
        self.assertContains(bot, planos.LINKS["bot0"])
        self.assertContains(bot, planos.LINKS["bot1"])
        for numero in (s["grupos"], s["ofertas_por_grupo_dia"], p["grupos"], p["ofertas_por_grupo_dia"]):  # os limites vêm do plano
            self.assertContains(bot, f"até {numero}")
        site = self.abrir(caminho="/meu-site/")
        self.assertContains(site, "seunome.appfiliado.com.br")
        self.assertContains(site, planos.LINKS["site1"])
        car = self.abrir(caminho="/gerador-de-carrosseis/")
        self.assertContains(car, "carrossel pronto pro Instagram")
        self.assertContains(car, planos.LINKS["carrosseis0"])
        for pagina in (bot, site, car):
            self.assertContains(pagina, "persistence.min.js")
            self.assertContains(pagina, "Todos os recursos")
        mapa = self.abrir(caminho="/sitemap.xml").content.decode()
        for caminho in ("/bot-de-whatsapp/", "/meu-site/", "/gerador-de-carrosseis/"):
            self.assertIn(caminho, mapa)
        self.assertContains(self.abrir(), "/bot-de-whatsapp/")  # a landing leva às páginas

    def test_paginas_das_ferramentas_incluidas_em_todos_os_planos(self):
        mapa = self.abrir(caminho="/sitemap.xml").content.decode()
        home = self.abrir()
        for caminho, trecho in (("/radar-de-ofertas/", "Ache o produto certo para divulgar"),
                                ("/conversor-de-links/", "Troque os links de qualquer texto"),
                                ("/resultados-e-metas/", "Veja quanto vendeu")):
            pagina = self.abrir(caminho=caminho)
            self.assertContains(pagina, trecho)
            self.assertContains(pagina, "Incluído em todos os planos")
            self.assertNotContains(pagina, "Standard × Premium")  # sem plano próprio: não tem comparação
            self.assertContains(pagina, "/prints/")
            self.assertIn(caminho, mapa)
            self.assertContains(home, f'href="{caminho}"')  # a faixa "Em todos os planos" e o mock do hero levam até elas

    def test_telas_do_painel_ilustram_cada_ferramenta(self):
        for caminho, arquivo in (("/bot-de-whatsapp/", "bot-ofertas"), ("/meu-site/", "site-editor"), ("/gerador-de-carrosseis/", "carrossel-editor"),
                                 ("/emissao-de-notas/", "notas-lote"), ("/radar-de-ofertas/", "radar-produtos"),
                                 ("/conversor-de-links/", "conversor"), ("/resultados-e-metas/", "metas")):
            pagina = self.abrir(caminho=caminho)
            self.assertContains(pagina, f"/prints/{arquivo}")
            self.assertContains(pagina, "prints-janela")
            self.assertNotContains(pagina, 'id="por-dentro"')  # as telas ficam dentro de cada seção, sem uma aba à parte

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
