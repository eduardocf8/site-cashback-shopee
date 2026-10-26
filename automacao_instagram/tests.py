import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from instagram_bot.models import RegistroPublicacao

from . import webhook
from .models import AutomacaoStory, ContaInstagramConectada, PadraoRespostaStory, RespostaStoryProcessada

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
        # O texto vem do padrão e o link vai no botão.
        self.assertEqual(texto_enviado, PadraoRespostaStory.TEXTO_PADRAO)
        titulo, url = mock_enviar.call_args.kwargs["botao"]
        self.assertEqual(titulo, PadraoRespostaStory.TEXTO_BOTAO_PADRAO)
        self.assertIn(f"/instagram/story/{self.registro.pk}/ir/", url)

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
            oferta_nome="Fone bluetooth",
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

        self.assertContains(resposta, "Fone bluetooth")
        self.assertContains(resposta, "sem link de produto associado")
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


def _registro_de_oferta(**campos) -> RegistroPublicacao:
    dados = dict(
        data="2026-10-26", tipo=RegistroPublicacao.TIPO_STORY,
        conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA, status=RegistroPublicacao.STATUS_PUBLICADO,
        sucesso=True, modo_simulacao=False, instagram_media_id="17900000000000001", oferta_item_id=777,
        oferta_nome="Fone Bluetooth TWS", link_produto_original="https://shopee.com.br/fone-i.1.777",
    )
    dados.update(campos)
    return RegistroPublicacao.objects.create(**dados)


