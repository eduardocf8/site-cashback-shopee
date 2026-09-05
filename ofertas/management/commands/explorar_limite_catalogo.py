import time

from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, buscar_ofertas_produtos

PAUSA_ENTRE_PAGINAS_SEGUNDOS = 0.5


class Command(BaseCommand):
    help = (
        "Descobre até onde vai o feed productOfferV2 (listType ALL) da Shopee, sem salvar nada "
        "no banco - só pra medir se o catálogo de ofertas de afiliado é maior do que os "
        "max_paginas x limite_por_pagina que sincronizar_ofertas() importa hoje (ver ROADMAP.md, "
        "'aumentar o número de produtos importados')."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=50, help="Produtos por página (padrão: 50).")
        parser.add_argument(
            "--max-paginas", type=int, default=300,
            help="Teto de segurança pra não ficar chamando a API pra sempre caso o feed seja "
            "gigante ou algo dê errado (padrão: 300, ou seja, até 15.000 produtos com --limite 50).",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        max_paginas = options["max_paginas"]

        self.stdout.write(f"Explorando productOfferV2 com {limite} produtos por página (teto de {max_paginas} páginas)...\n")

        total_produtos = 0
        pagina = 1
        try:
            while pagina <= max_paginas:
                resultado = buscar_ofertas_produtos(pagina, limite)
                quantidade_nesta_pagina = len(resultado["nodes"])
                total_produtos += quantidade_nesta_pagina
                tem_proxima = resultado["pageInfo"].get("hasNextPage")

                if pagina % 10 == 0 or not tem_proxima:
                    self.stdout.write(f"  página {pagina}: {total_produtos} produtos até aqui (hasNextPage={tem_proxima})")

                if not tem_proxima:
                    self.stdout.write(self.style.SUCCESS(
                        f"\nFim real do feed: {total_produtos} produtos em {pagina} página(s) - "
                        "esse é o teto que a Shopee está servindo agora pra essa conta, não um limite nosso."
                    ))
                    return

                pagina += 1
                time.sleep(PAUSA_ENTRE_PAGINAS_SEGUNDOS)

        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except ShopeeAPIError as erro:
            self.stderr.write(self.style.ERROR(f"A Shopee retornou um erro na página {pagina}: {erro}"))
            self.stdout.write(f"Produtos coletados até a falha: {total_produtos} (em {pagina - 1} página(s) completas).")
            return

        self.stdout.write(self.style.WARNING(
            f"\nParou no teto de segurança ({max_paginas} páginas, {total_produtos} produtos) ainda com "
            "hasNextPage=True - a Shopee tinha mais pra dar. Rode de novo com --max-paginas maior "
            "(ex: --max-paginas 600) pra continuar medindo até achar o fim de verdade."
        ))
