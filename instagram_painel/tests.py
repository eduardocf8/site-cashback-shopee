import base64
import hashlib
import hmac
import json
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from licencas.models import ContaAppfiliado
from painel import cripto

from . import api, conexao
from . import webhook as W
from .models import Automacao, ContaInstagram, Disparo

SEGREDO = "segredo-de-teste"
HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
IG_ID = "17841400000000001"


def conta(modulos="carrosseis_premium", email="bia@exemplo.com", beta=True):
    c = ContaAppfiliado.objects.create(email=email, modulos_cortesia=modulos, beta_estudio_instagram=beta)
    c.definir_senha(SENHA)
    c.save()
    return c


def conectada(c, ig_id=IG_ID, username="achadosdabia"):
    return ContaInstagram.objects.create(conta=c, ig_id=ig_id, username=username, token_cifrado=cripto.cifrar("tok"))


def aviso_comentario(texto, autor="999", username="maria", comentario="c1", midia="m1", ig_id=IG_ID, **extra):
    valor = {"id": comentario, "from": {"id": autor, "username": username}, "text": texto, "media": {"id": midia}, **extra}
    return {"object": "instagram", "entry": [{"id": ig_id, "time": 1, "changes": [{"field": "comments", "value": valor}]}]}


def aviso_mensagem(texto="", autor="888", mid="mid1", story=None, ig_id=IG_ID, **msg):
    m = {"mid": mid, "text": texto, **msg}
    if story:
        m["reply_to"] = {"story": {"id": story, "url": "https://x"}}
    return {"object": "instagram", "entry": [{"id": ig_id, "time": 1, "messaging": [
        {"sender": {"id": autor}, "recipient": {"id": ig_id}, "timestamp": 1, "message": m}]}]}


@mock.patch.object(api, "responder_comentario", return_value="r1")
@mock.patch.object(api, "resposta_privada", return_value="d1")
@mock.patch.object(api, "mensagem", return_value="d2")
class TestAvisos(TestCase):
    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, nome="Garrafa", gatilho=Automacao.COMENTARIO, midia_id="m1",
                                          palavras="quero, link", respostas="Te mandei no direto, {nome}!",
                                          texto_dm="Aqui está:", link="https://s.shopee.com.br/abc")

    def test_comentario_com_palavra_responde_e_manda_dm(self, msg, privada, resposta):
        W.separar_e_processar(aviso_comentario("Eu QUÉRO muito!"))
        resposta.assert_called_once_with("tok", "c1", "Te mandei no direto, @maria!")
        privada.assert_called_once_with("tok", IG_ID, "c1", "Aqui está:\n\nhttps://s.shopee.com.br/abc")
        d = Disparo.objects.get()
        self.assertTrue(d.resposta_ok and d.dm_ok)

    def test_sem_a_palavra_ou_em_outro_post_nao_responde(self, msg, privada, resposta):
        W.separar_e_processar(aviso_comentario("que lindo"))
        W.separar_e_processar(aviso_comentario("quero", midia="outro", comentario="c2"))
        W.separar_e_processar(aviso_comentario("queroo", comentario="c3"))  # palavra inteira
        resposta.assert_not_called()

    def test_aviso_repetido_e_mesma_pessoa_respondidos_uma_vez(self, msg, privada, resposta):
        W.separar_e_processar(aviso_comentario("quero"))
        W.separar_e_processar(aviso_comentario("quero"))  # a Meta repetiu
        W.separar_e_processar(aviso_comentario("link", comentario="c9"))  # mesma pessoa, outro comentário
        self.assertEqual(resposta.call_count, 1)
        self.assertEqual(Disparo.objects.count(), 1)

    def test_nao_responde_a_propria_conta_nem_resposta_de_resposta(self, msg, privada, resposta):
        W.separar_e_processar(aviso_comentario("quero", autor=IG_ID, username="achadosdabia"))
        W.separar_e_processar(aviso_comentario("quero", comentario="c5", parent_id="c1"))
        resposta.assert_not_called()

    def test_automacao_do_post_vem_antes_da_geral_e_pausada_nao_responde(self, msg, privada, resposta):
        Automacao.objects.create(conta=self.c, nome="Geral", gatilho=Automacao.COMENTARIO, respostas="Geral",
                                 enviar_dm=False)
        W.separar_e_processar(aviso_comentario("quero"))
        self.assertEqual(Disparo.objects.get().automacao, self.a)
        W.separar_e_processar(aviso_comentario("bonito", comentario="c7", autor="777", midia="m2"))
        resposta.assert_called_with("tok", "c7", "Geral")
        Automacao.objects.update(ativa=False)
        W.separar_e_processar(aviso_comentario("quero", comentario="c8", autor="666"))
        self.assertEqual(Disparo.objects.count(), 2)

    def test_resposta_a_story_e_direto(self, msg, privada, resposta):
        Automacao.objects.create(conta=self.c, nome="Story", gatilho=Automacao.STORY, texto_dm="Link do story")
        Automacao.objects.create(conta=self.c, nome="Direto", gatilho=Automacao.DIRETO, palavras="cupom", texto_dm="O cupom é X")
        W.separar_e_processar(aviso_mensagem("🔥", story="s1"))
        msg.assert_called_with("tok", IG_ID, "888", "Link do story")
        W.separar_e_processar(aviso_mensagem("tem cupom?", autor="777", mid="mid2"))
        msg.assert_called_with("tok", IG_ID, "777", "O cupom é X")
        W.separar_e_processar(aviso_mensagem("oi", autor="555", mid="mid3"))  # sem a palavra
        W.separar_e_processar(aviso_mensagem("cupom", autor="444", mid="mid4", is_echo=True))  # a própria conta
        self.assertEqual(msg.call_count, 2)

    def test_erro_do_instagram_fica_no_historico(self, msg, privada, resposta):
        privada.side_effect = api.ErroInstagram("janela de 7 dias")
        W.separar_e_processar(aviso_comentario("quero"))
        d = Disparo.objects.get()
        self.assertTrue(d.resposta_ok)
        self.assertFalse(d.dm_ok)
        self.assertIn("7 dias", d.erro)

    def test_avisos_de_outras_contas_seguem_para_a_cash_b(self, msg, privada, resposta):
        payload = aviso_comentario("quero", ig_id="outra")
        self.assertEqual(W.separar_e_processar(payload)["entry"], payload["entry"])
        self.assertEqual(W.separar_e_processar(aviso_comentario("quero", comentario="cx", autor="1"))["entry"], [])


