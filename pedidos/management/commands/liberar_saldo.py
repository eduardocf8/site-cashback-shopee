from django.core.management.base import BaseCommand

from pedidos.services import liberar_saldo


class Command(BaseCommand):
    help = "Libera o saldo dos pedidos validados cuja data prevista de liberação (mês da validação + 2) já chegou."

    def handle(self, *args, **options):
        total = liberar_saldo()
        self.stdout.write(self.style.SUCCESS(f"Pedidos liberados: {total}"))
