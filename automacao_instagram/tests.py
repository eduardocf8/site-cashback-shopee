import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from instagram_bot.models import RegistroPublicacao

from . import webhook
from .models import AutomacaoStory, ContaInstagramConectada, RespostaStoryProcessada

APP_SECRET_TESTE = "segredo-do-app-de-teste"


def _assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET_TESTE.encode(), corpo, hashlib.sha256).hexdigest()


@override_settings(INSTAGRAM_APP_SECRET=APP_SECRET_TESTE)
class VerificarAssinaturaDoWebhookTests(TestCase):
    """Mesma proteção que o instagram_bot tinha (essa automação assumiu a
    responsabilidade de receber o webhook de mensagens - ver
    marketing/instagram/README.md)."""

    def test_assinatura_valida_passa(self):
        corpo = b'{"entry": []}'
        self.assertTrue(webhook.verificar_assinatura(corpo, _assinar(corpo)))

    def test_assinatura_invalida_nao_passa(self):
        self.assertFalse(webhook.verificar_assinatura(b'{"entry": []}', "sha256=errada"))

    def test_sem_cabecalho_nao_passa(self):
        self.assertFalse(webhook.verificar_assinatura(b'{"entry": []}', None))


@override_settings(INSTAGRAM_APP_SECRET=APP_SECRET_TESTE)
class ProcessamentoDeRespostaAStoryTests(TestCase):
    """Fim a fim: alguém responde um story com AutomacaoStory ativa -> manda a DM
    configurada (link do produto detectado ou mensagem personalizada). Story sem
    automação configurada é ignorado silenciosamente, igual comentário sem
    palavra-chave em AutomacaoComentario."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dono", password="senha123", cpf="39053344705", is_staff=True
        )
        self.conta = ContaInstagramConectada.objects.create(
            usuario=self.usuario, nome_exibicao="@usecashb",
            instagram_business_account_id="1", access_token="token-conta",
        )
        self.registro = RegistroPublicacao.objects.create(
            data="2026-09-02",
            tipo=RegistroPublicacao.TIPO_STORY,
            conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
            status=RegistroPublicacao.STATUS_PUBLICADO,
            sucesso=True,
            instagram_media_id="17800000000000001",
            oferta_item_id=555,
            link_produto_original="https://shopee.com.br/produto-i.1.555",
        )

    def _postar(self, payload: dict):
        corpo = json.dumps(payload).encode()
        return self.client.post(
            reverse("automacao_webhook_instagram"), data=corpo, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_assinar(corpo),
        )

    def _payload_resposta_a_story(self, media_id: str, texto="Quero!", sender_id="99887766", is_echo=False):
        mensagem = {"text": texto, "reply_to": {"story": {"id": media_id}}}
        if is_echo:
            mensagem["is_echo"] = True
        return {"entry": [{"id": "1", "messaging": [{"sender": {"id": sender_id}, "message": mensagem}]}]}

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_story_sem_automacao_e_ignorado(self, mock_enviar):
        resposta = self._postar(self._payload_resposta_a_story("17800000000000001"))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_not_called()
        self.assertEqual(RespostaStoryProcessada.objects.count(), 0)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_modo_link_produto_manda_o_link_certo(self, mock_enviar):
        mock_enviar.return_value = "mid123"
        automacao = AutomacaoStory.objects.create(
            conta=self.conta, nome="Fone bluetooth", instagram_story_media_id="17800000000000001",
            modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO,
        )

        resposta = self._postar(self._payload_resposta_a_story("17800000000000001"))

        self.assertEqual(resposta.status_code, 200)
        registro_resposta = RespostaStoryProcessada.objects.get()
        self.assertEqual(registro_resposta.automacao, automacao)
        self.assertTrue(registro_resposta.dm_enviada)

        mock_enviar.assert_called_once()
        conta_id, destinatario, texto_enviado, token = mock_enviar.call_args[0]
        self.assertEqual(conta_id, "1")
        self.assertEqual(destinatario, "99887766")
        self.assertEqual(token, "token-conta")
        self.assertIn(f"/instagram/story/{self.registro.pk}/ir/", texto_enviado)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_modo_personalizada_manda_o_texto_configurado(self, mock_enviar):
        mock_enviar.return_value = "mid123"
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Dica", instagram_story_media_id="story-sem-link",
            modo_resposta=AutomacaoStory.MODO_PERSONALIZADA, texto_personalizado="Olha nosso site: cash-b.com",
        )

        resposta = self._postar(self._payload_resposta_a_story("story-sem-link"))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_called_once()
        _conta_id, _destinatario, texto_enviado, _token = mock_enviar.call_args[0]
        self.assertEqual(texto_enviado, "Olha nosso site: cash-b.com")

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_modo_link_produto_sem_registro_correspondente_nao_manda_nada(self, mock_enviar):
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Sem link", instagram_story_media_id="story-orfao",
            modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO,
        )

        resposta = self._postar(self._payload_resposta_a_story("story-orfao"))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_not_called()
        self.assertEqual(RespostaStoryProcessada.objects.count(), 0)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_automacao_pausada_e_ignorada(self, mock_enviar):
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Pausada", instagram_story_media_id="17800000000000001",
            modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO, ativa=False,
        )

        resposta = self._postar(self._payload_resposta_a_story("17800000000000001"))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_not_called()

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_eco_da_propria_conta_e_ignorado(self, mock_enviar):
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Fone", instagram_story_media_id="17800000000000001",
            modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO,
        )

        resposta = self._postar(self._payload_resposta_a_story("17800000000000001", is_echo=True))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_not_called()

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_mesma_pessoa_respondendo_de_novo_nao_recebe_outra_dm(self, mock_enviar):
        mock_enviar.return_value = "mid123"
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Fone", instagram_story_media_id="17800000000000001",
            modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO,
        )
        self._postar(self._payload_resposta_a_story("17800000000000001", texto="Quero!"))

        resposta = self._postar(self._payload_resposta_a_story("17800000000000001", texto="obrigada"))

        self.assertEqual(resposta.status_code, 200)
        mock_enviar.assert_called_once()
        self.assertEqual(RespostaStoryProcessada.objects.count(), 1)

    def test_assinatura_invalida_e_recusada(self):
        payload = self._payload_resposta_a_story("17800000000000001")
        corpo = json.dumps(payload).encode()

        resposta = self.client.post(
            reverse("automacao_webhook_instagram"), data=corpo, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalida",
        )

        self.assertEqual(resposta.status_code, 403)


@override_settings(INSTAGRAM_APP_SECRET=APP_SECRET_TESTE, INSTAGRAM_WEBHOOK_VERIFY_TOKEN="token-de-verificacao")
class HandshakeDoWebhookTests(TestCase):
    def test_challenge_correto_devolve_o_challenge(self):
        resposta = self.client.get(
            reverse("automacao_webhook_instagram"),
            {"hub.mode": "subscribe", "hub.verify_token": "token-de-verificacao", "hub.challenge": "abc123"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"abc123")

    def test_token_errado_e_recusado(self):
        resposta = self.client.get(
            reverse("automacao_webhook_instagram"),
            {"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "abc123"},
        )
        self.assertEqual(resposta.status_code, 403)


class FluxoDeCriacaoDeAutomacaoDeStoryTests(TestCase):
    """Nova automação: 1º escolhe o tipo (post ou story), depois a conta, depois o
    item específico - stories só listam stories, posts só listam posts."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dono", password="senha123", cpf="39053344705", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.conta = ContaInstagramConectada.objects.create(
            usuario=self.usuario, nome_exibicao="@usecashb",
            instagram_business_account_id="1", access_token="token-conta",
        )
        self.registro = RegistroPublicacao.objects.create(
            data="2026-09-02",
            tipo=RegistroPublicacao.TIPO_STORY,
            conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
            status=RegistroPublicacao.STATUS_PUBLICADO,
            sucesso=True,
            instagram_media_id="story-com-link",
            oferta_item_id=555,
            link_produto_original="https://shopee.com.br/produto-i.1.555",
        )

    def test_pagina_inicial_pede_pra_escolher_o_tipo(self):
        resposta = self.client.get(reverse("automacao_nova"))
        self.assertContains(resposta, "Comentário em post")
        self.assertContains(resposta, "Resposta a story")

    @patch("automacao_instagram.instagram_api.listar_stories_recentes")
    def test_tipo_story_lista_so_stories_e_marca_o_que_tem_link(self, mock_listar):
        mock_listar.return_value = [
            {"id": "story-com-link", "timestamp": "2026-09-02T10:00:00+0000", "permalink": ""},
            {"id": "story-sem-link", "timestamp": "2026-09-02T11:00:00+0000", "permalink": ""},
        ]

        resposta = self.client.get(reverse("automacao_nova"), {"tipo": "story", "conta": self.conta.pk})

        self.assertContains(resposta, "link do produto detectado")
        mock_listar.assert_called_once()

    @patch("automacao_instagram.instagram_api.listar_stories_recentes")
    def test_criar_automacao_modo_link_produto_com_story_elegivel(self, mock_listar):
        mock_listar.return_value = [{"id": "story-com-link", "timestamp": "", "permalink": "https://instagram.com/s/1"}]

        resposta = self.client.post(reverse("automacao_nova"), {
            "tipo": "story", "conta": self.conta.pk, "story_selecionado": "story-com-link",
            "nome": "Fone bluetooth", "modo_resposta": AutomacaoStory.MODO_LINK_PRODUTO, "ativa": "on",
        })

        self.assertRedirects(resposta, reverse("automacao_lista"))
        automacao = AutomacaoStory.objects.get()
        self.assertEqual(automacao.instagram_story_media_id, "story-com-link")
        self.assertEqual(automacao.modo_resposta, AutomacaoStory.MODO_LINK_PRODUTO)
        self.assertEqual(automacao.story_permalink, "https://instagram.com/s/1")

    @patch("automacao_instagram.instagram_api.listar_stories_recentes")
    def test_nao_deixa_escolher_link_produto_pra_story_sem_link_detectado(self, mock_listar):
        mock_listar.return_value = [{"id": "story-sem-link", "timestamp": "", "permalink": ""}]

        resposta = self.client.post(reverse("automacao_nova"), {
            "tipo": "story", "conta": self.conta.pk, "story_selecionado": "story-sem-link",
            "nome": "Sem link", "modo_resposta": AutomacaoStory.MODO_LINK_PRODUTO, "ativa": "on",
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(AutomacaoStory.objects.count(), 0)
        self.assertContains(resposta, "não tem um link de produto detectado")

    @patch("automacao_instagram.instagram_api.listar_stories_recentes")
    def test_criar_automacao_modo_personalizada(self, mock_listar):
        mock_listar.return_value = [{"id": "story-sem-link", "timestamp": "", "permalink": ""}]

        resposta = self.client.post(reverse("automacao_nova"), {
            "tipo": "story", "conta": self.conta.pk, "story_selecionado": "story-sem-link",
            "nome": "Dica", "modo_resposta": AutomacaoStory.MODO_PERSONALIZADA,
            "texto_personalizado": "Vê no site!", "ativa": "on",
        })

        self.assertRedirects(resposta, reverse("automacao_lista"))
        automacao = AutomacaoStory.objects.get()
        self.assertEqual(automacao.texto_personalizado, "Vê no site!")


class AutomacaoListaEAlternarAtivaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dono", password="senha123", cpf="39053344705", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.conta = ContaInstagramConectada.objects.create(
            usuario=self.usuario, nome_exibicao="@usecashb",
            instagram_business_account_id="1", access_token="token-conta",
        )
        self.automacao = AutomacaoStory.objects.create(
            conta=self.conta, nome="Fone", instagram_story_media_id="s1",
            modo_resposta=AutomacaoStory.MODO_PERSONALIZADA, texto_personalizado="oi",
        )

    def test_lista_mostra_automacao_de_story(self):
        resposta = self.client.get(reverse("automacao_lista"))
        self.assertContains(resposta, "Fone")

    def test_alternar_ativa_pausa_e_reativa(self):
        self.client.post(reverse("automacao_story_alternar_ativa", args=[self.automacao.pk]))
        self.automacao.refresh_from_db()
        self.assertFalse(self.automacao.ativa)

        self.client.post(reverse("automacao_story_alternar_ativa", args=[self.automacao.pk]))
        self.automacao.refresh_from_db()
        self.assertTrue(self.automacao.ativa)
