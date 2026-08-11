import hashlib
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from paginas.models import Banner

from .models import Click
from .shopee_client import (
    ShopeeAPIError,
    ShopeeConfigError,
    SubIdInvalidoError,
    executar_graphql,
    gerar_link_curto,
    validar_sub_ids,
)

CREDENCIAIS_TESTE = {
    "SHOPEE_AFFILIATE_APP_ID": "app123",
    "SHOPEE_AFFILIATE_SECRET": "segredo123",
    "SHOPEE_AFFILIATE_API_URL": "https://open-api.affiliate.shopee.com.br/graphql",
}


class AssinaturaShopeeTests(TestCase):
    @override_settings(**CREDENCIAIS_TESTE)
    @patch("links.shopee_client.requests.post")
    def test_header_de_autorizacao_usa_formula_sha256_app_id_timestamp_payload_secret(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"data": {"ok": True}}

        with patch("links.shopee_client.time.time", return_value=1700000000):
            executar_graphql("query { ok }")

        headers_enviados = mock_post.call_args.kwargs["headers"]
        payload_enviado = mock_post.call_args.kwargs["data"]

        assinatura_esperada = hashlib.sha256(
            f"app1231700000000{payload_enviado}segredo123".encode("utf-8")
        ).hexdigest()

        self.assertEqual(
            headers_enviados["Authorization"],
            f"SHA256 Credential=app123, Timestamp=1700000000, Signature={assinatura_esperada}",
        )

    def test_sem_credenciais_configuradas_gera_erro_claro(self):
        with override_settings(SHOPEE_AFFILIATE_APP_ID="", SHOPEE_AFFILIATE_SECRET=""):
            with self.assertRaises(ShopeeConfigError):
                executar_graphql("query { ok }")

    @override_settings(**CREDENCIAIS_TESTE)
    @patch("links.shopee_client.requests.post")
    def test_erro_retornado_pela_shopee_vira_shopee_api_error(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"errors": [{"message": "Invalid Signature"}]}

        with self.assertRaises(ShopeeAPIError):
            executar_graphql("query { ok }")

    @override_settings(**CREDENCIAIS_TESTE)
    @patch("links.shopee_client.requests.post")
    def test_gerar_link_curto_envia_origin_url_e_sub_ids_e_retorna_short_link(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "data": {"generateShortLink": {"shortLink": "https://shope.ee/abc123"}}
        }

        resultado = gerar_link_curto("https://shopee.com.br/produto-i.1.2", ["user1", "clickabc123"])

        self.assertEqual(resultado, "https://shope.ee/abc123")
        payload_enviado = json.loads(mock_post.call_args.kwargs["data"])
        query_enviada = payload_enviado["query"]
        self.assertIn('originUrl:"https://shopee.com.br/produto-i.1.2"', query_enviada)
        self.assertIn('subIds:["user1", "clickabc123"]', query_enviada)


class ClickModelTests(TestCase):
    def test_sub_id_click_e_hexadecimal_sem_hifen_valido_para_a_api_shopee(self):
        usuario = get_user_model().objects.create_user(
            username="usuarioteste", password="senha123", cpf="39053344705"
        )
        click = Click.objects.create(
            usuario=usuario, tipo=Click.TIPO_HOME, url_original="https://shopee.com.br/", link_gerado=""
        )
        sub_id = click.sub_id_click()
        self.assertEqual(len(sub_id), 32)
        validar_sub_ids([sub_id])


class ValidarSubIdsTests(TestCase):
    def test_aceita_letras_e_numeros(self):
        self.assertEqual(validar_sub_ids(["user1", "clickabc123"]), ["user1", "clickabc123"])

    def test_rejeita_hifen_ou_simbolos(self):
        with self.assertRaises(SubIdInvalidoError):
            validar_sub_ids(["click-com-hifen"])

    def test_rejeita_mais_de_cinco_sub_ids(self):
        with self.assertRaises(SubIdInvalidoError):
            validar_sub_ids(["a", "b", "c", "d", "e", "f"])


