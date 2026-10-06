from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch

from openpyxl import load_workbook

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import Indicacao
from links.models import Click
from saques.models import Saque

from .admin import PedidoAdmin
from .analytics import (
    obter_analytics,
    obter_grafico_sacado,
    obter_resumo_liberado,
    obter_saldo_disponivel,
    obter_saldo_por_usuario,
    obter_serie_diaria,
    origem_detalhada,
)
from .models import CampanhaCashback, Pedido
from .notificacoes import notificar_indicador_bonus_pendente
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
            [
                {
                    "orderId": "ORD1",
                    "orderStatus": "PENDING",
                    "items": [{"completeTime": None, "itemTotalCommission": "8.00", "actualAmount": "100.00"}],
                }
            ]
        )

        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD1")
        self.assertEqual(pedido.status, Pedido.STATUS_PENDENTE)
        self.assertEqual(pedido.usuario, self.usuario)
        self.assertEqual(pedido.click, self.click)
        self.assertEqual(pedido.valor_pedido, Decimal("100.00"))
        self.assertEqual(pedido.valor_comissao, Decimal("8.00"))
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))
        self.assertEqual(resultado, {"novos": 1, "atualizados": 0, "nao_identificados": 0})

    @patch("pedidos.services.buscar_conversoes")
    def test_valor_pedido_soma_actual_amount_de_todos_os_itens(self, mock_buscar):
        mock_buscar.return_value = self._pagina(
            [
                {
                    "orderId": "ORD-VALOR",
                    "orderStatus": "PENDING",
                    "items": [
                        {"completeTime": None, "itemTotalCommission": "1.00", "actualAmount": "50.00"},
                        {"completeTime": None, "itemTotalCommission": "2.00", "actualAmount": "30.00"},
                    ],
                }
            ]
        )

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-VALOR")
        self.assertEqual(pedido.valor_pedido, Decimal("80.00"))

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
            [
                {
                    "orderId": "ORD4",
                    "orderStatus": "PENDING",
                    "items": [{"completeTime": None, "itemTotalCommission": "3.00", "actualAmount": "40.00"}],
                }
            ]
        )
        pagina["nodes"][0]["utmContent"] = "origem-desconhecida"
        mock_buscar.return_value = pagina

        resultado = sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD4")
        self.assertIsNone(pedido.usuario)
        self.assertIsNone(pedido.click)
        self.assertEqual(resultado["nao_identificados"], 1)
        # Sem Click não tem usuário pra receber o cashback - não faz sentido calcular um
        # valor que nunca vai ser pago a ninguém. valor_comissao e valor_pedido (o que a
        # Shopee realmente paga/o que o comprador realmente pagou) continuam sendo
        # somados normalmente, independente da origem do pedido.
        self.assertEqual(pedido.valor_pedido, Decimal("40.00"))
        self.assertEqual(pedido.valor_comissao, Decimal("3.00"))
        self.assertEqual(pedido.valor_cashback, Decimal("0"))

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


