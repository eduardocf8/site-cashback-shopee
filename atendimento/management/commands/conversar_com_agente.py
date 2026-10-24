"""Conversa com o agente de vendas pelo terminal, sem WhatsApp (precisa da ANTHROPIC_API_KEY).
Uso: python manage.py conversar_com_agente   (linha vazia ou Ctrl+D encerra)"""

from django.core.management.base import BaseCommand

from atendimento import agente


class Command(BaseCommand):
    help = "Testa o agente de vendas do WhatsApp pelo terminal."

    def add_arguments(self, parser):
        parser.add_argument("--nome", default="", help="Nome da pessoa no WhatsApp (opcional).")

    def handle(self, *args, nome="", **opcoes):
        historico = []
        while True:
            try:
                texto = input("\nVocê: ").strip()
            except EOFError:
                break
            if not texto:
                break
            historico.append({"role": "user", "content": texto})
            resposta = agente.responder(historico, nome=nome)
            historico.append({"role": "assistant", "content": resposta.texto})
            self.stdout.write(f"\nAgente: {resposta.texto}")
            if resposta.humano:
                self.stdout.write(self.style.WARNING(f"\n[chamou você: {resposta.humano['motivo']} | {resposta.humano['resumo']}]"))
