from django.core.management.base import BaseCommand

from saques.services import verificar_saques_pendentes


class Command(BaseCommand):
    help = "Reconsulta na Asaas os saques que ficaram com status 'processando' e atualiza o status final."

    def handle(self, *args, **options):
        resultado = verificar_saques_pendentes()
        self.stdout.write(f"Saques verificados: {resultado['verificados']}")
        self.stdout.write(self.style.SUCCESS(f"Saques com status atualizado: {resultado['atualizados']}"))