@override_settings(INSTAGRAM_APP_SECRET=APP_SECRET_TESTE, INSTAGRAM_BUSINESS_ACCOUNT_ID="1")
class StoriesDeOfertaDoBotTests(TestCase):
    """Story de oferta postado pelo bot ganha a automação sozinho e a DM usa o padrão (texto + botão)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dono", password="senha123", cpf="39053344705", is_staff=True
        )
        self.conta = ContaInstagramConectada.objects.create(
            usuario=self.usuario, nome_exibicao="@usecashb",
            instagram_business_account_id="1", access_token="token-conta",
        )

    def _responder(self, media_id="17900000000000001", sender_id="99887766"):
        payload = {"entry": [{"id": "1", "messaging": [{
            "sender": {"id": sender_id}, "message": {"text": "Quero!", "reply_to": {"story": {"id": media_id}}},
        }]}]}
        corpo = json.dumps(payload).encode()
        return self.client.post(
            reverse("automacao_webhook_instagram"), data=corpo, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_assinar(corpo),
        )

    def test_story_de_oferta_publicado_ganha_a_automacao_sozinho(self):
        registro = _registro_de_oferta()

        automacao = AutomacaoStory.objects.get()
        self.assertTrue(automacao.automatica)
        self.assertTrue(automacao.ativa)
        self.assertEqual(automacao.conta, self.conta)
        self.assertEqual(automacao.instagram_story_media_id, "17900000000000001")
        self.assertEqual(automacao.modo_resposta, AutomacaoStory.MODO_LINK_PRODUTO)
        self.assertIn("Fone Bluetooth TWS", automacao.nome)

        registro.save()  # gravar de novo não duplica
        self.assertEqual(AutomacaoStory.objects.count(), 1)

    def test_story_aprovado_depois_por_email_ganha_a_automacao_na_aprovacao(self):
        registro = _registro_de_oferta(
            status=RegistroPublicacao.STATUS_PENDENTE_APROVACAO, sucesso=False, instagram_media_id="",
        )
        self.assertFalse(AutomacaoStory.objects.exists())

        registro.status, registro.sucesso = RegistroPublicacao.STATUS_PUBLICADO, True
        registro.instagram_media_id = "17900000000000009"
        registro.save(update_fields=["status", "sucesso", "instagram_media_id"])

        self.assertEqual(AutomacaoStory.objects.get().instagram_story_media_id, "17900000000000009")

    def test_link_gravado_depois_do_id_tambem_cria(self):
        # Publicação direta: o ID do story é gravado antes do link do produto.
        registro = _registro_de_oferta(link_produto_original="")
        self.assertFalse(AutomacaoStory.objects.exists())

        registro.link_produto_original = "https://shopee.com.br/fone-i.1.777"
        registro.save(update_fields=["link_produto_original"])
        self.assertTrue(AutomacaoStory.objects.filter(automatica=True).exists())

    def test_story_simulado_ou_sem_link_nao_ganha_automacao(self):
        _registro_de_oferta(modo_simulacao=True)
        _registro_de_oferta(
            instagram_media_id="17900000000000002", link_produto_original="",
            conteudo_tipo=RegistroPublicacao.CONTEUDO_DICA,
        )
        self.assertFalse(AutomacaoStory.objects.exists())

    @override_settings(INSTAGRAM_BUSINESS_ACCOUNT_ID="outra-conta")
    def test_sem_a_conta_do_bot_conectada_nao_cria_nem_quebra_a_publicacao(self):
        registro = _registro_de_oferta()
        self.assertTrue(registro.pk)
        self.assertFalse(AutomacaoStory.objects.exists())

    def test_padrao_desligado_nao_cria(self):
        PadraoRespostaStory.objects.create(pk=1, ativo=False)
        _registro_de_oferta()
        self.assertFalse(AutomacaoStory.objects.exists())

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_resposta_ao_story_manda_o_texto_do_padrao_com_o_botao(self, mock_enviar):
        PadraoRespostaStory.objects.create(pk=1, texto="Corre que acaba!", texto_botao="Quero o meu")
        registro = _registro_de_oferta()

        self.assertEqual(self._responder().status_code, 200)

        mock_enviar.assert_called_once()
        self.assertEqual(mock_enviar.call_args[0][2], "Corre que acaba!")
        titulo, url = mock_enviar.call_args.kwargs["botao"]
        self.assertEqual(titulo, "Quero o meu")
        self.assertTrue(url.endswith(f"/instagram/story/{registro.pk}/ir/"))
        self.assertTrue(RespostaStoryProcessada.objects.get().dm_enviada)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_botao_recusado_manda_o_texto_com_o_link_no_fim(self, mock_enviar):
        from . import instagram_api

        mock_enviar.side_effect = [instagram_api.InstagramAPIError("template recusado"), "mid"]
        registro = _registro_de_oferta()

        self._responder()

        self.assertEqual(mock_enviar.call_count, 2)
        texto = mock_enviar.call_args_list[1][0][2]
        self.assertTrue(texto.startswith(PadraoRespostaStory.TEXTO_PADRAO))
        self.assertTrue(texto.endswith(f"/instagram/story/{registro.pk}/ir/"))
        self.assertIsNone(mock_enviar.call_args_list[1].kwargs.get("botao"))
        self.assertTrue(RespostaStoryProcessada.objects.get().dm_enviada)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_desligar_o_padrao_para_as_automacoes_automaticas(self, mock_enviar):
        _registro_de_oferta()
        PadraoRespostaStory.objects.filter(pk=1).update(ativo=False)

        self._responder()

        mock_enviar.assert_not_called()

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_story_antigo_sem_automacao_ganha_uma_na_primeira_resposta(self, mock_enviar):
        PadraoRespostaStory.objects.create(pk=1, ativo=False)
        _registro_de_oferta()  # postado com o padrão desligado: ficou sem automação
        PadraoRespostaStory.objects.filter(pk=1).update(ativo=True)

        self._responder()

        self.assertTrue(AutomacaoStory.objects.get().automatica)
        mock_enviar.assert_called_once()

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_automacao_automatica_pausada_continua_pausada(self, mock_enviar):
        _registro_de_oferta()
        AutomacaoStory.objects.update(ativa=False)

        self._responder()

        mock_enviar.assert_not_called()
        self.assertEqual(AutomacaoStory.objects.count(), 1)

    @patch("automacao_instagram.instagram_api.enviar_mensagem_direta")
    def test_mensagem_personalizada_continua_sem_botao(self, mock_enviar):
        AutomacaoStory.objects.create(
            conta=self.conta, nome="Dica", instagram_story_media_id="story-dica",
            modo_resposta=AutomacaoStory.MODO_PERSONALIZADA, texto_personalizado="Olha nosso site",
        )
        self._responder(media_id="story-dica")
        self.assertEqual(mock_enviar.call_args[0][2], "Olha nosso site")
        self.assertIsNone(mock_enviar.call_args.kwargs.get("botao"))


@override_settings(INSTAGRAM_BUSINESS_ACCOUNT_ID="1")
class TelaDoPadraoDeRespostaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dono", password="senha123", cpf="39053344705", is_staff=True
        )
        self.client.force_login(self.usuario)
        self.url = reverse("automacao_padrao_story")

    def test_mostra_o_padrao_e_avisa_quando_a_conta_do_bot_falta(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, PadraoRespostaStory.TEXTO_PADRAO)
        self.assertContains(resposta, "A conta do bot não está em Contas conectadas")

        ContaInstagramConectada.objects.create(
            usuario=self.usuario, nome_exibicao="@usecashb", instagram_business_account_id="1", access_token="t",
        )
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, "A conta do bot não está em Contas conectadas")
        self.assertContains(resposta, "@usecashb")

    def test_salva_o_texto_e_o_botao(self):
        resposta = self.client.post(self.url, {"ativo": "on", "texto": "  Aproveita!  ", "texto_botao": "Comprar"})
        self.assertRedirects(resposta, self.url)
        padrao = PadraoRespostaStory.carregar()
        self.assertEqual((padrao.texto, padrao.texto_botao, padrao.ativo), ("Aproveita!", "Comprar", True))

    def test_desliga(self):
        self.client.post(self.url, {"texto": "Oi", "texto_botao": "Ver"})
        self.assertFalse(PadraoRespostaStory.carregar().ativo)

    def test_recusa_texto_vazio_e_botao_longo(self):
        resposta = self.client.post(self.url, {"ativo": "on", "texto": "   ", "texto_botao": "x" * 21})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Escreva a mensagem.")
        self.assertEqual(PadraoRespostaStory.carregar().texto, PadraoRespostaStory.TEXTO_PADRAO)

    def test_so_staff_entra(self):
        self.client.logout()
        cliente = get_user_model().objects.create_user(username="cliente", password="x", cpf="52998224725")
        self.client.force_login(cliente)
        self.assertEqual(self.client.get(self.url).status_code, 302)
