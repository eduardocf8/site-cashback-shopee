from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PaginasEstaticasSitemap(Sitemap):
    changefreq = "monthly"

    prioridades = {
        "home": 1.0,
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
