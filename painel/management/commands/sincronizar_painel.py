import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from painel.resultados import contas_pendentes, processar


class Command(BaseCommand):
    help = (
        "Busca na Shopee os resultados das contas do painel do Appfiliado (pedidos de "
        "\"Atualizar agora\" primeiro, depois quem está há mais de 3h sem atualizar). "
        "Com --loop fica rodando (Background Worker do Render) e também mantém as conexões "
        "do Bot de WhatsApp (bot_whatsapp/gerenciador.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Fica rodando, conferindo a fila de tempos em tempos.")
        parser.add_argument("--intervalo", type=int, default=30, help="Segundos entre uma conferência e outra (com --loop).")

    def handle(self, *args, loop=False, intervalo=30, **options):
        if loop and settings.APPFILIADO_WHATSAPP_NO_WORKER:
            from bot_whatsapp.gerenciador import iniciar_em_segundo_plano

            if iniciar_em_segundo_plano():
                self.stdout.write("Bot de WhatsApp ligado neste worker.")
        while True:
            close_old_connections()  # o worker fica dias no ar; conexões velhas caem
            try:
                for conta in contas_pendentes():
                    self.stdout.write(processar(conta))
            except Exception as erro:  # banco fora do ar etc.: tenta de novo na próxima volta
                if not loop:
                    raise
                self.stderr.write(f"Falha ao conferir a fila: {erro}")
            if not loop:
                break
            time.sleep(max(5, intervalo))
