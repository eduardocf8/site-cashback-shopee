import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from licencas.models import Assinatura, ContaAppfiliado, ProdutoZouti

from . import cripto
from .emails import link_definir_senha

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"


@override_settings(
    APPFILIADO_PAINEL_HOSTS=[HOST],
    ALLOWED_HOSTS=[HOST, "testserver"],
    APPFILIADO_PAINEL_URL=f"https://{HOST}",
)
class BasePainel(TestCase):
    def setUp(self):
        cache.clear()  # o contador de tentativas de login fica no cache
        self.client = Client(HTTP_HOST=HOST)
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", nome="Bia Souza", modulos_cortesia="whatsapp",
        )
        self.conta.definir_senha(SENHA)
        self.conta.save()

    def entrar(self, email="bia@exemplo.com", senha=SENHA):
        return self.client.post("/entrar/", {"email": email, "senha": senha})


class TestDominio(BasePainel):
    def test_raiz_do_dominio_pede_login(self):
        resposta = self.client.get("/")
        self.assertRedirects(resposta, "/entrar/?proximo=%2F", fetch_redirect_response=False)

    def test_nada_da_cash_b_aparece_no_dominio_do_painel(self):
        resposta = self.client.get("/admin/")
        self.assertEqual(resposta.status_code, 404)
        self.assertContains(resposta, "Appfiliado", status_code=404)
        self.assertNotContains(resposta, "cash-b", status_code=404)

    def test_api_de_licencas_tambem_responde_no_dominio(self):
        resposta = self.client.post(
            "/licencas/validar/", data='{"chave": "%s"}' % self.conta.chave, content_type="application/json",
        )
        self.assertTrue(resposta.json()["valido"])

    def test_painel_nao_existe_no_dominio_da_cash_b(self):
        self.assertEqual(Client().get("/entrar/").status_code, 404)


class TestLogin(BasePainel):
    def test_login_certo_entra_e_volta_pra_pagina_pedida(self):
        resposta = self.client.post("/entrar/?proximo=/plano/", {"email": "BIA@exemplo.com", "senha": SENHA})
        self.assertRedirects(resposta, "/plano/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "Olá, Bia")
        self.conta.refresh_from_db()
        self.assertIsNotNone(self.conta.ultimo_login)

    def test_proximo_pra_outro_site_e_ignorado(self):
        resposta = self.client.post("/entrar/?proximo=https://golpe.com/", {"email": "bia@exemplo.com", "senha": SENHA})
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)

    def test_email_com_maiusculas_no_cadastro_tambem_entra(self):
        ContaAppfiliado.objects.filter(pk=self.conta.pk).update(email="Bia@Exemplo.com")
        self.assertRedirects(self.entrar(), "/", fetch_redirect_response=False)

    def test_senha_errada(self):
        self.assertContains(self.entrar(senha="errada"), "E-mail ou senha incorretos")

    def test_conta_sem_senha_recebe_orientacao(self):
        ContaAppfiliado.objects.create(email="nova@exemplo.com")
        self.assertContains(self.entrar(email="nova@exemplo.com", senha="qualquer"), "ainda não criou sua senha")

    def test_muitas_tentativas_bloqueiam_mesmo_com_a_senha_certa(self):
        for _ in range(8):
            self.entrar(senha="errada")
        self.assertContains(self.entrar(), "Muitas tentativas")

    def test_sair(self):
        self.entrar()
        self.client.post("/sair/")
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_trocar_a_senha_em_outro_lugar_derruba_a_sessao(self):
        self.entrar()
        self.conta.definir_senha("outra-senha-boa-456")
        self.conta.save()
        self.assertEqual(self.client.get("/").status_code, 302)