class CampanhaCashbackModelTests(TestCase):
    """CampanhaCashback.multiplicador_em substitui o antigo CASHBACK_MULTIPLICADOR_CAMPANHA
    fixo no .env - o multiplicador de um pedido passa a depender da data_compra real,
    não do momento em que a sincronização roda (ver ROADMAP.md, Fase 44)."""

    def test_sem_nenhuma_campanha_cadastrada_multiplicador_e_1(self):
        momento = datetime(2024, 6, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(CampanhaCashback.multiplicador_em(momento), Decimal("1"))

    def test_momento_none_multiplicador_e_1(self):
        self.assertEqual(CampanhaCashback.multiplicador_em(None), Decimal("1"))

    def test_momento_dentro_da_janela_usa_o_multiplicador_da_campanha(self):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"),
            inicio=datetime(2024, 6, 1, tzinfo=dt_timezone.utc),
            fim=datetime(2024, 6, 30, tzinfo=dt_timezone.utc),
        )
        momento = datetime(2024, 6, 15, tzinfo=dt_timezone.utc)
        self.assertEqual(CampanhaCashback.multiplicador_em(momento), Decimal("2"))

    def test_momento_antes_do_inicio_nao_conta(self):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"),
            inicio=datetime(2024, 6, 1, tzinfo=dt_timezone.utc),
            fim=datetime(2024, 6, 30, tzinfo=dt_timezone.utc),
        )
        momento = datetime(2024, 5, 31, 23, 59, tzinfo=dt_timezone.utc)
        self.assertEqual(CampanhaCashback.multiplicador_em(momento), Decimal("1"))

    def test_momento_depois_do_fim_nao_conta(self):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"),
            inicio=datetime(2024, 6, 1, tzinfo=dt_timezone.utc),
            fim=datetime(2024, 6, 30, tzinfo=dt_timezone.utc),
        )
        momento = datetime(2024, 7, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(CampanhaCashback.multiplicador_em(momento), Decimal("1"))

    def test_sem_data_de_fim_continua_valendo_indefinidamente(self):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"), inicio=datetime(2024, 6, 1, tzinfo=dt_timezone.utc), fim=None,
        )
        momento = datetime(2030, 1, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(CampanhaCashback.multiplicador_em(momento), Decimal("2"))

    def test_multiplicador_atual_usa_agora(self):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("3"),
            inicio=timezone.now() - timedelta(days=1),
            fim=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(CampanhaCashback.multiplicador_atual(), Decimal("3"))


@override_settings(
    SHOPEE_AFFILIATE_APP_ID="app123", SHOPEE_AFFILIATE_SECRET="segredo123",
    SHOPEE_CASHBACK_PERCENTUAL=100,
    CASHBACK_MINIMO_VENDA_DIRETA=1.6, CASHBACK_MINIMO_VENDA_INDIRETA=1,
)
class CashbackMinimoGarantidoTests(TestCase):
    """Quando a comissão real da Shopee resultaria em menos que o piso mínimo
    garantido, vale o piso - a única parte do cálculo em que a cash-b pode pagar mais
    do que recebeu de comissão (o resto é sempre uma fração da comissão real, nunca um
    prejuízo). Venda direta (link/vitrine) só tem o piso maior quando o item comprado
    é comprovadamente o mesmo do link/card clicado (Click.item_id_alvo) - ver
    ROADMAP.md, Fase 41."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _pagina(self, click, order_id, comissao, valor_item, item_id=1):
        return {
            "nodes": [
                {
                    "conversionId": "999",
                    "purchaseTime": 1700000000,
                    "utmContent": f"{click.sub_id_usuario()},{click.sub_id_click()}",
                    "orders": [
                        {
                            "orderId": order_id,
                            "orderStatus": "PENDING",
                            "items": [
                                {
                                    "itemId": item_id,
                                    "completeTime": None,
                                    "itemTotalCommission": comissao,
                                    "actualAmount": valor_item,
                                }
                            ],
                        }
                    ],
                }
            ],
            "pageInfo": {"hasNextPage": False, "scrollId": ""},
        }

    @patch("pedidos.services.buscar_conversoes")
    def test_venda_direta_com_comissao_baixa_usa_o_piso_de_1_6_por_cento(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        # Comissão real (0,50) seria só 0,5% dos 100 - abaixo do piso de 1,6% (1,60).
        # item_id do pedido (1) bate com o item_id_alvo do click - venda direta de verdade.
        mock_buscar.return_value = self._pagina(click, "ORD-DIRETA-BAIXA", "0.50", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-DIRETA-BAIXA")
        self.assertEqual(pedido.valor_comissao, Decimal("0.50"))
        self.assertEqual(pedido.valor_cashback, Decimal("1.60"))

    @patch("pedidos.services.buscar_conversoes")
    def test_vitrine_tambem_conta_como_venda_direta_pro_piso_quando_item_bate(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_VITRINE, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        mock_buscar.return_value = self._pagina(click, "ORD-VITRINE-BAIXA", "0.50", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-VITRINE-BAIXA")
        self.assertEqual(pedido.valor_cashback, Decimal("1.60"))

    @patch("pedidos.services.buscar_conversoes")
    def test_comissao_zerada_nao_usa_o_piso_cashback_fica_zero(self, mock_buscar):
        # Categoria sem comissão de afiliado nenhuma (ex: alimentos/bebidas) - a Shopee
        # reporta itemTotalCommission=0. O piso só existe pra cobrir comissão BAIXA,
        # nunca ausente - senão a cash-b pagaria cashback sem ter recebido nada da
        # Shopee, contradizendo a mensagem "sem comissão, sem cashback" mostrada ao
        # converter o link (ver links/views.py::_buscar_cashback_real).
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        mock_buscar.return_value = self._pagina(click, "ORD-SEM-COMISSAO", "0", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-SEM-COMISSAO")
        self.assertEqual(pedido.valor_comissao, Decimal("0"))
        self.assertEqual(pedido.valor_cashback, Decimal("0"))

    @patch("pedidos.services.buscar_conversoes")
    def test_venda_indireta_com_comissao_baixa_usa_o_piso_de_1_por_cento(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/abc",
        )
        mock_buscar.return_value = self._pagina(click, "ORD-INDIRETA-BAIXA", "0.50", "100.00", item_id=42)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-INDIRETA-BAIXA")
        self.assertEqual(pedido.valor_cashback, Decimal("1.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_comissao_acima_do_piso_nao_e_afetada(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        # Comissão real de 5,00 (5% dos 100) já é bem maior que o piso de 1,6%.
        mock_buscar.return_value = self._pagina(click, "ORD-ACIMA-DO-PISO", "5.00", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-ACIMA-DO-PISO")
        self.assertEqual(pedido.valor_cashback, Decimal("5.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_multiplicador_de_campanha_tambem_dobra_o_piso(self, mock_buscar):
        # purchaseTime da _pagina é sempre 1700000000 - campanha cobrindo esse instante.
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"),
            inicio=datetime(2023, 1, 1, tzinfo=dt_timezone.utc),
            fim=datetime(2023, 12, 31, tzinfo=dt_timezone.utc),
        )
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        mock_buscar.return_value = self._pagina(click, "ORD-PISO-CAMPANHA", "0.50", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-PISO-CAMPANHA")
        # Piso (1,60) x multiplicador de campanha (2) = 3,20.
        self.assertEqual(pedido.valor_cashback, Decimal("3.20"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_sem_click_nao_aplica_piso_nenhum(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        pagina = self._pagina(click, "ORD-SEM-CLICK", "0.50", "100.00", item_id=1)
        pagina["nodes"][0]["utmContent"] = "origem-desconhecida"
        mock_buscar.return_value = pagina

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-SEM-CLICK")
        self.assertIsNone(pedido.usuario)
        self.assertEqual(pedido.valor_cashback, Decimal("0"))

    @patch("pedidos.services.buscar_conversoes")
    def test_comprar_produto_diferente_do_link_so_ganha_o_piso_indireto(self, mock_buscar):
        """O golpe que a Fase 41 fecha: converter o link de QUALQUER produto e comprar
        outro completamente diferente não deveria destravar o piso maior de venda
        direta."""
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        # Comprou o item 999, não o item 1 que estava no link.
        mock_buscar.return_value = self._pagina(click, "ORD-ITEM-DIFERENTE", "0.50", "100.00", item_id=999)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-ITEM-DIFERENTE")
        self.assertEqual(pedido.valor_cashback, Decimal("1.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_click_sem_item_id_alvo_identificado_so_ganha_o_piso_indireto(self, mock_buscar):
        """Link curto que não deu pra identificar na hora do clique (ver Fase 35) não
        consegue provar o vínculo com o item comprado - conta como não bate, por
        segurança (mais seguro errar pro lado de baixo)."""
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=None,
            url_original="https://s.shopee.com.br/abc123", link_gerado="https://shope.ee/abc",
        )
        mock_buscar.return_value = self._pagina(click, "ORD-SEM-ITEM-ALVO", "0.50", "100.00", item_id=1)

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-SEM-ITEM-ALVO")
        self.assertEqual(pedido.valor_cashback, Decimal("1.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_com_varios_itens_so_o_que_bate_ganha_o_piso_maior(self, mock_buscar):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        pagina = {
            "nodes": [
                {
                    "conversionId": "999",
                    "purchaseTime": 1700000000,
                    "utmContent": f"{click.sub_id_usuario()},{click.sub_id_click()}",
                    "orders": [
                        {
                            "orderId": "ORD-MULTI-ITEM",
                            "orderStatus": "PENDING",
                            "items": [
                                {
                                    "itemId": 1, "completeTime": None,
                                    "itemTotalCommission": "0.50", "actualAmount": "100.00",
                                },
                                {
                                    "itemId": 2, "completeTime": None,
                                    "itemTotalCommission": "0.30", "actualAmount": "100.00",
                                },
                            ],
                        }
                    ],
                }
            ],
            "pageInfo": {"hasNextPage": False, "scrollId": ""},
        }
        mock_buscar.return_value = pagina

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-MULTI-ITEM")
        # Item 1 (bate com o link): piso de 1,6% de 100 = 1,60. Item 2 (não bate):
        # piso de 1% de 100 = 1,00. Total: 2,60.
        self.assertEqual(pedido.valor_cashback, Decimal("2.60"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_com_varios_itens_item_sem_comissao_nao_soma_piso_so_o_outro(self, mock_buscar):
        # Mesmo pedido, 2 itens: item 1 com comissão normal (ganha o piso de venda
        # direta), item 2 com comissão zerada (categoria sem comissão nenhuma - não
        # ganha cashback nenhum, nem o piso). O cálculo é por item, então um pedido
        # pode ter os dois comportamentos ao mesmo tempo.
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO, item_id_alvo=1,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/abc",
        )
        pagina = {
            "nodes": [
                {
                    "conversionId": "999",
                    "purchaseTime": 1700000000,
                    "utmContent": f"{click.sub_id_usuario()},{click.sub_id_click()}",
                    "orders": [
                        {
                            "orderId": "ORD-MULTI-ITEM-SEM-COMISSAO",
                            "orderStatus": "PENDING",
                            "items": [
                                {
                                    "itemId": 1, "completeTime": None,
                                    "itemTotalCommission": "0.50", "actualAmount": "100.00",
                                },
                                {
                                    "itemId": 2, "completeTime": None,
                                    "itemTotalCommission": "0", "actualAmount": "100.00",
                                },
                            ],
                        }
                    ],
                }
            ],
            "pageInfo": {"hasNextPage": False, "scrollId": ""},
        }
        mock_buscar.return_value = pagina

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-MULTI-ITEM-SEM-COMISSAO")
        # Item 1 (bate com o link, comissão 0,50): piso de 1,6% de 100 = 1,60. Item 2
        # (comissão zerada): 0, mesmo sendo o resto do mesmo pedido. Total: 1,60.
        self.assertEqual(pedido.valor_comissao, Decimal("0.50"))
        self.assertEqual(pedido.valor_cashback, Decimal("1.60"))


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=20)
class MultiplicadorCampanhaTests(TestCase):
    """O multiplicador de campanha fica congelado no pedido quando ele é registrado.

    Sem isso, como a Shopee reenvia o mesmo pedido em toda sincronização seguinte e o
    cashback é recalculado do zero a cada vez, uma campanha de "cashback em dobro"
    seria desfeita sozinha assim que acabasse.
    """

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

    def _pagina(self, order_id, status="PENDING"):
        return {
            "nodes": [
                {
                    "conversionId": "999",
                    "purchaseTime": 1700000000,
                    "utmContent": f"{self.click.sub_id_usuario()},{self.click.sub_id_click()}",
                    "orders": [
                        {
                            "orderId": order_id,
                            "orderStatus": status,
                            "items": [{"completeTime": None, "itemTotalCommission": "20.00"}],
                        }
                    ],
                }
            ],
            "pageInfo": {"hasNextPage": False, "scrollId": ""},
        }

    def _campanha(self, inicio=None, fim=None, multiplicador="2"):
        return CampanhaCashback.objects.create(
            multiplicador=Decimal(multiplicador),
            inicio=inicio or datetime(2023, 1, 1, tzinfo=dt_timezone.utc),
            fim=fim,
        )

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_comprado_durante_a_campanha_recebe_o_dobro(self, mock_buscar):
        self._campanha()  # cobre o purchaseTime fixo da _pagina (1700000000)
        mock_buscar.return_value = self._pagina("ORD-CAMP-1")

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-CAMP-1")
        # 20% de R$20 = R$4, dobrado pela campanha = R$8
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))
        self.assertEqual(pedido.multiplicador_campanha, Decimal("2"))

    @patch("pedidos.services.buscar_conversoes")
    def test_campanha_encerrada_nao_reduz_cashback_de_pedido_ja_registrado(self, mock_buscar):
        campanha = self._campanha()
        mock_buscar.return_value = self._pagina("ORD-CAMP-2")
        sincronizar(1690000000, 1700000000)

        # Campanha acabou e a Shopee reenvia o mesmo pedido, agora validado - o
        # multiplicador gravado na primeira vez continua valendo, não importa se a
        # campanha ainda existe ou não nesse momento.
        campanha.delete()
        mock_buscar.return_value = self._pagina("ORD-CAMP-2", status="COMPLETED")
        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-CAMP-2")
        self.assertEqual(pedido.status, Pedido.STATUS_VALIDADO)
        self.assertEqual(pedido.valor_cashback, Decimal("8.00"))
        self.assertEqual(pedido.multiplicador_campanha, Decimal("2"))

    @patch("pedidos.services.buscar_conversoes")
    def test_campanha_nova_nao_dobra_retroativamente_pedido_antigo(self, mock_buscar):
        mock_buscar.return_value = self._pagina("ORD-CAMP-3")
        sincronizar(1690000000, 1700000000)

        # Campanha começa depois, mas cobre a mesma data_compra do pedido antigo (que
        # ainda está na janela de sincronização) - mesmo assim não dobra
        # retroativamente, porque o multiplicador já ficou gravado no pedido.
        self._campanha()
        mock_buscar.return_value = self._pagina("ORD-CAMP-3", status="COMPLETED")
        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-CAMP-3")
        self.assertEqual(pedido.valor_cashback, Decimal("4.00"))
        self.assertEqual(pedido.multiplicador_campanha, Decimal("1"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_registrado_fora_da_campanha_guarda_multiplicador_1(self, mock_buscar):
        mock_buscar.return_value = self._pagina("ORD-CAMP-4")

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-CAMP-4")
        self.assertEqual(pedido.valor_cashback, Decimal("4.00"))
        self.assertEqual(pedido.multiplicador_campanha, Decimal("1"))


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
    def test_pedido_em_campanha_nao_consome_o_bonus_de_indicacao(self, mock_buscar):
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"), inicio=datetime(2023, 1, 1, tzinfo=dt_timezone.utc),
        )
        # O pedido leva só o extra da campanha (5.00 x 2 = 10.00), e a indicação
        # continua pendente esperando a campanha acabar.
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-CAMP", "5.00")])

        sincronizar(1690000000, 1700000000)

        pedido = Pedido.objects.get(order_id="ORD-IND-CAMP")
        self.assertEqual(pedido.multiplicador_campanha, Decimal("2"))
        self.assertEqual(pedido.valor_cashback, Decimal("10.00"))
        self.indicacao.refresh_from_db()
        self.assertIsNone(self.indicacao.pedido_bonus_indicado)

    @patch("pedidos.services.buscar_conversoes")
    def test_bonus_na_fila_entra_no_proximo_pedido_depois_da_campanha(self, mock_buscar):
        # Campanha cobre só até o purchaseTime do 1º pedido (1700000000) - o 2º pedido
        # (purchase_time=1700000600) já compra depois dela ter acabado.
        CampanhaCashback.objects.create(
            multiplicador=Decimal("2"),
            inicio=datetime(2023, 1, 1, tzinfo=dt_timezone.utc),
            fim=datetime.fromtimestamp(1700000000, tz=dt_timezone.utc),
        )
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-FILA-1", "5.00")])
        sincronizar(1690000000, 1700000000)

        # O pedido seguinte do indicado, já fora da campanha, pega o bônus que ficou na fila.
        mock_buscar.return_value = self._pagina(
            [
                self._no(self.click_indicado, "ORD-FILA-1", "5.00"),
                self._no(self.click_indicado, "ORD-FILA-2", "5.00", purchase_time=1700000600),
            ]
        )
        sincronizar(1690000000, 1700000000)

        # O pedido da campanha continua com o valor da campanha, sem ganhar o bônus depois.
        pedido_campanha = Pedido.objects.get(order_id="ORD-FILA-1")
        self.assertEqual(pedido_campanha.valor_cashback, Decimal("10.00"))

        pedido_pos_campanha = Pedido.objects.get(order_id="ORD-FILA-2")
        self.assertEqual(pedido_pos_campanha.valor_cashback, Decimal("10.00"))  # 5.00 x 2 de indicação
        self.indicacao.refresh_from_db()
        self.assertEqual(self.indicacao.pedido_bonus_indicado, pedido_pos_campanha)

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
    def test_primeira_compra_validada_do_indicado_notifica_o_indicador_por_email(self, mock_buscar):
        self.indicador.email = "indicador@example.com"
        self.indicador.save()
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-EMAIL", "10.00")])

        sincronizar(1690000000, 1700000000)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["indicador@example.com"])
        self.assertIn(self.indicado.username, email.body)
        self.assertIn("dobro", email.subject.lower())

    @patch("pedidos.services.buscar_conversoes")
    def test_ressincronizar_o_mesmo_pedido_nao_notifica_de_novo(self, mock_buscar):
        self.indicador.email = "indicador@example.com"
        self.indicador.save()
        mock_buscar.return_value = self._pagina([self._no(self.click_indicado, "ORD-IND-EMAIL2", "10.00")])

        sincronizar(1690000000, 1700000000)
        sincronizar(1690000000, 1700000000)

        self.assertEqual(len(mail.outbox), 1)

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


class NotificarIndicadorBonusPendenteTests(TestCase):
    def setUp(self):
        self.indicador = get_user_model().objects.create_user(
            username="indicador", password="senha123", cpf="39053344705", email="indicador@example.com"
        )
        self.indicado = get_user_model().objects.create_user(
            username="indicado", password="senha123", cpf="14783246947"
        )
        self.indicacao = Indicacao.objects.create(indicador=self.indicador, indicado=self.indicado)

    def test_envia_email_pro_indicador_com_o_nome_do_indicado(self):
        notificar_indicador_bonus_pendente(self.indicacao)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["indicador@example.com"])
        self.assertIn(self.indicado.username, email.body)
        self.assertIn("dobro", email.subject.lower())

    def test_indicador_sem_email_nao_envia_nada(self):
        self.indicador.email = ""
        self.indicador.save()

        notificar_indicador_bonus_pendente(self.indicacao)

        self.assertEqual(len(mail.outbox), 0)


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


class ObterAnalyticsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _criar_pedido(self, order_id, status, comissao, cashback, data_compra, usuario=None, click=None):
        return Pedido.objects.create(
            order_id=order_id,
            conversion_id="1",
            usuario=usuario if usuario is not None else self.usuario,
            click=click,
            status=status,
            status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal(comissao),
            valor_cashback=Decimal(cashback),
            data_compra=data_compra,
        )

    def test_filtro_origem_site_traz_so_pedidos_com_click(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/abc",
        )
        self._criar_pedido("COM-CLICK", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now(), click=click)
        self._criar_pedido("SEM-CLICK", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now())

        dados = obter_analytics(origem="site")

        self.assertEqual(dados["total_pedidos"], 1)
        self.assertEqual(dados["total_comissao"], Decimal("10.00"))

    def test_filtro_origem_fora_traz_so_pedidos_sem_click(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/abc",
        )
        self._criar_pedido("COM-CLICK", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now(), click=click)
        self._criar_pedido("SEM-CLICK", Pedido.STATUS_VALIDADO, "20.00", "8.00", timezone.now())

        dados = obter_analytics(origem="fora")

        self.assertEqual(dados["total_pedidos"], 1)
        self.assertEqual(dados["total_comissao"], Decimal("20.00"))

    def test_sem_filtro_origem_traz_tudo(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/abc",
        )
        self._criar_pedido("COM-CLICK", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now(), click=click)
        self._criar_pedido("SEM-CLICK", Pedido.STATUS_VALIDADO, "20.00", "8.00", timezone.now())

        dados = obter_analytics()

        self.assertEqual(dados["total_pedidos"], 2)

    def test_soma_comissao_e_cashback_de_todos_os_pedidos(self):
        self._criar_pedido("A1", Pedido.STATUS_VALIDADO, "20.00", "10.00", timezone.now())
        self._criar_pedido("A2", Pedido.STATUS_PENDENTE, "8.00", "4.00", timezone.now())

        dados = obter_analytics()

        self.assertEqual(dados["total_comissao"], Decimal("28.00"))
        self.assertEqual(dados["total_cashback"], Decimal("14.00"))
        self.assertEqual(dados["total_pedidos"], 2)
        self.assertEqual(dados["margem_retida"], Decimal("14.00"))

    def test_filtro_por_periodo_exclui_pedido_fora_do_intervalo(self):
        dentro = timezone.make_aware(datetime(2026, 3, 15))
        fora = timezone.make_aware(datetime(2026, 5, 1))
        self._criar_pedido("DENTRO", Pedido.STATUS_VALIDADO, "10.00", "5.00", dentro)
        self._criar_pedido("FORA", Pedido.STATUS_VALIDADO, "10.00", "5.00", fora)

        dados = obter_analytics(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 31))

        self.assertEqual(dados["total_pedidos"], 1)
        self.assertEqual(dados["total_comissao"], Decimal("10.00"))

    def test_filtro_por_status(self):
        self._criar_pedido("VALIDADO", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now())
        self._criar_pedido("CANCELADO", Pedido.STATUS_CANCELADO, "10.00", "5.00", timezone.now())

        dados = obter_analytics(status=Pedido.STATUS_VALIDADO)

        self.assertEqual(dados["total_pedidos"], 1)

    def test_saldo_a_liberar_soma_pendente_e_validado_mas_nao_liberado(self):
        self._criar_pedido("PEND", Pedido.STATUS_PENDENTE, "10.00", "5.00", timezone.now())
        self._criar_pedido("VALID", Pedido.STATUS_VALIDADO, "10.00", "3.00", timezone.now())
        self._criar_pedido("LIB", Pedido.STATUS_LIBERADO, "10.00", "7.00", timezone.now())

        dados = obter_analytics()

        self.assertEqual(dados["saldo_a_liberar"], Decimal("8.00"))
        self.assertEqual(dados["saldo_liberado"], Decimal("7.00"))

    def test_resumo_status_inclui_status_sem_nenhum_pedido_zerado(self):
        self._criar_pedido("VALID", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now())

        dados = obter_analytics()
        por_chave = {linha["status"]: linha for linha in dados["resumo_status"]}

        self.assertEqual(por_chave[Pedido.STATUS_CANCELADO]["total"], 0)
        self.assertEqual(por_chave[Pedido.STATUS_CANCELADO]["cashback"], Decimal("0"))

    def test_ranking_indicadores_conta_indicacoes_e_concluidas(self):
        indicador = get_user_model().objects.create_user(username="indicador", password="senha123", cpf="14783246947")
        indicado1 = get_user_model().objects.create_user(username="ind1", password="senha123", cpf="52914637837")
        indicado2 = get_user_model().objects.create_user(username="ind2", password="senha123", cpf="91234567873")
        pedido_bonus = self._criar_pedido("BONUS", Pedido.STATUS_VALIDADO, "10.00", "20.00", timezone.now(), usuario=indicador)
        Indicacao.objects.create(indicador=indicador, indicado=indicado1, pedido_bonus_indicado=pedido_bonus, pedido_bonus_indicador=pedido_bonus)
        Indicacao.objects.create(indicador=indicador, indicado=indicado2)

        dados = obter_analytics()

        self.assertEqual(dados["total_indicacoes"], 2)
        self.assertEqual(dados["indicacoes_concluidas"], 1)
        self.assertEqual(dados["ranking_indicadores"][0]["indicador__username"], "indicador")
        self.assertEqual(dados["ranking_indicadores"][0]["total_indicacoes"], 2)
        self.assertEqual(dados["ranking_indicadores"][0]["concluidas"], 1)

    def test_total_saques_por_status(self):
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PAGO,
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("30.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_SOLICITADO,
        )

        dados = obter_analytics()

        self.assertEqual(dados["total_saques"], 2)
        self.assertEqual(dados["total_saques_valor"], Decimal("80.00"))
        por_status = {linha["status"]: linha for linha in dados["saques_por_status"]}
        self.assertEqual(por_status[Saque.STATUS_PAGO]["valor"], Decimal("50.00"))
        self.assertEqual(por_status[Saque.STATUS_SOLICITADO]["valor"], Decimal("30.00"))

    def test_pedido_sem_usuario_conta_comissao_mas_nao_cashback(self):
        # "Fora do site" (sem usuário - sincronizado da conta de afiliado Shopee sem
        # ter sido gerado por um link daqui) não tem cashback de verdade: ninguém vai
        # receber esse valor. A comissão é real (a Shopee pagou de verdade), então
        # essa continua contando - só o cashback que precisa ficar de fora.
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="1", usuario=None, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"),
            data_compra=timezone.now(),
        )
        self._criar_pedido("COM-USUARIO", Pedido.STATUS_VALIDADO, "10.00", "5.00", timezone.now())

        dados = obter_analytics()

        self.assertEqual(dados["total_pedidos"], 2)
        self.assertEqual(dados["total_comissao"], Decimal("110.00"))
        self.assertEqual(dados["total_cashback"], Decimal("5.00"))
        por_status = {linha["status"]: linha for linha in dados["resumo_status"]}
        self.assertEqual(por_status[Pedido.STATUS_VALIDADO]["comissao"], Decimal("110.00"))
        self.assertEqual(por_status[Pedido.STATUS_VALIDADO]["cashback"], Decimal("5.00"))
        self.assertEqual(dados["saldo_a_liberar"], Decimal("5.00"))


class ObterGraficoSacadoTests(TestCase):
    """Valor sacado (Saque pago) por mês - o gráfico de barras da tela de Resumo
    financeiro. Só olha pro passado + mês atual, não existe "saque futuro"."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.hoje = timezone.localdate()

    def _mes_relativo(self, delta):
        total = self.hoje.month - 1 + delta
        return self.hoje.year + total // 12, total % 12 + 1

    def _datetime_no_mes(self, delta, dia=15):
        ano, mes = self._mes_relativo(delta)
        return timezone.make_aware(datetime.combine(date(ano, mes, dia), datetime.min.time()))

    def _linha(self, linhas, delta):
        ano, mes = self._mes_relativo(delta)
        return next(l for l in linhas if l["ano"] == ano and l["mes"] == mes)

    def _saque_pago(self, valor, delta):
        return Saque.objects.create(
            usuario=self.usuario, valor=Decimal(valor), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PAGO, pago_em=self._datetime_no_mes(delta),
        )

    def test_soma_saques_pagos_do_mes(self):
        self._saque_pago("20.00", 0)
        self._saque_pago("5.00", 0)

        linha_atual = self._linha(obter_grafico_sacado(), 0)

        self.assertEqual(linha_atual["valor"], Decimal("25.00"))

    def test_saque_nao_pago_nao_conta(self):
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_SOLICITADO,
        )

        linha_atual = self._linha(obter_grafico_sacado(), 0)

        self.assertEqual(linha_atual["valor"], Decimal("0"))

    def test_mes_passado_fora_da_janela_nao_aparece(self):
        self._saque_pago("20.00", -10)

        linhas = obter_grafico_sacado(meses_passados=6)

        self.assertEqual(sum((l["valor"] for l in linhas), Decimal("0")), Decimal("0"))

    def test_quantidade_de_linhas_bate_com_meses_passados(self):
        linhas = obter_grafico_sacado(meses_passados=3)
        self.assertEqual(len(linhas), 4)  # 3 passados + atual

    def test_limite_maximo_e_respeitado(self):
        linhas = obter_grafico_sacado(meses_passados=9999)
        self.assertEqual(len(linhas), 24 + 1)

    def test_valor_negativo_vira_zero_meses_passados(self):
        linhas = obter_grafico_sacado(meses_passados=-5)
        self.assertEqual(len(linhas), 1)  # só o mês atual

    def test_nao_inclui_mes_futuro(self):
        linhas = obter_grafico_sacado(meses_passados=0)
        self.assertEqual(len(linhas), 1)
        self.assertEqual((linhas[0]["ano"], linhas[0]["mes"]), self._mes_relativo(0))


