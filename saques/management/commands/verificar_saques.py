from django.core.management.base import BaseCommand

from saques.models import Saque
from saques.services import atualizar_status_saque


class Command(BaseCommand):
    help = "Reconsulta na Asaas os saques que ficaram com status 'processando' e atualiza o status final."

    def handle(self, *args, **options):
        pendentes = Saque.objects.filter(status=Saque.STATUS_PROCESSANDO)
        atualizados = 0
        for saque in pendentes:
            status_antes = saque.status
            atualizar_status_saque(saque)
            if saque.status != status_antes:
                atualizados += 1

        self.stdout.write(f"Saques verificados: {pendentes.count()}")
        self.stdout.write(self.style.SUCCESS(f"Saques com status atualizado: {atualizados}"))
