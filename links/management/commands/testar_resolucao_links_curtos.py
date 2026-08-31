import time
from urllib.parse import urlparse

from django.core.management.base import BaseCommand

from links.models import Click
from ofertas.services import LinkProdutoInvalidoError, PADRAO_ITEM_ID_NA_URL, _resolver_item_id

DOMINIOS_LINK_CURTO = ("s.shopee.com.br", "shp.ee")
PAUSA_ENTRE_TESTES_SEGUNDOS = 1


class Command(BaseCommand):
    help = (
        "Testa DE VERDADE, contra a Shopee ao vivo, a resolução de cada link curto já "
        "convertido no site (ver analisar_links_curtos pra classificação só por formato) "
        "- pra saber a taxa de falha real, não só o teto do problema (ROADMAP.md Fase 35/36)."
    )

    def handle(self, *args, **options):
        clicks = Click.objects.filter(tipo=Click.TIPO_PRODUTO).exclude(url_original="")

        urls_curtas = set()
        for click in clicks.iterator():
            url = click.url_original
            if PADRAO_ITEM_ID_NA_URL.search(url):
                continue
            host = urlparse(url).netloc.lower()
            if any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_LINK_CURTO):
                urls_curtas.add(url)

        total = len(urls_curtas)
        if total == 0:
            self.stdout.write("Nenhum link curto encontrado pra testar.")
            return

        self.stdout.write(f"Testando {total} link(s) curto(s) único(s) contra a Shopee...\n")

        sucessos = 0
        falhas = 0
        for i, url in enumerate(sorted(urls_curtas), start=1):
            try:
                item_id = _resolver_item_id(url)
                sucessos += 1
                self.stdout.write(self.style.SUCCESS(f"[{i}/{total}] OK - {url} -> item_id={item_id}"))
            except LinkProdutoInvalidoError as erro:
                falhas += 1
                self.stdout.write(self.style.ERROR(f"[{i}/{total}] FALHOU - {url}: {erro}"))

            if i < total:
                time.sleep(PAUSA_ENTRE_TESTES_SEGUNDOS)

        self.stdout.write(
            f"\nResultado: {sucessos}/{total} resolveram ({sucessos / total * 100:.1f}%), "
            f"{falhas}/{total} falharam ({falhas / total * 100:.1f}%)."
        )
