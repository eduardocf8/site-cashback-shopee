import hashlib
import json
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from ofertas.models import CashbackMaximoCache, Oferta, OfertaDestaqueManual, OfertaManual
from ofertas.services import LinkProdutoInvalidoError, SemComissaoError

from . import services as links_services
from .models import URL_MAX_LENGTH, Click
from .services import gerar_click, resolver_item_id_alvo_pendentes
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

    def test_sub_id_usuario_de_clique_anonimo_e_anon(self):
        """ROADMAP 13.11 (decisão de 24/10/2026) - clique sem conta usa "anon" no
        lugar de "user<id>", pra identificar na sincronização que esse clique ainda
        não tem usuário (ver pedidos/services.py::_montar_defaults)."""
        click = Click.objects.create(
            usuario=None, tipo=Click.TIPO_HOME, url_original="https://shopee.com.br/", link_gerado=""
        )
        sub_id = click.sub_id_usuario()
        self.assertEqual(sub_id, "anon")
        validar_sub_ids([sub_id])


class GerarClickAnonimoTests(TestCase):
    """Clique sem conta (ROADMAP 13.11, decisão de 24/10/2026) - gerar_click aceita
    usuario=None (ou o AnonymousUser que request.user é quando não tem login)."""

    @patch("links.services.gerar_link_curto")
    def test_usuario_none_cria_click_sem_usuario_com_subid_anon(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(None, Click.TIPO_HOME, None)

        self.assertIsNone(click.usuario_id)
        self.assertEqual(mock_gerar_link.call_args.args[1], ["anon", click.id.hex])

    @patch("links.services.gerar_link_curto")
    def test_anonymous_user_e_normalizado_pra_none(self, mock_gerar_link):
        from django.contrib.auth.models import AnonymousUser

        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(AnonymousUser(), Click.TIPO_HOME, None)

        self.assertIsNone(click.usuario_id)


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

    @patch("links.views.enviar_evento")
    @patch("links.services.gerar_link_curto")
    def test_gerar_link_manda_evento_geroulinkcashback_pra_conversions_api(
        self, mock_gerar_link, mock_enviar_evento
    ):
        mock_gerar_link.return_value = "https://shope.ee/home123"

        self.client.post("/links/", {"acao": "home"}, follow=True)

        mock_enviar_evento.assert_called_once()
        nome_evento, _request, event_id, dados_customizados = mock_enviar_evento.call_args[0]
        self.assertEqual(nome_evento, "GerouLinkCashback")
        self.assertTrue(event_id)
        self.assertEqual(dados_customizados, {"tipo_click": Click.TIPO_HOME})


class GerarClickItemIdAlvoTests(TestCase):
    """item_id_alvo identifica qual produto gerou o clique - usado depois pra
    confirmar que a compra real bate com o produto do link/vitrine antes de aplicar
    o piso de cashback de venda direta (ver pedidos/services.py e ROADMAP.md, Fase
    41). Só tenta resolver pelo padrão de texto na URL, sem seguir redirecionamento -
    não pode deixar a conversão do link lenta (ver Fase 35)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    @patch("links.services.gerar_link_curto")
    def test_link_de_produto_com_padrao_reconhecido_preenche_item_id_alvo(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(self.usuario, Click.TIPO_PRODUTO, "https://shopee.com.br/produto-i.1.999")

        self.assertEqual(click.item_id_alvo, 999)

    @patch("links.services.gerar_link_curto")
    def test_link_curto_sem_padrao_reconhecido_fica_sem_item_id_alvo(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(self.usuario, Click.TIPO_PRODUTO, "https://s.shopee.com.br/abc123")

        self.assertIsNone(click.item_id_alvo)

    @patch("links.services.gerar_link_curto")
    def test_clique_na_home_nunca_tenta_resolver_item_id_alvo(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(self.usuario, Click.TIPO_HOME, None)

        self.assertIsNone(click.item_id_alvo)

    @patch("links.services.gerar_link_curto")
    def test_item_id_alvo_explicito_tem_prioridade_sobre_resolver_da_url(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/abc"

        click = gerar_click(
            self.usuario, Click.TIPO_VITRINE, "https://shopee.com.br/produto-i.1.999", item_id_alvo=555
        )

        self.assertEqual(click.item_id_alvo, 555)


class ResolverItemIdAlvoPendentesTests(TestCase):
    """Tarefa agendada (executar_resolucao_item_id_alvo) que tenta resolver, seguindo
    redirecionamento de verdade, o item_id_alvo dos cliques que a resolução rápida na
    hora do clique não conseguiu - ver ROADMAP.md, Fase 41/42."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _click(self, tipo=Click.TIPO_PRODUTO, item_id_alvo=None, url="https://s.shopee.com.br/abc"):
        return Click.objects.create(
            usuario=self.usuario, tipo=tipo, url_original=url, item_id_alvo=item_id_alvo,
            link_gerado="https://shope.ee/abc",
        )

    @patch("links.services.resolver_item_id_com_rede")
    def test_resolve_clique_pendente_e_conta_no_resultado(self, mock_resolver):
        click = self._click()
        mock_resolver.return_value = 999

        resultado = resolver_item_id_alvo_pendentes()

        click.refresh_from_db()
        self.assertEqual(click.item_id_alvo, 999)
        self.assertEqual(resultado, {"tentados": 1, "resolvidos": 1})

    @patch("links.services.resolver_item_id_com_rede")
    def test_link_ainda_nao_resolvivel_continua_pendente(self, mock_resolver):
        click = self._click()
        mock_resolver.return_value = None

        resultado = resolver_item_id_alvo_pendentes()

        click.refresh_from_db()
        self.assertIsNone(click.item_id_alvo)
        self.assertEqual(resultado, {"tentados": 1, "resolvidos": 0})

    @patch("links.services.resolver_item_id_com_rede")
    def test_ignora_clique_que_ja_tem_item_id_alvo(self, mock_resolver):
        self._click(item_id_alvo=1)

        resultado = resolver_item_id_alvo_pendentes()

        mock_resolver.assert_not_called()
        self.assertEqual(resultado, {"tentados": 0, "resolvidos": 0})

    @patch("links.services.resolver_item_id_com_rede")
    def test_ignora_clique_de_venda_indireta(self, mock_resolver):
        self._click(tipo=Click.TIPO_HOME, url="https://shopee.com.br/")

        resultado = resolver_item_id_alvo_pendentes()

        mock_resolver.assert_not_called()
        self.assertEqual(resultado, {"tentados": 0, "resolvidos": 0})

    @patch("links.services.resolver_item_id_com_rede")
    def test_respeita_o_limite_por_execucao(self, mock_resolver):
        mock_resolver.return_value = 1
        for _ in range(links_services.LIMITE_RESOLUCOES_POR_EXECUCAO + 5):
            self._click()

        resultado = resolver_item_id_alvo_pendentes()

        self.assertEqual(resultado["tentados"], links_services.LIMITE_RESOLUCOES_POR_EXECUCAO)


class HomeCashbackMaximoTests(TestCase):
    def test_home_mostra_o_maximo_calculado(self):
        CashbackMaximoCache.atualizar(Decimal("10.0"))

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.context["cashback_percentual_maximo"], Decimal("10.0"))
        self.assertContains(resposta, "até 10%")


