import base64
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.mail import EmailMessage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .brevo_email_backend import BrevoAPIEmailBackend
from .meta_capi import _hash, enviar_evento, gerar_event_id


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


class ServiceWorkerTests(TestCase):
    def test_servido_na_raiz_com_content_type_de_javascript(self):
        # Precisa estar em /sw.js (raiz), não em /static/sw.js - o escopo de um service
        # worker é limitado à pasta de onde ele é servido, e o push precisa alcançar o
        # site inteiro, não só /static/.
        resposta = self.client.get("/sw.js")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/javascript")
        self.assertIn(b'addEventListener("push"', resposta.content)

    def test_nao_fica_em_cache(self):
        resposta = self.client.get("/sw.js")
        self.assertIn("no-cache", resposta["Cache-Control"])


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


@override_settings(TAREFAS_TOKEN="segredo-de-teste")
class ExecutarResolucaoItemIdAlvoTests(TestCase):
    """Tarefa agendada própria (Fase 41/42) - separada da sincronização de pedidos
    porque seguir redirecionamento de link curto pode levar até 10s por clique."""

    def test_sem_token_retorna_forbidden(self):
        resposta = self.client.get(reverse("executar_resolucao_item_id_alvo"))
        self.assertEqual(resposta.status_code, 403)

    @patch("cashback_shopee.views.resolver_item_id_alvo_pendentes")
    def test_token_certo_resolve_os_pendentes(self, mock_resolver):
        mock_resolver.return_value = {"tentados": 5, "resolvidos": 3}

        resposta = self.client.get(reverse("executar_resolucao_item_id_alvo"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["item_id_alvo_resolvido"], {"tentados": 5, "resolvidos": 3})
        mock_resolver.assert_called_once()

    @patch("cashback_shopee.views.resolver_item_id_alvo_pendentes")
    def test_erro_fica_registrado_na_resposta_sem_quebrar(self, mock_resolver):
        mock_resolver.side_effect = Exception("falha inesperada")

        resposta = self.client.get(reverse("executar_resolucao_item_id_alvo"), {"token": "segredo-de-teste"})

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("item_id_alvo_erro", resposta.json())


@override_settings(BREVO_API_KEY="chave-de-teste")
class BrevoAPIEmailBackendTests(TestCase):
    """O Render bloqueia SMTP de saída, então o envio de e-mail usa a API HTTP do
    Brevo (ver brevo_email_backend.py) - EmailMessage.attach(...) guarda o anexo em
    message.attachments, mas o backend não lia esse atributo pra montar o payload:
    todo e-mail com imagem anexada (aprovação de story/carrossel, entre outros)
    chegava sem nenhuma imagem, mesmo o corpo do e-mail dizendo "N imagens anexadas"
    (bug real encontrado em 2026-09-04, via e-mail de aprovação do carrossel semanal)."""

    @patch("cashback_shopee.brevo_email_backend.requests.post")
    def test_sem_anexo_nao_manda_o_campo_attachment(self, mock_post):
        mock_post.return_value.raise_for_status = lambda: None
        email = EmailMessage(subject="Assunto", body="Corpo", to=["dono@exemplo.com"])

        BrevoAPIEmailBackend().send_messages([email])

        payload = mock_post.call_args.kwargs["json"]
        self.assertNotIn("attachment", payload)

    @patch("cashback_shopee.brevo_email_backend.requests.post")
    def test_anexo_vai_em_base64_no_payload(self, mock_post):
        mock_post.return_value.raise_for_status = lambda: None
        email = EmailMessage(subject="Assunto", body="Corpo", to=["dono@exemplo.com"])
        email.attach("cash-b-1.jpg", b"bytes-de-uma-jpeg-qualquer", "image/jpeg")
        email.attach("cash-b-2.jpg", b"bytes-de-outra-jpeg", "image/jpeg")

        BrevoAPIEmailBackend().send_messages([email])

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(len(payload["attachment"]), 2)
        self.assertEqual(payload["attachment"][0]["name"], "cash-b-1.jpg")
        self.assertEqual(
            base64.b64decode(payload["attachment"][0]["content"]), b"bytes-de-uma-jpeg-qualquer"
        )
        self.assertEqual(payload["attachment"][1]["name"], "cash-b-2.jpg")

    @patch("cashback_shopee.brevo_email_backend.requests.post")
    def test_anexo_de_texto_tambem_funciona(self, mock_post):
        """message.attachments aceita conteúdo str (não só bytes) - EmailMessage.attach
        permite anexar texto puro. A API do Brevo só aceita base64, então precisa
        codificar pra bytes primeiro."""
        mock_post.return_value.raise_for_status = lambda: None
        email = EmailMessage(subject="Assunto", body="Corpo", to=["dono@exemplo.com"])
        email.attach("notas.txt", "conteúdo em texto", "text/plain")

        BrevoAPIEmailBackend().send_messages([email])

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(
            base64.b64decode(payload["attachment"][0]["content"]).decode("utf-8"), "conteúdo em texto"
        )


class MetaCapiTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, usuario=None, **cookies):
        request = self.factory.get("/qualquer-pagina/")
        request.COOKIES = cookies
        request.user = usuario or AnonymousUser()
        return request

    def test_gerar_event_id_produz_valores_diferentes_a_cada_chamada(self):
        self.assertNotEqual(gerar_event_id(), gerar_event_id())

    def test_hash_e_sha256_minusculo_sem_espaco_nas_pontas(self):
        self.assertEqual(_hash("  ANA@Example.com  "), _hash("ana@example.com"))
        self.assertEqual(len(_hash("ana@example.com")), 64)  # tamanho de um sha256 em hexadecimal

    @override_settings(META_PIXEL_ID="", META_CAPI_ACCESS_TOKEN="")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_sem_credenciais_configuradas_nao_manda_nada(self, mock_post):
        enviar_evento("TesteEvento", self._request(), gerar_event_id())

        mock_post.assert_not_called()

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_manda_o_evento_com_credenciais_configuradas(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {"events_received": 1})

        enviar_evento("TesteEvento", self._request(), "event-abc123", {"foo": "bar"})

        mock_post.assert_called_once()
        url_chamada = mock_post.call_args[0][0]
        payload = mock_post.call_args.kwargs["json"]
        evento = payload["data"][0]
        self.assertIn("123456/events", url_chamada)
        self.assertEqual(evento["event_name"], "TesteEvento")
        self.assertEqual(evento["event_id"], "event-abc123")
        self.assertEqual(evento["action_source"], "website")
        self.assertEqual(evento["custom_data"], {"foo": "bar"})

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_inclui_fbp_e_fbc_quando_presentes_nos_cookies(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {})

        enviar_evento("TesteEvento", self._request(_fbp="fb.1.111.222", _fbc="fb.1.111.333"), gerar_event_id())

        user_data = mock_post.call_args.kwargs["json"]["data"][0]["user_data"]
        self.assertEqual(user_data["fbp"], "fb.1.111.222")
        self.assertEqual(user_data["fbc"], "fb.1.111.333")

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_sem_fbp_fbc_nos_cookies_nao_inclui_esses_campos(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {})

        enviar_evento("TesteEvento", self._request(), gerar_event_id())

        user_data = mock_post.call_args.kwargs["json"]["data"][0]["user_data"]
        self.assertNotIn("fbp", user_data)
        self.assertNotIn("fbc", user_data)

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_email_do_usuario_autenticado_vai_hasheado_nunca_em_texto_puro(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {})
        usuario = get_user_model().objects.create_user(
            username="ana", password="senha123", cpf="39053344705", email="ANA@Example.com",
        )

        enviar_evento("TesteEvento", self._request(usuario=usuario), gerar_event_id())

        user_data = mock_post.call_args.kwargs["json"]["data"][0]["user_data"]
        self.assertEqual(user_data["em"], [_hash("ana@example.com")])
        self.assertNotIn("ANA@Example.com", str(user_data))

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_usuario_anonimo_nao_manda_campo_de_email(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {})

        enviar_evento("TesteEvento", self._request(), gerar_event_id())

        user_data = mock_post.call_args.kwargs["json"]["data"][0]["user_data"]
        self.assertNotIn("em", user_data)

    @override_settings(META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste")
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_falha_de_rede_nao_propaga_erro(self, mock_post):
        """Rastreamento de anúncio não pode derrubar uma ação real do usuário
        (cadastro, gerar link) só porque a Meta está fora do ar ou lenta."""
        mock_post.side_effect = requests.RequestException("timeout")

        enviar_evento("TesteEvento", self._request(), gerar_event_id())  # não deve levantar

    @override_settings(
        META_PIXEL_ID="123456", META_CAPI_ACCESS_TOKEN="token-teste", META_CAPI_TEST_EVENT_CODE="TEST12345",
    )
    @patch("cashback_shopee.meta_capi.requests.post")
    def test_inclui_test_event_code_quando_configurado(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {})

        enviar_evento("TesteEvento", self._request(), gerar_event_id())

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["test_event_code"], "TEST12345")
