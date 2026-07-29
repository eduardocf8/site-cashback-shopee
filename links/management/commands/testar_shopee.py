from django.conf import settings
from django.core.management.base import BaseCommand

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError, gerar_link_curto


class Command(BaseCommand):
    help = "Testa a conexão com a API de afiliados Shopee usando as credenciais do .env"

    def handle(self, *args, **options):
        self.stdout.write(f"Endpoint: {settings.SHOPEE_AFFILIATE_API_URL}")
        self.stdout.write(f"AppId configurado: {'sim' if settings.SHOPEE_AFFILIATE_APP_ID else 'NÃO'}")
        self.stdout.write("Tentando gerar um link de afiliado para a página inicial da Shopee...\n")

        try:
            link = gerar_link_curto(settings.SHOPEE_HOME_URL, ["testeconexao"])
        except ShopeeConfigError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except SubIdInvalidoError as erro:
            self.stderr.write(self.style.ERROR(str(erro)))
            return
        except ShopeeAPIError as erro:
            self.stderr.write(self.style.ERROR(f"A Shopee retornou um erro: {erro}"))
            self.stdout.write(
                "\nIsso confirma que a conexão chegou até a Shopee (a assinatura foi aceita), "
                "mas algo no pedido em si foi rejeitado. Copie a mensagem de erro acima para "
                "ajustarmos juntos."
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Sucesso! Link gerado: {link}"))
