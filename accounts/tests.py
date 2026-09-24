import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ofertas.models import Oferta
from pedidos.models import Pedido
from saques.models import Saque

from .comunicacoes import enviar_comunicacao, obter_destinatarios, renderizar_corpo_html
from .forms import EditarPerfilForm
from .models import ComunicacaoEmail, ConfiguracaoIndicacao, Indicacao, PushSubscription, User
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
        cache.clear()  # evita herdar contador de rate limit de outro teste (ver RateLimitTests)
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


class MetaPixelCadastroTests(TestCase):
    """CompleteRegistration sai pelos dois canais: Conversions API (servidor, disparada
    na hora do cadastro) e Pixel (navegador, disparado na 1ª renderização do dashboard
    depois do redirect) - com o MESMO event_id, pra Meta deduplicar (ver
    cashback_shopee/meta_capi.py)."""

    def _dados_cadastro(self, **extra):
        dados = {
            "username": "novaconta", "email": "nova@example.com", "cpf": "14783246947",
            "password1": "senha-forte-123", "password2": "senha-forte-123",
        }
        dados.update(extra)
        return dados

    @patch("accounts.views.enviar_evento")
    def test_cadastro_completo_manda_evento_pra_conversions_api(self, mock_enviar_evento):
        self.client.post(reverse("registrar"), self._dados_cadastro())

        mock_enviar_evento.assert_called_once()
        nome_evento, _request, event_id = mock_enviar_evento.call_args[0]
        self.assertEqual(nome_evento, "CompleteRegistration")
        self.assertTrue(event_id)

    def test_dashboard_dispara_o_pixel_do_navegador_so_na_primeira_visita(self):
        resposta = self.client.post(reverse("registrar"), self._dados_cadastro(), follow=True)
        self.assertContains(resposta, 'fbq("track", "CompleteRegistration"')

        resposta_seguinte = self.client.get(reverse("dashboard"))
        self.assertNotContains(resposta_seguinte, 'fbq("track", "CompleteRegistration"')

    @patch("accounts.views.enviar_evento")
    def test_event_id_do_navegador_bate_com_o_da_conversions_api(self, mock_enviar_evento):
        resposta = self.client.post(reverse("registrar"), self._dados_cadastro(), follow=True)

        event_id_capi = mock_enviar_evento.call_args[0][2]
        self.assertContains(resposta, f'eventID: "{event_id_capi}"')


class RateLimitTests(TestCase):
    """django-axes só protege o login - registrar/reenviar_verificacao/password_reset
    não exigem login (ou não passam pelo axes) e disparam e-mail/criam conta, então
    ganharam seu próprio limite por IP (ver accounts/ratelimit.py)."""

    def setUp(self):
        cache.clear()  # cada teste começa com o contador zerado (cache é global ao processo)

    def test_registrar_bloqueia_depois_do_limite(self):
        for _ in range(10):
            resposta = self.client.get(reverse("registrar"))
            self.assertEqual(resposta.status_code, 200)

        resposta = self.client.get(reverse("registrar"))

        self.assertEqual(resposta.status_code, 429)

    def test_reenviar_verificacao_bloqueia_depois_do_limite(self):
        usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.client.force_login(usuario)
        for _ in range(3):
            resposta = self.client.get(reverse("reenviar_verificacao"))
            self.assertEqual(resposta.status_code, 302)

        resposta = self.client.get(reverse("reenviar_verificacao"))

        self.assertEqual(resposta.status_code, 429)

    def test_password_reset_bloqueia_depois_do_limite(self):
        for _ in range(5):
            resposta = self.client.get(reverse("password_reset"))
            self.assertEqual(resposta.status_code, 200)

        resposta = self.client.get(reverse("password_reset"))

        self.assertEqual(resposta.status_code, 429)

    def test_ips_diferentes_tem_contadores_independentes(self):
        for _ in range(10):
            self.client.get(reverse("registrar"), REMOTE_ADDR="1.1.1.1")
        bloqueado = self.client.get(reverse("registrar"), REMOTE_ADDR="1.1.1.1")
        livre = self.client.get(reverse("registrar"), REMOTE_ADDR="2.2.2.2")

        self.assertEqual(bloqueado.status_code, 429)
        self.assertEqual(livre.status_code, 200)


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


class AcaoDeTesteDoPushNoAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="14783246947")
        self.inscricao = PushSubscription.objects.create(
            usuario=self.usuario,
            endpoint="https://push.exemplo.com/abc",
            chave_p256dh="chave-p256dh",
            chave_auth="chave-auth",
        )
        self.client.force_login(self.staff)

    @patch("accounts.admin.enviar_push")
    def test_manda_pro_usuario_da_inscricao_selecionada(self, mock_enviar_push):
        mock_enviar_push.return_value = 1

        resposta = self.client.post(
            reverse("admin:accounts_pushsubscription_changelist"),
            {"action": "mandar_notificacao_de_teste", "_selected_action": [self.inscricao.pk]},
            follow=True,
        )

        mock_enviar_push.assert_called_once()
        self.assertEqual(mock_enviar_push.call_args.args[0], self.usuario)
        self.assertContains(resposta, "enviada com sucesso")

    @patch("accounts.admin.enviar_push")
    def test_falha_no_envio_avisa_em_vez_de_dizer_que_deu_certo(self, mock_enviar_push):
        # enviar_push retorna 0 quando o push falhou no servidor pra todo mundo (ex:
        # chave VAPID errada) - sem checar isso, a ação sempre dizia "enviado" mesmo
        # quando não saiu nada, escondendo o erro de quem só olha o admin.
        mock_enviar_push.return_value = 0

        resposta = self.client.post(
            reverse("admin:accounts_pushsubscription_changelist"),
            {"action": "mandar_notificacao_de_teste", "_selected_action": [self.inscricao.pk]},
            follow=True,
        )

        self.assertContains(resposta, "Não saiu nenhuma notificação")


class ObterDestinatariosTests(TestCase):
    def setUp(self):
        self.sem_pedido = User.objects.create_user(
            username="sem_pedido", password="senha123", cpf="14783246947", email="sem_pedido@example.com"
        )
        self.com_pedido = User.objects.create_user(
            username="com_pedido", password="senha123", cpf="39053344705", email="com_pedido@example.com"
        )
        Pedido.objects.create(
            order_id="PED001", conversion_id="conv1", status_shopee_bruto="UNPAID", usuario=self.com_pedido
        )
        self.sacou = User.objects.create_user(
            username="sacou", password="senha123", cpf="11144477735", email="sacou@example.com"
        )
        Saque.objects.create(usuario=self.sacou, valor=Decimal("20"), chave_pix="x", tipo_chave_pix="EMAIL")
        self.verificado = User.objects.create_user(
            username="verificado",
            password="senha123",
            cpf="52998224725",
            email="verificado@example.com",
            email_verificado=True,
        )
        self.sem_email = User.objects.create_user(username="sem_email", password="senha123", cpf="93541134780")

    def test_todos_exclui_quem_nao_tem_email(self):
        usuarios = obter_destinatarios("todos")
        self.assertNotIn(self.sem_email, usuarios)
        self.assertIn(self.com_pedido, usuarios)

    def test_com_pedidos_so_traz_quem_tem_pelo_menos_um(self):
        usuarios = obter_destinatarios(ComunicacaoEmail.FILTRO_COM_PEDIDOS)
        self.assertIn(self.com_pedido, usuarios)
        self.assertNotIn(self.sem_pedido, usuarios)

    def test_sem_pedidos_e_o_complemento(self):
        usuarios = obter_destinatarios(ComunicacaoEmail.FILTRO_SEM_PEDIDOS)
        self.assertIn(self.sem_pedido, usuarios)
        self.assertNotIn(self.com_pedido, usuarios)

    def test_ja_sacou_e_nunca_sacou(self):
        ja_sacou = obter_destinatarios(ComunicacaoEmail.FILTRO_JA_SACOU)
        nunca_sacou = obter_destinatarios(ComunicacaoEmail.FILTRO_NUNCA_SACOU)
        self.assertIn(self.sacou, ja_sacou)
        self.assertNotIn(self.sacou, nunca_sacou)
        self.assertIn(self.sem_pedido, nunca_sacou)

    def test_email_verificado_e_nao_verificado(self):
        verificados = obter_destinatarios(ComunicacaoEmail.FILTRO_EMAIL_VERIFICADO)
        nao_verificados = obter_destinatarios(ComunicacaoEmail.FILTRO_EMAIL_NAO_VERIFICADO)
        self.assertIn(self.verificado, verificados)
        self.assertNotIn(self.verificado, nao_verificados)
        self.assertIn(self.sem_pedido, nao_verificados)

    def test_filtro_invalido_nao_quebra_view_de_contagem(self):
        # a view de contagem passa direto o que vier no GET - um filtro desconhecido
        # deveria cair no "todos" em vez de derrubar a página com erro.
        usuarios = obter_destinatarios("isso-nao-existe")
        self.assertIn(self.com_pedido, usuarios)

    def test_anuncio_nao_manda_pra_quem_desligou_marketing(self):
        self.com_pedido.aceita_email_marketing = False
        self.com_pedido.save(update_fields=["aceita_email_marketing"])

        anuncio = obter_destinatarios("todos", tipo=ComunicacaoEmail.TIPO_ANUNCIO)
        geral = obter_destinatarios("todos", tipo=ComunicacaoEmail.TIPO_GERAL)

        self.assertNotIn(self.com_pedido, anuncio)
        self.assertIn(self.com_pedido, geral)

    def test_tipo_padrao_e_anuncio(self):
        # chamar sem passar tipo (comportamento antigo, antes desse campo existir)
        # deveria continuar respeitando o opt-out, não mandar pra todo mundo sem filtro.
        self.com_pedido.aceita_email_marketing = False
        self.com_pedido.save(update_fields=["aceita_email_marketing"])

        usuarios = obter_destinatarios("todos")

        self.assertNotIn(self.com_pedido, usuarios)


class EnviarComunicacaoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        for i in range(3):
            User.objects.create_user(
                username=f"usuario{i}", password="senha123", cpf=f"1111111111{i}"[:11], email=f"u{i}@example.com"
            )
        self.oferta = Oferta.objects.create(
            item_id=1,
            nome="Produto Teste",
            nome_curto="Produto Teste Curto",
            categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            imagem_url="https://exemplo.com/produto.jpg",
            preco_min=Decimal("100"),
            percentual_comissao=Decimal("0.1000"),
        )

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_manda_em_lotes_via_bcc_e_nao_estoura_o_lote_maximo(self, MockEmailMessage):
        mock_instancia = Mock()
        MockEmailMessage.return_value = mock_instancia

        import accounts.comunicacoes as comunicacoes_module

        tamanho_original = comunicacoes_module.TAMANHO_LOTE
        comunicacoes_module.TAMANHO_LOTE = 2
        try:
            comunicacao = enviar_comunicacao(
                assunto="Assunto de teste", corpo="Corpo de teste", filtro="todos", enviado_por=self.staff
            )
        finally:
            comunicacoes_module.TAMANHO_LOTE = tamanho_original

        # 3 destinatários, lote de 2 -> 2 chamadas (uma com 2, outra com 1)
        self.assertEqual(MockEmailMessage.call_count, 2)
        self.assertEqual(mock_instancia.send.call_count, 2)
        self.assertEqual(comunicacao.total_destinatarios, 3)
        self.assertEqual(comunicacao.total_enviados, 3)
        self.assertEqual(comunicacao.enviado_por, self.staff)

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_falha_num_lote_nao_impede_os_outros_e_conta_certo(self, MockEmailMessage):
        primeiro_lote = Mock()
        primeiro_lote.send.side_effect = Exception("Brevo fora do ar")
        segundo_lote = Mock()
        MockEmailMessage.side_effect = [primeiro_lote, segundo_lote]

        import accounts.comunicacoes as comunicacoes_module

        tamanho_original = comunicacoes_module.TAMANHO_LOTE
        comunicacoes_module.TAMANHO_LOTE = 2
        try:
            comunicacao = enviar_comunicacao(
                assunto="Assunto", corpo="Corpo", filtro="todos", enviado_por=self.staff
            )
        finally:
            comunicacoes_module.TAMANHO_LOTE = tamanho_original

        self.assertEqual(comunicacao.total_destinatarios, 3)
        self.assertEqual(comunicacao.total_enviados, 1)  # só o segundo lote (1 destinatário) foi contado

    def test_filtro_sem_ninguem_nao_manda_nada(self):
        comunicacao = enviar_comunicacao(
            assunto="Assunto",
            corpo="Corpo",
            filtro=ComunicacaoEmail.FILTRO_JA_SACOU,
            enviado_por=self.staff,
        )
        self.assertEqual(comunicacao.total_destinatarios, 0)
        self.assertEqual(comunicacao.total_enviados, 0)


class ComunicacaoViewNoAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        User.objects.create_user(username="ana", password="senha123", cpf="14783246947", email="ana@example.com")
        self.client.force_login(self.staff)

    def test_pagina_carrega_com_o_formulario(self):
        resposta = self.client.get(reverse("admin:accounts_comunicacao"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Enviar comunicação por e-mail")

    def test_endpoint_de_contagem_responde_json(self):
        resposta = self.client.get(reverse("admin:accounts_comunicacao_contar"), {"filtro": "todos"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(json.loads(resposta.content)["total"], 1)

    @patch("accounts.admin.enviar_comunicacao")
    def test_post_valido_chama_envio_e_redireciona(self, mock_enviar):
        mock_enviar.return_value = ComunicacaoEmail(
            assunto="Oi", corpo="Corpo", filtro="todos", total_destinatarios=1, total_enviados=1
        )

        resposta = self.client.post(
            reverse("admin:accounts_comunicacao"),
            {"assunto": "Oi", "corpo": "Corpo do e-mail", "filtro": "todos"},
            follow=True,
        )

        mock_enviar.assert_called_once()
        self.assertContains(resposta, "enviado com sucesso")

    def test_post_sem_assunto_nao_manda_nada(self):
        with patch("accounts.admin.enviar_comunicacao") as mock_enviar:
            resposta = self.client.post(
                reverse("admin:accounts_comunicacao"),
                {"assunto": "", "corpo": "Corpo", "filtro": "todos"},
                follow=True,
            )
        mock_enviar.assert_not_called()
        self.assertContains(resposta, "Preencha o assunto")

    def test_usuario_nao_staff_nao_acessa(self):
        comum = User.objects.create_user(username="comum", password="senha123", cpf="93541134780")
        self.client.logout()
        self.client.force_login(comum)

        resposta = self.client.get(reverse("admin:accounts_comunicacao"))

        self.assertNotEqual(resposta.status_code, 200)


class RenderizarCorpoHtmlTests(TestCase):
    def setUp(self):
        self.oferta = Oferta.objects.create(
            item_id=1,
            nome="Produto Teste",
            nome_curto="Produto Teste Curto",
            categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            imagem_url="https://exemplo.com/produto.jpg",
            preco_min=Decimal("100"),
            percentual_comissao=Decimal("0.1000"),
        )
        self.request = RequestFactory().get("/admin/accounts/user/comunicacoes/")

    def test_inclui_nome_imagem_e_link_da_oferta(self):
        html = renderizar_corpo_html("Confira essa oferta!", [self.oferta], self.request)

        self.assertIn("Produto Teste Curto", html)
        self.assertIn("https://exemplo.com/produto.jpg", html)
        self.assertIn(reverse("ofertas_ir", args=[self.oferta.id]), html)
        self.assertIn("Confira essa oferta!", html)

    def test_texto_do_corpo_e_escapado_nunca_vira_html_de_verdade(self):
        # corpo vem de um <textarea> digitado por quem está logado no admin - não é
        # HTML confiável, tem que escapar antes de jogar no template.
        html = renderizar_corpo_html("<script>alert(1)</script>", [], self.request)

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sem_ofertas_nao_quebra(self):
        html = renderizar_corpo_html("Só um aviso, sem produtos.", [], self.request)
        self.assertIn("Só um aviso, sem produtos.", html)


class EnviarComunicacaoComOfertasTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        User.objects.create_user(username="ana", password="senha123", cpf="14783246947", email="ana@example.com")
        self.oferta = Oferta.objects.create(
            item_id=1,
            nome="Produto Teste",
            nome_curto="Produto Teste Curto",
            categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1",
            imagem_url="https://exemplo.com/produto.jpg",
            preco_min=Decimal("100"),
            percentual_comissao=Decimal("0.1000"),
        )

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_com_ofertas_anexa_html_e_guarda_no_historico(self, MockEmail):
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia
        request = RequestFactory().get("/admin/accounts/user/comunicacoes/")

        comunicacao = enviar_comunicacao(
            assunto="Oferta imperdível",
            corpo="Confira!",
            filtro="todos",
            ofertas=[self.oferta],
            enviado_por=self.staff,
            request=request,
        )

        mock_instancia.attach_alternative.assert_called_once()
        html_enviado = mock_instancia.attach_alternative.call_args.args[0]
        self.assertIn("Produto Teste Curto", html_enviado)
        self.assertIn("Produto Teste Curto", comunicacao.corpo_html)
        self.assertEqual(list(comunicacao.ofertas.all()), [self.oferta])

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_sem_ofertas_nao_anexa_html(self, MockEmail):
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia

        comunicacao = enviar_comunicacao(
            assunto="Assunto", corpo="Corpo", filtro="todos", enviado_por=self.staff
        )

        mock_instancia.attach_alternative.assert_not_called()
        self.assertEqual(comunicacao.corpo_html, "")
        self.assertEqual(comunicacao.ofertas.count(), 0)

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_ofertas_sem_request_tambem_nao_anexa_html(self, MockEmail):
        # renderizar_corpo_html precisa de request pra montar o link absoluto - sem
        # ele, melhor cair pro texto simples do que quebrar o envio inteiro.
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia

        comunicacao = enviar_comunicacao(
            assunto="Assunto", corpo="Corpo", filtro="todos", ofertas=[self.oferta], enviado_por=self.staff
        )

        mock_instancia.attach_alternative.assert_not_called()
        self.assertEqual(comunicacao.corpo_html, "")


class ComunicacaoBuscarOfertasViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.staff)
        Oferta.objects.create(
            item_id=1, nome="Creatina Monohidratada", nome_curto="Creatina", categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1", imagem_url="https://exemplo.com/creatina.jpg",
        )
        Oferta.objects.create(
            item_id=2, nome="Fone de ouvido bluetooth", nome_curto="Fone bluetooth", categoria_id=1,
            product_link="https://shopee.com.br/produto-2-i.2.2", imagem_url="https://exemplo.com/fone.jpg",
        )

    def test_busca_por_nome_curto(self):
        resposta = self.client.get(
            reverse("admin:accounts_comunicacao_buscar_ofertas"), {"q": "creatina"}
        )
        dados = json.loads(resposta.content)
        self.assertEqual(len(dados["resultados"]), 1)
        self.assertEqual(dados["resultados"][0]["nome"], "Creatina")

    def test_sem_termo_lista_ofertas_recentes(self):
        resposta = self.client.get(reverse("admin:accounts_comunicacao_buscar_ofertas"))
        dados = json.loads(resposta.content)
        self.assertEqual(len(dados["resultados"]), 2)

    def test_termo_sem_correspondencia_retorna_vazio(self):
        resposta = self.client.get(
            reverse("admin:accounts_comunicacao_buscar_ofertas"), {"q": "isso-nao-existe"}
        )
        dados = json.loads(resposta.content)
        self.assertEqual(dados["resultados"], [])


class RodapeDescadastroTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        User.objects.create_user(username="ana", password="senha123", cpf="14783246947", email="ana@example.com")

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_anuncio_inclui_link_de_descadastro_no_texto(self, MockEmail):
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia
        request = RequestFactory().get("/admin/accounts/user/comunicacoes/")

        enviar_comunicacao(
            assunto="Oferta",
            corpo="Corpo do anúncio",
            filtro="todos",
            tipo=ComunicacaoEmail.TIPO_ANUNCIO,
            enviado_por=self.staff,
            request=request,
        )

        corpo_enviado = MockEmail.call_args.kwargs["body"]
        self.assertIn("Corpo do anúncio", corpo_enviado)
        self.assertIn(reverse("preferencias_email"), corpo_enviado)
        self.assertIn("Não quer mais receber", corpo_enviado)

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_comunicacao_geral_nao_inclui_link_de_descadastro(self, MockEmail):
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia
        request = RequestFactory().get("/admin/accounts/user/comunicacoes/")

        enviar_comunicacao(
            assunto="Aviso",
            corpo="Corpo do aviso geral",
            filtro="todos",
            tipo=ComunicacaoEmail.TIPO_GERAL,
            enviado_por=self.staff,
            request=request,
        )

        corpo_enviado = MockEmail.call_args.kwargs["body"]
        self.assertEqual(corpo_enviado, "Corpo do aviso geral")
        self.assertNotIn(reverse("preferencias_email"), corpo_enviado)

    @patch("accounts.comunicacoes.EmailMultiAlternatives")
    def test_anuncio_com_ofertas_inclui_link_no_html_tambem(self, MockEmail):
        mock_instancia = Mock()
        MockEmail.return_value = mock_instancia
        oferta = Oferta.objects.create(
            item_id=1, nome="Produto", nome_curto="Produto Curto", categoria_id=1,
            product_link="https://shopee.com.br/produto-1-i.1.1", imagem_url="https://exemplo.com/p.jpg",
            preco_min=Decimal("50"), percentual_comissao=Decimal("0.05"),
        )
        request = RequestFactory().get("/admin/accounts/user/comunicacoes/")

        enviar_comunicacao(
            assunto="Oferta",
            corpo="Confira",
            filtro="todos",
            tipo=ComunicacaoEmail.TIPO_ANUNCIO,
            ofertas=[oferta],
            enviado_por=self.staff,
            request=request,
        )

        html_enviado = mock_instancia.attach_alternative.call_args.args[0]
        self.assertIn(reverse("preferencias_email"), html_enviado)


class PreferenciasEmailViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="ana", password="senha123", cpf="14783246947", email="ana@example.com"
        )

    def test_exige_login(self):
        resposta = self.client.get(reverse("preferencias_email"))
        self.assertNotEqual(resposta.status_code, 200)

    def test_desligar_marketing(self):
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse("preferencias_email"), {"aceita": "nao"}, follow=True)

        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.aceita_email_marketing)
        self.assertContains(resposta, "não vai mais receber")

    def test_religar_marketing(self):
        self.usuario.aceita_email_marketing = False
        self.usuario.save(update_fields=["aceita_email_marketing"])
        self.client.force_login(self.usuario)

        resposta = self.client.post(reverse("preferencias_email"), {"aceita": "sim"}, follow=True)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.aceita_email_marketing)
        self.assertContains(resposta, "volta a receber")

    def test_get_mostra_o_estado_atual(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("preferencias_email"))
        self.assertContains(resposta, "Você está recebendo")


class ComunicacaoViewPassaTipoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", password="senha123", cpf="39053344705", is_staff=True, is_superuser=True
        )
        self.client.force_login(self.staff)

    @patch("accounts.admin.enviar_comunicacao")
    def test_tipo_geral_e_repassado_pro_envio(self, mock_enviar):
        mock_enviar.return_value = ComunicacaoEmail(
            assunto="Oi", corpo="Corpo", filtro="todos", tipo="geral", total_destinatarios=1, total_enviados=1
        )

        self.client.post(
            reverse("admin:accounts_comunicacao"),
            {"assunto": "Oi", "corpo": "Corpo", "filtro": "todos", "tipo": "geral"},
            follow=True,
        )

        self.assertEqual(mock_enviar.call_args.kwargs["tipo"], "geral")

    def test_contagem_respeita_o_tipo(self):
        User.objects.create_user(
            username="optou_fora", password="senha123", cpf="14783246947", email="fora@example.com",
            aceita_email_marketing=False,
        )

        resposta_anuncio = self.client.get(
            reverse("admin:accounts_comunicacao_contar"), {"filtro": "todos", "tipo": "anuncio"}
        )
        resposta_geral = self.client.get(
            reverse("admin:accounts_comunicacao_contar"), {"filtro": "todos", "tipo": "geral"}
        )

        self.assertEqual(json.loads(resposta_anuncio.content)["total"], 0)
        self.assertEqual(json.loads(resposta_geral.content)["total"], 1)


class EditarPerfilFormTests(TestCase):
    def test_form_inclui_campo_de_marketing(self):
        self.assertIn("aceita_email_marketing", EditarPerfilForm.Meta.fields)
