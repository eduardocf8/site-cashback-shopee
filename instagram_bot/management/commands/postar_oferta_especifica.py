from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from instagram_bot.services import publicar_story_oferta_especifica
from ofertas.services import LinkProdutoInvalidoError


class Command(BaseCommand):
    help = (
        "Posta um story pra UM produto específico da Shopee, escolhido na mão (fora "
        "do calendário automático) - passa o link do produto (aceita shopee.com.br e "
        "link curto shp.ee). Roda pelo Shell do Render: "
        "python manage.py postar_oferta_especifica <link>"
    )

    def add_arguments(self, parser):
        parser.add_argument("url_produto", help="Link do produto na Shopee")

    def handle(self, *args, **options):
        # Não existe request de verdade aqui (é um comando de terminal, não uma
        # requisição HTTP) - monta um fake com o host de produção, senão os links de
        # aprovar/rejeitar no e-mail (aprovacao.py, request.build_absolute_uri) saem
        # com o host de teste do Django ("testserver") em vez do domínio real.
        host = settings.RENDER_EXTERNAL_HOSTNAME
        if not host:
            raise CommandError(
                "RENDER_EXTERNAL_HOSTNAME não configurado - esse comando espera rodar em produção "
                "(Shell do Render), pra montar os links do e-mail de aprovação com o host certo."
            )
        request = RequestFactory().get("/", secure=True, SERVER_NAME=host)

        try:
            registro = publicar_story_oferta_especifica(options["url_produto"], request)
        except LinkProdutoInvalidoError as erro:
            raise CommandError(str(erro))

        self.stdout.write(self.style.SUCCESS(
            f"Registro criado: oferta={registro.oferta_nome!r}, status={registro.get_status_display()}"
        ))
        if registro.status == registro.STATUS_PENDENTE_APROVACAO:
            self.stdout.write(
                f"Aprovação enviada por e-mail pra {settings.INSTAGRAM_APROVADOR_EMAIL} - "
                "confira e clique em \"Aprovar e publicar\" por lá."
            )
        elif registro.status == registro.STATUS_ERRO:
            self.stdout.write(self.style.ERROR(f"Erro: {registro.erro}"))