@override_settings(**CREDENCIAIS_TESTE)
class GerarLinkViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="usuarioteste", password="senhaSegura123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)

    @patch("links.services.gerar_link_curto")
    def test_gerar_link_da_home_cria_click_com_sub_ids_do_usuario(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/home123"

        resposta = self.client.post("/links/", {"acao": "home"}, follow=True)

        click = Click.objects.get()
        self.assertEqual(click.usuario, self.usuario)
        self.assertEqual(click.tipo, Click.TIPO_HOME)
        self.assertEqual(click.link_gerado, "https://shope.ee/home123")
        mock_gerar_link.assert_called_once_with(
            "https://shopee.com.br/", [f"user{self.usuario.id}", click.id.hex]
        )
        self.assertContains(resposta, "Link gerado com sucesso!")
        self.assertContains(resposta, "https://shope.ee/home123")

    @patch("links.services.gerar_link_curto")
    def test_gerar_link_de_produto_valido(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/produto123"

        resposta = self.client.post(
            "/links/",
            {"acao": "produto", "url_produto": "https://shopee.com.br/produto-exemplo-i.123.456"},
            follow=True,
        )

        click = Click.objects.get()
        self.assertEqual(click.tipo, Click.TIPO_PRODUTO)
        self.assertEqual(click.url_original, "https://shopee.com.br/produto-exemplo-i.123.456")
        self.assertContains(resposta, "https://shope.ee/produto123")

    def test_url_de_produto_fora_da_shopee_e_rejeitada(self):
        resposta = self.client.post(
            "/links/", {"acao": "produto", "url_produto": "https://outrosite.com/produto"}, follow=True
        )

        self.assertEqual(Click.objects.count(), 0)
        self.assertContains(resposta, "Informe um link de um produto da Shopee.")

    @patch("links.services.gerar_link_curto")
    def test_erro_da_api_shopee_mostra_mensagem_e_nao_deixa_click_orfao(self, mock_gerar_link):
        mock_gerar_link.side_effect = ShopeeAPIError("Invalid Signature")

        resposta = self.client.post("/links/", {"acao": "home"}, follow=True)

        self.assertContains(resposta, "A Shopee recusou o pedido: Invalid Signature")
        self.assertEqual(Click.objects.count(), 0)

    def test_usuario_nao_logado_e_redirecionado_para_login(self):
        self.client.logout()
        resposta = self.client.get("/links/")
        self.assertRedirects(resposta, "/login/?next=/links/")


class HomeBannerTests(TestCase):
    def setUp(self):
        # A migração de dados 0003 semeia 2 banners reais (inauguração/ofertas) - os testes
        # abaixo querem controlar o estado deles diretamente, então partem de uma base limpa.
        Banner.objects.all().delete()

    def test_sem_banners_ativos_nao_mostra_a_faixa(self):
        resposta = self.client.get("/")
        self.assertNotContains(resposta, '<div class="banner-carrossel">')

    def test_banner_inativo_nao_aparece(self):
        Banner.objects.create(texto="Promoção escondida", ativo=False)
        resposta = self.client.get("/")
        self.assertNotContains(resposta, "Promoção escondida")

    def test_banner_ativo_aparece_com_link(self):
        Banner.objects.create(texto="Cashback em dobro!", link="/ofertas/", ativo=True)
        resposta = self.client.get("/")
        self.assertContains(resposta, "Cashback em dobro!")
        self.assertContains(resposta, 'href="/ofertas/"')

    def test_banners_aparecem_na_ordem_configurada(self):
        Banner.objects.create(texto="Segundo", ordem=2, ativo=True)
        Banner.objects.create(texto="Primeiro", ordem=1, ativo=True)
        resposta = self.client.get("/")
        conteudo = resposta.content.decode()
        self.assertLess(conteudo.index("Primeiro"), conteudo.index("Segundo"))
