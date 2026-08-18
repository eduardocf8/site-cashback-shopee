from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse


class HealthcheckTests(TestCase):
    def test_banco_acessivel_retorna_ok(self):
        resposta = self.client.get(reverse("healthcheck"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content.decode(), "ok")

    @patch("cashback_shopee.views.connection")
    def test_banco_inacessivel_retorna_503(self, mock_connection):
        mock_connection.cursor.side_effect = Exception("sem conexão")
        resposta = self.client.get(reverse("healthcheck"))
        self.assertEqual(resposta.status_code, 503)


@override_settings(TAREFAS_TOKEN="segredo-de-teste")
class ExecutarTarefasAgendadasTests(TestCase):
    def test_sem_token_retorna_forbidden(self):
        resposta = self.client.get(reverse("executar_tarefas_agendadas"))
        self.assertEqual(resposta.status_code, 403)

    def test_token_errado_retorna_forbidden(self):
        resposta = self.client.get(reverse("executar_tarefas_agendadas"), {"token": "errado"})
        self.assertEqual(resposta.status_code, 403)

    @override_settings(TAREFAS_TOKEN="")
    def test_sem_token_configurado_sempre_bloqueia(self):
        resposta = self.client.get(reverse("executar_tarefas_agendadas"), {"token": ""})
        self.assertEqual(resposta.status_code, 403)

    @patch("cashback_shopee.views.verificar_saques_pendentes")
    @patch("cashback_shopee.views.liberar_saldo")
    @patch("cashback_shopee.views.sincronizar")
    def test_token_certo_executa_as_tres_tarefas(self, mock_sincronizar, mock_liberar, mock_verificar):
        mock_sincronizar.return_value = {"novos": 1, "atualizados": 2, "nao_identificados": 0}
        mock_liberar.return_value = 3
        mock_verificar.return_value = {"verificados": 1, "atualizados": 1}

        resposta = self.client.get(reverse("executar_tarefas_agendadas"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["sincronizacao"]["novos"], 1)
        self.assertEqual(dados["saldos_liberados"], 3)
        self.assertEqual(dados["saques_verificados"]["atualizados"], 1)
        self.assertNotIn("instagram", dados)
        mock_sincronizar.assert_called_once()
        mock_liberar.assert_called_once()
        mock_verificar.assert_called_once()

    @patch("cashback_shopee.views.verificar_saques_pendentes")
    @patch("cashback_shopee.views.liberar_saldo")
    @patch("cashback_shopee.views.sincronizar")
    def test_erro_na_shopee_nao_impede_liberar_saldo_e_verificar_saques(
        self, mock_sincronizar, mock_liberar, mock_verificar
    ):
        from links.shopee_client import ShopeeConfigError

        mock_sincronizar.side_effect = ShopeeConfigError("Configure as credenciais.")
        mock_liberar.return_value = 0
        mock_verificar.return_value = {"verificados": 0, "atualizados": 0}

        resposta = self.client.get(reverse("executar_tarefas_agendadas"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertIn("sincronizacao_erro", dados)
        mock_liberar.assert_called_once()
        mock_verificar.assert_called_once()


@override_settings(TAREFAS_TOKEN="segredo-de-teste")
class ExecutarPublicacoesInstagramTests(TestCase):
    def test_sem_token_retorna_forbidden(self):
        resposta = self.client.get(reverse("executar_publicacoes_instagram"))
        self.assertEqual(resposta.status_code, 403)

    @patch("cashback_shopee.views.verificar_validade_token")
    @patch("cashback_shopee.views.executar_publicacoes_do_dia")
    def test_token_certo_publica_e_confere_o_token(self, mock_publicacoes, mock_token):
        mock_publicacoes.return_value = {"publicados": 1}
        mock_token.return_value = {"valido": True}

        resposta = self.client.get(reverse("executar_publicacoes_instagram"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["instagram"], {"publicados": 1})
        self.assertEqual(dados["token_instagram"], {"valido": True})
        mock_publicacoes.assert_called_once()
        mock_token.assert_called_once()

    @patch("cashback_shopee.views.verificar_validade_token")
    @patch("cashback_shopee.views.executar_publicacoes_do_dia")
    def test_erro_ao_publicar_nao_impede_conferir_o_token(self, mock_publicacoes, mock_token):
        mock_publicacoes.side_effect = Exception("falha ao publicar")
        mock_token.return_value = {"valido": True}

        resposta = self.client.get(reverse("executar_publicacoes_instagram"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertIn("instagram_erro", dados)
        self.assertEqual(dados["token_instagram"], {"valido": True})
        mock_token.assert_called_once()
