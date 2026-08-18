from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, buscar_conversoes


class Command(BaseCommand):
    help = (
        "Consulta o conversionReport da Shopee direto (sem gravar nada no banco) e imprime "
        "o itemTotalCommission cru de cada pedido - útil pra comparar com o valor mostrado "
        "no painel oficial de afiliados da Shopee pra um pedido específico, e assim descobrir "
        "se esse campo já inclui ou não o bônus de campanha do vendedor."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=30,
            help="Quantidade de dias para trás a partir de hoje que serão consultados (padrão: 30).",
        )
        parser.add_argument(
            "--pedido", type=str, default="",
            help="Filtra só o(s) orderId que contenha esse texto (ex: --pedido 250813ABCDE1). "
            "Sem esse filtro, imprime todos os pedidos do período.",
        )

    def handle(self, *args, **options):
        agora = datetime.now(tz=dt_timezone.utc)
        inicio = agora - timedelta(days=options["dias"])
        filtro_pedido = options["pedido"].strip()

        self.stdout.write(f"Consultando conversionReport de {inicio:%d/%m/%Y} até {agora:%d/%m/%Y}...\n")

        scroll_id = None
        total_pedidos = 0
        total_comissao = 0.0

        try:
            while True:
                pagina = buscar_conversoes(int(inicio.timestamp()), int(agora.timestamp()), scroll_id)

                for conversao in pagina["nodes"]:
                    for pedido in conversao.get("orders", []):
                        if filtro_pedido and filtro_pedido not in pedido["orderId"]:
                            continue

                        total_pedidos += 1
                        comissao_pedido = 0.0
                        self.stdout.write(self.style.SUCCESS(f"\nPedido {pedido['orderId']} — status: {pedido['orderStatus']}"))
                        self.stdout.write(f"  conversionId: {conversao.get('conversionId')}")
                        self.stdout.write(f"  utmContent:   {conversao.get('utmContent')}")
                        self.stdout.write(f"  purchaseTime: {_formatar_timestamp(conversao.get('purchaseTime'))}")

                        for item in pedido.get("items", []):
                            comissao_item = float(item.get("itemTotalCommission") or 0)
                            comissao_pedido += comissao_item
                            self.stdout.write(f"  - {item.get('itemName', '(sem nome)')}")
                            self.stdout.write(f"      completeTime:        {_formatar_timestamp(item.get('completeTime'))}")
                            self.stdout.write(f"      itemTotalCommission: R$ {comissao_item:.2f}")
                            if item.get("fraudReason"):
                                self.stdout.write(self.style.WARNING(f"      fraudReason: {item['fraudReason']}"))

                        self.stdout.write(f"  total do pedido: R$ {comissao_pedido:.2f}")
                        total_comissao += comissao_pedido

                scroll_id = pagina["pageInfo"].get("scrollId")
                if not pagina["pageInfo"].get("hasNextPage"):
                    break
        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except ShopeeAPIError as erro:
            self.stderr.write(self.style.ERROR(f"A Shopee retornou um erro: {erro}"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n{total_pedidos} pedido(s) encontrado(s). Comissão total: R$ {total_comissao:.2f}"))
        if filtro_pedido and total_pedidos == 0:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum pedido bateu com o filtro --pedido. Confira se o orderId está certo e se ele "
                    "caiu dentro da janela de --dias consultada (o purchaseTime é o que conta)."
                )
            )


def _formatar_timestamp(valor):
    if not valor:
        return "—"
    return datetime.fromtimestamp(int(valor), tz=dt_timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
