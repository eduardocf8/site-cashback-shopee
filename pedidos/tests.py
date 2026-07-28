from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from links.models import Click

from .models import Pedido
from .services import mapear_status, resolver_click, sincronizar


class MapearStatusTests(TestCase):
    def test_termos_de_cancelamento(self):
        for bruto in ["CANCELLED", "INVALID", "REJECTED", "UNPAID", "FRAUD_ORDER"]:
            self.assertEqual(mapear_status(bruto), Pedido.STATUS_CANCELADO, bruto)

    def test_termos_de_validacao(self):
        for bruto in ["COMPLETED", "CONFIRMED", "PAID", "SUCCESS"]:
            self.assertEqual(mapear_status(bruto), Pedido.STATUS_VALIDADO, bruto)

    def test_desconhecido_cai_para_pendente(self):
        self.assertEqual(mapear_status("PENDING_REVIEW"), Pedido.STATUS_PENDENTE)
        self.assertEqual(mapear_status("ALGO_QUE_NUNCA_VIMOS"), Pedido.STATUS_PENDENTE)
        self.assertEqual(mapear_status(""), Pedido.STATUS_PENDENTE)
        self.assertEqual(mapear_status(None), Pedido.STATUS_PENDENTE)


class ResolverClickTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.click = Click.objects.create(
            usuario=self.usuario,
            tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/",
            link_gerado="https://shope.ee/abc",
        )

    def test_identifica_click_com_subids_separados_por_virgula(self):
        utm = f"{self.click.sub_id_usuario()},{self.click.sub_id_click()}"
        encontrado = resolver_click(utm)
        self.assertEqual(encontrado, self.click)

    def test_identifica_click_com_subids_separados_por_pipe(self):
        utm = f"{self.click.sub_id_usuario()}|{self.click.sub_id_click()}"
        encontrado = resolver_click(utm)
        self.assertEqual(encontrado, self.click)

    def test_utm_content_vazio_retorna_none(self):
        self.assertIsNone(resolver_click(""))
        self.assertIsNone(resolver_click(None))

    def test_utm_content_sem_uuid_conhecido_retorna_none(self):
        self.assertIsNone(resolver_click("facebook,instagram"))


@override_settings(
    SHOPEE_AFFILIATE_APP_ID="app123",
    SHOPEE_AFFILIATE_SECRET="segredo123",
    SHOPEE_CASHBACK_PERCENTUAL=100,
)
class SincronizarTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.click = Click.objects.create(
            usuario=self.usuario,
            tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/",
            link_gerado="https://shope.ee/abc",
        )

    def _pagina(self, orders, has_next_page=False, scroll_id=""):
        return {
            "nodes": [
                {
                    "conversionId": "999",
                    "purchaseTime": 1700000000,
                    "utmContent": f"{self.click.sub_id_usuario()},{self.click.sub_id_click()}",
                    "orders": orders,
                }
            ],
            "pageInfo": {"hasNextPage": has_next_page, "scrollId": scroll_id},
        }

    @patch("pedidos.services.buscar_conversoes")
    def test_cria_pedido_pendente_e_calcula_cashback_com_100_por_cento(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD1", "orderStatus": "PENDING", "completeTime": None, "netCommission": "12.50"}]
        )

        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD1")
        self.assertEqual(pedido.status, Pedido.STATUS_PENDENTE)
        self.assertEqual(pedido.usuario, self.usuario)
        self.assertEqual(pedido.click, self.click)
        self.assertEqual(pedido.valor_comissao, Decimal("12.50"))
        self.assertEqual(pedido.valor_cashback, Decimal("12.50"))
        self.assertEqual(resultado, {"novos": 1, "atualizados": 0, "nao_identificados": 0})

    @override_settings(SHOPEE_CASHBACK_PERCENTUAL=80)
    @patch("pedidos.services.buscar_conversoes")
    def test_calcula_cashback_com_percentual_configurado(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD2", "orderStatus": "PENDING", "completeTime": None, "netCommission": "10.00"}]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD2")
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_atualiza_pedido_existente_quando_status_muda(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD3", "orderStatus": "PENDING", "completeTime": None, "netCommission": "5.00"}]
        )
        sincronizar(1690000000, 1700000000)

        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD3", "orderStatus": "COMPLETED", "completeTime": 1700000500, "netCommission": "5.00"}]
        )
        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD3")
        self.assertEqual(pedido.status, Pedido.STATUS_VALIDADO)
        self.assertIsNotNone(pedido.data_validacao)
        self.assertEqual(resultado, {"novos": 0, "atualizados": 1, "nao_identificados": 0})
        self.assertEqual(Pedido.objects.count(), 1)

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_sem_click_identificavel_fica_sem_usuario_mas_e_salvo(self, mock_buscar):
        pagina = self._pagina(
            [{"orderId": "ORD4", "orderStatus": "PENDING", "completeTime": None, "netCommission": "3.00"}]
        )
        pagina["nodes"][0]["utmContent"] = "origem-desconhecida"
        mock_buscar.return_value = pagina

        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD4")
        self.assertIsNone(pedido.usuario)
        self.assertIsNone(pedido.click)
        self.assertEqual(resultado["nao_identificados"], 1)

    @patch("pedidos.services.buscar_conversoes")
    def test_segue_paginacao_ate_acabar(self, mock_buscar):
        pagina1 = self._pagina(
            [{"orderId": "ORD5", "orderStatus": "PENDING", "completeTime": None, "netCommission": "1.00"}],
            has_next_page=True,
            scroll_id="cursor-1",
        )
        pagina2 = self._pagina(
            [{"orderId": "ORD6", "orderStatus": "PENDING", "completeTime": None, "netCommission": "2.00"}],
            has_next_page=False,
        )
        mock_buscar.side_effect = [pagina1, pagina2]

        resultado = sincronizar(1690000000, 1700000000)

        self.assertEqual(resultado["novos"], 2)
        self.assertTrue(Pedido.objects.filter(order_id="ORD5").exists())
        self.assertTrue(Pedido.objects.filter(order_id="ORD6").exists())
        mock_buscar.assert_any_call(1690000000, 1700000000, None)
        mock_buscar.assert_any_call(1690000000, 1700000000, "cursor-1")
