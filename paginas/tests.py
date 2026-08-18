from django.test import TestCase
from django.urls import reverse


class MetaSocialTests(TestCase):
    """Tags de compartilhamento e canônica nas páginas públicas.

    Existe porque um comentário multi-linha escrito como {# ... #} (que no Django só
    vale pra UMA linha) fez o exemplo de {% include %} dentro dele ser executado de
    verdade: o template se incluía sozinho e a home inteira caía com RecursionError.
    Testar o status junto com as tags pega esse tipo de quebra na hora.
    """

    def _paginas_publicas(self):
        return [
            ("home", reverse("home")),
            ("ofertas", reverse("ofertas_lista")),
            ("faq", reverse("faq")),
            ("regras", reverse("regras_cashback")),
            ("vale a pena", reverse("cashback_vale_a_pena")),
            ("e confiavel", reverse("e_confiavel")),
        ]

    def test_paginas_publicas_respondem_200(self):
        for nome, url in self._paginas_publicas():
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_paginas_publicas_tem_card_de_compartilhamento(self):
        for nome, url in self._paginas_publicas():
            with self.subTest(pagina=nome):
                html = self.client.get(url).content.decode()
                self.assertIn('property="og:title"', html)
                self.assertIn('property="og:description"', html)
                # Sem a extensão: fora do DEBUG o whitenoise serve o arquivo com hash
                # no nome (og-cash-b.<hash>.png), então prender no nome exato quebraria.
                self.assertIn("/static/images/og-cash-b", html)
                self.assertIn('name="twitter:card"', html)

    def test_url_da_imagem_de_compartilhamento_e_absoluta(self):
        # WhatsApp e Facebook não resolvem caminho relativo - sem o domínio na frente,
        # a prévia do link aparece sem imagem nenhuma.
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn('content="http://testserver/static/images/og-cash-b', html)

    def test_paginas_publicas_tem_canonica(self):
        for nome, url in self._paginas_publicas():
            with self.subTest(pagina=nome):
                html = self.client.get(url).content.decode()
                self.assertIn('rel="canonical"', html)

    def test_paginas_de_conteudo_sobrescrevem_o_card_generico(self):
        # As duas páginas de conteúdo usam o block meta_social pra ter título/descrição
        # próprios em vez do card genérico do base.html - se o override quebrar, a busca
        # e o WhatsApp mostrariam sempre o mesmo texto genérico pra qualquer página.
        html = self.client.get(reverse("cashback_vale_a_pena")).content.decode()
        self.assertIn('content="Cashback na Shopee vale a pena? — cash-b"', html)
        html = self.client.get(reverse("e_confiavel")).content.decode()
        self.assertIn('content="A cash-b é confiável? — cash-b"', html)

    def test_canonica_das_ofertas_ignora_filtros(self):
        # Categoria, busca e ordenação são query params sobre o mesmo conteúdo: todas
        # essas variações precisam apontar pra mesma URL limpa, senão o Google divide a
        # relevância entre dezenas de páginas quase idênticas.
        url = f"{reverse('ofertas_lista')}?categoria=11&ordenar=menor_preco&q=fone"
        html = self.client.get(url).content.decode()
        self.assertIn(f'rel="canonical" href="http://testserver{reverse("ofertas_lista")}"', html)


class SitemapTests(TestCase):
    def test_sitemap_lista_a_vitrine_de_ofertas(self):
        conteudo = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(f"<loc>http://testserver{reverse('ofertas_lista')}</loc>", conteudo)

    def test_paginas_que_mudam_todo_dia_sao_marcadas_como_daily(self):
        # A home e a vitrine são remontadas a cada sincronização com a Shopee; o resto
        # é texto institucional. Marcar tudo igual desperdiça rastreamento.
        conteudo = self.client.get("/sitemap.xml").content.decode()
        self.assertEqual(conteudo.count("<changefreq>daily</changefreq>"), 2)