class ObterResumoLiberadoTests(TestCase):
    """Tabela de saldo liberado (mês atual + 2 meses de projeção) da tela de Resumo
    financeiro. Mês atual = saldo real (já processado por liberar_saldo); os 2 meses
    seguintes somam validado (por data_prevista_liberacao) + pendente (projetado de
    forma otimista a partir da data_compra + 2, já que ainda não tem data_validacao)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.hoje = timezone.localdate()

    def _mes_relativo(self, delta):
        total = self.hoje.month - 1 + delta
        return self.hoje.year + total // 12, total % 12 + 1

    def _data_no_mes(self, delta, dia=15):
        ano, mes = self._mes_relativo(delta)
        return date(ano, mes, dia)

    def _datetime_no_mes(self, delta, dia=15):
        return timezone.make_aware(datetime.combine(self._data_no_mes(delta, dia), datetime.min.time()))

    def _linha(self, linhas, delta):
        ano, mes = self._mes_relativo(delta)
        return next(l for l in linhas if l["ano"] == ano and l["mes"] == mes)

    def test_sempre_retorna_exatamente_3_linhas(self):
        linhas = obter_resumo_liberado()
        self.assertEqual(len(linhas), 3)

    def test_mes_atual_e_marcado_como_atual_e_futuros_como_projecao(self):
        linhas = obter_resumo_liberado()
        atual = self._linha(linhas, 0)
        futuro_1 = self._linha(linhas, 1)
        futuro_2 = self._linha(linhas, 2)

        self.assertTrue(atual["eh_atual"])
        self.assertFalse(atual["eh_projecao"])
        self.assertTrue(futuro_1["eh_projecao"])
        self.assertTrue(futuro_2["eh_projecao"])

    def test_mes_atual_usa_liberado_real_por_data_liberacao(self):
        Pedido.objects.create(
            order_id="LIB-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("5.00"),
            data_compra=self._datetime_no_mes(-2), data_liberacao=self._datetime_no_mes(0),
        )

        atual = self._linha(obter_resumo_liberado(), 0)

        self.assertEqual(atual["valor"], Decimal("5.00"))

    def test_validado_projeta_pela_data_prevista_liberacao(self):
        Pedido.objects.create(
            order_id="VAL-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("7.00"),
            data_compra=self._datetime_no_mes(0), data_validacao=self._datetime_no_mes(0),
            data_prevista_liberacao=self._data_no_mes(2),
        )

        linhas = obter_resumo_liberado()

        self.assertEqual(self._linha(linhas, 0)["valor"], Decimal("0"))
        self.assertEqual(self._linha(linhas, 2)["valor"], Decimal("7.00"))

    def test_pendente_projeta_pela_data_compra_mais_2_meses(self):
        Pedido.objects.create(
            order_id="PEND-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_PENDENTE,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("9.00"),
            data_compra=self._datetime_no_mes(-1),
        )

        linhas = obter_resumo_liberado()

        self.assertEqual(self._linha(linhas, 1)["valor"], Decimal("9.00"))

    def test_pendente_e_validado_se_somam_no_mesmo_mes_projetado(self):
        Pedido.objects.create(
            order_id="PEND-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_PENDENTE,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("9.00"),
            data_compra=self._datetime_no_mes(0),
        )
        Pedido.objects.create(
            order_id="VAL-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("3.00"),
            data_compra=self._datetime_no_mes(0), data_validacao=self._datetime_no_mes(0),
            data_prevista_liberacao=self._data_no_mes(2),
        )

        futuro_2 = self._linha(obter_resumo_liberado(), 2)

        self.assertEqual(futuro_2["valor"], Decimal("12.00"))

    def test_pedido_sem_usuario_fora_do_site_nunca_conta(self):
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="1", usuario=None, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"),
            data_liberacao=self._datetime_no_mes(0),
        )
        Pedido.objects.create(
            order_id="FORA-DO-SITE-2", conversion_id="1", usuario=None, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"),
            data_compra=self._datetime_no_mes(0), data_validacao=self._datetime_no_mes(0),
            data_prevista_liberacao=self._data_no_mes(2),
        )

        linhas = obter_resumo_liberado()

        self.assertEqual(sum((l["valor"] for l in linhas), Decimal("0")), Decimal("0"))

    def test_cancelado_nunca_conta(self):
        Pedido.objects.create(
            order_id="CANC-1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_CANCELADO,
            status_shopee_bruto="CANCELLED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("5.00"),
            data_compra=self._datetime_no_mes(0),
        )

        linhas = obter_resumo_liberado()

        self.assertEqual(sum((l["valor"] for l in linhas), Decimal("0")), Decimal("0"))


class ObterSaldoDisponivelTests(TestCase):
    """Saldo acumulado de sempre disponível pra saque (linha "Disponível pra saque" da
    tela de Resumo financeiro) - diferente do "mês atual" de obter_resumo_liberado, que
    só olha o liberado NESSE mês. Aqui soma todo liberado histórico menos todo pago
    histórico, não importa o mês."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.hoje = timezone.localdate()

    def _mes_relativo(self, delta):
        total = self.hoje.month - 1 + delta
        return self.hoje.year + total // 12, total % 12 + 1

    def _datetime_no_mes(self, delta, dia=15):
        ano, mes = self._mes_relativo(delta)
        return timezone.make_aware(datetime.combine(date(ano, mes, dia), datetime.min.time()))

    def test_soma_liberado_de_varios_meses_passados(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("20.00"),
            data_liberacao=self._datetime_no_mes(-5),
        )
        Pedido.objects.create(
            order_id="B", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("15.00"),
            data_liberacao=self._datetime_no_mes(0),
        )

        self.assertEqual(obter_saldo_disponivel(), Decimal("35.00"))

    def test_desconta_saques_pagos_de_qualquer_mes(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("50.00"),
            data_liberacao=self._datetime_no_mes(-3),
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PAGO, pago_em=self._datetime_no_mes(-1),
        )

        self.assertEqual(obter_saldo_disponivel(), Decimal("30.00"))

    def test_saque_nao_pago_nao_desconta(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("50.00"),
            data_liberacao=self._datetime_no_mes(0),
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_SOLICITADO,
        )

        self.assertEqual(obter_saldo_disponivel(), Decimal("50.00"))

    def test_pedido_sem_usuario_fora_do_site_nunca_conta(self):
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="1", usuario=None, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"),
            data_liberacao=self._datetime_no_mes(0),
        )

        self.assertEqual(obter_saldo_disponivel(), Decimal("0"))

    def test_sem_nada_retorna_zero(self):
        self.assertEqual(obter_saldo_disponivel(), Decimal("0"))


