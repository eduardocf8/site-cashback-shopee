from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from instagram_bot.models import RegistroPublicacao
from links.models import Click

from .models import Oferta, OfertaDestaqueManual, OfertaManual
from .services import (
    LinkProdutoInvalidoError,
    SemComissaoError,
    _montar_oferta,
    _resolver_item_id,
    buscar_oferta_por_link,
    obter_cashback_maximo_anunciado,
    resolver_item_id_com_rede,
    resolver_item_id_sem_rede,
    selecionar_carrossel_home,
    sincronizar_ofertas,
)

CREDENCIAIS_TESTE = {
    "SHOPEE_AFFILIATE_APP_ID": "app123",
    "SHOPEE_AFFILIATE_SECRET": "segredo123",
    "SHOPEE_AFFILIATE_API_URL": "https://open-api.affiliate.shopee.com.br/graphql",
}


class OrdenarPorCashbackTests(TestCase):
    def setUp(self):
        Oferta.objects.create(
            item_id=1, nome="Comissão baixa", categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            percentual_comissao=Decimal("0.0200"), vendas=100,
        )
        Oferta.objects.create(
            item_id=2, nome="Comissão alta", categoria_id=1,
            product_link="https://shopee.com.br/produto-2-i.2.2",
            percentual_comissao=Decimal("0.1000"), vendas=10,
        )
        Oferta.objects.create(
            item_id=3, nome="Comissão média", categoria_id=1,
            product_link="https://shopee.com.br/produto-3-i.3.3",
            percentual_comissao=Decimal("0.0500"), vendas=50,
        )

    def test_ordena_por_maior_cashback(self):
        resposta = self.client.get(reverse("ofertas_lista"), {"ordenar": "maior_cashback"})

        nomes = [oferta.nome for oferta in resposta.context["ofertas"]]
        self.assertEqual(nomes, ["Comissão alta", "Comissão média", "Comissão baixa"])

    def test_ordena_por_maior_cashback_em_reais_diferente_do_percentual(self):
        # Preço e comissão desenhados pra dar ordens DIFERENTES entre % e R$, provando
        # que são duas ordenações de fato distintas, não a mesma coisa disfarçada:
        # - "Caro comissão baixa": 2% de R$1000 = R$20 (menor % da tabela, maior R$)
        # - "Barato comissão alta": 10% de R$100 = R$10 (maior % da tabela, menor R$)
        Oferta.objects.create(
            item_id=10, nome="Caro comissão baixa", categoria_id=1,
            product_link="https://shopee.com.br/produto-10-i.10.10",
            preco_min=Decimal("1000.00"), percentual_comissao=Decimal("0.02"), vendas=1,
        )
        Oferta.objects.create(
            item_id=11, nome="Barato comissão alta", categoria_id=1,
            product_link="https://shopee.com.br/produto-11-i.11.11",
            preco_min=Decimal("100.00"), percentual_comissao=Decimal("0.10"), vendas=1,
        )

        resposta = self.client.get(reverse("ofertas_lista"), {"ordenar": "maior_cashback_reais"})

        nomes = [oferta.nome for oferta in resposta.context["ofertas"]]
        indice_caro = nomes.index("Caro comissão baixa")
        indice_barato = nomes.index("Barato comissão alta")
        self.assertLess(indice_caro, indice_barato)

    def test_maior_cashback_aparece_nas_opcoes_de_ordenacao(self):
        resposta = self.client.get(reverse("ofertas_lista"))

        valores = [valor for valor, _rotulo in resposta.context["ordenacoes"]]
        self.assertIn("maior_cashback", valores)
        self.assertIn("maior_cashback_reais", valores)


