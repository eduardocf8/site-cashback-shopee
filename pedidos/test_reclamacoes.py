from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import ItemPedido, Pedido, ReclamacaoPedido
from .reclamacoes import (
    DIAS_PROCURANDO,
    ReclamacaoInvalida,
    abrir_reclamacao,
    atualizar_reclamacoes,
    recusar,
    vincular,
)
from .services import sincronizar

User = get_user_model()


def _pagina_sem_clique(order_id, comissao="2.00", valor="100.00"):
    """Conversão que a Shopee manda sem utmContent - pedido "fora do site"."""
    return {
        "nodes": [
            {
                "conversionId": "555",
                "purchaseTime": 1700000000,
                "utmContent": "",
                "orders": [
                    {
                        "orderId": order_id,
                        "orderStatus": "PENDING",
                        "items": [
                            {
                                "itemId": 7,
                                "itemName": "Fone bluetooth",
                                "completeTime": None,
                                "itemTotalCommission": comissao,
                                "actualAmount": valor,
                            }
                        ],
                    }
                ],
            }
        ],
        "pageInfo": {"hasNextPage": False, "scrollId": ""},
    }


@override_settings(SHOPEE_CASHBACK_PERCENTUAL=50, CASHBACK_MINIMO_VENDA_INDIRETA=1)
class ReclamacaoTestBase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="ana", password="senha123", email="ana@example.com", cpf="39053344705"
        )
        self.outra = User.objects.create_user(
            username="bia", password="senha123", email="bia@example.com", cpf="52998224725"
        )
        self.hoje = timezone.localdate()
        self.ha_tres_dias = self.hoje - timedelta(days=3)

    def _pedido_fora(self, order_id="2410ABCD1234", comissao="0.40", valor="100.00"):
        pedido = Pedido.objects.create(
            order_id=order_id, conversion_id="1", status_shopee_bruto="PENDING",
            valor_pedido=Decimal(valor), valor_comissao=Decimal(comissao),
            produto_nome="Fone bluetooth", data_compra=timezone.now() - timedelta(days=3),
        )
        ItemPedido.objects.create(
            pedido=pedido, item_id=7, nome="Fone bluetooth",
            valor_item=Decimal(valor), comissao_item=Decimal(comissao),
        )
        return pedido


class AbrirReclamacaoTests(ReclamacaoTestBase):
    def test_pedido_ja_sincronizado_sem_dono_fica_em_analise(self):
        pedido = self._pedido_fora()
        reclamacao = abrir_reclamacao(self.usuario, " 2410abcd-1234 ", self.ha_tres_dias, "Fone")
        self.assertEqual(reclamacao.order_id, "2410ABCD1234")
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_EM_ANALISE)
        self.assertEqual(reclamacao.pedido, pedido)

    def test_pedido_que_ainda_nao_chegou_fica_aguardando(self):
        reclamacao = abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.ha_tres_dias, "Fone")
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_AGUARDANDO)
        self.assertIsNone(reclamacao.pedido)

    def test_recusa_numero_invalido(self):
        with self.assertRaises(ReclamacaoInvalida):
            abrir_reclamacao(self.usuario, "abc", self.ha_tres_dias, "Fone")

    def test_recusa_compra_de_menos_de_2_dias(self):
        with self.assertRaisesMessage(ReclamacaoInvalida, "em até 2 dias"):
            abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.hoje - timedelta(days=1), "Fone")

    def test_recusa_data_no_futuro_e_compra_antiga_demais(self):
        with self.assertRaises(ReclamacaoInvalida):
            abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.hoje + timedelta(days=1), "Fone")
        with self.assertRaises(ReclamacaoInvalida):
            abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.hoje - timedelta(days=61), "Fone")

    def test_pedido_que_ja_e_da_pessoa(self):
        pedido = self._pedido_fora()
        pedido.usuario = self.usuario
        pedido.save()
        with self.assertRaisesMessage(ReclamacaoInvalida, "já está na sua conta"):
            abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")

    def test_pedido_de_outra_conta(self):
        pedido = self._pedido_fora()
        pedido.usuario = self.outra
        pedido.save()
        with self.assertRaisesMessage(ReclamacaoInvalida, "outra conta"):
            abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        self.assertFalse(ReclamacaoPedido.objects.exists())

    def test_nao_repete_o_mesmo_pedido_e_limita_abertas(self):
        abrir_reclamacao(self.usuario, "2410ZZZZ0001", self.ha_tres_dias, "Fone")
        with self.assertRaisesMessage(ReclamacaoInvalida, "já avisou"):
            abrir_reclamacao(self.usuario, "2410ZZZZ0001", self.ha_tres_dias, "Fone")
        abrir_reclamacao(self.usuario, "2410ZZZZ0002", self.ha_tres_dias, "Fone")
        abrir_reclamacao(self.usuario, "2410ZZZZ0003", self.ha_tres_dias, "Fone")
        with self.assertRaisesMessage(ReclamacaoInvalida, "avisos em andamento"):
            abrir_reclamacao(self.usuario, "2410ZZZZ0004", self.ha_tres_dias, "Fone")


