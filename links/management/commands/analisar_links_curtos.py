from urllib.parse import urlparse

from django.core.management.base import BaseCommand

from links.models import Click
from ofertas.services import PADRAO_ITEM_ID_NA_URL

DOMINIOS_LINK_CURTO = ("s.shopee.com.br", "shp.ee")


class Command(BaseCommand):
    help = (
        "Classifica os links de produto já convertidos no site (Click.TIPO_PRODUTO) pra "
        "estimar quantos são links curtos/dinâmicos (risco de cair no fallback genérico "
        "de cashback real, ver ROADMAP.md Fase 34/35/36) - não testa a resolução de "
        "verdade contra a Shopee, só classifica pelo formato da URL."
    )

    def handle(self, *args, **options):
        clicks = Click.objects.filter(tipo=Click.TIPO_PRODUTO).exclude(url_original="")
        total = clicks.count()

        if total == 0:
            self.stdout.write("Nenhum Click de produto encontrado ainda.")
            return

        resolve_direto = 0
        link_curto = 0
        outro_formato = 0

        for click in clicks.iterator():
            url = click.url_original
            if PADRAO_ITEM_ID_NA_URL.search(url):
                resolve_direto += 1
                continue

            host = urlparse(url).netloc.lower()
            if any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_LINK_CURTO):
                link_curto += 1
            else:
                outro_formato += 1

        def pct(n):
            return f"{n} ({n / total * 100:.1f}%)"

        self.stdout.write(f"Total de links de produto convertidos: {total}\n")
        self.stdout.write(
            f"Resolve direto (já tem -i.<loja>.<item> ou /product/<loja>/<item> na URL, "
            f"sem precisar de rede): {pct(resolve_direto)}"
        )
        self.stdout.write(
            f"Link curto (s.shopee.com.br / shp.ee - risco de cair no bloqueio JS visto "
            f"na Fase 35): {pct(link_curto)}"
        )
        self.stdout.write(f"Outro formato (URL da Shopee sem os dois padrões acima): {pct(outro_formato)}")
        self.stdout.write(
            "\nAtenção: isso classifica só o FORMATO da URL, não testa contra a Shopee de "
            "verdade - dentro de 'link curto', pode ter links que resolvem bem (redirect "
            "HTTP normal) e outros que caem no bloqueio via JavaScript (Fase 35). O número "
            "acima é o teto do problema, não a taxa de falha real."
        )
