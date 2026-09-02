from decimal import Decimal

from django.template.defaultfilters import floatformat
from django.test import TestCase, override_settings
from django.urls import reverse

from ofertas.models import Oferta
from ofertas.services import obter_cashback_maximo_anunciado


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
            ("checklist confiavel", reverse("checklist_cashback_confiavel")),
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
        html = self.client.get(reverse("checklist_cashback_confiavel")).content.decode()
        self.assertIn('content="Como saber se um site de cashback é confiável — cash-b"', html)

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


@override_settings(
    URL_WHATSAPP_CANAL="https://whatsapp.com/channel/exemplo",
    URL_INSTAGRAM="https://www.instagram.com/usecashb/",
    URL_YOUTUBE="https://www.youtube.com/@usecashb",
)
class PaginaDeBioTests(TestCase):
    """A página /bio/, que substitui a ferramenta de link na bio.

    O que importa aqui não é o visual e sim o que o visual depende: um botão principal
    só (senão não existe principal), o percentual vindo da mesma fonte da home, a página
    fora da indexação, e endereço de rede vazio sumindo em vez de virar link quebrado.
    """

    def test_abre(self):
        self.assertEqual(self.client.get(reverse("links_bio")).status_code, 200)

    def test_tem_um_unico_botao_principal(self):
        # Dois botões roxos viram dois secundários: a hierarquia da página inteira
        # depende de existir um só. Conta o atributo do elemento, não a classe solta -
        # ela também aparece nas regras de CSS da própria página.
        html = self.client.get(reverse("links_bio")).content.decode()
        self.assertEqual(html.count('class="bio-botao bio-botao-principal"'), 1)

    def test_o_botao_principal_leva_para_a_vitrine(self):
        html = self.client.get(reverse("links_bio")).content.decode()
        marcador = 'class="bio-botao bio-botao-principal" href="'
        destino = html.split(marcador)[1].split('"')[0]
        self.assertEqual(destino, reverse("ofertas_lista"))

    def test_mostra_o_mesmo_percentual_anunciado_na_home(self):
        # É a única coisa nesta página que uma ferramenta de fora não faria. Se sair de
        # uma fonte diferente da home, o site promete dois números ao mesmo tempo.
        Oferta.objects.create(
            item_id=1, nome="Fone", nome_curto="fone",
            preco_min=Decimal("100"), preco_max=Decimal("100"),
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )
        # floatformat e não f-string: o template localiza o número (8,00 e não 8.00),
        # e comparar com ponto faria o teste falhar mesmo com a página certa.
        esperado = floatformat(obter_cashback_maximo_anunciado(), 2)

        html = self.client.get(reverse("links_bio")).content.decode()

        self.assertIn(esperado, html)

    def test_fica_fora_da_indexacao_e_do_sitemap(self):
        # É navegação, não conteúdo: indexada, competiria com a home pelas mesmas
        # buscas sem ter nada próprio a dizer.
        html = self.client.get(reverse("links_bio")).content.decode()
        self.assertIn('name="robots" content="noindex', html)

        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn(f"<loc>http://testserver{reverse('links_bio')}</loc>", sitemap)

    def test_endereco_de_rede_vazio_nao_vira_link_quebrado(self):
        with override_settings(URL_WHATSAPP_CANAL="", URL_YOUTUBE=""):
            html = self.client.get(reverse("links_bio")).content.decode()

        self.assertNotIn("Ofertas no WhatsApp", html)
        self.assertNotIn("cash-b no YouTube", html)
        # o principal continua de pé
        self.assertIn('class="bio-botao bio-botao-principal"', html)

    def test_home_e_bio_usam_o_mesmo_endereco_de_whatsapp(self):
        # Os dois liam o endereço escrito à mão no template; um deles desatualizado é o
        # tipo de erro que ninguém percebe.
        with override_settings(URL_WHATSAPP_CANAL="https://whatsapp.com/channel/novo"):
            home = self.client.get(reverse("home")).content.decode()
            links = self.client.get(reverse("links_bio")).content.decode()

        self.assertIn("https://whatsapp.com/channel/novo", home)
        self.assertIn("https://whatsapp.com/channel/novo", links)