class VincularTests(ReclamacaoTestBase):
    def test_vincula_com_cashback_de_venda_indireta_e_avisa(self):
        pedido = self._pedido_fora(comissao="0.40", valor="100.00")
        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        concorrente = abrir_reclamacao(self.outra, pedido.order_id, self.ha_tres_dias, "Fone")

        vincular(reclamacao)

        pedido.refresh_from_db()
        reclamacao.refresh_from_db()
        concorrente.refresh_from_db()
        self.assertEqual(pedido.usuario, self.usuario)
        self.assertIsNotNone(pedido.vinculado_manualmente_em)
        # 50% de 0,40 = 0,20, abaixo do piso indireto de 1% de 100 = 1,00.
        self.assertEqual(pedido.valor_cashback, Decimal("1.00"))
        self.assertEqual(pedido.itens.get().cashback_pago, Decimal("1.00"))
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_VINCULADA)
        self.assertEqual(concorrente.status, ReclamacaoPedido.STATUS_RECUSADA)
        destinatarios = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(destinatarios, ["ana@example.com", "bia@example.com"])
        self.assertTrue(Pedido.objects.filter(Pedido.filtro_do_site(), pk=pedido.pk).exists())

    def test_item_sem_comissao_continua_sem_cashback(self):
        pedido = self._pedido_fora(comissao="0", valor="50.00")
        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Café")
        vincular(reclamacao)
        pedido.refresh_from_db()
        self.assertEqual(pedido.valor_cashback, Decimal("0.00"))

    def test_nao_vincula_pedido_que_ja_tem_dono(self):
        pedido = self._pedido_fora()
        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        Pedido.objects.filter(pk=pedido.pk).update(usuario=self.outra)
        with self.assertRaises(ReclamacaoInvalida):
            vincular(reclamacao)

    def test_recusar_guarda_resposta_e_avisa(self):
        pedido = self._pedido_fora()
        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        recusar(reclamacao, "")
        reclamacao.refresh_from_db()
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_RECUSADA)
        self.assertTrue(reclamacao.resposta)
        self.assertEqual(len(mail.outbox), 1)
        pedido.refresh_from_db()
        self.assertIsNone(pedido.usuario)

    @patch("pedidos.services.buscar_conversoes")
    def test_sincronizacao_seguinte_mantem_o_vinculo(self, mock_buscar):
        mock_buscar.return_value = _pagina_sem_clique("2410SYNC0001", comissao="2.00", valor="100.00")
        sincronizar(1690000000, 1700000000)
        pedido = Pedido.objects.get(order_id="2410SYNC0001")
        self.assertIsNone(pedido.usuario)

        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        vincular(reclamacao)
        sincronizar(1690000000, 1700000000)

        pedido.refresh_from_db()
        self.assertEqual(pedido.usuario, self.usuario)
        self.assertIsNone(pedido.click)
        # 50% de 2,00 = 1,00 (igual ao piso de 1% de 100).
        self.assertEqual(pedido.valor_cashback, Decimal("1.00"))
        self.assertEqual(pedido.itens.get().cashback_pago, Decimal("1.00"))

    @patch("pedidos.services.buscar_conversoes")
    def test_pedido_fora_do_site_sem_vinculo_continua_sem_dono(self, mock_buscar):
        mock_buscar.return_value = _pagina_sem_clique("2410SYNC0002")
        sincronizar(1690000000, 1700000000)
        sincronizar(1690000000, 1700000000)
        pedido = Pedido.objects.get(order_id="2410SYNC0002")
        self.assertIsNone(pedido.usuario)
        self.assertEqual(pedido.valor_cashback, Decimal("0"))