class ObterSaldoPorUsuarioTests(TestCase):
    """Quebra de 1 mês+tipo (1 célula da tela de Saldos por mês) por usuário - usado
    pra achar quem já tem saldo suficiente pra sacar escondido dentro de um total."""

    def setUp(self):
        self.hoje = timezone.localdate()
        self.ana = get_user_model().objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.bia = get_user_model().objects.create_user(username="bia", password="senha123", cpf="14783246947")

    def _datetime_no_mes_atual(self, dia=15):
        return timezone.make_aware(datetime.combine(date(self.hoje.year, self.hoje.month, dia), datetime.min.time()))

    def test_soma_por_usuario_do_tipo_liberado_no_mes_certo(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("20.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )
        Pedido.objects.create(
            order_id="B", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("5.00"), valor_cashback=Decimal("8.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )
        Pedido.objects.create(
            order_id="C", conversion_id="1", usuario=self.bia, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("5.00"), valor_cashback=Decimal("3.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )

        linhas = obter_saldo_por_usuario(self.hoje.year, self.hoje.month, "liberado")

        por_usuario = {linha["username"]: linha["total"] for linha in linhas}
        self.assertEqual(por_usuario["ana"], Decimal("28.00"))
        self.assertEqual(por_usuario["bia"], Decimal("3.00"))

    def test_ordenado_do_maior_pro_menor(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("3.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )
        Pedido.objects.create(
            order_id="B", conversion_id="1", usuario=self.bia, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("30.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )

        linhas = obter_saldo_por_usuario(self.hoje.year, self.hoje.month, "liberado")

        self.assertEqual([linha["username"] for linha in linhas], ["bia", "ana"])

    def test_nao_traz_pedido_de_outro_mes(self):
        mes_passado = self.hoje.month - 1 or 12
        ano_passado = self.hoje.year if self.hoje.month > 1 else self.hoje.year - 1
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("3.00"),
            data_liberacao=timezone.make_aware(datetime(ano_passado, mes_passado, 15)),
        )

        linhas = obter_saldo_por_usuario(self.hoje.year, self.hoje.month, "liberado")

        self.assertEqual(linhas, [])

    def test_tipo_invalido_retorna_lista_vazia(self):
        linhas = obter_saldo_por_usuario(self.hoje.year, self.hoje.month, "lixo")
        self.assertEqual(linhas, [])

    def test_projecao_usa_data_prevista_liberacao_do_validado(self):
        # "validado" usa data_prevista_liberacao, não data_compra - mesma regra de
        # obter_resumo_liberado.
        mes_seguinte = self.hoje.month % 12 + 1
        ano_seguinte = self.hoje.year + (1 if self.hoje.month == 12 else 0)
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("12.00"),
            data_compra=self._datetime_no_mes_atual(), data_prevista_liberacao=date(ano_seguinte, mes_seguinte, 1),
        )

        linhas_mes_atual = obter_saldo_por_usuario(self.hoje.year, self.hoje.month, "projecao")
        linhas_mes_seguinte = obter_saldo_por_usuario(ano_seguinte, mes_seguinte, "projecao")

        self.assertEqual(linhas_mes_atual, [])
        self.assertEqual(linhas_mes_seguinte[0]["total"], Decimal("12.00"))

    def test_projecao_usa_data_compra_mais_2_meses_do_pendente(self):
        # Compra este mês, projeção cai 2 meses à frente (mesma conta de _somar_meses).
        total = self.hoje.month - 1 + 2
        ano_projetado, mes_projetado = self.hoje.year + total // 12, total % 12 + 1
        Pedido.objects.create(
            order_id="B", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_PENDENTE,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("9.00"),
            data_compra=self._datetime_no_mes_atual(),
        )

        linhas = obter_saldo_por_usuario(ano_projetado, mes_projetado, "projecao")

        self.assertEqual(linhas[0]["total"], Decimal("9.00"))

    def test_projecao_soma_pendente_e_validado_do_mesmo_usuario_no_mesmo_mes(self):
        total = self.hoje.month - 1 + 2
        ano_projetado, mes_projetado = self.hoje.year + total // 12, total % 12 + 1
        Pedido.objects.create(
            order_id="C", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_PENDENTE,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("9.00"),
            data_compra=self._datetime_no_mes_atual(),
        )
        Pedido.objects.create(
            order_id="D", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_VALIDADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("4.00"),
            data_compra=self._datetime_no_mes_atual(), data_prevista_liberacao=date(ano_projetado, mes_projetado, 1),
        )

        linhas = obter_saldo_por_usuario(ano_projetado, mes_projetado, "projecao")

        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["total"], Decimal("13.00"))

    def test_disponivel_soma_liberado_de_varios_meses_menos_o_que_ja_foi_sacado(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("30.00"),
            data_liberacao=timezone.make_aware(datetime(self.hoje.year, self.hoje.month, 15)) - timedelta(days=90),
        )
        Pedido.objects.create(
            order_id="B", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("10.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )
        Saque.objects.create(
            usuario=self.ana, valor=Decimal("15.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PAGO, pago_em=self._datetime_no_mes_atual(),
        )

        linhas = obter_saldo_por_usuario(None, None, "disponivel")

        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["username"], "ana")
        self.assertEqual(linhas[0]["total"], Decimal("25.00"))

    def test_disponivel_nao_traz_usuario_com_saldo_zero_ou_negativo(self):
        Pedido.objects.create(
            order_id="A", conversion_id="1", usuario=self.ana, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("1.00"), valor_cashback=Decimal("20.00"),
            data_liberacao=self._datetime_no_mes_atual(),
        )
        Saque.objects.create(
            usuario=self.ana, valor=Decimal("20.00"), chave_pix="a@a.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PAGO, pago_em=self._datetime_no_mes_atual(),
        )

        linhas = obter_saldo_por_usuario(None, None, "disponivel")

        self.assertEqual(linhas, [])


class ObterSerieDiariaTests(TestCase):
    """Série dia a dia usada no gráfico de linha da tela de analytics."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _criar_pedido(self, order_id, comissao, cashback, data_compra):
        return Pedido.objects.create(
            order_id=order_id, conversion_id="1", usuario=self.usuario,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal(comissao), valor_cashback=Decimal(cashback), data_compra=data_compra,
        )

    def test_um_ponto_por_dia_no_periodo_mesmo_sem_pedido(self):
        serie = obter_serie_diaria(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 3))

        self.assertEqual(serie["rotulos"], ["01/03", "02/03", "03/03"])
        self.assertEqual(serie["series"]["pedidos"], [0, 0, 0])

    def test_agrupa_pedidos_por_dia_da_compra(self):
        self._criar_pedido("A1", "10.00", "5.00", timezone.make_aware(datetime(2026, 3, 1, 8)))
        self._criar_pedido("A2", "20.00", "8.00", timezone.make_aware(datetime(2026, 3, 1, 20)))
        self._criar_pedido("B1", "6.00", "3.00", timezone.make_aware(datetime(2026, 3, 2, 12)))

        serie = obter_serie_diaria(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 3))

        self.assertEqual(serie["series"]["pedidos"], [2, 1, 0])
        self.assertEqual(serie["series"]["comissao"], [30.0, 6.0, 0])
        self.assertEqual(serie["series"]["cashback"], [13.0, 3.0, 0])

    def test_pedido_sem_usuario_conta_no_grafico_de_pedidos_mas_nao_no_de_cashback(self):
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="1", usuario=None,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"),
            data_compra=timezone.make_aware(datetime(2026, 3, 1, 8)),
        )

        serie = obter_serie_diaria(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 1))

        self.assertEqual(serie["series"]["pedidos"], [1])
        self.assertEqual(serie["series"]["comissao"], [100.0])
        self.assertEqual(serie["series"]["cashback"], [0])

    def test_agrupa_saques_indicacoes_e_novos_usuarios_por_dia(self):
        # criado_em é auto_now_add em Saque/Indicacao - passar no create() é ignorado,
        # então cria e ajusta a data depois com update() (que não passa pelo auto_now_add).
        saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="a@a.com", tipo_chave_pix="EMAIL",
            status=Saque.STATUS_PAGO,
        )
        Saque.objects.filter(pk=saque.pk).update(criado_em=timezone.make_aware(datetime(2026, 3, 1, 10)))
        indicado = get_user_model().objects.create_user(username="indicado", password="s", cpf="14783246947")
        indicacao = Indicacao.objects.create(indicador=self.usuario, indicado=indicado)
        Indicacao.objects.filter(pk=indicacao.pk).update(criado_em=timezone.make_aware(datetime(2026, 3, 2, 9)))

        serie = obter_serie_diaria(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 2))

        self.assertEqual(serie["series"]["saques_quantidade"], [1, 0])
        self.assertEqual(serie["series"]["saques_valor"], [50.0, 0])
        self.assertEqual(serie["series"]["indicacoes"], [0, 1])
        # self.usuario (setUp) e indicado foram criados "agora", fora do período de março -
        # não devem contar em nenhum dos dois dias filtrados.
        self.assertEqual(serie["series"]["novos_usuarios"], [0, 0])

    def test_sem_periodo_usa_os_ultimos_30_dias_terminando_hoje(self):
        serie = obter_serie_diaria()

        hoje = timezone.localdate()
        self.assertEqual(len(serie["rotulos"]), 30)
        self.assertEqual(serie["rotulos"][-1], hoje.strftime("%d/%m"))

    def test_periodo_maior_que_180_dias_e_recortado_pro_final_dele(self):
        serie = obter_serie_diaria(data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31))

        self.assertEqual(len(serie["rotulos"]), 180)
        self.assertEqual(serie["rotulos"][-1], "31/12")

    def test_respeita_filtro_de_status_igual_ao_resto_da_tela(self):
        self._criar_pedido("VALID", "10.00", "5.00", timezone.make_aware(datetime(2026, 3, 1, 8)))
        Pedido.objects.create(
            order_id="CANC", conversion_id="2", usuario=self.usuario,
            status=Pedido.STATUS_CANCELADO, status_shopee_bruto="CANCELLED",
            valor_comissao=Decimal("10.00"), valor_cashback=Decimal("0"),
            data_compra=timezone.make_aware(datetime(2026, 3, 1, 9)),
        )

        serie = obter_serie_diaria(data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 1), status=Pedido.STATUS_VALIDADO)

        self.assertEqual(serie["series"]["pedidos"], [1])


class OrigemDetalhadaTests(TestCase):
    """Diferencia a origem de cada pedido: conversão de link direto, clique num card da
    vitrine de ofertas ou venda indireta (botão "Ir pra Shopee") - além do caso sem
    Click (pedido não gerado por aqui, ver OrigemFilter em pedidos/admin.py)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _pedido(self, order_id, click=None):
        return Pedido.objects.create(
            order_id=order_id, conversion_id="1", usuario=self.usuario, click=click,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
        )

    def test_sem_click_e_fora_do_site(self):
        pedido = self._pedido("ORD-SEM-CLICK")
        self.assertEqual(origem_detalhada(pedido), "Fora do site")

    def test_click_tipo_produto_e_link_direto(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_PRODUTO,
            url_original="https://shopee.com.br/produto-i.1.1", link_gerado="https://shope.ee/a",
        )
        pedido = self._pedido("ORD-LINK-DIRETO", click=click)
        self.assertEqual(origem_detalhada(pedido), "Link direto")

    def test_click_tipo_vitrine_e_vitrine_de_ofertas(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_VITRINE,
            url_original="https://shopee.com.br/produto-i.2.2", link_gerado="https://shope.ee/b",
        )
        pedido = self._pedido("ORD-VITRINE", click=click)
        self.assertEqual(origem_detalhada(pedido), "Vitrine de ofertas")

    def test_click_tipo_home_e_venda_indireta(self):
        click = Click.objects.create(
            usuario=self.usuario, tipo=Click.TIPO_HOME,
            url_original="https://shopee.com.br/", link_gerado="https://shope.ee/c",
        )
        pedido = self._pedido("ORD-INDIRETA", click=click)
        self.assertEqual(origem_detalhada(pedido), "Venda indireta (Ir pra Shopee)")


class AnalyticsAdminViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="equipe", password="senha123", cpf="39053344705", is_staff=True
        )
        self.usuario_comum = get_user_model().objects.create_user(
            username="comum", password="senha123", cpf="14783246947"
        )
        Pedido.objects.create(
            order_id="ORD-1", conversion_id="1", usuario=self.usuario_comum,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("10.00"), valor_cashback=Decimal("5.00"), data_compra=timezone.now(),
        )

    def test_staff_acessa_a_tela_de_analytics(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Comissão total")
        self.assertContains(resposta, "Quantidade de pedidos")

    def test_usuario_comum_nao_acessa_analytics(self):
        self.client.force_login(self.usuario_comum)
        resposta = self.client.get(reverse("admin:pedidos_analytics"))
        self.assertEqual(resposta.status_code, 302)

    def test_anonimo_e_redirecionado_para_login(self):
        resposta = self.client.get(reverse("admin:pedidos_analytics"))
        self.assertEqual(resposta.status_code, 302)

    def test_exportar_csv_traz_o_pedido_filtrado(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "text/csv")
        conteudo = resposta.content.decode()
        self.assertIn("ORD-1", conteudo)
        self.assertIn("comum", conteudo)

    def test_filtro_origem_site_exclui_pedido_sem_click(self):
        # ORD-1 (setUp) não tem Click vinculado - é "fora do site".
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics"), {"origem": "site"})
        self.assertEqual(resposta.context["dados"]["total_pedidos"], 0)
        self.assertEqual(resposta.context["filtro_origem"], "site")

    def test_filtro_origem_fora_inclui_pedido_sem_click(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics"), {"origem": "fora"})
        self.assertEqual(resposta.context["dados"]["total_pedidos"], 1)

    def test_filtro_origem_invalido_e_ignorado(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics"), {"origem": "lixo"})
        self.assertEqual(resposta.context["dados"]["total_pedidos"], 1)
        self.assertEqual(resposta.context["filtro_origem"], "")

    def test_exportar_csv_respeita_filtro_de_status(self):
        Pedido.objects.create(
            order_id="ORD-CANCELADO", conversion_id="2", usuario=self.usuario_comum,
            status=Pedido.STATUS_CANCELADO, status_shopee_bruto="CANCELLED",
            valor_comissao=Decimal("0"), valor_cashback=Decimal("0"), data_compra=timezone.now(),
        )
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar"), {"status": Pedido.STATUS_VALIDADO})
        conteudo = resposta.content.decode()
        self.assertIn("ORD-1", conteudo)
        self.assertNotIn("ORD-CANCELADO", conteudo)

    def test_exportar_excel_traz_resumo_e_pedidos_formatados(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar_excel"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        livro = load_workbook(BytesIO(resposta.content))
        self.assertEqual(livro.sheetnames, ["Resumo", "Pedidos"])

        resumo = livro["Resumo"]
        self.assertEqual(resumo["A1"].value, "Analytics — cash-b")

        aba_pedidos = livro["Pedidos"]
        cabecalho = [celula.value for celula in aba_pedidos[1]]
        self.assertEqual(cabecalho[0], "Order ID")
        linhas = list(aba_pedidos.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0][0], "ORD-1")
        self.assertEqual(linhas[0][2], "Fora do site")
        self.assertEqual(linhas[0][5], Decimal("10.00"))
        celula_comissao = aba_pedidos.cell(row=2, column=6)
        self.assertEqual(celula_comissao.number_format, '"R$" #,##0.00')

    def test_exportar_excel_usuario_comum_e_redirecionado(self):
        self.client.force_login(self.usuario_comum)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar_excel"))
        self.assertEqual(resposta.status_code, 302)

    def test_exportar_csv_zera_cashback_de_pedido_sem_usuario(self):
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="2", usuario=None,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"), data_compra=timezone.now(),
        )
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar"))
        conteudo = resposta.content.decode()
        linha = next(l for l in conteudo.splitlines() if l.startswith("FORA-DO-SITE"))
        self.assertIn(",100.00,0", linha)

    def test_exportar_excel_zera_cashback_de_pedido_sem_usuario(self):
        Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="2", usuario=None,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("100.00"), valor_cashback=Decimal("50.00"), data_compra=timezone.now(),
        )
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_analytics_exportar_excel"))

        livro = load_workbook(BytesIO(resposta.content))
        aba_pedidos = livro["Pedidos"]
        linhas = {linha[0]: linha for linha in aba_pedidos.iter_rows(min_row=2, values_only=True)}
        self.assertEqual(linhas["FORA-DO-SITE"][5], Decimal("100.00"))  # comissão real
        self.assertEqual(linhas["FORA-DO-SITE"][6], Decimal("0"))  # cashback zerado


class PedidoAdminValorCashbackExibidoTests(TestCase):
    def test_pedido_com_usuario_mostra_o_valor_de_verdade(self):
        usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        pedido = Pedido.objects.create(
            order_id="COM-USUARIO", conversion_id="1", usuario=usuario,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("10.00"), valor_cashback=Decimal("5.00"),
        )

        self.assertEqual(PedidoAdmin(Pedido, admin.site).valor_cashback_exibido(pedido), Decimal("5.00"))

    def test_pedido_sem_usuario_mostra_travessao(self):
        pedido = Pedido.objects.create(
            order_id="FORA-DO-SITE", conversion_id="1", usuario=None,
            status=Pedido.STATUS_VALIDADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("10.00"), valor_cashback=Decimal("5.00"),
        )

        self.assertEqual(PedidoAdmin(Pedido, admin.site).valor_cashback_exibido(pedido), "—")


class ResumoFinanceiroAdminViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="equipe", password="senha123", cpf="39053344705", is_staff=True
        )
        self.usuario_comum = get_user_model().objects.create_user(
            username="comum", password="senha123", cpf="14783246947"
        )

    def test_staff_acessa_a_tela(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Resumo financeiro")

    def test_usuario_comum_nao_acessa(self):
        self.client.force_login(self.usuario_comum)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"))
        self.assertEqual(resposta.status_code, 302)

    def test_anonimo_e_redirecionado_para_login(self):
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"))
        self.assertEqual(resposta.status_code, 302)

    def test_contexto_traz_grafico_e_tabela(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"))
        self.assertIn("grafico_sacado", resposta.context)
        self.assertIn("tabela_liberado", resposta.context)
        # linha de "disponível pra saque" (acumulado) + mês atual + 2 meses de projeção.
        self.assertEqual(len(resposta.context["tabela_liberado"]), 4)
        self.assertTrue(resposta.context["tabela_liberado"][0]["eh_disponivel"])

    def test_parametro_meses_passados_e_respeitado(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"), {"meses_passados": 2})
        self.assertEqual(len(resposta.context["grafico_sacado"]), 3)
        self.assertEqual(resposta.context["meses_passados"], 2)

    def test_parametro_invalido_cai_no_padrao(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"), {"meses_passados": "lixo"})
        self.assertEqual(resposta.context["meses_passados"], 6)

    def test_valores_linkam_pra_tela_de_saldo_por_usuario_em_nova_aba(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_resumo_financeiro"))
        self.assertContains(resposta, reverse("admin:pedidos_saldo_por_usuario"))
        self.assertContains(resposta, "target=\"_blank\"")


class SaldoPorUsuarioAdminViewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="equipe", password="senha123", cpf="39053344705", is_staff=True
        )
        self.usuario_comum = get_user_model().objects.create_user(
            username="comum", password="senha123", cpf="14783246947"
        )
        self.comprador = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="93541134780"
        )
        self.hoje = timezone.localdate()
        Pedido.objects.create(
            order_id="ORD-1", conversion_id="1", usuario=self.comprador, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("10.00"), valor_cashback=Decimal("25.00"),
            data_liberacao=timezone.make_aware(datetime(self.hoje.year, self.hoje.month, 15)),
        )

    def test_staff_ve_a_quebra_por_usuario(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(
            reverse("admin:pedidos_saldo_por_usuario"),
            {"ano": self.hoje.year, "mes": self.hoje.month, "tipo": "liberado"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "compradora")
        self.assertContains(resposta, "R$ 25,00")

    def test_usuario_comum_nao_acessa(self):
        self.client.force_login(self.usuario_comum)
        resposta = self.client.get(
            reverse("admin:pedidos_saldo_por_usuario"),
            {"ano": self.hoje.year, "mes": self.hoje.month, "tipo": "liberado"},
        )
        self.assertEqual(resposta.status_code, 302)

    def test_tipo_invalido_redireciona_pra_tela_principal(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(
            reverse("admin:pedidos_saldo_por_usuario"),
            {"ano": self.hoje.year, "mes": self.hoje.month, "tipo": "lixo"},
        )
        self.assertRedirects(resposta, reverse("admin:pedidos_resumo_financeiro"))

    def test_sem_parametros_redireciona_pra_tela_principal(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_saldo_por_usuario"))
        self.assertRedirects(resposta, reverse("admin:pedidos_resumo_financeiro"))

    def test_link_do_usuario_aponta_pro_change_dele_no_admin(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(
            reverse("admin:pedidos_saldo_por_usuario"),
            {"ano": self.hoje.year, "mes": self.hoje.month, "tipo": "liberado"},
        )
        self.assertContains(resposta, reverse("admin:accounts_user_change", args=[self.comprador.pk]))

    def test_tipo_disponivel_nao_precisa_de_ano_e_mes(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse("admin:pedidos_saldo_por_usuario"), {"tipo": "disponivel"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "compradora")
        self.assertContains(resposta, "R$ 25,00")
        self.assertContains(resposta, "acumulado até hoje")



class FaixaCampanhaTests(TestCase):
    """A faixa do site anuncia a campanha. O que importa provar: ela nunca anuncia uma
    campanha diferente da que está pagando, e o texto não promete mais do que o sistema paga."""

    def setUp(self):
        self.agora = timezone.now()

    def _campanha(self, multiplicador="1.5", inicio_em_dias=-1, fim_em_dias=1):
        return CampanhaCashback.objects.create(
            multiplicador=Decimal(multiplicador),
            inicio=self.agora + timedelta(days=inicio_em_dias),
            fim=None if fim_em_dias is None else self.agora + timedelta(days=fim_em_dias),
        )

    def test_percentual_extra_sai_do_multiplicador(self):
        self.assertEqual(CampanhaCashback(multiplicador=Decimal("1.5")).percentual_extra, 50)
        self.assertEqual(CampanhaCashback(multiplicador=Decimal("2")).percentual_extra, 100)
        self.assertEqual(CampanhaCashback(multiplicador=Decimal("1.25")).percentual_extra, 25)

    def test_sem_campanha_nao_ha_faixa(self):
        self.assertIsNone(CampanhaCashback.para_faixa(self.agora))

    def test_campanha_em_curso_vira_faixa_ativa(self):
        c = self._campanha()
        faixa = CampanhaCashback.para_faixa(self.agora)
        self.assertTrue(faixa["ativa"])
        self.assertEqual(faixa["campanha"], c)

    def test_campanha_que_comeca_em_ate_3_dias_vira_aviso(self):
        c = self._campanha(inicio_em_dias=2, fim_em_dias=3)
        faixa = CampanhaCashback.para_faixa(self.agora)
        self.assertFalse(faixa["ativa"])
        self.assertEqual(faixa["campanha"], c)

    def test_campanha_longe_demais_nao_vira_aviso(self):
        self._campanha(inicio_em_dias=4, fim_em_dias=5)
        self.assertIsNone(CampanhaCashback.para_faixa(self.agora))

    def test_campanha_encerrada_nao_vira_faixa(self):
        self._campanha(inicio_em_dias=-5, fim_em_dias=-1)
        self.assertIsNone(CampanhaCashback.para_faixa(self.agora))

    def test_multiplicador_1_nao_gera_faixa(self):
        self._campanha(multiplicador="1")
        self.assertIsNone(CampanhaCashback.para_faixa(self.agora))

    def test_em_curso_tem_prioridade_sobre_a_que_vem_ai(self):
        atual = self._campanha(inicio_em_dias=-1, fim_em_dias=1)
        self._campanha(inicio_em_dias=2, fim_em_dias=3)
        self.assertEqual(CampanhaCashback.para_faixa(self.agora)["campanha"], atual)

    def test_entre_duas_futuras_avisa_a_mais_proxima(self):
        proxima = self._campanha(inicio_em_dias=1, fim_em_dias=2)
        self._campanha(inicio_em_dias=3, fim_em_dias=4)
        self.assertEqual(CampanhaCashback.para_faixa(self.agora)["campanha"], proxima)

    def test_campanha_sem_fim_continua_ativa(self):
        self._campanha(fim_em_dias=None)
        self.assertTrue(CampanhaCashback.para_faixa(self.agora)["ativa"])

    # --- o que aparece de fato nas páginas

    def test_home_mostra_50_por_cento_a_mais_quando_ativa(self):
        self._campanha()
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "faixa-campanha")
        self.assertContains(resposta, "50% a mais de cashback")
        self.assertNotContains(resposta, "+50%")

    def test_campanha_de_um_dia_diz_no_dia_e_nao_diz_a_hora(self):
        hoje = timezone.localtime(self.agora)
        inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        CampanhaCashback.objects.create(
            multiplicador=Decimal("1.5"), inicio=inicio, fim=inicio.replace(hour=23, minute=59, second=59)
        )
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, f"em toda compra no {hoje:%d/%m}.")
        self.assertNotContains(resposta, "23h59")

    def test_campanha_de_varios_dias_diz_ate_e_nao_no(self):
        self._campanha(inicio_em_dias=-1, fim_em_dias=2)
        fim = timezone.localtime(self.agora + timedelta(days=2))
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, f"em toda compra até {fim:%d/%m}.")

    def test_campanha_sem_fim_diz_por_tempo_limitado(self):
        self._campanha(fim_em_dias=None)
        self.assertContains(self.client.get(reverse("home")), "por tempo limitado")

    def test_um_so_dia_so_vale_com_fim_no_mesmo_dia_local(self):
        inicio = timezone.localtime(self.agora).replace(hour=1)
        self.assertTrue(CampanhaCashback(inicio=inicio, fim=inicio.replace(hour=23)).um_so_dia)
        self.assertFalse(CampanhaCashback(inicio=inicio, fim=inicio + timedelta(days=1)).um_so_dia)
        self.assertFalse(CampanhaCashback(inicio=inicio, fim=None).um_so_dia)

    def test_multiplicador_2_vira_em_dobro(self):
        self._campanha(multiplicador="2")
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "Cashback em dobro")
        self.assertNotContains(resposta, "100% a mais")

    def test_aviso_previo_diz_o_dia_e_nao_diz_ate_quando(self):
        inicio = (self.agora + timedelta(days=2)).replace(hour=3, minute=0)
        CampanhaCashback.objects.create(multiplicador=Decimal("1.5"), inicio=inicio, fim=inicio + timedelta(hours=20))
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "50% a mais de cashback")
        self.assertContains(resposta, f"Dia {timezone.localtime(inicio):%d.%m}")

    def test_sem_campanha_a_pagina_nao_tem_faixa(self):
        resposta = self.client.get(reverse("home"))
        self.assertNotContains(resposta, "faixa-campanha")

    def test_faixa_aparece_na_pagina_de_cadastro_onde_o_anuncio_aponta(self):
        self._campanha()
        resposta = self.client.get(reverse("registrar"))
        self.assertContains(resposta, "50% a mais de cashback")

    def test_faixa_aparece_na_lista_de_ofertas(self):
        self._campanha()
        resposta = self.client.get(reverse("ofertas_lista"))
        self.assertContains(resposta, "50% a mais de cashback")


class SimularCampanhaTests(TestCase):
    """O comando responde se uma campanha dá prejuízo. O que ele precisa acertar: normalizar o
    multiplicador que já estava gravado, separar indireta de vitrine e não contar bônus de
    indicação nem pedido cancelado."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="u", password="x", cpf="39053344705")
        self.n = 0

    def _pedido(self, comissao, cashback, tipo=Click.TIPO_PRODUTO, status=Pedido.STATUS_VALIDADO,
                multiplicador="1", valor="100.00", dias_atras=3):
        self.n += 1
        click = Click.objects.create(usuario=self.usuario, tipo=tipo, url_original="https://shopee.com.br/x",
                                     link_gerado="https://s.shopee.com.br/y")
        return Pedido.objects.create(
            order_id=f"ORD-{self.n}", conversion_id="1", click=click, usuario=self.usuario, status=status,
            valor_pedido=Decimal(valor), valor_comissao=Decimal(comissao), valor_cashback=Decimal(cashback),
            multiplicador_campanha=Decimal(multiplicador),
            data_compra=timezone.now() - timedelta(days=dias_atras),
        )

    def _rodar(self, **opcoes):
        saida = StringIO()
        call_command("simular_campanha", stdout=saida, **opcoes)
        return saida.getvalue()

    def test_margem_simulada_com_multiplicador(self):
        self._pedido("8.00", "1.60")                       # 20% da comissão
        saida = self._rodar(multiplicador="1.5")
        self.assertRegex(saida, r"cashback hoje\s+R\$ 1,60")
        self.assertRegex(saida, r"cashback simulado \(x1\.5\)\s+R\$ 2,40")
        self.assertRegex(saida, r"margem simulada\s+R\$ 5,60")
        self.assertIn("Nenhum pedido pagaria mais cashback do que a comissão", saida)

    def test_indireta_a_33_por_cento_nao_da_prejuizo_a_1_5_mas_da_a_3(self):
        self._pedido("3.00", "1.00", tipo=Click.TIPO_HOME)  # 1% de cashback sobre 3% de comissão
        self.assertIn("Nenhum pedido pagaria mais", self._rodar(multiplicador="1.5"))
        saida = self._rodar(multiplicador="3.5")
        self.assertIn("1 pedido(s) pagariam MAIS cashback", saida)

    def test_normaliza_o_multiplicador_ja_gravado(self):
        # pedido feito durante uma campanha x2: cashback gravado 3,20 vem de uma base de 1,60
        self._pedido("8.00", "3.20", multiplicador="2")
        saida = self._rodar(multiplicador="1.5")
        self.assertRegex(saida, r"cashback hoje\s+R\$ 1,60")
        self.assertRegex(saida, r"cashback simulado \(x1\.5\)\s+R\$ 2,40")

    def test_separa_indireta_de_vitrine(self):
        self._pedido("8.00", "1.60", tipo=Click.TIPO_VITRINE)
        self._pedido("3.00", "1.00", tipo=Click.TIPO_HOME)
        saida = self._rodar()
        self.assertRegex(saida, r"link / vitrine\s+1 pedidos")
        self.assertRegex(saida, r"indireta\)\s+1 pedidos")

    def test_cancelado_e_fora_da_janela_nao_entram(self):
        self._pedido("8.00", "1.60", status=Pedido.STATUS_CANCELADO)
        self._pedido("8.00", "1.60", dias_atras=90)
        self.assertIn("Nenhum pedido na janela", self._rodar(dias=60))

    def test_pedido_de_bonus_de_indicacao_fica_de_fora(self):
        pedido = self._pedido("8.00", "3.20")              # já dobrado pela indicação
        outro = get_user_model().objects.create_user(username="i", password="x", cpf="52998224725")
        Indicacao.objects.create(indicador=outro, indicado=self.usuario, pedido_bonus_indicado=pedido)
        saida = self._rodar()
        self.assertIn("fora da conta (bônus de indicação): 1", saida)
        self.assertIn("Nenhum pedido na janela", saida)

    def test_multiplicador_invalido_da_erro_claro(self):
        with self.assertRaisesMessage(Exception, "precisa ser um número"):
            self._rodar(multiplicador="abc")


class PreviaCampanhaTests(TestCase):
    """A prévia da campanha (pedidos/previa.py) só pode ser vista pelo superusuário que a ligou,
    em páginas públicas, em GET, por tempo limitado, sem cache e sem vazar para a requisição
    seguinte. Cada teste aqui prova uma dessas travas - e a campanha usada começa daqui a 4 dias,
    fora da janela de 3 dias da faixa de aviso: tudo o que aparecer na página é, portanto, a prévia."""

    def setUp(self):
        from types import SimpleNamespace

        self.SimpleNamespace = SimpleNamespace
        self.agora = timezone.now()
        self.campanha = CampanhaCashback.objects.create(
            multiplicador=Decimal("1.5"),
            inicio=self.agora + timedelta(days=4),
            fim=self.agora + timedelta(days=4, hours=23),
        )
        User = get_user_model()
        self.admin = User.objects.create_user(username="dono", password="senha123", cpf="39053344705")
        self.admin.is_staff = self.admin.is_superuser = True
        self.admin.save()
        self.staff = User.objects.create_user(username="influencer", password="senha123", cpf="52998224725")
        self.staff.is_staff = True
        self.staff.save()
        self.comum = User.objects.create_user(username="cliente", password="senha123", cpf="11144477735")

    def _ligar(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("previa_campanha"), {"acao": "ligar"})

    def _marca_futura(self):
        return (timezone.now() + timedelta(hours=1)).isoformat()

    # --- quem liga

    def test_anonimo_recebe_404_na_tela(self):
        self.assertEqual(self.client.get(reverse("previa_campanha")).status_code, 404)
        self.assertEqual(self.client.post(reverse("previa_campanha"), {"acao": "ligar"}).status_code, 404)

    def test_usuario_comum_e_staff_que_nao_e_superusuario_recebem_404(self):
        for usuario in (self.comum, self.staff):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("previa_campanha")).status_code, 404, usuario.username)
            self.assertEqual(
                self.client.post(reverse("previa_campanha"), {"acao": "ligar"}).status_code, 404, usuario.username
            )
            self.assertNotIn("previa_campanha_ate", self.client.session)

    def test_superusuario_abre_a_tela_e_liga(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("previa_campanha")), "Prévia desligada")
        self.client.post(reverse("previa_campanha"), {"acao": "ligar"})
        self.assertIn("previa_campanha_ate", self.client.session)
        self.assertContains(self.client.get(reverse("previa_campanha")), "Prévia LIGADA")

    def test_desligar_remove_a_marca(self):
        self._ligar()
        self.client.post(reverse("previa_campanha"), {"acao": "desligar"})
        self.assertNotIn("previa_campanha_ate", self.client.session)
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_sem_campanha_cadastrada_a_previa_nao_liga(self):
        CampanhaCashback.objects.all().delete()
        self.client.force_login(self.admin)
        self.client.post(reverse("previa_campanha"), {"acao": "ligar"})
        self.assertNotIn("previa_campanha_ate", self.client.session)
        self.assertContains(self.client.get(reverse("previa_campanha")), "Não há campanha cadastrada")

    # --- quem vê

    def test_superusuario_ve_a_faixa_e_o_aviso_vermelho(self):
        self._ligar()
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "faixa-campanha")
        self.assertContains(resposta, "50% a mais de cashback")
        self.assertContains(resposta, "PRÉVIA DA CAMPANHA")

    def test_sem_a_previa_ligada_nem_o_superusuario_ve(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_outro_navegador_nao_ve_nada(self):
        from django.test import Client

        self._ligar()
        self.assertContains(self.client.get(reverse("home")), "faixa-campanha")
        anonimo = Client()
        for url in (reverse("home"), reverse("ofertas_lista"), reverse("registrar"), reverse("login")):
            resposta = anonimo.get(url)
            self.assertNotContains(resposta, "faixa-campanha", msg_prefix=url)
            self.assertNotContains(resposta, "PRÉVIA", msg_prefix=url)

    def test_marca_forjada_na_sessao_de_usuario_comum_nao_mostra_nada(self):
        self.client.force_login(self.comum)
        sessao = self.client.session
        sessao["previa_campanha_ate"] = self._marca_futura()
        sessao.save()
        resposta = self.client.get(reverse("home"))
        self.assertNotContains(resposta, "faixa-campanha")
        self.assertNotContains(resposta, "PRÉVIA")

    def test_marca_forjada_na_sessao_de_staff_nao_superusuario_nao_mostra_nada(self):
        self.client.force_login(self.staff)
        sessao = self.client.session
        sessao["previa_campanha_ate"] = self._marca_futura()
        sessao.save()
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_marca_forjada_sem_login_nao_mostra_nada(self):
        sessao = self.client.session
        sessao["previa_campanha_ate"] = self._marca_futura()
        sessao.save()
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_perdeu_o_poder_de_superusuario_deixa_de_ver(self):
        self._ligar()
        self.admin.is_superuser = False
        self.admin.save()
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_usuario_desativado_nao_ve(self):
        from .previa import pode_ver_previa

        self.admin.is_active = False
        self.assertFalse(pode_ver_previa(self.admin))
        self.assertFalse(pode_ver_previa(None))

    def test_marca_expirada_nao_mostra_nada(self):
        self._ligar()
        sessao = self.client.session
        sessao["previa_campanha_ate"] = (timezone.now() - timedelta(minutes=1)).isoformat()
        sessao.save()
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    def test_marca_ilegivel_nao_quebra_a_pagina(self):
        self._ligar()
        sessao = self.client.session
        sessao["previa_campanha_ate"] = "lixo"
        sessao.save()
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_logout_desliga_a_previa(self):
        self._ligar()
        self.client.logout()
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("home")), "faixa-campanha")

    # --- onde vale

    def test_so_vale_em_get_ou_head_nas_paginas_publicas_da_lista(self):
        from .middleware import campanha_para_previa

        def pedido(metodo, caminho, usuario=None):
            return self.SimpleNamespace(
                method=metodo, path=caminho, user=usuario or self.admin,
                session={"previa_campanha_ate": self._marca_futura()},
            )

        self.assertEqual(campanha_para_previa(pedido("GET", "/")), self.campanha)
        self.assertEqual(campanha_para_previa(pedido("HEAD", "/ofertas/")), self.campanha)
        # POST nunca (gravaria/publicaria um valor da prévia)
        self.assertIsNone(campanha_para_previa(pedido("POST", "/")))
        # admin, tarefas agendadas, geração de story e de e-mail: fora da lista
        for caminho in (
            "/admin/", "/admin/ofertas/oferta/", "/tarefas/executar/", "/tarefas/postar-story-oferta/",
            "/ofertas/1/ir/", "/previa-campanha/", "/automacao/", "/links/", "/ir-para-shopee/", "/healthz/",
        ):
            self.assertIsNone(campanha_para_previa(pedido("GET", caminho)), caminho)
        # e só para superusuário
        self.assertIsNone(campanha_para_previa(pedido("GET", "/", self.comum)))
        self.assertIsNone(campanha_para_previa(pedido("GET", "/", self.staff)))

    def test_a_tela_da_previa_e_o_admin_nao_mostram_a_previa(self):
        self._ligar()
        self.assertNotContains(self.client.get(reverse("previa_campanha")), "PRÉVIA DA CAMPANHA")
        self.assertNotContains(self.client.get("/admin/"), "PRÉVIA DA CAMPANHA")

    # --- cache e vazamento entre requisições

    def test_resposta_da_previa_sai_sem_cache(self):
        self._ligar()
        resposta = self.client.get(reverse("home"))
        controle = resposta["Cache-Control"]
        self.assertIn("no-store", controle)
        self.assertIn("private", controle)
        self.assertIn("Cookie", resposta["Vary"])

    def test_nao_vaza_para_a_requisicao_seguinte(self):
        from .previa import campanha_da_previa

        self._ligar()
        self.client.get(reverse("home"))
        self.assertIsNone(campanha_da_previa())
        self.assertEqual(CampanhaCashback.multiplicador_atual(), Decimal("1"))
        self.assertIsNone(CampanhaCashback.para_faixa())

    def test_a_variavel_da_previa_e_restaurada_mesmo_se_a_pagina_falhar(self):
        from django.test import RequestFactory

        from .middleware import PreviaCampanhaMiddleware
        from .previa import campanha_da_previa

        def view_que_falha(request):
            self.assertEqual(campanha_da_previa(), self.campanha)
            raise RuntimeError("falhou")

        pedido = RequestFactory().get("/")
        pedido.user = self.admin
        pedido.session = {"previa_campanha_ate": self._marca_futura()}
        with self.assertRaises(RuntimeError):
            PreviaCampanhaMiddleware(view_que_falha)(pedido)
        self.assertIsNone(campanha_da_previa())

    # --- o que a prévia NÃO pode tocar

    def test_nao_muda_o_multiplicador_que_carimba_o_pedido(self):
        from .previa import _campanha_previa

        token = _campanha_previa.set(self.campanha)
        try:
            self.assertEqual(CampanhaCashback.multiplicador_atual(), Decimal("1.5"))
            self.assertEqual(CampanhaCashback.multiplicador_em(timezone.now()), Decimal("1"))
        finally:
            _campanha_previa.reset(token)

    def test_nao_grava_nada_no_banco(self):
        self._ligar()
        antes = (CampanhaCashback.objects.count(), Pedido.objects.count(), Click.objects.count())
        for url in (reverse("home"), reverse("ofertas_lista"), reverse("registrar")):
            self.client.get(url)
        depois = (CampanhaCashback.objects.count(), Pedido.objects.count(), Click.objects.count())
        self.assertEqual(antes, depois)

    def test_card_de_oferta_mostra_o_valor_da_campanha_so_na_previa(self):
        from ofertas.models import Oferta

        from .previa import _campanha_previa

        oferta = Oferta.objects.create(
            item_id=991, nome="Produto de prévia", categoria_id=1,
            product_link="https://shopee.com.br/produto-991-i.1.991",
            percentual_comissao=Decimal("0.1000"), preco_min=Decimal("100"), preco_max=Decimal("100"), vendas=5,
        )
        normal = str(oferta.percentual_cashback).replace(".", ",")  # a página usa vírgula
        token = _campanha_previa.set(self.campanha)
        try:
            com_campanha = str(oferta.percentual_cashback).replace(".", ",")
        finally:
            _campanha_previa.reset(token)
        self.assertNotEqual(com_campanha, normal)

        self.assertContains(self.client.get(reverse("ofertas_lista")), f"{normal}% cashback")
        self._ligar()
        resposta = self.client.get(reverse("ofertas_lista"))
        self.assertContains(resposta, f"{com_campanha}% cashback")
        self.assertNotContains(resposta, f"{normal}% cashback")
        # e quem não é o administrador continua vendo o valor normal
        from django.test import Client

        self.assertContains(Client().get(reverse("ofertas_lista")), f"{normal}% cashback")
