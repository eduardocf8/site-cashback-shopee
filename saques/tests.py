from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from pedidos.models import Pedido

from .asaas_client import AsaasAPIError, AsaasConfigError
from .inter_client import InterAPIError, InterConfigError
from .models import Saque
from .services import (
    ChavePixNaoConfiguradaError,
    ValorAbaixoDoMinimoError,
    atualizar_status_saque,
    calcular_resumo_saldo_nav,
    calcular_saldo_disponivel,
    processar_saque_asaas,
    processar_saque_inter,
    solicitar_saque,
)


@override_settings(SAQUE_VALOR_MINIMO=Decimal("20.00"))
class CalcularSaldoDisponivelTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _criar_pedido(self, order_id, status, valor):
        return Pedido.objects.create(
            order_id=order_id,
            conversion_id="1",
            usuario=self.usuario,
            status=status,
            status_shopee_bruto="COMPLETED",
            valor_comissao=valor,
            valor_cashback=valor,
        )

    def test_soma_apenas_pedidos_liberados(self):
        self._criar_pedido("P1", Pedido.STATUS_LIBERADO, Decimal("30.00"))
        self._criar_pedido("P2", Pedido.STATUS_VALIDADO, Decimal("50.00"))
        self._criar_pedido("P3", Pedido.STATUS_PENDENTE, Decimal("10.00"))

        self.assertEqual(calcular_saldo_disponivel(self.usuario), Decimal("30.00"))

    def test_desconta_saques_solicitados_e_pagos(self):
        self._criar_pedido("P4", Pedido.STATUS_LIBERADO, Decimal("100.00"))
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("30.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_SOLICITADO,
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_PAGO,
        )

        self.assertEqual(calcular_saldo_disponivel(self.usuario), Decimal("50.00"))

    def test_nao_desconta_saques_cancelados_ou_que_falharam(self):
        self._criar_pedido("P5", Pedido.STATUS_LIBERADO, Decimal("100.00"))
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("30.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_CANCELADO,
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("40.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_FALHOU,
        )

        self.assertEqual(calcular_saldo_disponivel(self.usuario), Decimal("100.00"))


class CalcularResumoSaldoNavTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _criar_pedido(self, order_id, status, valor):
        return Pedido.objects.create(
            order_id=order_id,
            conversion_id="1",
            usuario=self.usuario,
            status=status,
            status_shopee_bruto="COMPLETED",
            valor_comissao=valor,
            valor_cashback=valor,
        )

    def test_liberado_desconta_o_ja_sacado(self):
        self._criar_pedido("P1", Pedido.STATUS_LIBERADO, Decimal("40.00"))
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_PAGO,
        )

        resumo = calcular_resumo_saldo_nav(self.usuario)

        self.assertEqual(resumo["saldo_liberado_nav"], Decimal("20.00"))

    def test_outros_soma_pendente_e_validado(self):
        self._criar_pedido("P2", Pedido.STATUS_PENDENTE, Decimal("5.00"))
        self._criar_pedido("P3", Pedido.STATUS_VALIDADO, Decimal("7.00"))

        resumo = calcular_resumo_saldo_nav(self.usuario)

        self.assertEqual(resumo["saldo_outros_nav"], Decimal("12.00"))


@override_settings(SAQUE_VALOR_MINIMO=Decimal("20.00"))
class SolicitarSaqueTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )

    def _liberar_saldo(self, valor):
        Pedido.objects.create(
            order_id="P1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=valor, valor_cashback=valor,
        )

    def test_sem_chave_pix_nao_deixa_solicitar(self):
        self._liberar_saldo(Decimal("50.00"))
        with self.assertRaises(ChavePixNaoConfiguradaError):
            solicitar_saque(self.usuario)

    def test_saldo_abaixo_do_minimo_nao_deixa_solicitar(self):
        self.usuario.chave_pix = "fulano@example.com"
        self.usuario.tipo_chave_pix = "EMAIL"
        self.usuario.save()
        self._liberar_saldo(Decimal("10.00"))

        with self.assertRaises(ValorAbaixoDoMinimoError):
            solicitar_saque(self.usuario)

    def test_solicita_saque_do_saldo_total_disponivel(self):
        self.usuario.chave_pix = "fulano@example.com"
        self.usuario.tipo_chave_pix = "EMAIL"
        self.usuario.save()
        self._liberar_saldo(Decimal("75.00"))

        saque = solicitar_saque(self.usuario)

        self.assertEqual(saque.valor, Decimal("75.00"))
        self.assertEqual(saque.chave_pix, "fulano@example.com")
        self.assertEqual(saque.tipo_chave_pix, "EMAIL")
        self.assertEqual(saque.status, Saque.STATUS_SOLICITADO)
        # o saldo disponível cai a zero, já que o saque em si passa a reservar o valor
        self.assertEqual(calcular_saldo_disponivel(self.usuario), Decimal("0"))


class ProcessarSaqueAsaasTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="fulano@example.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_SOLICITADO,
        )

    @patch("saques.services.criar_transferencia_pix")
    def test_transferencia_concluida_marca_como_pago(self, mock_criar):
        mock_criar.return_value = {"id": "tr_123", "status": "DONE"}

        processar_saque_asaas(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PAGO)
        self.assertEqual(self.saque.provedor, Saque.PROVEDOR_ASAAS)
        self.assertEqual(self.saque.asaas_transfer_id, "tr_123")
        self.assertIsNotNone(self.saque.pago_em)

    @patch("saques.services.criar_transferencia_pix")
    def test_transferencia_com_status_pendente_fica_processando(self, mock_criar):
        mock_criar.return_value = {"id": "tr_124", "status": "PENDING"}

        processar_saque_asaas(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PROCESSANDO)
        self.assertIsNone(self.saque.pago_em)

    @patch("saques.services.criar_transferencia_pix")
    def test_erro_da_asaas_marca_como_falhou(self, mock_criar):
        mock_criar.side_effect = AsaasAPIError("Chave PIX inválida")

        processar_saque_asaas(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_FALHOU)
        self.assertIn("Chave PIX inválida", self.saque.resposta_asaas)

    @patch("saques.services.criar_transferencia_pix")
    def test_sem_api_key_configurada_marca_como_falhou(self, mock_criar):
        mock_criar.side_effect = AsaasConfigError("Configure ASAAS_API_KEY...")

        processar_saque_asaas(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_FALHOU)


class ProcessarSaqueInterTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="fulano@example.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_SOLICITADO,
        )

    @patch("saques.services.criar_pagamento_pix")
    def test_solicitacao_aceita_fica_processando(self, mock_criar):
        mock_criar.return_value = {"tipoRetorno": "APROVACAO", "codigoSolicitacao": "abc-123"}

        processar_saque_inter(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PROCESSANDO)
        self.assertEqual(self.saque.provedor, Saque.PROVEDOR_INTER)
        self.assertEqual(self.saque.inter_codigo_solicitacao, "abc-123")

    @patch("saques.services.criar_pagamento_pix")
    def test_erro_do_inter_marca_como_falhou(self, mock_criar):
        mock_criar.side_effect = InterAPIError("Chave PIX inválida")

        processar_saque_inter(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_FALHOU)
        self.assertIn("Chave PIX inválida", self.saque.resposta_inter)

    @patch("saques.services.criar_pagamento_pix")
    def test_sem_certificado_configurado_marca_como_falhou(self, mock_criar):
        mock_criar.side_effect = InterConfigError("Configure INTER_CERT_PATH...")

        processar_saque_inter(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_FALHOU)


class AtualizarStatusSaqueTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="fulano@example.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PROCESSANDO,
            provedor=Saque.PROVEDOR_ASAAS, asaas_transfer_id="tr_999",
        )

    @patch("saques.services.consultar_transferencia")
    def test_atualiza_para_pago_quando_concluida(self, mock_consultar):
        mock_consultar.return_value = {"id": "tr_999", "status": "DONE"}

        atualizar_status_saque(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PAGO)
        self.assertIsNotNone(self.saque.pago_em)

    def test_sem_transfer_id_nao_faz_nada(self):
        self.saque.asaas_transfer_id = ""
        atualizar_status_saque(self.saque)
        self.assertEqual(self.saque.status, Saque.STATUS_PROCESSANDO)


class AtualizarStatusSaqueInterTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="fulano@example.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PROCESSANDO,
            provedor=Saque.PROVEDOR_INTER, inter_codigo_solicitacao="abc-999",
        )

    @patch("saques.services.consultar_pagamento_pix")
    def test_atualiza_para_pago_quando_realizado(self, mock_consultar):
        mock_consultar.return_value = {"codigoSolicitacao": "abc-999", "status": "REALIZADO"}

        atualizar_status_saque(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PAGO)
        self.assertIsNotNone(self.saque.pago_em)

    @patch("saques.services.consultar_pagamento_pix")
    def test_status_desconhecido_mantem_processando(self, mock_consultar):
        mock_consultar.return_value = {"codigoSolicitacao": "abc-999", "status": "EM_ANALISE"}

        atualizar_status_saque(self.saque)

        self.assertEqual(self.saque.status, Saque.STATUS_PROCESSANDO)

    def test_sem_codigo_solicitacao_nao_faz_nada(self):
        self.saque.inter_codigo_solicitacao = ""
        atualizar_status_saque(self.saque)
        self.assertEqual(self.saque.status, Saque.STATUS_PROCESSANDO)


@override_settings(SAQUE_VALOR_MINIMO=Decimal("20.00"))
class PedirSaqueViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705", email_verificado=True
        )
        self.client.login(username="compradora", password="senha123")

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.post(reverse("pedir_saque"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login/", resposta.url)

    def test_email_nao_verificado_bloqueia_e_nao_cria_saque(self):
        self.usuario.email_verificado = False
        self.usuario.save()
        Pedido.objects.create(
            order_id="P0", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("50.00"), valor_cashback=Decimal("50.00"),
        )
        resposta = self.client.post(reverse("pedir_saque"), follow=True)

        self.assertEqual(Saque.objects.count(), 0)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("e-mail" in m for m in mensagens))

    def test_sem_chave_pix_mostra_erro_e_nao_cria_saque(self):
        Pedido.objects.create(
            order_id="P1", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("50.00"), valor_cashback=Decimal("50.00"),
        )
        resposta = self.client.post(reverse("pedir_saque"), follow=True)

        self.assertEqual(Saque.objects.count(), 0)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("chave PIX" in m for m in mensagens))

    def test_com_saldo_e_chave_cria_saque(self):
        self.usuario.chave_pix = "fulano@example.com"
        self.usuario.tipo_chave_pix = "EMAIL"
        self.usuario.save()
        Pedido.objects.create(
            order_id="P2", conversion_id="1", usuario=self.usuario, status=Pedido.STATUS_LIBERADO,
            status_shopee_bruto="COMPLETED", valor_comissao=Decimal("50.00"), valor_cashback=Decimal("50.00"),
        )

        resposta = self.client.post(reverse("pedir_saque"), follow=True)

        self.assertEqual(Saque.objects.count(), 1)
        self.assertEqual(Saque.objects.first().valor, Decimal("50.00"))


@override_settings(ASAAS_WEBHOOK_TOKEN="token-secreto-de-teste")
class WebhookValidacaoAsaasTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.saque = Saque.objects.create(
            usuario=self.usuario, valor=Decimal("50.00"), chave_pix="fulano@example.com",
            tipo_chave_pix="EMAIL", status=Saque.STATUS_PROCESSANDO,
            provedor=Saque.PROVEDOR_ASAAS, asaas_transfer_id="tr_conhecida",
        )

    def _postar(self, payload, token="token-secreto-de-teste"):
        return self.client.post(
            reverse("webhook_validacao_asaas"),
            data=payload,
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=token,
        )

    def test_sem_token_correto_recusa_com_403(self):
        resposta = self._postar(
            {"type": "TRANSFER", "transfer": {"id": "tr_conhecida"}}, token="token-errado"
        )
        self.assertEqual(resposta.status_code, 403)

    def test_transferencia_conhecida_e_autorizada(self):
        resposta = self._postar({"type": "TRANSFER", "transfer": {"id": "tr_conhecida"}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "APPROVED"})

    def test_transferencia_desconhecida_e_recusada(self):
        resposta = self._postar({"type": "TRANSFER", "transfer": {"id": "tr_desconhecida"}})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["status"], "REFUSED")

    @override_settings(ASAAS_WEBHOOK_TOKEN="")
    def test_sem_token_configurado_recusa_com_403(self):
        resposta = self._postar({"type": "TRANSFER", "transfer": {"id": "tr_conhecida"}})
        self.assertEqual(resposta.status_code, 403)
