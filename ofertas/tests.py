from decimal import Decimal

from django.test import TestCase
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
    def test_usa_shopeeCommissionRate_e_nao_o_bonus_de_vendedor(self):
        # commissionRate = shopeeCommissionRate + sellerCommissionRate (bônus de campanha
        # do vendedor, temporário e não confirmado pra toda conta de afiliado - ver
        # links/shopee_client.py). Usar o combinado infla o cashback exibido bem acima
        # do que a Shopee garante de fato.
        node = {
            "itemId": 26142718061,
            "shopeeCommissionRate": "0.08",
            "productName": "Cama Cabana Pet",
            "productCatIds": [100629],
        }

        oferta = _montar_oferta(node, categorias_nivel1={100629: "Casa"})

        self.assertEqual(oferta.percentual_comissao, Decimal("0.08"))