@override_settings(INSTAGRAM_APP_SECRET=SEGREDO, APPFILIADO_INSTAGRAM_APP_SECRET=SEGREDO, APPFILIADO_INSTAGRAM_APP_ID="123")
class TestWebhookEConexao(TestCase):
    def test_webhook_assinado_chega_na_automacao_do_afiliado(self):
        c = conta()
        conectada(c)
        Automacao.objects.create(conta=c, nome="x", palavras="quero", respostas="ok", enviar_dm=False)
        corpo = json.dumps(aviso_comentario("quero")).encode()
        assinatura = "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
        with mock.patch.object(api, "responder_comentario", return_value="r") as resposta:
            r = Client().post("/instagram/automacao/webhook/", corpo, content_type="application/json",
                              HTTP_X_HUB_SIGNATURE_256=assinatura)
        self.assertEqual(r.status_code, 200)
        resposta.assert_called_once()

    def test_conectar_guarda_token_cifrado_e_liga_os_avisos(self):
        c = conta()
        with mock.patch.object(api, "trocar_codigo", return_value={"access_token": "curto", "user_id": "app1", "permissions": "a,b"}), \
                mock.patch.object(api, "token_longo", return_value={"access_token": "longo", "expires_in": 5184000}), \
                mock.patch.object(api, "perfil", return_value={"id": "app1", "user_id": IG_ID, "username": "achadosdabia"}), \
                mock.patch.object(api, "ligar_avisos") as ligar:
            ig = conexao.conectar(c, "codigo", "https://x/retorno/")
        self.assertEqual((ig.ig_id, ig.app_user_id, ig.username, ig.token), (IG_ID, "app1", "achadosdabia", "longo"))
        self.assertNotIn("longo", ig.token_cifrado)
        self.assertTrue(ig.avisos_ligados)
        ligar.assert_called_once_with("longo")

    def test_mesmo_instagram_em_duas_contas_nao(self):
        conectada(conta(email="outra@exemplo.com"))
        with mock.patch.object(api, "trocar_codigo", return_value={"access_token": "c"}), \
                mock.patch.object(api, "token_longo", return_value={"access_token": "l"}), \
                mock.patch.object(api, "perfil", return_value={"user_id": IG_ID, "username": "x"}):
            with self.assertRaises(conexao.ErroConexao):
                conexao.conectar(conta(), "codigo", "https://x/")

    def test_renova_so_o_que_esta_vencendo(self):
        from datetime import timedelta

        from django.utils import timezone

        agora = timezone.now()
        ig = conectada(conta())
        ContaInstagram.objects.filter(pk=ig.pk).update(token_expira_em=agora + timedelta(days=5), token_renovado_em=agora - timedelta(days=50))
        nova = conectada(conta(email="nova@exemplo.com"), ig_id="2", username="nova")
        ContaInstagram.objects.filter(pk=nova.pk).update(token_expira_em=agora + timedelta(days=55), token_renovado_em=agora)
        with mock.patch.object(api, "renovar_token", return_value={"access_token": "novo", "expires_in": 5184000}) as renovar:
            conexao.renovar_tokens(agora)
        renovar.assert_called_once_with("tok")
        self.assertEqual(ContaInstagram.objects.get(pk=ig.pk).token, "novo")

    def test_desautorizar_apaga_e_pausa(self):
        c = conta()
        ig = conectada(c)
        ContaInstagram.objects.filter(pk=ig.pk).update(app_user_id="app1")
        a = Automacao.objects.create(conta=c, nome="x", respostas="ok")
        corpo = base64.urlsafe_b64encode(json.dumps({"user_id": "app1", "algorithm": "HMAC-SHA256"}).encode()).decode().rstrip("=")
        assinatura = base64.urlsafe_b64encode(hmac.new(SEGREDO.encode(), corpo.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        cliente = Client(HTTP_HOST=HOST)
        with override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"]):
            self.assertEqual(cliente.post("/instagram/desautorizar/", {"signed_request": "x.y"}).status_code, 400)
            self.assertEqual(cliente.post("/instagram/apagar-dados/", {"signed_request": f"{assinatura}.{corpo}"}).status_code, 200)
        self.assertFalse(ContaInstagram.objects.exists())
        a.refresh_from_db()
        self.assertFalse(a.ativa)


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}",
                   APPFILIADO_INSTAGRAM_APP_ID="123", APPFILIADO_INSTAGRAM_APP_SECRET=SEGREDO)
