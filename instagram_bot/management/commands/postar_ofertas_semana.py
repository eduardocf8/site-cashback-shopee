from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from django.utils import timezone

from instagram_bot.services import publicar_post_ofertas_semana


class Command(BaseCommand):
    help = (
        "Posta o carrossel \"melhores ofertas da semana\" agora, fora do calendário "
        "automático (normalmente só roda toda sexta) - útil pra testar sem esperar até "
        "sexta. Roda pelo Shell do Render: python manage.py postar_ofertas_semana"
    )

    def handle(self, *args, **options):
        # Mesmo motivo do postar_oferta_especifica: não existe request de verdade aqui
        # (comando de terminal, não requisição HTTP) - monta um fake com o host de
        # produção, senão os links de aprovar/rejeitar no e-mail saem com o host de
        # teste do Django ("testserver") em vez do domínio real.
        host = settings.RENDER_EXTERNAL_HOSTNAME
        if not host:
            raise CommandError(
                "RENDER_EXTERNAL_HOSTNAME não configurado - esse comando espera rodar em produção "
                "(Shell do Render), pra montar os links do e-mail de aprovação com o host certo."
            )
        request = RequestFactory().get("/", secure=True, SERVER_NAME=host)

        registro = publicar_post_ofertas_semana(timezone.localdate(), request)
        if registro is None:
            self.stdout.write(self.style.WARNING("Sem ofertas sincronizadas - nada foi postado."))
            return

        self.stdout.write(self.style.SUCCESS(f"Registro criado: status={registro.get_status_display()}"))
        if registro.status == registro.STATUS_PENDENTE_APROVACAO:
            self.stdout.write(
                f"Aprovação enviada por e-mail pra {settings.INSTAGRAM_APROVADOR_EMAIL} - "
                "confira e clique em \"Aprovar e publicar\" por lá."
            )
        elif registro.status == registro.STATUS_ERRO:
            self.stdout.write(self.style.ERROR(f"Erro: {registro.erro}"))
