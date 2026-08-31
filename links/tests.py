import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ofertas.models import CashbackMaximoCache, Oferta, OfertaDestaqueManual, OfertaManual
from ofertas.services import LinkProdutoInvalidoError, SemComissaoError

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


class HomeCashbackMaximoTests(TestCase):
    def test_home_mostra_o_maximo_calculado(self):
        CashbackMaximoCache.atualizar(Decimal("10.0"))

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.context["cashback_percentual_maximo"], Decimal("10.0"))
        self.assertContains(resposta, "até 10%")


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=100, CASHBACK_MULTIPLICADOR_CAMPANHA=1)
class HomeConversaoCashbackRealTests(TestCase):
    """Ao converter um link no site, o resultado mostra a comissão REAL daquele
    produto (ofertas.services.buscar_oferta_por_link), não o "até X%" genérico do
    catálogo sincronizado - ver links/views.py::_buscar_cashback_real."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)

    @patch("links.views.buscar_oferta_por_link")
    @patch("links.services.gerar_link_curto")
    def test_mostra_o_cashback_real_do_produto_convertido(self, mock_gerar_link, mock_buscar_oferta):
        mock_gerar_link.return_value = "https://shope.ee/produto123"
        mock_buscar_oferta.return_value = Oferta(
            item_id=999, nome="Produto real",
            preco_min=Decimal("50.00"), percentual_comissao=Decimal("0.08"),
        )

        resposta = self.client.post(
            reverse("home"), {"url_produto": "https://shopee.com.br/produto-exemplo-i.1.999"}
        )

        self.assertContains(resposta, "Cashback ativado! 🎉")
        self.assertContains(resposta, "Esse produto rende 8,0% de cashback (R$ 4,00 de volta).")

    @patch("links.views.buscar_oferta_por_link")
    @patch("links.services.gerar_link_curto")
    def test_produto_sem_comissao_ativa_mostra_mensagem_especifica_sem_confete(
        self, mock_gerar_link, mock_buscar_oferta
    ):
        mock_gerar_link.return_value = "https://shope.ee/produto123"
        mock_buscar_oferta.side_effect = SemComissaoError("sem comissão")

        resposta = self.client.post(
            reverse("home"), {"url_produto": "https://shopee.com.br/produto-exemplo-i.1.999"}
        )

        self.assertContains(resposta, "Link gerado, mas sem cashback dessa vez")
        self.assertContains(resposta, "A Shopee não oferece comissão para esse produto, portanto também não há cashback.")
        self.assertNotContains(resposta, "Cashback ativado")
        self.assertNotContains(resposta, '<span class="confete confete-1">')

    @patch("links.views.buscar_oferta_por_link")
    @patch("links.services.gerar_link_curto")
    def test_falha_ao_buscar_comissao_real_nao_impede_o_link_ja_gerado(self, mock_gerar_link, mock_buscar_oferta):
        """Quando a busca da comissão real falha por um motivo genérico (nem confirma
        comissão, nem confirma ausência dela), o link continua funcionando e o site
        mostra um texto neutro, sem afirmar nada que não foi confirmado de verdade -
        ver ROADMAP.md Fase 36. Chegou a existir uma segunda tentativa via navegador
        headless (Fase 37), removida depois de confirmar que a Shopee bloqueia esse
        tipo de navegador nesse cenário."""
        mock_gerar_link.return_value = "https://shope.ee/produto123"
        mock_buscar_oferta.side_effect = LinkProdutoInvalidoError("não consegui abrir o link")

        resposta = self.client.post(
            reverse("home"), {"url_produto": "https://shopee.com.br/produto-exemplo-i.1.999"}
        )

        self.assertContains(resposta, "Link gerado!")
        self.assertContains(resposta, "Para conferir o cashback desse produto, acesse sua conta em alguns dias.")
        self.assertContains(resposta, "https://shope.ee/produto123")
        self.assertNotContains(resposta, "Cashback ativado")
        self.assertNotContains(resposta, '<span class="confete confete-1">')


class HomeCarrosselOfertaManualTests(TestCase):
    def test_oferta_manual_aparece_no_carrossel_com_selo_imperdivel(self):
        OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-manual-i.1.1",
            nome="Produto imperdível", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"), imperdivel=True,
        )

        resposta = self.client.get(reverse("home"))

        nomes_carrossel = [oferta.nome for oferta in resposta.context["ofertas_em_alta"]]
        self.assertIn("Produto imperdível", nomes_carrossel)
        self.assertContains(resposta, "Produto imperdível")
        self.assertContains(resposta, "Oferta imperdível")
        self.assertContains(resposta, "R$ 100,00")  # preço antigo riscado
        self.assertContains(resposta, reverse("ofertas_manual_ir", args=[OfertaManual.objects.get().id]))


class HomeDestaqueManualTests(TestCase):
    def test_destaque_manual_substitui_a_oferta_do_dia(self):
        destaque = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto do dia manual", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("150.00"), preco_novo=Decimal("99.90"),
            preco_avista=Decimal("89.90"), percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.context["oferta_destaque"], destaque)
        self.assertContains(resposta, "Produto do dia manual")
        self.assertContains(resposta, "R$ 150,00")  # preço antigo riscado
        self.assertContains(resposta, "R$ 89,90 à vista")
        self.assertContains(resposta, reverse("ofertas_destaque_manual_ir", args=[destaque.id]))