class HomeConversorVisitanteNaoLogadoTests(TestCase):
    """Quem chega de anúncio e tenta converter um link sem estar logado cai na
    página de escolha (ROADMAP 13.11, decisão de 24/10/2026), não direto no cadastro:
    "Cadastrar e continuar" (link preservado, ver accounts/views.py::registrar) ou
    "Continuar sem cadastro" (clique fica anônimo, ver links/views.py::home)."""

    URL_PRODUTO = "https://shopee.com.br/produto-exemplo-i.1.999"

    def setUp(self):
        cache.clear()  # evita herdar contador de rate limit de click_anonimo de outro teste

    def test_redireciona_pra_pagina_de_escolha_preservando_o_link_colado(self):
        resposta = self.client.post(reverse("home"), {"url_produto": self.URL_PRODUTO})

        proximo = f"{reverse('home')}?{urlencode({'url_produto': self.URL_PRODUTO})}"
        esperado = f"{reverse('continuar_sem_cadastro')}?{urlencode({'next': proximo, 'origem': 'conversor'})}"
        self.assertRedirects(resposta, esperado, fetch_redirect_response=False)

    def test_nao_cria_click_nem_tenta_converter_sem_estar_logado(self):
        resposta = self.client.post(reverse("home"), {"url_produto": self.URL_PRODUTO})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Click.objects.count(), 0)

    @patch("links.services.gerar_link_curto")
    def test_continuar_sem_cadastro_converte_o_link_anonimamente(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/produto123"

        resposta = self.client.get(reverse("home"), {"url_produto": self.URL_PRODUTO, "continuar": "sem_cadastro"})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "https://shope.ee/produto123")
        click = Click.objects.get()
        self.assertIsNone(click.usuario_id)
        self.assertEqual(click.tipo, Click.TIPO_PRODUTO)
        cookie = resposta.cookies.get("cashb_clique_anonimo")
        self.assertIsNotNone(cookie)
        self.assertIn(click.id.hex, cookie.value)

    @patch("links.services.gerar_link_curto")
    def test_continuar_sem_cadastro_registra_etapa_do_funil(self, mock_gerar_link):
        from accounts.models import EventoFunil

        mock_gerar_link.return_value = "https://shope.ee/produto123"

        self.client.get(reverse("home"), {"url_produto": self.URL_PRODUTO, "continuar": "sem_cadastro"})

        self.assertTrue(EventoFunil.objects.filter(etapa=EventoFunil.CLICOU_SEM_CONTA, origem="conversor").exists())

    @patch("links.services.gerar_link_curto")
    def test_limite_de_cliques_anonimos_por_ip(self, mock_gerar_link):
        from accounts.funil import LIMITE_CLIQUES_ANONIMOS_POR_HORA

        mock_gerar_link.return_value = "https://shope.ee/produto123"

        for _ in range(LIMITE_CLIQUES_ANONIMOS_POR_HORA):
            self.client.get(reverse("home"), {"url_produto": self.URL_PRODUTO, "continuar": "sem_cadastro"})

        resposta = self.client.get(reverse("home"), {"url_produto": self.URL_PRODUTO, "continuar": "sem_cadastro"})

        self.assertEqual(resposta.status_code, 429)


