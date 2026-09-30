"""Mesma planilha de /pinterest/planilha.csv, pelo Shell do Render - ver
pinterest/services.py."""
from django.core.management.base import BaseCommand

from pinterest import services


class Command(BaseCommand):
    help = "Imprime a planilha CSV da semana pro \"Importar conteúdo\" do Pinterest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantidade", type=int, default=services.PINS_POR_SEMANA,
            help=f"Quantos Pins (um por categoria). Padrão: {services.PINS_POR_SEMANA}.",
        )

    def handle(self, *args, **opcoes):
        self.stdout.write(services.gerar_csv(services.montar_linhas(opcoes["quantidade"])), ending="")
