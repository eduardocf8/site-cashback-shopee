from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.utils import timezone

from instagram_bot.services import publicar_carrossel_tematico


class Command(BaseCommand):
    help = (
        "Posta o próximo carrossel temático da rotação agora, fora do calendário "
        "automático (normalmente só roda toda quarta) - útil para testar sem esperar "
        "até quarta. Publica direto, sem e-mail de aprovação (ver conteudo.py, "
        "TEMAS_CARROSSEL). Roda pelo Shell do Render: "
        "python manage.py postar_carrossel_tematico"
    )

    def handle(self, *args, **options):
        # Mesmo motivo do postar_ofertas_semana: não existe request de verdade aqui
        # (comando de terminal, não requisição HTTP) - monta um fake com o host de
        # produção, pra _url_publica_da_midia montar a URL pública certa.
        host = settings.RENDER_EXTERNAL_HOSTNAME
        if not host:
            raise CommandError(
                "RENDER_EXTERNAL_HOSTNAME não configurado - esse comando espera rodar em produção "
                "(Shell do Render), para montar a URL pública da mídia com o host certo."
            )
        request = RequestFactory().get("/", secure=True, SERVER_NAME=host)

        registro = publicar_carrossel_tematico(timezone.localdate(), request)

        self.stdout.write(self.style.SUCCESS(f"Registro criado: status={registro.get_status_display()}"))
        if registro.status == registro.STATUS_ERRO:
            self.stdout.write(self.style.ERROR(f"Erro: {registro.erro}"))