class MontarOfertaTests(TestCase):
    def test_usa_commissionRate_combinado_com_bonus_de_vendedor(self):
        # commissionRate = shopeeCommissionRate + sellerCommissionRate. Confirmado
        # comparando com o painel oficial de afiliados da Shopee que o bônus de campanha
        # do vendedor já entra de fato no cashback pago em vendas diretas reais - por
        # isso o site também deve mostrar esse valor combinado, não só a base da Shopee
        # (ver links/shopee_client.py e pedidos/services.py).
        node = {
            "itemId": 26142718061,
            "commissionRate": "0.14",
            "productName": "Cama Cabana Pet",
            "productCatIds": [100629],
        }

        oferta = _montar_oferta(node, categorias_nivel1={100629: "Casa"})

        self.assertEqual(oferta.percentual_comissao, Decimal("0.14"))


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=100, CASHBACK_MULTIPLICADOR_CAMPANHA=1)
class CashbackEstimadoTests(TestCase):
    def test_calcula_valor_e_percentual_sem_limite(self):
        oferta = Oferta(
            item_id=1, nome="Produto com comissão alta", categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            preco_min=Decimal("100.00"), preco_max=Decimal("100.00"),
            percentual_comissao=Decimal("0.20"),  # 20% de R$100 = R$20, sem teto nenhum
        )

        self.assertEqual(oferta.valor_cashback_estimado, Decimal("20.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("20.0"))

    def test_preco_zero_nao_quebra(self):
        oferta = Oferta(
            item_id=3, nome="Produto sem preço sincronizado", categoria_id=1,
            product_link="https://shopee.com.br/produto-3-i.3.3",
            preco_min=Decimal("0"), preco_max=Decimal("0"),
            percentual_comissao=Decimal("0.05"),
        )

        self.assertEqual(oferta.valor_cashback_estimado, Decimal("0.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("5.0"))

    @override_settings(CASHBACK_MINIMO_VENDA_DIRETA=1.6)
    def test_comissao_abaixo_do_piso_mostra_o_piso_de_venda_direta(self):
        """Toda oferta do catálogo vira um clique de link/vitrine específico
        (ir_para_oferta), verificado 1:1 com o item comprado - então o card nunca deve
        anunciar menos que o piso de venda direta, mesmo quando a comissão real da
        Shopee é baixa (ver ROADMAP.md, Fase 39/41)."""
        oferta = Oferta(
            item_id=4, nome="Produto com comissão baixa", categoria_id=1,
            product_link="https://shopee.com.br/produto-4-i.4.4",
            preco_min=Decimal("100.00"), preco_max=Decimal("100.00"),
            percentual_comissao=Decimal("0.005"),  # 0,5% de R$100 = R$0,50, abaixo do piso
        )

        self.assertEqual(oferta.percentual_cashback, Decimal("1.6"))
        self.assertEqual(oferta.valor_cashback_estimado, Decimal("1.60"))


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=100, CASHBACK_MULTIPLICADOR_CAMPANHA=1, CASHBACK_MAXIMO_ANUNCIADO=2.4,
)
class CashbackMaximoAnunciadoTests(TestCase):
    def _pagina(self, nodes, has_next_page=False):
        return {"nodes": nodes, "pageInfo": {"page": 1, "limit": 50, "hasNextPage": has_next_page}}

    def _node(self, item_id, commission_rate, price):
        return {
            "itemId": item_id,
            "commissionRate": commission_rate,
            "productName": f"Produto {item_id}",
            "priceMin": price,
            "priceMax": price,
            "productCatIds": [100],
        }

    def test_sem_sincronizacao_ainda_cai_pro_fallback_configurado(self):
        maximo = obter_cashback_maximo_anunciado()

        self.assertEqual(maximo, Decimal("2.4"))

    @patch("ofertas.services.buscar_ofertas_produtos")
    def test_sincronizacao_calcula_o_maximo_real_do_catalogo(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [
                self._node(1, "0.03", "100.00"),  # 3% de R$100 = R$3
                self._node(2, "0.08", "100.00"),  # 8% de R$100 = R$8
            ]
        )

        sincronizar_ofertas()
        maximo = obter_cashback_maximo_anunciado()

        self.assertEqual(maximo, Decimal("8.0"))

    @patch("ofertas.services.buscar_ofertas_produtos")
    def test_oferta_sem_preco_nao_entra_na_conta_do_maximo(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [
                self._node(1, "0.20", "0"),  # sem preço sincronizado - fica de fora
                self._node(2, "0.08", "50.00"),
            ]
        )

        sincronizar_ofertas()
        maximo = obter_cashback_maximo_anunciado()

        self.assertEqual(maximo, Decimal("8.0"))

    @patch("ofertas.services.buscar_ofertas_produtos")
    def test_resincronizar_atualiza_o_maximo_anterior(self, mock_buscar):
        mock_buscar.return_value = self._pagina([self._node(1, "0.05", "100.00")])
        sincronizar_ofertas()

        mock_buscar.return_value = self._pagina([self._node(2, "0.09", "100.00")])
        sincronizar_ofertas()

        maximo = obter_cashback_maximo_anunciado()
        self.assertEqual(maximo, Decimal("9.0"))


class BuscarOfertaPorLinkTests(TestCase):
    """buscar_oferta_por_link busca a comissão REAL de UM produto específico (usada
    tanto pra postar um story manual quanto, em links/views.py, pra mostrar o cashback
    de verdade ao converter um link no site - em vez do "até X%" genérico calculado do
    catálogo sincronizado)."""

    def _node(self, item_id, commission_rate, price):
        return {
            "itemId": item_id,
            "commissionRate": commission_rate,
            "productName": f"Produto {item_id}",
            "priceMin": price,
            "priceMax": price,
            "productCatIds": [100],
        }

    @override_settings(SHOPEE_CASHBACK_PERCENTUAL=100, CASHBACK_MULTIPLICADOR_CAMPANHA=1)
    @patch("ofertas.services.buscar_oferta_por_item_id")
    def test_busca_a_comissao_real_do_produto_pelo_item_id_do_link(self, mock_buscar):
        mock_buscar.return_value = self._node(999, "0.08", "50.00")

        oferta = buscar_oferta_por_link("https://shopee.com.br/produto-exemplo-i.1.999")

        self.assertEqual(oferta.item_id, 999)
        self.assertEqual(oferta.percentual_cashback, Decimal("8.0"))
        self.assertEqual(oferta.valor_cashback_estimado, Decimal("4.00"))
        mock_buscar.assert_called_once_with(999)

    def test_reconhece_tambem_o_padrao_mais_novo_product_shop_item(self):
        """Além de .../produto-exemplo-i.<shopId>.<itemId>, a Shopee também usa
        .../product/<shopId>/<itemId> - visto resolvendo um link curto de verdade que
        caía no erro genérico antes desse padrão ser reconhecido (ver ROADMAP.md,
        Fase 35)."""
        url = (
            "https://shopee.com.br/product/537151226/22593050282"
            "?exp_group=rollout&utm_source=an_18398680454"
        )

        self.assertEqual(_resolver_item_id(url), 22593050282)

    @patch("ofertas.services.buscar_oferta_por_item_id")
    def test_produto_sem_comissao_ativa_levanta_sem_comissao_error(self, mock_buscar):
        mock_buscar.return_value = None

        with self.assertRaises(SemComissaoError):
            buscar_oferta_por_link("https://shopee.com.br/produto-exemplo-i.1.999")

    @patch("ofertas.services.buscar_oferta_por_item_id")
    def test_sem_comissao_error_continua_sendo_um_link_produto_invalido_error(self, mock_buscar):
        """Quem já trata LinkProdutoInvalidoError genericamente (ex: o management
        command postar_oferta_especifica) continua funcionando sem mudança."""
        mock_buscar.return_value = None

        with self.assertRaises(LinkProdutoInvalidoError):
            buscar_oferta_por_link("https://shopee.com.br/produto-exemplo-i.1.999")


class ResolverItemIdSemRedeTests(TestCase):
    """Versão rápida (sem chamada de rede) de identificar o item_id de uma URL - usada
    em links/services.py::gerar_click pra não deixar a conversão de um link/clique na
    vitrine lenta (a versão completa, _resolver_item_id, pode levar até 10s seguindo
    redirecionamento de link curto - ver ROADMAP.md, Fase 35/41)."""

    def test_reconhece_o_padrao_antigo(self):
        self.assertEqual(
            resolver_item_id_sem_rede("https://shopee.com.br/produto-exemplo-i.1.999"), 999
        )

    def test_reconhece_o_padrao_novo(self):
        self.assertEqual(
            resolver_item_id_sem_rede("https://shopee.com.br/product/537151226/22593050282?x=1"), 22593050282
        )

    def test_link_curto_sem_padrao_retorna_none_sem_seguir_redirecionamento(self):
        self.assertIsNone(resolver_item_id_sem_rede("https://s.shopee.com.br/abc123"))


class ResolverItemIdComRedeTests(TestCase):
    """Versão completa (segue redirecionamento, pode levar até 10s) - só deve ser
    chamada fora do ciclo de requisição de um usuário (ver
    links/services.py::resolver_item_id_alvo_pendentes, ROADMAP.md Fase 41/42)."""

    @patch("ofertas.services.requests.get")
    def test_resolve_seguindo_o_redirecionamento(self, mock_get):
        mock_get.return_value = Mock(
            url="https://shopee.com.br/produto-i.1.999", text="", status_code=200, history=[1],
        )

        self.assertEqual(resolver_item_id_com_rede("https://s.shopee.com.br/abc123"), 999)

    @patch("ofertas.services.requests.get")
    def test_link_nao_identificado_retorna_none_em_vez_de_levantar_erro(self, mock_get):
        mock_get.return_value = Mock(
            url="https://s.shopee.com.br/abc123", text="", status_code=200, history=[],
        )

        self.assertIsNone(resolver_item_id_com_rede("https://s.shopee.com.br/abc123"))


@override_settings(**CREDENCIAIS_TESTE)
class IrParaOfertaTests(TestCase):
    """Clicar num card da vitrine precisa gerar um Click TIPO_VITRINE - diferente do
    TIPO_PRODUTO usado pelo conversor de link (ver links/views.py) - pra permitir
    diferenciar a origem do pedido depois em pedidos/admin.py::origem_detalhada."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)
        self.oferta = Oferta.objects.create(
            item_id=1, nome="Produto vitrine", categoria_id=1,
            product_link="https://shopee.com.br/produto-vitrine-i.1.1",
            percentual_comissao=Decimal("0.05"), vendas=10,
        )

    @patch("links.services.gerar_link_curto")
    def test_cria_click_tipo_vitrine_e_redireciona_pro_link_gerado(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/vitrine123"

        resposta = self.client.get(reverse("ofertas_ir", args=[self.oferta.id]))

        click = Click.objects.get()
        self.assertEqual(click.tipo, Click.TIPO_VITRINE)
        self.assertEqual(click.url_original, self.oferta.product_link)
        self.assertEqual(click.item_id_alvo, self.oferta.item_id)
        self.assertRedirects(resposta, "https://shope.ee/vitrine123", fetch_redirect_response=False)

    @patch("links.services.gerar_link_curto")
    def test_item_id_alvo_vem_do_campo_item_id_da_oferta_nao_da_url(self, mock_gerar_link):
        """Oferta.item_id é confiável (vem da sincronização) - usado direto, sem
        precisar resolver de novo a partir da URL (ver ROADMAP.md, Fase 41)."""
        mock_gerar_link.return_value = "https://shope.ee/vitrine456"
        oferta_sem_padrao_na_url = Oferta.objects.create(
            item_id=555, nome="Produto sem padrão no link", categoria_id=1,
            product_link="https://shopee.com.br/s/abc123",  # não bate com o regex -i.<loja>.<item>
            percentual_comissao=Decimal("0.05"), vendas=5,
        )

        self.client.get(reverse("ofertas_ir", args=[oferta_sem_padrao_na_url.id]))

        click = Click.objects.get()
        self.assertEqual(click.item_id_alvo, 555)


class OfertaManualCashbackTests(TestCase):
    """A matemática do cashback é a mesma da Oferta sincronizada (_CashbackEstimadoMixin)
    - só a base de preço muda: usa preco_avista quando preenchido, senão preco_novo."""

    def _oferta_manual(self, **kwargs):
        padrao = dict(
            product_link="https://shopee.com.br/produto-manual-i.1.1",
            nome="Produto manual",
            imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"),
            preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )
        padrao.update(kwargs)
        return OfertaManual(**padrao)

    def test_usa_preco_novo_quando_nao_ha_preco_avista(self):
        oferta = self._oferta_manual()
        self.assertEqual(oferta.preco_base_cashback, Decimal("80.00"))

    def test_usa_preco_avista_quando_preenchido(self):
        oferta = self._oferta_manual(preco_avista=Decimal("70.00"))
        self.assertEqual(oferta.preco_base_cashback, Decimal("70.00"))

    def test_cashback_segue_percentual_comissao_e_repasse_configurado(self):
        # comissão 10%, repasse 100% (padrão dos testes) -> 10% de cashback sobre 80.00 = 8.00
        oferta = self._oferta_manual()
        self.assertEqual(oferta.valor_cashback_estimado, Decimal("8.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("10.0"))

    def test_aliases_pro_gerador_de_story_do_catalogo(self):
        # nome_curto/preco_min/categoria_id/item_id existem só pra reaproveitar
        # instagram_bot/templates_imagem.py::gerar_imagem_oferta_story e
        # instagram_bot/services.py::_publicar_story_de_oferta (escritos pro catálogo
        # sincronizado, Oferta) sem duplicar - ver "Criar story" em ofertas/admin.py.
        oferta = self._oferta_manual(preco_avista=Decimal("70.00"))

        self.assertEqual(oferta.nome_curto, oferta.nome)
        self.assertEqual(oferta.preco_min, Decimal("70.00"))  # preco_base_cashback
        self.assertIsNone(oferta.categoria_id)
        self.assertIsNone(oferta.item_id)


class SelecionarCarrosselHomeTests(TestCase):
    def _oferta_sincronizada(self, item_id, vendas):
        return Oferta.objects.create(
            item_id=item_id, nome=f"Produto sincronizado {item_id}", categoria_id=1,
            product_link=f"https://shopee.com.br/produto-{item_id}-i.{item_id}.{item_id}",
            percentual_comissao=Decimal("0.05"), vendas=vendas,
        )

    def _oferta_manual(self, nome):
        return OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-manual-i.1.1",
            nome=nome, imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

    def test_sem_oferta_manual_carrossel_e_so_organico(self):
        for i in range(1, 10):
            self._oferta_sincronizada(i, vendas=10 - i)

        destaque, carrossel = selecionar_carrossel_home(8)

        self.assertEqual(destaque.item_id, 1)
        self.assertEqual(len(carrossel), 8)
        self.assertNotIn(destaque, carrossel)

    def test_uma_oferta_manual_substitui_uma_vaga_do_carrossel(self):
        for i in range(1, 10):
            self._oferta_sincronizada(i, vendas=10 - i)
        manual = self._oferta_manual("Produto manual único")

        destaque, carrossel = selecionar_carrossel_home(8)

        self.assertEqual(len(carrossel), 8)
        self.assertEqual(carrossel[0], manual)
        # a destaque continua vindo só do catálogo sincronizado, nunca de uma manual.
        self.assertEqual(destaque.item_id, 1)

    def test_ofertas_manuais_nao_tem_limite_mesmo_acima_do_tamanho_do_carrossel(self):
        for i in range(1, 3):
            self._oferta_sincronizada(i, vendas=10 - i)
        manuais = [self._oferta_manual(f"Manual {i}") for i in range(10)]

        destaque, carrossel = selecionar_carrossel_home(8)

        self.assertEqual(len(carrossel), 10)
        self.assertEqual(set(carrossel), set(manuais))

    def test_sem_nenhuma_oferta_retorna_vazio(self):
        destaque, carrossel = selecionar_carrossel_home(8)
        self.assertIsNone(destaque)
        self.assertEqual(carrossel, [])


@override_settings(**CREDENCIAIS_TESTE)
class IrParaOfertaManualTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)
        self.oferta = OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-manual-i.1.1",
            nome="Produto manual", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

    @patch("links.services.gerar_link_curto")
    def test_cria_click_tipo_vitrine_e_redireciona_pro_link_gerado(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/manual123"

        resposta = self.client.get(reverse("ofertas_manual_ir", args=[self.oferta.id]))

        click = Click.objects.get()
        self.assertEqual(click.tipo, Click.TIPO_VITRINE)
        self.assertEqual(click.url_original, self.oferta.product_link)
        self.assertRedirects(resposta, "https://shope.ee/manual123", fetch_redirect_response=False)

    def test_erro_da_shopee_redireciona_pra_home_nao_pra_vitrine(self):
        from links.shopee_client import ShopeeConfigError

        with patch("links.services.gerar_link_curto", side_effect=ShopeeConfigError("sem credenciais")):
            resposta = self.client.get(reverse("ofertas_manual_ir", args=[self.oferta.id]), follow=True)

        self.assertRedirects(resposta, reverse("home"))
        self.assertContains(resposta, "sem credenciais")


class OfertaDestaqueManualTests(TestCase):
    """Singleton: só existe um registro (pk sempre 1), ver OfertaDestaqueManual.save."""

    def _dados(self, **kwargs):
        padrao = dict(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )
        padrao.update(kwargs)
        return padrao

    def test_editar_em_pe_atualiza_a_mesma_linha(self):
        destaque = OfertaDestaqueManual.objects.create(**self._dados(nome="Primeiro"))

        destaque.nome = "Segundo"
        destaque.save()

        self.assertEqual(OfertaDestaqueManual.objects.count(), 1)
        self.assertEqual(OfertaDestaqueManual.objects.get().nome, "Segundo")

    def test_cashback_usa_o_mesmo_mixin_de_ofertamanual(self):
        destaque = OfertaDestaqueManual(**self._dados())
        self.assertEqual(destaque.preco_base_cashback, Decimal("80.00"))
        self.assertEqual(destaque.valor_cashback_estimado, Decimal("8.00"))


class SelecionarCarrosselHomeComDestaqueManualTests(TestCase):
    def _oferta_sincronizada(self, item_id, vendas):
        return Oferta.objects.create(
            item_id=item_id, nome=f"Produto sincronizado {item_id}", categoria_id=1,
            product_link=f"https://shopee.com.br/produto-{item_id}-i.{item_id}.{item_id}",
            percentual_comissao=Decimal("0.05"), vendas=vendas,
        )

    def _destaque_manual(self):
        return OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

    def test_destaque_manual_substitui_a_hero_e_libera_uma_vaga_a_mais_no_carrossel(self):
        for i in range(1, 10):
            self._oferta_sincronizada(i, vendas=10 - i)
        destaque_manual = self._destaque_manual()

        destaque, carrossel = selecionar_carrossel_home(8)

        self.assertEqual(destaque, destaque_manual)
        # sem destaque manual, o item_id=1 (mais vendido) seria a hero e ficaria de fora
        # do carrossel - com a hero vindo da manual, ele agora cabe como a 8ª vaga.
        self.assertEqual(len(carrossel), 8)
        self.assertEqual(carrossel[0].item_id, 1)

    def test_sem_nenhuma_oferta_organica_destaque_manual_ainda_aparece(self):
        destaque_manual = self._destaque_manual()

        destaque, carrossel = selecionar_carrossel_home(8)

        self.assertEqual(destaque, destaque_manual)
        self.assertEqual(carrossel, [])


@override_settings(**CREDENCIAIS_TESTE)
class IrParaOfertaDestaqueManualTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.client.force_login(self.usuario)
        self.oferta = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

    @patch("links.services.gerar_link_curto")
    def test_cria_click_tipo_vitrine_e_redireciona_pro_link_gerado(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/destaque123"

        resposta = self.client.get(reverse("ofertas_destaque_manual_ir", args=[self.oferta.id]))

        click = Click.objects.get()
        self.assertEqual(click.tipo, Click.TIPO_VITRINE)
        self.assertEqual(click.url_original, self.oferta.product_link)
        self.assertRedirects(resposta, "https://shope.ee/destaque123", fetch_redirect_response=False)


class OfertaDestaqueManualAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="equipe", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.staff)

    def test_changelist_redireciona_pro_formulario_de_criacao_quando_nao_existe_nenhuma(self):
        resposta = self.client.get(reverse("admin:ofertas_ofertadestaquemanual_changelist"))
        self.assertRedirects(resposta, reverse("admin:ofertas_ofertadestaquemanual_add"))

    def test_changelist_redireciona_pro_formulario_de_edicao_quando_ja_existe_uma(self):
        destaque = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("admin:ofertas_ofertadestaquemanual_changelist"))

        self.assertRedirects(resposta, reverse("admin:ofertas_ofertadestaquemanual_change", args=[destaque.pk]))

    def test_nao_deixa_adicionar_uma_segunda_quando_ja_existe_uma(self):
        OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("admin:ofertas_ofertadestaquemanual_add"))

        self.assertEqual(resposta.status_code, 403)

    def test_botao_criar_story_aparece_na_tela_de_edicao(self):
        destaque = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

        resposta = self.client.get(reverse("admin:ofertas_ofertadestaquemanual_change", args=[destaque.pk]))

        self.assertContains(resposta, "Criar story e mandar pra aprovação")

    def test_botao_criar_story_gera_registro_pendente_e_volta_pra_edicao(self):
        destaque = OfertaDestaqueManual.objects.create(
            product_link="https://shopee.com.br/produto-destaque-i.1.1",
            nome="Produto destaque", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

        # INSTAGRAM_BOT_ATIVO=False por padrão nos testes -> vira simulação, sem chamar
        # a API do Instagram nem mandar e-mail de aprovação de verdade.
        resposta = self.client.get(
            reverse("admin:ofertas_ofertadestaquemanual_criar_story", args=[destaque.pk])
        )

        self.assertRedirects(resposta, reverse("admin:ofertas_ofertadestaquemanual_change", args=[destaque.pk]))
        registro = RegistroPublicacao.objects.get(oferta_nome="Produto destaque")
        self.assertEqual(registro.status, RegistroPublicacao.STATUS_SIMULADO)
        self.assertEqual(registro.conteudo_tipo, RegistroPublicacao.CONTEUDO_OFERTA_DIARIA)


class CriarStoryDeOfertaManualAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="equipe3", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.staff)
        self.oferta = OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-manual-i.1.1",
            nome="Produto manual", imagem_url="https://exemplo.com/img.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.10"),
        )

    def test_acao_em_lote_gera_registro_pendente_por_oferta_selecionada(self):
        resposta = self.client.post(
            reverse("admin:ofertas_ofertamanual_changelist"),
            {"action": "criar_story_de_oferta", "_selected_action": [self.oferta.pk]},
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        registro = RegistroPublicacao.objects.get(oferta_nome="Produto manual")
        self.assertEqual(registro.status, RegistroPublicacao.STATUS_SIMULADO)
        self.assertEqual(registro.conteudo_tipo, RegistroPublicacao.CONTEUDO_OFERTA_DIARIA)
