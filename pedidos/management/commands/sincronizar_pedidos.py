from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError
from pedidos.services import sincronizar


class Command(BaseCommand):
    help = "Sincroniza os pedidos da Shopee (conversionReport) dos últimos N dias com o banco local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=60,
            help="Quantidade de dias para trás a partir de hoje que serão consultados (padrão: 60).",
        )

    def handle(self, *args, **options):
        agora = datetime.now(tz=dt_timezone.utc)
        inicio = agora - timedelta(days=options["dias"])

        self.stdout.write(f"Consultando pedidos de {inicio:%d/%m/%Y} até {agora:%d/%m/%Y}...")

        try:
            resultado = sincronizar(int(inicio.timestamp()), int(agora.timestamp()))
        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except ShopeeAPIError as erro:
            self.stderr.write(self.style.ERROR(f"A Shopee retornou um erro: {erro}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Pedidos novos: {resultado['novos']}"))
        self.stdout.write(self.style.SUCCESS(f"Pedidos atualizados: {resultado['atualizados']}"))
        if resultado["nao_identificados"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Conversões sem usuário identificado: {resultado['nao_identificados']} "
                    "(confira no /admin/ os pedidos com 'usuario' em branco)"
                )
            )