class IrParaShopeeSemCadastroTests(TestCase):
    """ROADMAP 13.11 (decisão de 24/10/2026): quem clica em "Ir pra Shopee" sem conta
    cai na página de escolha; só gera o clique (anônimo) se escolher "continuar sem
    cadastro" ali."""

    def setUp(self):
        cache.clear()  # evita herdar contador de rate limit de outro teste (click_anonimo)

    def test_sem_login_manda_pra_pagina_de_escolha_com_next_e_origem(self):
        resposta = self.client.get(reverse("ir_para_shopee"))

        self.assertRedirects(
            resposta,
            f"{reverse('continuar_sem_cadastro')}?next=%2Fir-para-shopee%2F&origem=ir_shopee",
            fetch_redirect_response=False,
        )
        self.assertEqual(Click.objects.count(), 0)

    @patch("links.services.gerar_link_curto")
    def test_continuar_sem_cadastro_gera_click_anonimo_e_guarda_cookie(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/home123"

        resposta = self.client.get(reverse("ir_para_shopee") + "?continuar=sem_cadastro")

        click = Click.objects.get()
        self.assertIsNone(click.usuario_id)
        self.assertRedirects(resposta, "https://shope.ee/home123", fetch_redirect_response=False)
        cookie = resposta.cookies.get("cashb_clique_anonimo")
        self.assertIsNotNone(cookie)
        # Assinado (ver django.http.HttpResponse.set_signed_cookie), mas sem
        # criptografia - o valor original aparece de qualquer jeito, antes da
        # assinatura.
        self.assertIn(click.id.hex, cookie.value)

    @patch("links.services.gerar_link_curto")
    def test_continuar_sem_cadastro_registra_etapa_do_funil(self, mock_gerar_link):
        from accounts.models import EventoFunil

        mock_gerar_link.return_value = "https://shope.ee/home123"

        self.client.get(reverse("ir_para_shopee") + "?continuar=sem_cadastro")

        self.assertTrue(
            EventoFunil.objects.filter(etapa=EventoFunil.CLICOU_SEM_CONTA, origem="ir_shopee").exists()
        )

    @patch("links.services.gerar_link_curto")
    def test_limite_de_cliques_anonimos_por_ip(self, mock_gerar_link):
        from accounts.funil import LIMITE_CLIQUES_ANONIMOS_POR_HORA

        mock_gerar_link.return_value = "https://shope.ee/home123"

        for _ in range(LIMITE_CLIQUES_ANONIMOS_POR_HORA):
            self.client.get(reverse("ir_para_shopee") + "?continuar=sem_cadastro")

        resposta = self.client.get(reverse("ir_para_shopee") + "?continuar=sem_cadastro")

        self.assertEqual(resposta.status_code, 429)


class ContinuarSemCadastroViewTests(TestCase):
    """Página de escolha (ROADMAP 13.11) - ver accounts/funil.py::exigir_login_ou_pagina_de_escolha."""

    def test_mostra_as_duas_opcoes_com_os_links_certos(self):
        resposta = self.client.get(
            reverse("continuar_sem_cadastro") + "?next=/ir-para-shopee/&origem=ir_shopee"
        )

        self.assertContains(resposta, "Cadastrar e continuar")
        self.assertContains(resposta, "Continuar sem cadastro")
        self.assertContains(resposta, f"{reverse('registrar')}?next=%2Fir-para-shopee%2F")
        self.assertContains(resposta, "/ir-para-shopee/?continuar=sem_cadastro")

    def test_next_externo_e_recusado(self):
        resposta = self.client.get(
            reverse("continuar_sem_cadastro") + "?next=https://outrosite.com/roubo"
        )

        self.assertRedirects(resposta, reverse("home"))

    def test_sem_next_redireciona_pra_home(self):
        resposta = self.client.get(reverse("continuar_sem_cadastro"))

        self.assertRedirects(resposta, reverse("home"))

    def test_aviso_do_navegador_instagram_so_aparece_nesse_navegador(self):
        navegador_instagram = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Mobile/15E148 Instagram 330.0.0.0"
        )
        resposta = self.client.get(
            reverse("continuar_sem_cadastro") + "?next=/ir-para-shopee/&origem=ir_shopee",
            HTTP_USER_AGENT=navegador_instagram,
        )

        self.assertContains(resposta, "Você está no navegador do Instagram")

    def test_sem_navegador_instagram_nao_mostra_o_aviso(self):
        resposta = self.client.get(
            reverse("continuar_sem_cadastro") + "?next=/ir-para-shopee/&origem=ir_shopee",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        )

        self.assertNotContains(resposta, "Você está no navegador do Instagram")


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=100)
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
        self.assertContains(resposta, "O pedido aparece na sua conta em até 2 dias.")
        self.assertContains(resposta, "Prazos e o que não gera cashback")
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
        self.assertContains(resposta, "Para conferir o cashback desse produto, acesse sua conta em até 2 dias.")
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

    def test_preco_avista_aparece_destacado_e_parcelado_embaixo(self):
        """O preço à vista (com desconto) é o destacado no cartão; o parcelado (preco_novo)
        vira uma linha menor abaixo dele - não o contrário."""
        OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-manual-i.2.2",
            nome="Produto com preço à vista", imagem_url="https://exemplo.com/img.jpg",
            preco_novo=Decimal("99.90"), preco_avista=Decimal("89.90"),
            percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("home"))

        self.assertContains(resposta, "R$ 89,90")
        self.assertContains(resposta, "R$ 99,90 parcelado")


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
        self.assertContains(resposta, "R$ 89,90")  # preço à vista, destacado como preço principal
        self.assertContains(resposta, "R$ 99,90 parcelado")
        self.assertContains(resposta, reverse("ofertas_destaque_manual_ir", args=[destaque.id]))

    def test_destaque_manual_sem_preco_antigo_nao_mostra_riscado(self):
        """preco_antigo é opcional - nem toda loja mostra um preço "de" pra comparar
        (ver ROADMAP.md)."""
        destaque = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.2.2",
            nome="Produto sem preço antigo", imagem_url="https://exemplo.com/img.jpg",
            preco_novo=Decimal("99.90"), percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.context["oferta_destaque"], destaque)
        self.assertContains(resposta, "R$ 99,90")
        self.assertNotContains(resposta, '<span class="destaque-preco-riscado">')


