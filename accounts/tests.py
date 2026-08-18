import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from pedidos.models import Pedido
from saques.models import Saque

from .models import ConfiguracaoIndicacao, Indicacao, PushSubscription, User
from .push import enviar_push


class CodigoIndicacaoTests(TestCase):
    def test_gera_codigo_ao_salvar(self):
        usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.assertTrue(usuario.codigo_indicacao)
        self.assertEqual(len(usuario.codigo_indicacao), 8)

    def test_codigos_gerados_sao_unicos(self):
        usuario1 = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        usuario2 = User.objects.create_user(username="bia", password="senha123", cpf="14783246947")
        self.assertNotEqual(usuario1.codigo_indicacao, usuario2.codigo_indicacao)

    def test_nao_sobrescreve_codigo_existente_ao_salvar_de_novo(self):
        usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        codigo_original = usuario.codigo_indicacao
        usuario.first_name = "Ana"
        usuario.save()
        self.assertEqual(usuario.codigo_indicacao, codigo_original)


class RegistrarComIndicacaoTests(TestCase):
    def setUp(self):
        self.indicador = User.objects.create_user(username="indicador", password="senha123", cpf="39053344705")

    def _dados_cadastro(self, **extra):
        dados = {
            "username": "novaconta",
            "email": "nova@example.com",
            "cpf": "14783246947",
            "password1": "senha-forte-123",
            "password2": "senha-forte-123",
        }
        dados.update(extra)
        return dados

    def test_cadastro_com_codigo_valido_cria_indicacao(self):
        self.client.post(
            reverse("registrar"), self._dados_cadastro(ref=self.indicador.codigo_indicacao)
        )
        novo_usuario = User.objects.get(username="novaconta")
        indicacao = Indicacao.objects.get(indicado=novo_usuario)
        self.assertEqual(indicacao.indicador, self.indicador)
        self.assertIsNone(indicacao.pedido_bonus_indicado)
        self.assertIsNone(indicacao.pedido_bonus_indicador)

    def test_cadastro_com_codigo_desconhecido_nao_cria_indicacao(self):
        self.client.post(reverse("registrar"), self._dados_cadastro(ref="NAOEXISTE"))
        novo_usuario = User.objects.get(username="novaconta")
        self.assertFalse(Indicacao.objects.filter(indicado=novo_usuario).exists())

    def test_cadastro_sem_codigo_nao_cria_indicacao(self):
        self.client.post(reverse("registrar"), self._dados_cadastro())
        novo_usuario = User.objects.get(username="novaconta")
        self.assertFalse(Indicacao.objects.filter(indicado=novo_usuario).exists())

    def test_pagina_de_cadastro_preenche_campo_oculto_com_ref_da_url(self):
        resposta = self.client.get(reverse("registrar"), {"ref": self.indicador.codigo_indicacao})
        self.assertContains(resposta, f'name="ref" value="{self.indicador.codigo_indicacao}"')

    def test_campanha_pausada_nao_cria_indicacao_mesmo_com_codigo_valido(self):
        ConfiguracaoIndicacao.objects.update_or_create(pk=1, defaults={"ativa": False})

        self.client.post(reverse("registrar"), self._dados_cadastro(ref=self.indicador.codigo_indicacao))

        novo_usuario = User.objects.get(username="novaconta")
        self.assertFalse(Indicacao.objects.filter(indicado=novo_usuario).exists())


class DashboardIndicacaoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.client.force_login(self.usuario)

    def test_contexto_traz_link_de_indicacao_com_o_codigo_do_usuario(self):
        resposta = self.client.get(reverse("dashboard"))
        self.assertIn(self.usuario.codigo_indicacao, resposta.context["link_indicacao"])

    def test_lista_indicacoes_feitas_pelo_usuario(self):
        indicado = User.objects.create_user(username="bia", password="senha123", cpf="14783246947")
        Indicacao.objects.create(indicador=self.usuario, indicado=indicado)

        resposta = self.client.get(reverse("dashboard"))

        self.assertEqual(len(resposta.context["indicacoes"]), 1)
        self.assertEqual(resposta.context["indicacoes_concluidas"], 0)

    def test_secao_indique_e_ganhe_aparece_por_padrao(self):
        resposta = self.client.get(reverse("dashboard"))
        self.assertTrue(resposta.context["indicacao_ativa"])
        self.assertContains(resposta, "Indique e ganhe")

    def test_secao_indique_e_ganhe_some_quando_campanha_pausada(self):
        ConfiguracaoIndicacao.objects.update_or_create(pk=1, defaults={"ativa": False})

        resposta = self.client.get(reverse("dashboard"))

        self.assertFalse(resposta.context["indicacao_ativa"])
        self.assertNotContains(resposta, "Indique e ganhe")
        self.assertNotContains(resposta, self.usuario.codigo_indicacao)


class ConfiguracaoIndicacaoTests(TestCase):
    def test_esta_ativa_por_padrao(self):
        self.assertTrue(ConfiguracaoIndicacao.esta_ativa())

    def test_esta_ativa_reflete_a_linha_unica_pausada_pelo_admin(self):
        ConfiguracaoIndicacao.objects.update_or_create(pk=1, defaults={"ativa": False})
        self.assertFalse(ConfiguracaoIndicacao.esta_ativa())

    def test_esta_ativa_sem_nenhuma_linha_cai_pro_padrao_ligado(self):
        ConfiguracaoIndicacao.objects.all().delete()
        self.assertTrue(ConfiguracaoIndicacao.esta_ativa())


class DashboardSaldoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.client.force_login(self.usuario)

    def test_liberado_mostra_so_o_que_ainda_da_pra_sacar(self):
        Pedido.objects.create(
            order_id="P1", conversion_id="1", usuario=self.usuario,
            status=Pedido.STATUS_LIBERADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("40.00"), valor_cashback=Decimal("40.00"),
        )
        Saque.objects.create(
            usuario=self.usuario, valor=Decimal("20.00"), chave_pix="x", tipo_chave_pix="EVP",
            status=Saque.STATUS_PAGO,
        )

        resposta = self.client.get(reverse("dashboard"))

        self.assertEqual(resposta.context["saldo_liberado"], Decimal("20.00"))
        self.assertEqual(resposta.context["saldo_sacado"], Decimal("20.00"))

    def test_sem_saque_o_ja_sacado_fica_zerado(self):
        Pedido.objects.create(
            order_id="P2", conversion_id="1", usuario=self.usuario,
            status=Pedido.STATUS_LIBERADO, status_shopee_bruto="COMPLETED",
            valor_comissao=Decimal("15.00"), valor_cashback=Decimal("15.00"),
        )

        resposta = self.client.get(reverse("dashboard"))

        self.assertEqual(resposta.context["saldo_liberado"], Decimal("15.00"))
        self.assertEqual(resposta.context["saldo_sacado"], Decimal("0"))


class LoginForcaBrutaTests(TestCase):
    """django-axes: protege /login/ contra tentativas repetidas de senha (ver
    cashback_shopee/settings.py, AXES_FAILURE_LIMIT=5)."""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username="protegida", password="senha-correta-123", cpf="91234567873"
        )

    def _tentar_login(self, senha):
        return self.client.post(reverse("login"), {"username": "protegida", "password": senha})

    def test_apos_o_limite_de_tentativas_bloqueia_mesmo_com_senha_certa(self):
        for _ in range(5):
            self._tentar_login("senha-errada")

        resposta = self._tentar_login("senha-correta-123")

        self.assertNotEqual(resposta.status_code, 302)
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)

    def test_antes_do_limite_login_correto_ainda_funciona(self):
        for _ in range(4):
            self._tentar_login("senha-errada")

        resposta = self._tentar_login("senha-correta-123")

        self.assertRedirects(resposta, reverse("dashboard"))

    def test_bloqueio_e_por_usuario_mais_ip_nao_afeta_outra_conta(self):
        User.objects.create_user(username="outra", password="outra-senha-123", cpf="52914637837")
        for _ in range(5):
            self._tentar_login("senha-errada")

        resposta = self.client.post(reverse("login"), {"username": "outra", "password": "outra-senha-123"})

        self.assertRedirects(resposta, reverse("dashboard"))


class InscreverPushTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.client.force_login(self.usuario)

    def _inscricao(self, endpoint="https://push.exemplo.com/abc"):
        return {"endpoint": endpoint, "keys": {"p256dh": "chave-p256dh", "auth": "chave-auth"}}

    def test_cria_inscricao_pro_usuario_logado(self):
        resposta = self.client.post(
            reverse("inscrever_push"), data=json.dumps(self._inscricao()), content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 200)
        inscricao = PushSubscription.objects.get(usuario=self.usuario)
        self.assertEqual(inscricao.endpoint, "https://push.exemplo.com/abc")

    def test_reenviar_a_mesma_inscricao_nao_duplica(self):
        for _ in range(2):
            self.client.post(
                reverse("inscrever_push"), data=json.dumps(self._inscricao()), content_type="application/json"
            )
        self.assertEqual(PushSubscription.objects.filter(usuario=self.usuario).count(), 1)

    def test_dados_invalidos_retorna_400(self):
        resposta = self.client.post(
            reverse("inscrever_push"), data=json.dumps({"endpoint": "sem-keys"}), content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 400)

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.post(
            reverse("inscrever_push"), data=json.dumps(self._inscricao()), content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 302)

    def test_desinscrever_remove_a_inscricao(self):
        self.client.post(
            reverse("inscrever_push"), data=json.dumps(self._inscricao()), content_type="application/json"
        )
        resposta = self.client.post(
            reverse("desinscrever_push"),
            data=json.dumps({"endpoint": "https://push.exemplo.com/abc"}),
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(usuario=self.usuario).exists())


@override_settings(VAPID_PRIVATE_KEY="chave-privada-de-teste", VAPID_CLAIMS_EMAIL="contato@cash-b.com")
class EnviarPushTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.inscricao = PushSubscription.objects.create(
            usuario=self.usuario,
            endpoint="https://push.exemplo.com/abc",
            chave_p256dh="chave-p256dh",
            chave_auth="chave-auth",
        )

    @patch("accounts.push.webpush")
    def test_manda_pra_cada_inscricao_do_usuario(self, mock_webpush):
        enviar_push(self.usuario, "Título", "Corpo", url="/dashboard/")

        mock_webpush.assert_called_once()
        kwargs = mock_webpush.call_args.kwargs
        self.assertEqual(kwargs["subscription_info"]["endpoint"], self.inscricao.endpoint)
        self.assertEqual(kwargs["vapid_private_key"], "chave-privada-de-teste")
        dados = json.loads(kwargs["data"])
        self.assertEqual(dados, {"titulo": "Título", "corpo": "Corpo", "url": "/dashboard/"})

    @patch("accounts.push.webpush")
    def test_sem_vapid_configurado_nao_manda_nada(self, mock_webpush):
        with override_settings(VAPID_PRIVATE_KEY=""):
            enviar_push(self.usuario, "Título", "Corpo")
        mock_webpush.assert_not_called()

    @patch("accounts.push.webpush")
    def test_sem_usuario_nao_falha(self, mock_webpush):
        enviar_push(None, "Título", "Corpo")
        mock_webpush.assert_not_called()

    @patch("accounts.push.webpush")
    def test_inscricao_expirada_e_apagada(self, mock_webpush):
        from pywebpush import WebPushException

        resposta_410 = Mock(status_code=410)
        mock_webpush.side_effect = WebPushException("gone", response=resposta_410)

        enviar_push(self.usuario, "Título", "Corpo")

        self.assertFalse(PushSubscription.objects.filter(pk=self.inscricao.pk).exists())

    @patch("accounts.push.webpush")
    def test_erro_diferente_de_410_mantem_a_inscricao(self, mock_webpush):
        from pywebpush import WebPushException

        resposta_500 = Mock(status_code=500)
        mock_webpush.side_effect = WebPushException("erro no servidor", response=resposta_500)

        enviar_push(self.usuario, "Título", "Corpo")

        self.assertTrue(PushSubscription.objects.filter(pk=self.inscricao.pk).exists())
