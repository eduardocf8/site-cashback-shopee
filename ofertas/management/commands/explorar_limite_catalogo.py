import time

from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, listar_ids_de_ofertas

PAUSA_ENTRE_PAGINAS_SEGUNDOS = 0.5

# sortType da productOfferV2.
ORDENS = {1: "relevância (só com palavra-chave)", 2: "mais vendidos", 3: "maior preço", 4: "menor preço",
          5: "maior comissão"}
# Palavras do pacote padrão: assuntos que costumam vender bem e não se sobrepõem tanto.
PALAVRAS_DO_PACOTE = ["fone", "celular", "vestido", "tenis", "maquiagem", "cozinha", "organizador", "infantil",
                      "pet", "academia"]


class Command(BaseCommand):
    help = (
        "Mede quantos produtos a productOfferV2 da Shopee entrega, sem salvar nada no banco. "
        "Sem opções: o feed geral (listType ALL) que a sincronização da cash-b usa hoje. "
        "Com --ordem/--palavra/--categoria/--loja: uma busca específica. Com --pacote: várias "
        "buscas diferentes, contando quantos produtos ÚNICOS aparecem somando todas (para saber "
        "se dá para importar mais do que os 2.800 do feed geral)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=50, help="Produtos por página (padrão: 50).")
        parser.add_argument(
            "--max-paginas", type=int, default=300,
            help="Teto de segurança por busca (padrão: 300, ou seja, até 15.000 produtos com --limite 50).",
        )
        parser.add_argument("--ordem", type=int, choices=sorted(ORDENS), help="sortType: " + ", ".join(
            f"{k} = {v}" for k, v in ORDENS.items()))
        parser.add_argument("--palavra", default="", help="Palavra-chave (ex: fone).")
        parser.add_argument("--categoria", type=int, help="productCatId da Shopee (ex: 100636).")
        parser.add_argument("--loja", type=int, help="shopId de uma loja.")
        parser.add_argument(
            "--pacote", action="store_true",
            help="Roda o feed geral, as ordens 2, 3, 4 e 5 e uma busca por palavra-chave para cada "
                 "palavra de --palavras, e mostra quantos produtos únicos somam.",
        )
        parser.add_argument("--palavras", default=",".join(PALAVRAS_DO_PACOTE),
                            help="Palavras do --pacote, separadas por vírgula.")
        parser.add_argument("--pausa", type=float, default=PAUSA_ENTRE_PAGINAS_SEGUNDOS,
                            help="Segundos entre uma página e outra (padrão: 0,5).")

    def handle(self, *args, **options):
        self.limite, self.max_paginas, self.pausa = options["limite"], options["max_paginas"], options["pausa"]
        try:
            if options["pacote"]:
                self.pacote([p.strip() for p in options["palavras"].split(",") if p.strip()])
            else:
                busca = {"ordem": options["ordem"], "palavra": options["palavra"].strip(),
                         "categoria": options["categoria"], "loja": options["loja"]}
                ids, fim = self.medir(busca, mostrar_paginas=True)
                self.resumo(busca, ids, fim)
        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))

    @staticmethod
    def nome(busca: dict) -> str:
        partes = []
        if busca.get("palavra"):
            partes.append(f"palavra '{busca['palavra']}'")
        if busca.get("categoria"):
            partes.append(f"categoria {busca['categoria']}")
        if busca.get("loja"):
            partes.append(f"loja {busca['loja']}")
        if not partes:
            partes.append("feed geral")
        if busca.get("ordem"):
            partes.append(f"ordem {busca['ordem']} ({ORDENS[busca['ordem']]})")
        return ", ".join(partes)

    def medir(self, busca: dict, mostrar_paginas: bool = False) -> tuple[set, str]:
        """(itemIds da busca, como ela terminou: "fim", "teto" ou o erro da Shopee)."""
        ids, pagina = set(), 1
        while pagina <= self.max_paginas:
            try:
                resultado = listar_ids_de_ofertas(pagina, self.limite, ordem=busca.get("ordem"),
                                                  palavra=busca.get("palavra", ""), categoria=busca.get("categoria"),
                                                  loja=busca.get("loja"))
            except ShopeeAPIError as erro:
                return ids, f"erro da Shopee na página {pagina}: {erro}"
            ids.update(str(no.get("itemId")) for no in resultado.get("nodes") or [] if no.get("itemId"))
            tem_proxima = (resultado.get("pageInfo") or {}).get("hasNextPage")
            if mostrar_paginas and (pagina % 10 == 0 or not tem_proxima):
                self.stdout.write(f"  página {pagina}: {len(ids)} produtos até aqui (hasNextPage={tem_proxima})")
            if not tem_proxima:
                return ids, f"fim em {pagina} página(s)"
            pagina += 1
            time.sleep(self.pausa)
        return ids, f"parou no teto de {self.max_paginas} páginas com hasNextPage=True (a Shopee tinha mais)"

    def resumo(self, busca, ids, fim):
        self.stdout.write(self.style.SUCCESS(f"\n{self.nome(busca)}: {len(ids)} produtos ({fim})."))

    def pacote(self, palavras: list[str]):
        buscas = [{}] + [{"ordem": o} for o in (2, 3, 4, 5)] + [{"palavra": p} for p in palavras]
        self.stdout.write(f"Medindo {len(buscas)} buscas (até {self.max_paginas} páginas de {self.limite} cada)...\n")
        todos = set()
        geral = set()
        for i, busca in enumerate(buscas):
            ids, fim = self.medir(busca)
            novos = ids - todos
            todos |= ids
            if i == 0:
                geral = ids
            self.stdout.write(
                f"- {self.nome(busca)}: {len(ids)} produtos ({fim}); {len(novos)} novos; "
                f"{len(ids & geral)} também estão no feed geral. Total único: {len(todos)}"
            )
        ganho = len(todos) - len(geral)
        self.stdout.write(self.style.SUCCESS(
            f"\nSomando as {len(buscas)} buscas: {len(todos)} produtos únicos, contra {len(geral)} do feed geral "
            f"sozinho ({'+' if ganho >= 0 else ''}{ganho})."
        ))