class LinkLongoTests(TestCase):
    """Link da Shopee copiado do navegador (com parâmetros de rastreio) passa de 200
    caracteres, o padrão do URLField: o Postgres recusava (varchar(200)) e o usuário via
    erro 500 na home. Os campos de URL do Click agora comportam links longos e o
    formulário recusa só o que passa do limite, com mensagem em vez de erro."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="colalinklongo", password="senha123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)

    def _url(self, tamanho):
        base = "https://shopee.com.br/produto-exemplo-i.123.456?"
        return base + "x=" + "a" * (tamanho - len(base) - 2)

    def test_campos_de_url_do_click_aceitam_mais_de_200_caracteres(self):
        self.assertGreater(Click._meta.get_field("url_original").max_length, 1000)
        self.assertGreater(Click._meta.get_field("link_gerado").max_length, 1000)

    @patch("links.views._buscar_cashback_real", return_value=(None, False))
    @patch("links.services.gerar_link_curto")
    def test_home_converte_link_com_mais_de_200_caracteres(self, mock_gerar_link, _):
        mock_gerar_link.return_value = "https://shope.ee/longo123"
        url = self._url(600)

        resposta = self.client.post("/", {"url_produto": url})

        self.assertEqual(resposta.status_code, 200)
        click = Click.objects.get()
        self.assertEqual(click.url_original, url)
        self.assertContains(resposta, "https://shope.ee/longo123")

    @patch("links.services.gerar_link_curto")
    def test_home_recusa_link_acima_do_limite_com_mensagem_e_sem_erro(self, mock_gerar_link):
        resposta = self.client.post("/", {"url_produto": self._url(URL_MAX_LENGTH + 100)})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Esse link é longo demais")
        self.assertEqual(Click.objects.count(), 0)
        mock_gerar_link.assert_not_called()


class CashbackEstimadoAoVivoTests(TestCase):
    """Estimativa consultada assim que o link é colado no conversor da home, antes de
    gerar o link - ver links/views.py::cashback_estimado."""

    URL_COMPLETA = "https://shopee.com.br/Geladeira-437L-Philco-i.123.456"

    def setUp(self):
        cache.clear()

    def _consultar(self, url):
        return self.client.get(reverse("cashback_estimado"), {"url": url}).json()

    @patch("links.views.buscar_oferta_por_item")
    def test_link_completo_traz_percentual_e_valor_reais(self, mock_buscar):
        mock_buscar.return_value = Oferta(
            item_id=456, nome="Geladeira", preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.098"),
        )

        dados = self._consultar(self.URL_COMPLETA)

        mock_buscar.assert_called_once_with(456)
        self.assertEqual(dados, {"status": "ok", "percentual": "9,8", "valor": "9,80"})

    @patch("links.views.buscar_oferta_por_item")
    def test_percentual_inteiro_sai_sem_casa_decimal(self, mock_buscar):
        mock_buscar.return_value = Oferta(
            item_id=456, nome="Geladeira", preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.12"),
        )

        self.assertEqual(self._consultar(self.URL_COMPLETA)["percentual"], "12")

    @patch("links.views.buscar_oferta_por_item")
    def test_produto_sem_comissao(self, mock_buscar):
        mock_buscar.side_effect = SemComissaoError("sem comissão")

        self.assertEqual(self._consultar(self.URL_COMPLETA), {"status": "sem_comissao"})

    @patch("links.views.resolver_item_id_com_rede", return_value=456)
    @patch("links.views.buscar_oferta_por_item")
    def test_link_curto_resolvido_traz_percentual_real(self, mock_buscar, mock_resolver):
        mock_buscar.return_value = Oferta(
            item_id=456, nome="Geladeira", preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.098"),
        )

        dados = self._consultar("https://s.shopee.com.br/8V9juuKQqX")

        self.assertEqual(dados["status"], "ok")
        mock_buscar.assert_called_once_with(456)
        # Timeout curto: rota pública com 1 worker só no gunicorn.
        self.assertLessEqual(mock_resolver.call_args.kwargs["timeout"], 5)

    @patch("links.views.resolver_item_id_com_rede", return_value=None)
    @patch("links.views.buscar_oferta_por_item")
    def test_link_curto_nao_identificado(self, mock_buscar, _mock_resolver):
        for url in ("https://s.shopee.com.br/8V9juuKQqX", "https://br.shp.ee/SPbtUzbT"):
            self.assertEqual(self._consultar(url), {"status": "link_curto"})
        mock_buscar.assert_not_called()

    @patch("links.views.resolver_item_id_com_rede", return_value=456)
    @patch("links.views.buscar_oferta_por_item")
    def test_link_curto_repetido_nao_abre_a_pagina_da_shopee_de_novo(self, mock_buscar, mock_resolver):
        mock_buscar.side_effect = SemComissaoError("sem comissão")

        self._consultar("https://br.shp.ee/SPbtUzbT")
        self._consultar("https://br.shp.ee/SPbtUzbT")

        mock_resolver.assert_called_once()

    @patch("links.views.buscar_oferta_por_item")
    def test_link_completo_sem_id_do_produto_nao_e_chamado_de_link_curto(self, mock_buscar):
        self.assertEqual(self._consultar("https://shopee.com.br/flash_sale"), {"status": "nao_identificado"})
        mock_buscar.assert_not_called()

    @patch("links.views.buscar_oferta_por_item")
    def test_falha_na_api_da_shopee_vira_indisponivel_sem_guardar_no_cache(self, mock_buscar):
        mock_buscar.side_effect = ShopeeAPIError("fora do ar")
        self.assertEqual(self._consultar(self.URL_COMPLETA), {"status": "indisponivel"})

        mock_buscar.side_effect = None
        mock_buscar.return_value = Oferta(
            item_id=456, nome="Geladeira", preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.098"),
        )
        self.assertEqual(self._consultar(self.URL_COMPLETA)["status"], "ok")

    @patch("links.views.buscar_oferta_por_item")
    def test_mesmo_produto_consultado_de_novo_usa_o_cache(self, mock_buscar):
        mock_buscar.return_value = Oferta(
            item_id=456, nome="Geladeira", preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.098"),
        )

        self._consultar(self.URL_COMPLETA)
        self._consultar(self.URL_COMPLETA + "?sp_atk=abc")

        mock_buscar.assert_called_once()

    @patch("links.views.buscar_oferta_por_item")
    def test_limite_de_consultas_por_ip(self, mock_buscar):
        mock_buscar.side_effect = SemComissaoError("sem comissão")
        for _ in range(30):
            self.client.get(reverse("cashback_estimado"), {"url": self.URL_COMPLETA})

        resposta = self.client.get(reverse("cashback_estimado"), {"url": self.URL_COMPLETA})

        self.assertEqual(resposta.status_code, 429)
