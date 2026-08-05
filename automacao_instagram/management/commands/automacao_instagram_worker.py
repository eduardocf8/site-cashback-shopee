import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from automacao_instagram.services import processar_ciclo

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Loop infinito: a cada AUTOMACAO_INSTAGRAM_INTERVALO_SEGUNDOS, verifica "
        "comentários novos nas automações ativas (todas as contas) e responde/envia "
        "DM conforme configurado. Pensado pra rodar como Background Worker no Render "
        "(processo à parte do site, não do gunicorn) - ver README."
    )

    def handle(self, *args, **options):
        intervalo = settings.AUTOMACAO_INSTAGRAM_INTERVALO_SEGUNDOS
        self.stdout.write(self.style.SUCCESS(
            f"[automacao_instagram] worker iniciado - verificando a cada {intervalo}s"
        ))
        while True:
            try:
                processar_ciclo()
            except Exception:
                logger.exception("[automacao_instagram] erro inesperado no ciclo do worker")
            time.sleep(intervalo)
