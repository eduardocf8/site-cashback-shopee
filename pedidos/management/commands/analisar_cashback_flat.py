from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, buscar_conversoes


class Command(BaseCommand):
    help = (
        "Simula trocar o modelo atual (repassa a comissão real recebida, com teto por produto) por "
        "um cashback FLAT sobre o preço, sem teto - a mesma %% pra todo mundo, não importa a comissão "
        "real do produto. Usa o histórico real da conta de afiliado inteira (item por item, não por "
        "pedido total - ver analisar_teto_por_produto). Não grava nada no banco."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=90,
            help="Quantos dias pra trás consultar (padrão: 90 - a Shopee só libera os últimos 3 meses).",
        )
        parser.add_argument(
            "--percentual", type=float, default=20.0,
            help="%% de cashback flat sobre o preço, sem teto (padrão: 20).",
        )

    def handle(self, *args, **options):
        agora = datetime.now(tz=dt_timezone.utc)
        inicio = agora - timedelta(days=options["dias"])
        percentual_flat = Decimal(str(options["percentual"])) / Decimal("100")
        percentual_repasse = Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL)) / Decimal("100")
        teto_atual = Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO))

        self.stdout.write(f"Consultando conversionReport de {inicio:%d/%m/%Y} até {agora:%d/%m/%Y}...\n")

        total_itens = 0
        preco_total = Decimal("0")
        comissao_total = Decimal("0")
        cashback_hoje_total = Decimal("0")
        cashback_flat_total = Decimal("0")
        itens_com_prejuizo = 0
        prejuizo_total = Decimal("0")

        scroll_id = None
        try:
            while True:
                pagina = buscar_conversoes(int(inicio.timestamp()), int(agora.timestamp()), scroll_id)
                for conversao in pagina["nodes"]:
                    for pedido in conversao.get("orders", []):
                        for item in pedido.get("items", []):
                            preco = Decimal(str(item.get("actualAmount") or "0"))
                            comissao_item = Decimal(str(item.get("itemTotalCommission") or "0"))
                            if not preco or not comissao_item:
                                continue

                            total_itens += 1
                            preco_total += preco
                            comissao_total += comissao_item

                            cashback_hoje = min(comissao_item * percentual_repasse, teto_atual)
                            cashback_hoje_total += cashback_hoje

                            cashback_flat = preco * percentual_flat
                            cashback_flat_total += cashback_flat
                            if cashback_flat > comissao_item:
                                itens_com_prejuizo += 1
                                prejuizo_total += cashback_flat - comissao_item

                scroll_id = pagina["pageInfo"].get("scrollId")
                if not pagina["pageInfo"].get("hasNextPage"):
                    break
        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except ShopeeAPIError as erro:
            self.stderr.write(self.style.ERROR(f"A Shopee retornou um erro: {erro}"))
            return

        if not total_itens:
            self.stdout.write(self.style.WARNING("Nenhum item com preço e comissão encontrado no período."))
            return

        comissao_media_pct = (comissao_total / preco_total * 100) if preco_total else Decimal("0")

        self.stdout.write(self.style.SUCCESS(f"\n{total_itens} item(ns) com preço e comissão encontrados."))
        self.stdout.write(f"Preço total desses itens:                     R$ {preco_total:.2f}")
        self.stdout.write(f"Comissão real total recebida da Shopee:       R$ {comissao_total:.2f}")
        self.stdout.write(f"  (comissão média real: {comissao_media_pct:.2f}% do preço)\n")

        self.stdout.write(f"Cashback pago hoje (repasse + teto R$ {teto_atual}): R$ {cashback_hoje_total:.2f}")
        self.stdout.write(
            f"Cashback se fosse flat {options['percentual']:.1f}% sem teto:      R$ {cashback_flat_total:.2f}"
        )

        margem_hoje = comissao_total - cashback_hoje_total
        margem_flat = comissao_total - cashback_flat_total
        self.stdout.write(self.style.SUCCESS(f"\nMargem retida hoje (comissão - cashback):        R$ {margem_hoje:.2f}"))
        estilo_margem_flat = self.style.ERROR if margem_flat < 0 else self.style.SUCCESS
        self.stdout.write(estilo_margem_flat(f"Margem retida com o flat proposto (comissão - cashback): R$ {margem_flat:.2f}"))

        percentual_prejuizo = itens_com_prejuizo / total_itens * 100
        self.stdout.write(
            self.style.WARNING(
                f"\n{itens_com_prejuizo} de {total_itens} item(ns) ({percentual_prejuizo:.1f}%) pagariam mais "
                f"de cashback do que a comissão recebida por eles - prejuízo de R$ {prejuizo_total:.2f} só nesses."
            )
        )
        if margem_flat < 0:
            self.stdout.write(
                self.style.ERROR(
                    f"\nNo período analisado, um flat de {options['percentual']:.1f}% sem teto pagaria "
                    f"R$ {-margem_flat:.2f} A MAIS do que toda a comissão recebida da Shopee - ou seja, "
                    "prejuízo líquido, não só em alguns itens."
                )
            )