class TestTelas(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST=HOST)

    def entrar(self, c):
        self.client.post("/entrar/", {"email": c.email, "senha": SENHA})

    def test_sem_a_chave_de_teste_tudo_404(self):
        self.entrar(conta(beta=False))
        for url in ("/estudio/automacoes/", "/estudio/automacoes/nova/", "/estudio/instagram/conectar/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_conectar_manda_para_o_instagram_e_volta_conferindo_o_state(self):
        c = conta()
        self.entrar(c)
        r = self.client.get("/estudio/instagram/conectar/")
        self.assertTrue(r["Location"].startswith("https://www.instagram.com/oauth/authorize?"))
        self.assertIn("redirect_uri=https%3A%2F%2Fapp.appfiliado.com.br%2Festudio%2Finstagram%2Fretorno%2F", r["Location"])
        self.client.get("/estudio/instagram/retorno/?code=abc&state=errado")
        self.assertFalse(ContaInstagram.objects.exists())
        self.client.get("/estudio/instagram/conectar/")
        state = self.client.session["instagram_state"]
        with mock.patch.object(conexao, "conectar", return_value=ContaInstagram(username="bia")) as conectar:
            self.client.get(f"/estudio/instagram/retorno/?code=abc%23_&state={state}")
        conectar.assert_called_once_with(c, "abc", f"https://{HOST}/estudio/instagram/retorno/")

    def test_criar_automacao_premium_com_o_link_do_post(self):
        from estudio.models import PostInstagram

        c = conta()
        conectada(c)
        self.entrar(c)
        post = PostInstagram.objects.create(conta=c, nome="Garrafa", produto={"nome": "Garrafa", "link": "https://s.shopee.com.br/abc"})
        pagina = self.client.get(f"/estudio/automacoes/nova/?post={post.pk}")
        self.assertContains(pagina, "https://s.shopee.com.br/abc")
        r = self.client.post("/estudio/automacoes/nova/", {
            "nome": "Garrafa", "gatilho": "comentario", "palavras": "QUERO", "responder_comentario": "on",
            "respostas": "Te mandei!", "enviar_dm": "on", "texto_dm": "Aqui:", "link": "https://s.shopee.com.br/abc",
            "ativa": "on", "post": post.pk})
        a = Automacao.objects.get()
        self.assertRedirects(r, f"/estudio/automacoes/{a.pk}/", fetch_redirect_response=False)
        self.assertEqual(a.post_estudio, post)
        self.assertContains(self.client.get("/estudio/automacoes/"), "Garrafa")

    def test_direto_sem_palavra_nao_salva_e_standard_nao_cria(self):
        c = conta()
        self.entrar(c)
        r = self.client.post("/estudio/automacoes/nova/", {"nome": "x", "gatilho": "direto", "enviar_dm": "on", "texto_dm": "oi"})
        self.assertContains(r, "No direto, escolha pelo menos uma palavra")
        self.client = Client(HTTP_HOST=HOST)
        self.entrar(conta(modulos="carrosseis", email="std@exemplo.com"))
        self.assertRedirects(self.client.get("/estudio/automacoes/nova/"), "/estudio/automacoes/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/estudio/automacoes/"), "plano Premium")

    def test_automacao_de_outra_conta_nao_abre(self):
        outra = Automacao.objects.create(conta=conta(email="outra@exemplo.com"), nome="x", respostas="ok")
        self.entrar(conta())
        self.assertEqual(self.client.get(f"/estudio/automacoes/{outra.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/estudio/automacoes/{outra.pk}/apagar/").status_code, 404)
