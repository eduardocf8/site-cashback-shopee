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


def conta(modulos="carrosseis_premium, instagram_premium", email="bia@exemplo.com", beta=True):
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
        # Premium: o link vai num botão
        privada.assert_called_once_with("tok", IG_ID, "c1", "Aqui está:", ("Ver produto", "https://s.shopee.com.br/abc"))
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
        msg.assert_called_with("tok", IG_ID, "888", "Link do story", None)  # sem link: só o texto
        W.separar_e_processar(aviso_mensagem("tem cupom?", autor="777", mid="mid2"))
        msg.assert_called_with("tok", IG_ID, "777", "O cupom é X", None)
        W.separar_e_processar(aviso_mensagem("oi", autor="555", mid="mid3"))  # sem a palavra
        W.separar_e_processar(aviso_mensagem("cupom", autor="444", mid="mid4", is_echo=True))  # a própria conta
        self.assertEqual(msg.call_count, 2)

    def test_botao_recusado_vai_em_texto_e_standard_vai_sem_botao(self, msg, privada, resposta):
        privada.side_effect = [api.ErroInstagram("template não suportado"), "d1", "d2"]
        W.separar_e_processar(aviso_comentario("quero"))
        self.assertEqual(privada.call_args_list[1].args, ("tok", IG_ID, "c1", "Aqui está:\n\nhttps://s.shopee.com.br/abc", None))
        self.assertTrue(Disparo.objects.get().dm_ok)
        self.c.modulos_cortesia = "instagram"
        self.c.save()
        W.separar_e_processar(aviso_comentario("quero", autor="2", comentario="c2"))
        self.assertEqual(privada.call_args_list[2].args, ("tok", IG_ID, "c2", "Aqui está:\n\nhttps://s.shopee.com.br/abc", None))

    def test_link_com_sub_id_e_o_que_vai_na_dm(self, msg, privada, resposta):
        self.a.link_afiliado = "https://s.shopee.com.br/comsubid"
        self.a.save()
        W.separar_e_processar(aviso_comentario("quero"))
        self.assertEqual(privada.call_args.args[4], ("Ver produto", "https://s.shopee.com.br/comsubid"))

    def test_standard_so_valem_as_5_ligadas_mais_recentes(self, msg, privada, resposta):
        self.c.modulos_cortesia = "instagram"
        self.c.save()
        for i in range(5):  # 5 mais novas, para outros posts: a "Garrafa" (a mais antiga) fica de fora
            Automacao.objects.create(conta=self.c, nome=f"a{i}", midia_id=f"outro{i}", respostas="ok", texto_dm="oi")
        W.separar_e_processar(aviso_comentario("quero"))
        resposta.assert_not_called()

    def test_plano_standard_so_responde_comentario(self, msg, privada, resposta):
        self.c.modulos_cortesia = "instagram"
        self.c.save()
        Automacao.objects.create(conta=self.c, nome="Story", gatilho=Automacao.STORY, texto_dm="Link do story")
        W.separar_e_processar(aviso_mensagem("🔥", story="s1"))
        msg.assert_not_called()  # resposta a story é do Premium
        W.separar_e_processar(aviso_comentario("quero", autor="1", comentario="c1"))
        self.assertEqual(resposta.call_count, 1)
        self.c.modulos_cortesia = "carrosseis_premium"  # sem o módulo das Automações
        self.c.save()
        W.separar_e_processar(aviso_comentario("quero", autor="3", comentario="c3"))
        self.assertEqual(resposta.call_count, 1)

    def test_post_viral_passa_do_limite_da_hora_vai_para_a_fila_e_sai_depois(self, msg, privada, resposta):
        from datetime import timedelta

        from django.utils import timezone

        with mock.patch.object(W, "LIMITE_POR_HORA", 2):
            for i in range(4):
                W.separar_e_processar(aviso_comentario("quero", autor=str(i), comentario=f"c{i}"))
            self.assertEqual(privada.call_count, 2)
            self.assertEqual(W.na_fila(self.c), 2)
            self.assertEqual(W.enviar_fila(), [])  # a hora ainda está cheia
            # uma hora depois: a fila sai, por ordem de chegada
            Disparo.objects.filter(na_fila=False).update(enviado_em=timezone.now() - timedelta(hours=2))
            self.assertIn("2 resposta(s) da fila", W.enviar_fila()[0])
        self.assertEqual([c.args[2] for c in privada.call_args_list], ["c0", "c1", "c2", "c3"])
        self.assertEqual(W.na_fila(self.c), 0)
        self.assertEqual(Disparo.objects.filter(dm_ok=True).count(), 4)

    def test_fila_respeita_o_prazo_do_instagram(self, msg, privada, resposta):
        from datetime import timedelta

        from django.utils import timezone

        d = Disparo.objects.create(automacao=self.a, evento_id="velho", autor_id="9", na_fila=True)
        Disparo.objects.filter(pk=d.pk).update(criado_em=timezone.now() - timedelta(days=8))
        W.enviar_fila()
        d.refresh_from_db()
        self.assertFalse(d.na_fila)
        self.assertIn("prazo", d.erro)
        privada.assert_not_called()

    def test_erro_do_instagram_fica_no_historico(self, msg, privada, resposta):
        privada.side_effect = api.ErroInstagram("janela de 7 dias")
        W.separar_e_processar(aviso_comentario("quero"))
        d = Disparo.objects.get()
        self.assertTrue(d.resposta_ok)
        self.assertFalse(d.dm_ok)
        self.assertIn("7 dias", d.erro)

    def test_avisos_seguem_tambem_para_a_cash_b(self, msg, privada, resposta):
        # A mesma conta pode estar no Appfiliado e na automação da cash-b: o aviso passa pelos dois.
        for payload in (aviso_comentario("quero", ig_id="outra"), aviso_comentario("quero", comentario="cx", autor="1")):
            self.assertEqual(W.separar_e_processar(payload)["entry"], payload["entry"])
        self.assertEqual(Disparo.objects.count(), 1)


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
        self.assertRedirects(r, "/estudio/automacoes/", fetch_redirect_response=False)  # volta para a lista
        self.assertEqual(a.post_estudio, post)
        self.assertContains(self.client.get("/estudio/automacoes/"), "Garrafa")

    def test_direto_sem_palavra_nao_salva(self):
        self.entrar(conta())
        r = self.client.post("/estudio/automacoes/nova/", {"nome": "x", "gatilho": "direto", "enviar_dm": "on", "texto_dm": "oi"})
        self.assertContains(r, "Para DM, escolha pelo menos uma palavra")

    def test_standard_so_cria_automacao_de_comentario(self):
        c = conta(modulos="instagram", email="std@exemplo.com")
        conectada(c)
        self.entrar(c)
        r = self.client.get("/estudio/automacoes/nova/")
        self.assertContains(r, 'value="story" disabled')
        r = self.client.post("/estudio/automacoes/nova/", {"nome": "x", "gatilho": "story", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi"})
        self.assertContains(r, "do plano Premium das Automações")
        r = self.client.post("/estudio/automacoes/nova/", {"nome": "y", "gatilho": "comentario", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi"})
        self.assertRedirects(r, "/estudio/automacoes/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/estudio/automacoes/"), "Sem limite por mês")

    def test_standard_ate_5_ligadas(self):
        c = conta(modulos="instagram", email="cinco@exemplo.com")
        conectada(c)
        self.entrar(c)
        for i in range(5):
            Automacao.objects.create(conta=c, nome=f"a{i}", respostas="ok", texto_dm="oi")
        dados = {"nome": "sexta", "gatilho": "comentario", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi", "ativa": "on"}
        self.assertContains(self.client.post("/estudio/automacoes/nova/", dados), "até 5 automações ligadas")
        del dados["ativa"]
        self.assertEqual(self.client.post("/estudio/automacoes/nova/", dados).status_code, 302)  # desligada pode
        sexta = Automacao.objects.get(nome="sexta")
        self.client.post(f"/estudio/automacoes/{sexta.pk}/ligar/")
        sexta.refresh_from_db()
        self.assertFalse(sexta.ativa)
        self.assertContains(self.client.get("/estudio/automacoes/"), "5 de 5 automações ligadas")

    def test_premium_gera_o_link_com_o_sub_id(self):
        c = conta(email="sub@exemplo.com")
        conectada(c)
        self.entrar(c)
        dados = {"nome": "Garrafa", "gatilho": "comentario", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi",
                 "link": "https://s.shopee.com.br/abc", "sub_id": "garrafa", "botao": "on", "texto_botao": "Quero!", "ativa": "on"}
        with mock.patch("painel.conversor.converter", return_value={"texto": "https://s.shopee.com.br/novo"}) as conv:
            self.client.post("/estudio/automacoes/nova/", dados)
            a = Automacao.objects.get(nome="Garrafa")
            self.assertEqual((a.link_afiliado, a.sub_id, a.texto_botao), ("https://s.shopee.com.br/novo", "garrafa", "Quero!"))
            self.assertEqual(conv.call_args.args[3], "garrafa")
            self.client.post(f"/estudio/automacoes/{a.pk}/", dados)  # nada mudou: não gera de novo
            self.assertEqual(conv.call_count, 1)
        r = self.client.post("/estudio/automacoes/nova/", {**dados, "nome": "x", "sub_id": "com espaço"})
        self.assertContains(r, "só pode ter letras e números")

    def test_so_estudio_nao_abre_automacoes_mas_conecta_e_publica(self):
        self.entrar(conta(modulos="carrosseis_premium", email="estudio@exemplo.com"))
        r = self.client.get("/estudio/automacoes/")
        self.assertContains(r, "Não incluso no seu plano")
        self.assertEqual(self.client.post("/estudio/automacoes/nova/").status_code, 403)
        self.assertEqual(self.client.get("/estudio/instagram/conectar/").status_code, 302)
        self.assertContains(self.client.get("/estudio/publicacoes/"), "Conecte o seu Instagram")

    def test_automacao_de_outra_conta_nao_abre(self):
        outra = Automacao.objects.create(conta=conta(email="outra@exemplo.com"), nome="x", respostas="ok")
        self.entrar(conta())
        self.assertEqual(self.client.get(f"/estudio/automacoes/{outra.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/estudio/automacoes/{outra.pk}/excluir/").status_code, 404)


class TestAvisosRecebidos(TestCase):
    def test_guarda_resumo_de_qualquer_conta_e_mostra_na_tela(self):
        from .models import AvisoRecebido

        W.separar_e_processar(aviso_comentario("quero muito", ig_id="qualquer"))
        W.separar_e_processar(aviso_mensagem("🔥", story="s1", ig_id=IG_ID))
        self.assertEqual(AvisoRecebido.objects.get(ig_id="qualquer").resumo, "@maria comentou: quero muito")
        self.assertEqual(AvisoRecebido.objects.get(ig_id=IG_ID).resumo, "Resposta a story: 🔥")


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}",
                   APPFILIADO_INSTAGRAM_APP_ID="123", APPFILIADO_INSTAGRAM_APP_SECRET=SEGREDO)
class TestJanelaHistoricoEExcluir(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST=HOST)
        self.c = conta()
        self.client.post("/entrar/", {"email": self.c.email, "senha": SENHA})

    def test_login_na_janela_volta_fechando_a_janela(self):
        self.client.get("/estudio/instagram/conectar/?janela=1")
        state = self.client.session["instagram_state"]
        with mock.patch.object(conexao, "conectar", return_value=ContaInstagram(username="bia")):
            r = self.client.get(f"/estudio/instagram/retorno/?code=abc&state={state}")
        self.assertContains(r, "window.opener.location.href = destino")
        self.assertContains(r, "/estudio/automacoes/")
        # sem a janela, continua voltando direto
        self.client.get("/estudio/instagram/conectar/")
        state = self.client.session["instagram_state"]
        with mock.patch.object(conexao, "conectar", return_value=ContaInstagram(username="bia")):
            r = self.client.get(f"/estudio/instagram/retorno/?code=abc&state={state}")
        self.assertRedirects(r, "/estudio/automacoes/", fetch_redirect_response=False)

    def test_historico_mostra_so_as_respostas_da_conta_e_filtra(self):
        a = Automacao.objects.create(conta=self.c, nome="Garrafa", respostas="ok")
        b = Automacao.objects.create(conta=self.c, nome="Story", gatilho=Automacao.STORY, texto_dm="oi")
        Disparo.objects.create(automacao=a, evento_id="1", autor_username="maria", texto="quero", resposta_ok=True, dm_ok=True)
        Disparo.objects.create(automacao=b, evento_id="2", autor_username="joao", texto="🔥", dm_ok=True)
        outra = Automacao.objects.create(conta=conta(email="outra@exemplo.com"), nome="Dela", respostas="ok")
        Disparo.objects.create(automacao=outra, evento_id="3", autor_username="intruso")
        pagina = self.client.get("/estudio/automacoes/historico/")
        self.assertContains(pagina, "@maria")
        self.assertContains(pagina, "@joao")
        self.assertNotContains(pagina, "@intruso")
        filtrada = self.client.get(f"/estudio/automacoes/historico/?automacao={b.pk}")
        self.assertNotContains(filtrada, "@maria")
        self.assertContains(filtrada, "@joao")

    def test_excluir_pela_lista(self):
        a = Automacao.objects.create(conta=self.c, nome="Garrafa", respostas="ok")
        conectada(self.c)
        self.assertContains(self.client.get("/estudio/automacoes/"), f"/estudio/automacoes/{a.pk}/excluir/")
        self.assertRedirects(self.client.post(f"/estudio/automacoes/{a.pk}/excluir/"), "/estudio/automacoes/", fetch_redirect_response=False)
        self.assertFalse(Automacao.objects.exists())
