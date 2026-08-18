from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PaginasEstaticasSitemap(Sitemap):
    prioridades = {
        "home": 1.0,
        # A vitrine renova sozinha a cada sincronização com a Shopee, então é a página
        # que mais muda depois da home - por isso prioridade alta e changefreq próprio.
        "ofertas_lista": 0.8,
        "faq": 0.6,
        "regras_cashback": 0.6,
        "registrar": 0.5,
        "contato": 0.5,
        "termos_de_uso": 0.3,
        "privacidade": 0.3,
        "cookies": 0.2,
        "login": 0.1,
    }

    def items(self):
        return list(self.prioridades.keys())

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.prioridades[item]

    def changefreq(self, item):
        # A vitrine é remontada a cada sincronização com a Shopee; a home mostra as
        # ofertas em alta e muda junto. O resto é texto institucional, que raramente
        # muda - dizer "monthly" nesses evita gastar rastreamento à toa.
        return "daily" if item in {"home", "ofertas_lista"} else "monthly"
