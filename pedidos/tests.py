from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import Indicacao
from links.models import Click

from .models import Pedido
from .services import calcular_data_prevista_liberacao, liberar_saldo, mapear_status, resolver_click, sincronizar


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


class CalcularDataPrevistaLiberacaoTests(TestCase):
    def test_sem_data_validacao_retorna_none(self):
        self.assertIsNone(calcular_data_prevista_liberacao(None))

    def test_soma_dois_meses_dentro_do_mesmo_ano(self):
        validacao = datetime(2026, 3, 15, tzinfo=dt_timezone.utc)
        self.assertEqual(calcular_data_prevista_liberacao(validacao), date(2026, 5, 1))

    def test_vira_o_ano_quando_ultrapassa_dezembro(self):
        validacao = datetime(2026, 11, 20, tzinfo=dt_timezone.utc)
        self.assertEqual(calcular_data_prevista_liberacao(validacao), date(2027, 1, 1))

        validacao = datetime(2026, 12, 5, tzinfo=dt_timezone.utc)
        self.assertEqual(calcular_data_prevista_liberacao(validacao), date(2027, 2, 1))

    def test_dia_do_mes_da_validacao_nao_importa(self):
        self.assertEqual(
            calcular_data_prevista_liberacao(datetime(2026, 1, 31, tzinfo=dt_timezone.utc)),
            calcular_data_prevista_liberacao(datetime(2026, 1, 1, tzinfo=dt_timezone.utc)),
        )


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
            [{"orderId": "ORD1", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "12.50"}]}]
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
            [{"orderId": "ORD2", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "10.00"}]}]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD2")
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_atualiza_pedido_existente_quando_status_muda(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD3", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "5.00"}]}]
        )
        sincronizar(1690000000, 1700000000)

        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD3", "orderStatus": "COMPLETED", "items": [{"completeTime": 1700000500, "itemTotalCommission": "5.00"}]}]
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
            [{"orderId": "ORD4", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "3.00"}]}]
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
            [{"orderId": "ORD5", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "1.00"}]}],
            has_next_page=True,
            scroll_id="cursor-1",
        )
        pagina2 = self._pagina(
            [{"orderId": "ORD6", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "2.00"}]}],
            has_next_page=False,
        )
        mock_buscar.side_effect = [pagina1, pagina2]

        resultado = sincronizar(1690000000, 1700000000)

        self.assertEqual(resultado["novos"], 2)
        self.assertTrue(Pedido.objects.filter(order_id="ORD5").exists())
        self.assertTrue(Pedido.objects.filter(order_id="ORD6").exists())
        mock_buscar.assert_any_call(1690000000, 1700000000, None)
        mock_buscar.assert_any_call(1690000000, 1700000000, "cursor-1")

    @patch("pedidos.services.buscar_conversoes")
    def test_define_data_prevista_liberacao_ao_validar(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD7", "orderStatus": "COMPLETED", "items": [{"completeTime": 1700000500, "itemTotalCommission": "5.00"}]}]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD7")
        self.assertEqual(pedido.status, Pedido.STATUS_VALIDADO)
        esperado = calcular_data_prevista_liberacao(pedido.data_validacao)
        self.assertEqual(pedido.data_prevista_liberacao, esperado)

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_ja_liberado_nao_regride_ao_ressincronizar(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD8", "orderStatus": "COMPLETED", "items": [{"completeTime": 1700000500, "itemTotalCommission": "5.00"}]}]
        )
        sincronizar(1690000000, 1700000000)
        Pedido.objects.filter(order_id="ORD8").update(
            status=Pedido.STATUS_LIBERADO, data_liberacao=timezone.now()
        )

        # A Shopee continua reportando COMPLETED (ela não sabe que já liberamos o saldo).
        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD8")
        self.assertEqual(pedido.status, Pedido.STATUS_LIBERADO)
        self.assertIsNotNone(pedido.data_liberacao)
        self.assertEqual(resultado, {"novos": 0, "atualizados": 1, "nao_identificados": 0})

    @patch("pedidos.services.buscar_conversoes")
    def test_guarda_nome_imagem_do_produto_e_motivo_de_cancelamento(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [
                {
                    "orderId": "ORD9",
                    "orderStatus": "CANCELLED",
                    "items": [
                        {
                            "completeTime": None,
                            "itemTotalCommission": "0",
                            "itemName": "Fone de ouvido Bluetooth",
                            "imageUrl": "https://cf.shopee.com.br/file/foto.jpg",
                            "fraudReason": "Pedido cancelado pelo comprador",
                        }
                    ],
                }
            ]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD9")
        self.assertEqual(pedido.status, Pedido.STATUS_CANCELADO)
        self.assertEqual(pedido.produto_nome, "Fone de ouvido Bluetooth")
        self.assertEqual(pedido.produto_imagem_url, "https://cf.shopee.com.br/file/foto.jpg")
        self.assertEqual(pedido.motivo_cancelamento, "Pedido cancelado pelo comprador")

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_valido_nao_tem_motivo_de_cancelamento(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [{"orderId": "ORD10", "orderStatus": "PENDING", "items": [{"completeTime": None, "itemTotalCommission": "1.00"}]}]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD10")
        self.assertEqual(pedido.motivo_cancelamento, "")

    @patch("pedidos.services.buscar_conversoes")
    def test_sincroniza_muitos_pedidos_com_poucas_consultas_ao_banco(self, mock_buscar):
        # Uma conta com uso real pode ter milhares de pedidos - se processarmos um por
        # um, cada request estoura o tempo limite do servidor em produção (foi o que
        # aconteceu). Esse teste garante que o número de consultas não cresce junto
        # com a quantidade de pedidos.
        quantidade = 300
        orders = [
            {
                "orderId": f"ORD-LOTE-{i}",
                "orderStatus": "PENDING",
                "items": [{"completeTime": None, "itemTotalCommission": "1.00"}],
            }
            for i in range(quantidade)
        ]
        mock_buscar.return_value = self._pagina(orders)

        with CaptureQueriesContext(connection) as contexto:
            resultado = sincronizar(1690000000, 1700000000)

        self.assertEqual(resultado["novos"], quantidade)
        self.assertEqual(Pedido.objects.count(), quantidade)
        self.assertLess(len(contexto), 20)


class SincronizarBonusIndicacaoTests(TestCase):
    def setUp(self):
        self.indicador = get_user_model().objects.create_user(
            username="indicador", password="senha123", cpf="39053344705"
        )
        self.indicado = get_user_model().objects.create_user(
            username="indicado", password="senha123", cpf="14783246947"
        )
        self.indicacao = Indicacao.objects.create(indicador=self.indicador, indicado=self.indicado)

        self.click_indicador = Click.objects.create(
            usuario=self.indicador, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/indicador",
        )
        self.click_indicado = Click.objects.create(
            usuario=self.indicado, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/indicado",
        )

    def _no(self, click, order_id, comissao, order_status="COMPLETED", purchase_time=1700000000, complete_time=1700000500):
        return {
            "conversionId": order_id,
            "purchaseTime": purchase_time,
            "utmContent": f"{click.sub_id_usuario()},{click.sub_id_click()}",
            "orders": [
                {"orderId": order_id, "orderStatus": order_status, "items": [{"completeTime": complete_time, "itemTotalCommission": comissao}]}
            ],
        }

    def _pagina(self, nodes):
        return {"nodes": nodes, "pageInfo": {"hasNextPage": False, "scrollId": ""}}

    @patch("pedidos.services.buscar_conversoes")
    def test_primeira_compra_validada_do_indicado_dobra_cashback(self, mock_buscar):
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-1", "10.00")])

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-IND-1")
        self.assertEqual(pedido.valor_cashback, Decimal("20.00"))
        self.indicacao.refresh_from_db()
        self.assertEqual(self.indicacao.pedido_bonus_indicado, pedido)
        self.assertIsNone(self.indicacao.pedido_bonus_indicador)

    @patch("pedidos.services.buscar_conversoes")
    def test_indicador_ganha_dobro_na_proxima_compra_apos_indicado_validar(self, mock_buscar):
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-1", "10.00")])
        sincronizar(1690000000, 1700000000)

        mock_buscar.return_value = self._pagina([self._no(self.click_indicador, "ORD-REF-1", "5.00")])
        sincronizar(1690000000, 1700000000)

        pedido_indicador = Pedido.objects.get(order_id="ORD-REF-1")
        self.assertEqual(pedido_indicador.valor_cashback, Decimal("10.00"))
        self.indicacao.refresh_from_db()
        self.assertEqual(self.indicacao.pedido_bonus_indicador, pedido_indicador)

    @patch("pedidos.services.buscar_conversoes")
    def test_segunda_compra_do_indicador_nao_recebe_bonus_de_novo(self, mock_buscar):
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-1", "10.00")])
        sincronizar(1690000000, 1700000000)
        mock_buscar.return_value = self._pagina([self._no(self.click_indicador, "ORD-REF-1", "5.00")])
        sincronizar(1690000000, 1700000000)

        mock_buscar.return_value = self._pagina([self._no(self.click_indicador, "ORD-REF-2", "7.00")])
        sincronizar(1690000000, 1700000000)

        pedido_seguinte = Pedido.objects.get(order_id="ORD-REF-2")
        self.assertEqual(pedido_seguinte.valor_cashback, Decimal("7.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_ressincronizar_o_mesmo_pedido_nao_dobra_de_novo(self, mock_buscar):
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-1", "10.00")])
        sincronizar(1690000000, 1700000000)
        # A Shopee reenvia o mesmo pedido validado em toda sincronização seguinte.
        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-IND-1")
        self.assertEqual(pedido.valor_cashback, Decimal("20.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_ainda_pendente_do_indicado_nao_recebe_bonus(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [self._no(self.click_indicado, "ORD-IND-1", "10.00", order_status="PENDING", complete_time=None)]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-IND-1")
        self.assertEqual(pedido.valor_cashback, Decimal("10.00"))
        self.indicacao.refresh_from_db()
        self.assertIsNone(self.indicacao.pedido_bonus_indicado)

    @patch("pedidos.services.buscar_conversoes")
    def test_fila_fifo_quando_indicador_tem_duas_indicacoes_pendentes(self, mock_buscar):
        indicado2 = get_user_model().objects.create_user(
            username="indicado2", password="senha123", cpf="52914637837"
        )
        indicacao2 = Indicacao.objects.create(indicador=self.indicador, indicado=indicado2)
        click_indicado2 = Click.objects.create(
            usuario=indicado2, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/indicado2",
        )

        mock_buscar.return_value = self._pagina(
            [
                self._no(self.click_indicado, "ORD-IND-1", "10.00"),
                self._no(click_indicado2, "ORD-IND-2", "10.00"),
            ]
        )
        sincronizar(1690000000, 1700000000)

        # O indicador faz duas compras que validam na mesma sincronização - a mais
        # antiga (por purchaseTime) deve atender a indicação mais antiga primeiro.
        mock_buscar.return_value = self._pagina(
            [
                self._no(self.click_indicador, "ORD-REF-1", "5.00", purchase_time=1700000200),
                self._no(self.click_indicador, "ORD-REF-2", "5.00", purchase_time=1700000100),
            ]
        )
        sincronizar(1690000000, 1700000000)

        self.indicacao.refresh_from_db()
        indicacao2.refresh_from_db()
        self.assertEqual(self.indicacao.pedido_bonus_indicador.order_id, "ORD-REF-2")
        self.assertEqual(indicacao2.pedido_bonus_indicador.order_id, "ORD-REF-1")

    @patch("pedidos.services.buscar_conversoes")
    def test_usuario_sem_indicacao_nao_e_afetado(self, mock_buscar):
        avulso = get_user_model().objects.create_user(username="avulso", password="senha123", cpf="94834869092")
        click_avulso = Click.objects.create(
            usuario=avulso, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/avulso",
        )
        mock_buscar.return_value = self._pagina([self._no(click_avulso, "ORD-AVULSO-1", "8.00")])

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-AVULSO-1")
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))


class LiberarSaldoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _criar_pedido(self, order_id, status, data_prevista_liberacao):
        return Pedido.objects.create(
            order_id=order_id,
            conversion_id="1",
            usuario=self.usuario,
            status=status,
            status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("10.00"),
            valor_cashback=Decimal("10.00"),
            data_prevista_liberacao=data_prevista_liberacao,
        )

    def test_libera_pedido_validado_com_data_ja_vencida(self):
        ontem = timezone.localdate() - timedelta(days=1)
        pedido = self._criar_pedido("ORD-VENCIDO", Pedido.STATUS_VALIDADO, ontem)

        total = liberar_saldo()

        pedido.refresh_from_db()
        self.assertEqual(total, 1)
        self.assertEqual(pedido.status, Pedido.STATUS_LIBERADO)
        self.assertIsNotNone(pedido.data_liberacao)

    def test_nao_libera_pedido_com_data_futura(self):
        amanha = timezone.localdate() + timedelta(days=1)
        pedido = self._criar_pedido("ORD-FUTURO", Pedido.STATUS_VALIDADO, amanha)

        total = liberar_saldo()

        pedido.refresh_from_db()
        self.assertEqual(total, 0)
        self.assertEqual(pedido.status, Pedido.STATUS_VALIDADO)
        self.assertIsNone(pedido.data_liberacao)

    def test_nao_mexe_em_pedido_pendente_ou_cancelado_mesmo_com_data_vencida(self):
        ontem = timezone.localdate() - timedelta(days=1)
        pendente = self._criar_pedido("ORD-PENDENTE", Pedido.STATUS_PENDENTE, ontem)
        cancelado = self._criar_pedido("ORD-CANCELADO", Pedido.STATUS_CANCELADO, ontem)

        total = liberar_saldo()

        pendente.refresh_from_db()
        cancelado.refresh_from_db()
        self.assertEqual(total, 0)
        self.assertEqual(pendente.status, Pedido.STATUS_PENDENTE)
        self.assertEqual(cancelado.status, Pedido.STATUS_CANCELADO)
