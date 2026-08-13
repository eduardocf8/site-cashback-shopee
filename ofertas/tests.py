from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Oferta
from .services import _montar_oferta


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

    def test_maior_cashback_aparece_nas_opcoes_de_ordenacao(self):
        resposta = self.client.get(reverse("ofertas_lista"))

        valores = [valor for valor, _rotulo in resposta.context["ordenacoes"]]
        self.assertIn("maior_cashback", valores)


class MontarOfertaTests(TestCase):
    def test_usa_commissionRate_combinado_com_bonus_de_vendedor(self):
        # commissionRate = shopeeCommissionRate + sellerCommissionRate. Confirmado
        # comparando com o painel oficial de afiliados da Shopee que o bônus de campanha
        # do vendedor já entra de fato no cashback pago em vendas diretas reais - por
        # isso o site também deve mostrar esse valor combinado, não só a base da Shopee
        # (ver links/shopee_client.py e pedidos/services.py). O teto por produto
        # (CASHBACK_MAXIMO_POR_PRODUTO) é o que protege contra exibir um valor
        # desproporcional, não a exclusão desse campo.
        node = {
            "itemId": 26142718061,
            "commissionRate": "0.14",
            "productName": "Cama Cabana Pet",
            "productCatIds": [100629],
        }

        oferta = _montar_oferta(node, categorias_nivel1={100629: "Casa"})

        self.assertEqual(oferta.percentual_comissao, Decimal("0.14"))


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=100, CASHBACK_MULTIPLICADOR_CAMPANHA=1, CASHBACK_MAXIMO_POR_PRODUTO=10)
class TetoCashbackPorProdutoTests(TestCase):
    def test_abaixo_do_teto_mostra_valor_cheio(self):
        oferta = Oferta(
            item_id=1, nome="Produto barato", categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            preco_min=Decimal("100.00"), preco_max=Decimal("100.00"),
            percentual_comissao=Decimal("0.05"),  # 5% de R$100 = R$5, abaixo do teto de R$10
        )

        self.assertEqual(oferta.valor_cashback_estimado, Decimal("5.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("5.0"))
        self.assertFalse(oferta.cashback_no_limite)

    def test_acima_do_teto_limita_valor_e_reduz_percentual_exibido(self):
        oferta = Oferta(
            item_id=2, nome="Produto com comissão alta", categoria_id=1,
            product_link="https://shopee.com.br/produto-2-i.2.2",
            preco_min=Decimal("100.00"), preco_max=Decimal("100.00"),
            percentual_comissao=Decimal("0.20"),  # 20% de R$100 = R$20, acima do teto de R$10
        )

        self.assertEqual(oferta.valor_cashback_estimado, Decimal("10.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("10.0"))
        self.assertTrue(oferta.cashback_no_limite)

    def test_preco_zero_nao_quebra_e_nao_conta_como_no_limite(self):
        oferta = Oferta(
            item_id=3, nome="Produto sem preço sincronizado", categoria_id=1,
            product_link="https://shopee.com.br/produto-3-i.3.3",
            preco_min=Decimal("0"), preco_max=Decimal("0"),
            percentual_comissao=Decimal("0.05"),
        )

        self.assertEqual(oferta.valor_cashback_estimado, Decimal("0.00"))
        self.assertEqual(oferta.percentual_cashback, Decimal("5.0"))
        self.assertFalse(oferta.cashback_no_limite)