class TestSenha(BasePainel):
    def test_esqueci_senha_manda_link_so_pra_quem_existe_mas_responde_igual(self):
        resposta = self.client.post("/senha/esqueci/", {"email": "bia@exemplo.com"})
        self.assertContains(resposta, "Se esse e-mail tiver uma assinatura")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"https://{HOST}/senha/definir/", mail.outbox[0].body)

        resposta = self.client.post("/senha/esqueci/", {"email": "ninguem@exemplo.com"})
        self.assertContains(resposta, "Se esse e-mail tiver uma assinatura")
        self.assertEqual(len(mail.outbox), 1)

    def test_link_define_senha_entra_e_nao_vale_de_novo(self):
        nova = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        caminho = link_definir_senha(nova).replace(f"https://{HOST}", "")

        self.assertContains(self.client.get(caminho), "Crie sua senha")
        resposta = self.client.post(caminho, {"senha": "senha-nova-789", "confirmacao": "senha-nova-789"})
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)
        nova.refresh_from_db()
        self.assertTrue(nova.confere_senha("senha-nova-789"))

        self.client.post("/sair/")
        self.assertContains(self.client.get(caminho), "Link vencido", status_code=400)

    def test_senhas_diferentes_ou_fracas_sao_recusadas(self):
        nova = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        caminho = link_definir_senha(nova).replace(f"https://{HOST}", "")
        self.assertContains(self.client.post(caminho, {"senha": "senha-nova-789", "confirmacao": "outra"}),
                            "não são iguais")
        self.assertContains(self.client.post(caminho, {"senha": "12345678", "confirmacao": "12345678"}),
                            "erro")
        nova.refresh_from_db()
        self.assertFalse(nova.tem_senha)

    def test_trocar_senha_logado(self):
        self.entrar()
        resposta = self.client.post("/configuracoes/", {
            "formulario": "senha", "senha_atual": SENHA,
            "senha": "nova-senha-boa-321", "confirmacao": "nova-senha-boa-321",
        })
        self.assertRedirects(resposta, "/configuracoes/", fetch_redirect_response=False)
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.confere_senha("nova-senha-boa-321"))
        self.assertEqual(self.client.get("/").status_code, 200)  # a sessão atual continua


class TestShopee(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    @mock.patch("painel.views.testar_credenciais", return_value=(True, "Conexão com a Shopee funcionando."))
    def test_salva_secret_cifrado_quando_a_shopee_aceita(self, _):
        resposta = self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "123", "secret": "segredo"})
        self.assertRedirects(resposta, "/configuracoes/", fetch_redirect_response=False)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.shopee_app_id, "123")
        self.assertNotIn("segredo", self.conta.shopee_secret_cifrado)
        self.assertEqual(cripto.decifrar(self.conta.shopee_secret_cifrado), "segredo")
        self.assertIsNotNone(self.conta.shopee_validado_em)
        self.assertNotContains(self.client.get("/configuracoes/"), "segredo")

    @mock.patch("painel.views.testar_credenciais", return_value=(False, "A Shopee não aceitou esse AppID e Secret."))
    def test_nao_salva_quando_a_shopee_recusa(self, _):
        resposta = self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "123", "secret": "errado"})
        self.assertContains(resposta, "não aceitou")
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.shopee_app_id, "")

    @mock.patch("painel.views.testar_credenciais", return_value=(True, "ok"))
    def test_secret_em_branco_mantem_o_salvo(self, testar):
        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("antigo")
        self.conta.save()
        self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "456", "secret": ""})
        testar.assert_called_with("456", "antigo")

    def test_cifra_e_decifra(self):
        cifrado = cripto.cifrar("abc")
        self.assertNotEqual(cifrado, "abc")
        self.assertEqual(cripto.decifrar(cifrado), "abc")
        self.assertEqual(cripto.decifrar("lixo"), "")


class TestPaginas(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_menu_mostra_cadeado_e_em_breve(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Não incluso no seu plano", html)  # vídeos (fora do plano): cadeado
        self.assertIn("Em breve", html)  # Bot (liberado, mas ainda não está no painel)

    def test_modulo_fora_do_plano_mostra_convite(self):
        self.assertContains(self.client.get("/m/site/"), "Não incluso no seu plano")

    def test_modulo_do_plano_ainda_nao_pronto_mostra_em_breve(self):
        self.assertContains(self.client.get("/m/whatsapp/"), "Em breve")

    def test_modulo_inexistente(self):
        self.assertEqual(self.client.get("/m/nada/").status_code, 404)

    def test_plano_mostra_modulos_assinaturas_e_chave(self):
        ProdutoZouti.objects.create(zouti_product_id="prod_site", nome="Site", modulos="site")
        Assinatura.objects.create(
            conta=self.conta, zouti_subscription_id="sub_1", zouti_product_ids="prod_site",
            plano="Mensal", status=Assinatura.STATUS_ATIVA, proxima_cobranca=timezone.localdate() + timedelta(days=20),
        )
        html = self.client.get("/plano/").content.decode()
        self.assertIn(self.conta.chave, html)
        self.assertIn("Mensal", html)
        self.assertEqual(len(re.findall(r"estado-liberado", html)), 2)  # whatsapp (cortesia) e site


@override_settings(APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestEmailDaChave(TestCase):
    def test_email_da_chave_convida_pra_criar_a_senha_do_painel(self):
        from licencas.services import enviar_email_chave

        conta = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        enviar_email_chave(conta.pk)
        self.assertIn(conta.chave, mail.outbox[0].body)
        self.assertIn(f"https://{HOST}/senha/definir/", mail.outbox[0].body)
