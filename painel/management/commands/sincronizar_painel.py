import os
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from bot_whatsapp.avisos_de_queda import uma_volta as avisar_bots_parados
from licencas.dono import enviar_resumo_semanal
from painel.memoria import memoria_em_uso_mb
from painel.emails_valor import enviar_pendentes as enviar_dicas
from painel.primeiros_passos import enviar_pendentes as enviar_primeiros_passos
from meusite.vitrine import uma_volta as atualizar_vitrines
from notas.fila import tem_fila as notas_na_fila
from notas.fila import uma_volta as emitir_notas
from painel.relatorio import enviar_pendentes as enviar_relatorios
from painel.resultados import contas_pendentes, processar

MINUTOS_ENTRE_LOGS_DE_MEMORIA = 10


class Command(BaseCommand):
    help = (
        "Busca na Shopee os resultados das contas do painel do Appfiliado (pedidos de "
        "\"Atualizar 30 dias\" primeiro, depois quem está há mais de 3h sem atualizar). "
        "Com --loop fica rodando (Background Worker do Render) e também mantém as conexões "
        "do Bot de WhatsApp (bot_whatsapp/gerenciador.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Fica rodando, conferindo a fila de tempos em tempos.")
        parser.add_argument("--intervalo", type=int, default=30, help="Segundos entre uma conferência e outra (com --loop).")

    def handle(self, *args, loop=False, intervalo=30, **options):
        if loop and settings.APPFILIADO_WHATSAPP_NO_WORKER:
            from bot_whatsapp.gerenciador import garantir_limite_de_memoria, iniciar_em_segundo_plano

            garantir_limite_de_memoria(sys.argv)  # pode reiniciar o processo uma vez
            if iniciar_em_segundo_plano():
                self.stdout.write(f"Bot de WhatsApp ligado neste worker (GOMEMLIMIT={os.environ['GOMEMLIMIT']}).")
        if loop:
            from bot_whatsapp.alertas import iniciar_em_segundo_plano as iniciar_alerta_de_preco

            iniciar_alerta_de_preco()  # confere os preços dos produtos acompanhados (thread própria)
            from ofertas.catalogo import iniciar_em_segundo_plano as iniciar_catalogo

            iniciar_catalogo()  # catálogo de ofertas da cash-b, aos poucos (thread própria)
            from bot_whatsapp.mensagens import iniciar_em_segundo_plano as iniciar_mensagens

            iniciar_mensagens()  # mensagens avulsas agendadas nos grupos (thread própria)
        proximo_log_de_memoria = 0.0
        while True:
            if loop and time.monotonic() >= proximo_log_de_memoria:
                # O Render reinicia o worker se passar de 512 MB (plano Starter): este
                # número no log mostra se está chegando perto.
                self.stdout.write(f"Memória em uso: {memoria_em_uso_mb()} MB")
                proximo_log_de_memoria = time.monotonic() + MINUTOS_ENTRE_LOGS_DE_MEMORIA * 60
            close_old_connections()  # o worker fica dias no ar; conexões velhas caem
            try:
                for conta in contas_pendentes():
                    self.stdout.write(processar(conta))
                for linha in enviar_relatorios():  # relatório diário por e-mail (de manhã)
                    self.stdout.write(linha)
                for linha in atualizar_vitrines():  # Meu site: busca/links da vitrine
                    self.stdout.write(linha)
                for linha in emitir_notas():  # Notas fiscais: fila de emissão e e-mails
                    self.stdout.write(linha)
                for linha in avisar_bots_parados():  # e-mail quando o WhatsApp de alguém para
                    self.stdout.write(linha)
                for linha in enviar_primeiros_passos():  # e-mails do dia 1 e do dia 3 pra quem assinou
                    self.stdout.write(linha)
                for linha in enviar_dicas():  # e-mails de dicas dos dias 2 a 21, às 10h
                    self.stdout.write(linha)
                for linha in enviar_resumo_semanal():  # painel do dono: domingo às 9h, pro e-mail de suporte
                    self.stdout.write(linha)
            except Exception as erro:  # banco fora do ar etc.: tenta de novo na próxima volta
                if not loop:
                    raise
                self.stderr.write(f"Falha ao conferir a fila: {erro}")
            if not loop:
                break
            # Com notas fiscais na fila, volta logo (a barra de emissão anda sem pausas longas).
            time.sleep(5 if notas_na_fila() else max(5, intervalo))