class AtualizarReclamacoesTests(ReclamacaoTestBase):
    def test_pedido_que_chegou_depois_vai_para_analise(self):
        reclamacao = abrir_reclamacao(self.usuario, "2410ABCD1234", self.ha_tres_dias, "Fone")
        pedido = self._pedido_fora("2410ABCD1234")
        resultado = atualizar_reclamacoes()
        reclamacao.refresh_from_db()
        self.assertEqual(resultado["encontradas"], 1)
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_EM_ANALISE)
        self.assertEqual(reclamacao.pedido, pedido)

    def test_pedido_que_chegou_com_o_clique_da_pessoa_encerra_sozinho(self):
        reclamacao = abrir_reclamacao(self.usuario, "2410ABCD1234", self.ha_tres_dias, "Fone")
        pedido = self._pedido_fora("2410ABCD1234")
        pedido.usuario = self.usuario
        pedido.save()
        atualizar_reclamacoes()
        reclamacao.refresh_from_db()
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_VINCULADA)

    def test_encerra_depois_do_prazo_sem_encontrar(self):
        reclamacao = abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.ha_tres_dias, "Fone")
        ReclamacaoPedido.objects.filter(pk=reclamacao.pk).update(
            criado_em=timezone.now() - timedelta(days=DIAS_PROCURANDO + 1)
        )
        resultado = atualizar_reclamacoes()
        reclamacao.refresh_from_db()
        self.assertEqual(resultado["nao_encontradas"], 1)
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_NAO_ENCONTRADA)
        self.assertEqual(len(mail.outbox), 1)

    def test_ainda_dentro_do_prazo_continua_procurando(self):
        reclamacao = abrir_reclamacao(self.usuario, "2410ZZZZ9999", self.ha_tres_dias, "Fone")
        atualizar_reclamacoes()
        reclamacao.refresh_from_db()
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_AGUARDANDO)


class CompraNaoApareceuViewTests(ReclamacaoTestBase):
    def test_exige_login(self):
        resposta = self.client.get(reverse("compra_nao_apareceu"))
        self.assertEqual(resposta.status_code, 302)

    def test_envia_e_mostra_andamento(self):
        self._pedido_fora("2410ABCD1234")
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse("compra_nao_apareceu"),
            {"order_id": "2410ABCD1234", "data_compra": self.ha_tres_dias.isoformat(), "produto": "Fone"},
            follow=True,
        )
        self.assertContains(resposta, "Encontramos esse pedido")
        self.assertContains(resposta, "Pedido encontrado, em análise")

    def test_mostra_erro_no_formulario(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse("compra_nao_apareceu"),
            {"order_id": "2410ABCD1234", "data_compra": self.hoje.isoformat(), "produto": "Fone"},
        )
        self.assertContains(resposta, "em até 2 dias")
        self.assertFalse(ReclamacaoPedido.objects.exists())

    def test_painel_tem_link_para_avisar(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("dashboard"))
        self.assertContains(resposta, reverse("compra_nao_apareceu"))


class ReclamacaoAdminTests(ReclamacaoTestBase):
    def test_acao_vincular_no_admin(self):
        admin_user = User.objects.create_superuser(
            username="admin", password="senha123", email="admin@example.com", cpf="11144477735"
        )
        pedido = self._pedido_fora()
        reclamacao = abrir_reclamacao(self.usuario, pedido.order_id, self.ha_tres_dias, "Fone")
        self.client.force_login(admin_user)
        url = reverse("admin:pedidos_reclamacaopedido_changelist")
        lista = self.client.get(url)
        self.assertContains(lista, pedido.order_id)
        self.client.post(url, {"action": "acao_vincular", "_selected_action": [reclamacao.pk]})
        reclamacao.refresh_from_db()
        self.assertEqual(reclamacao.status, ReclamacaoPedido.STATUS_VINCULADA)
