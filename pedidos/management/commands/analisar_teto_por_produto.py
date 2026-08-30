from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, buscar_conversoes

# Faixas de preço por PRODUTO (não por pedido - o teto de cashback sempre foi aplicado
# por item, ver pedidos/services.py::_montar_defaults). Ajuste aqui pra testar outros
# cortes/valores sem mexer no resto do comando.
FAIXAS = [
    ("até R$ 1.000", Decimal("0"), Decimal("1000")),
    ("R$ 1.000 – 2.000", Decimal("1000"), Decimal("2000")),
    ("acima de R$ 2.000", Decimal("2000"), None),
]
TETOS_PROPOSTOS = {
    "até R$ 1.000": Decimal("10"),
    "R$ 1.000 – 2.000": Decimal("20"),
    "acima de R$ 2.000": Decimal("30"),
}


def _faixa(preco: Decimal) -> str:
    for nome, minimo, maximo in FAIXAS:
        if preco >= minimo and (maximo is None or preco < maximo):
            return nome
    return FAIXAS[-1][0]


class Command(BaseCommand):
    help = (
        "Analisa o histórico real de pedidos da conta de afiliado (TODOS os pedidos da conta, não só "
        "os gerados pelo site) pra embasar uma proposta de teto de cashback escalonado por preço do "
        "produto - ver FAIXAS/TETOS_PROPOSTOS acima. Não grava nada no banco, só imprime um resumo. "
        "Ignora CASHBACK_MULTIPLICADOR_CAMPANHA (usa sempre o valor base) - se algum pedido do "
        "período caiu numa campanha de cashback em dobro, o cashback real pago pode ter sido maior "
        "do que o estimado aqui pra uma pequena parte dos itens."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=365,
            help="Quantidade de dias para trás a partir de hoje que serão consultados (padrão: 365). "
            "A Shopee pode limitar o quanto dá pra voltar no tempo - se der erro, tenta um valor menor.",
        )

    def handle(self, *args, **options):
        agora = datetime.now(tz=dt_timezone.utc)
        inicio = agora - timedelta(days=options["dias"])
        percentual_repasse = Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL)) / Decimal("100")
        teto_atual = Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO))

        self.stdout.write(f"Consultando conversionReport de {inicio:%d/%m/%Y} até {agora:%d/%m/%Y}...\n")

        contagem = defaultdict(int)
        comissao_total = defaultdict(Decimal)
        cashback_atual_total = defaultdict(Decimal)
        cashback_proposto_total = defaultdict(Decimal)
        itens_no_teto_atual = defaultdict(int)
        itens_no_teto_proposto = defaultdict(int)
        total_itens = 0

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
                            faixa = _faixa(preco)
                            contagem[faixa] += 1
                            comissao_total[faixa] += comissao_item

                            cashback_bruto = comissao_item * percentual_repasse
                            cashback_hoje = min(cashback_bruto, teto_atual)
                            cashback_novo = min(cashback_bruto, TETOS_PROPOSTOS[faixa])
                            cashback_atual_total[faixa] += cashback_hoje
                            cashback_proposto_total[faixa] += cashback_novo
                            if cashback_bruto > teto_atual:
                                itens_no_teto_atual[faixa] += 1
                            if cashback_bruto > TETOS_PROPOSTOS[faixa]:
                                itens_no_teto_proposto[faixa] += 1

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

        self.stdout.write(self.style.SUCCESS(f"\n{total_itens} item(ns) com preço e comissão encontrados.\n"))
        for nome, _min, _max in FAIXAS:
            n = contagem[nome]
            percentual_do_total = n / total_itens * 100
            self.stdout.write(self.style.SUCCESS(f"\n{nome} — {n} item(ns) ({percentual_do_total:.1f}% do total)"))
            if not n:
                continue
            self.stdout.write(f"  Comissão total gerada:                        R$ {comissao_total[nome]:.2f}")
            self.stdout.write(
                f"  Cashback pago hoje (teto único R$ {teto_atual}):        "
                f"R$ {cashback_atual_total[nome]:.2f}  ({itens_no_teto_atual[nome]} item(ns) bateram no teto)"
            )
            self.stdout.write(
                f"  Cashback com teto R$ {TETOS_PROPOSTOS[nome]} proposto pra essa faixa: "
                f"R$ {cashback_proposto_total[nome]:.2f}  ({itens_no_teto_proposto[nome]} item(ns) bateriam no teto)"
            )
            diferenca = cashback_proposto_total[nome] - cashback_atual_total[nome]
            self.stdout.write(self.style.WARNING(f"  Custo extra estimado nessa faixa:             R$ {diferenca:.2f}"))

        total_hoje = sum(cashback_atual_total.values())
        total_novo = sum(cashback_proposto_total.values())
        self.stdout.write(self.style.SUCCESS(f"\nTotal pago hoje (teto único R$ {teto_atual}):         R$ {total_hoje:.2f}"))
        self.stdout.write(self.style.SUCCESS(f"Total pago com os tetos escalonados propostos: R$ {total_novo:.2f}"))
        self.stdout.write(self.style.WARNING(f"Diferença total no período: R$ {total_novo - total_hoje:.2f}"))
