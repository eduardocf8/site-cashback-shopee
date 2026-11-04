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
from .models import AnuncioVisto, Automacao, ContaInstagram, Disparo

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
        patcher = mock.patch.object(api, "stories_no_ar", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, nome="Garrafa", gatilho=Automacao.COMENTARIO, midia_id="m1",
                                          palavras="quero, link", respostas="Te mandei no direto, {nome}!",
                                          texto_dm="Aqui está:", link="https://s.shopee.com.br/abc")

    def test_comentario_com_palavra_responde_e_manda_dm(self, msg, privada, resposta):
        W.separar_e_processar(aviso_comentario("Eu QUÉRO muito!"))
        resposta.assert_called_once_with("tok", "c1", "Te mandei no direto, @maria!")
        # Premium: o link vai num botão
        privada.assert_called_once_with("tok", IG_ID, "c1", "Aqui está:", [("Ver produto", "https://s.shopee.com.br/abc")])
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
        self.assertEqual(privada.call_args.args[4], [("Ver produto", "https://s.shopee.com.br/comsubid")])

    def test_ate_3_botoes_e_sem_botao(self, msg, privada, resposta):
        self.a.botoes, self.a.texto_botao = 3, "Ver garrafa"
        self.a.botoes_extras = [
            {"texto": "Entrar no grupo", "link": "https://appfiliado.com.br/bia/grupo-vip/", "link_afiliado": ""},
            {"texto": "Mais achadinhos", "link": "https://s.shopee.com.br/xyz", "link_afiliado": "https://s.shopee.com.br/comsubid"}]
        self.a.save()
        privada.side_effect = ["d1", api.ErroInstagram("template não suportado"), "d3", "d4", "d5"]
        W.separar_e_processar(aviso_comentario("quero"))
        botoes = [("Ver garrafa", "https://s.shopee.com.br/abc"), ("Entrar no grupo", "https://appfiliado.com.br/bia/grupo-vip/"),
                  ("Mais achadinhos", "https://s.shopee.com.br/comsubid")]  # o link com o Sub ID
        self.assertEqual(privada.call_args.args[3:], ("Aqui está:", botoes))

        W.separar_e_processar(aviso_comentario("quero", autor="2", comentario="c2"))  # Instagram recusou: links no texto
        texto = ("Aqui está:\n\nVer garrafa: https://s.shopee.com.br/abc\nEntrar no grupo: https://appfiliado.com.br/bia/grupo-vip/"
                 "\nMais achadinhos: https://s.shopee.com.br/comsubid")
        self.assertEqual(privada.call_args.args[3:], (texto, None))

        Automacao.objects.filter(pk=self.a.pk).update(botoes=2)  # só os 2 primeiros
        W.separar_e_processar(aviso_comentario("quero", autor="3", comentario="c3"))
        self.assertEqual(privada.call_args.args[4], botoes[:2])
        Automacao.objects.filter(pk=self.a.pk).update(botoes=0)  # sem botão: o link no texto
        W.separar_e_processar(aviso_comentario("quero", autor="4", comentario="c4"))
        self.assertEqual(privada.call_args.args[3:], ("Aqui está:\n\nhttps://s.shopee.com.br/abc", None))

    def test_standard_so_valem_as_5_ligadas_mais_recentes(self, msg, privada, resposta):
        self.c.modulos_cortesia = "instagram"
        self.c.save()
        for i in range(5):  # 5 mais novas, para outros posts: a "Garrafa" (a mais antiga) fica de fora
            Automacao.objects.create(conta=self.c, nome=f"a{i}", midia_id=f"outro{i}", respostas="ok", texto_dm="oi")
        W.separar_e_processar(aviso_comentario("quero"))
        resposta.assert_not_called()

    def test_automacao_de_outro_instagram_nao_responde(self, msg, privada, resposta):
        self.a.ig_id, self.a.ig_username = "outro", "usecashb"
        self.a.save()
        W.separar_e_processar(aviso_comentario("quero"))
        resposta.assert_not_called()
        self.a.ig_id = IG_ID  # a do Instagram conectado responde
        self.a.save()
        W.separar_e_processar(aviso_comentario("quero"))
        resposta.assert_called_once()

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

    def test_automacao_guarda_o_instagram_e_a_lista_mostra(self):
        c = conta(email="contas@exemplo.com")
        conectada(c)
        self.entrar(c)
        dados = {"nome": "Nova", "gatilho": "comentario", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi", "ativa": "on"}
        self.client.post("/estudio/automacoes/nova/", dados)
        self.assertEqual(Automacao.objects.get(nome="Nova").ig_username, "achadosdabia")
        Automacao.objects.create(conta=c, nome="Antiga", ig_id="outro", ig_username="usecashb", respostas="ok", texto_dm="oi")
        r = self.client.get("/estudio/automacoes/")
        self.assertContains(r, "@achadosdabia")
        self.assertContains(r, "é do @usecashb, que não está conectado")

    def test_sem_instagram_nao_cria_automacao(self):
        self.entrar(conta(email="semig@exemplo.com"))
        r = self.client.post("/estudio/automacoes/nova/", {"nome": "x", "gatilho": "comentario", "enviar_dm": "on", "texto_dm": "oi"})
        self.assertContains(r, "Conecte o seu Instagram antes de criar a automação.")

    def test_standard_ate_5_ligadas(self):
        c = conta(modulos="instagram", email="cinco@exemplo.com")
        conectada(c)
        self.entrar(c)
        for i in range(5):
            Automacao.objects.create(conta=c, nome=f"a{i}", ig_id=IG_ID, respostas="ok", texto_dm="oi")
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

    def test_contador_de_botoes(self):
        c = conta(email="botoes@exemplo.com")
        conectada(c)
        self.entrar(c)
        dados = {"nome": "Garrafa", "gatilho": "comentario", "palavras": "quero", "enviar_dm": "on", "texto_dm": "oi",
                 "link": "https://s.shopee.com.br/abc", "sub_id": "garrafa", "botoes": "2", "texto_botao": "Ver garrafa",
                 "texto_botao_2": "  Mais   ofertas ", "link_botao_2": "https://s.shopee.com.br/dois",
                 "texto_botao_3": "Grupo", "link_botao_3": "https://chat.whatsapp.com/x", "ativa": "on"}
        def convertido(conta_, link, modo, sub_id, ferramenta):
            return {"texto": link + "-" + sub_id}

        with mock.patch("painel.conversor.converter", side_effect=convertido) as conv:
            self.client.post("/estudio/automacoes/nova/", dados)
            a = Automacao.objects.get(nome="Garrafa")
            self.assertEqual((a.botoes, a.texto_botao, a.link_afiliado), (2, "Ver garrafa", "https://s.shopee.com.br/abc-garrafa"))
            self.assertEqual(a.botoes_extras, [  # o 3º fica guardado para quando voltar a 3
                {"texto": "Mais ofertas", "link": "https://s.shopee.com.br/dois", "link_afiliado": "https://s.shopee.com.br/dois-garrafa"},
                {"texto": "Grupo", "link": "https://chat.whatsapp.com/x", "link_afiliado": ""}])
            self.assertEqual(conv.call_count, 2)
            self.client.post(f"/estudio/automacoes/{a.pk}/", {**dados, "botoes": "3"})  # 3º fora da Shopee: vai como está
            self.assertEqual(conv.call_count, 2)  # nada mudou nos outros: não gera de novo
        a.refresh_from_db()
        self.assertEqual(a.botoes, 3)

        html = self.client.get(f"/estudio/automacoes/{a.pk}/").content.decode()
        self.assertIn('<output id="ig-botoes-num" aria-live="polite">3</output>', html)
        self.assertIn('value="Mais ofertas"', html)
        self.assertIn('name="link_botao_3" value="https://chat.whatsapp.com/x"', html)

        r = self.client.post(f"/estudio/automacoes/{a.pk}/", {**dados, "texto_botao_2": "", "link_botao_3": "grupo"})
        self.assertContains(r, "Botão 2: escreva o texto.")
        r = self.client.post(f"/estudio/automacoes/{a.pk}/", {**dados, "botoes": "3", "link_botao_3": "grupo"})
        self.assertContains(r, "Botão 3: coloque um link completo")
        r = self.client.post(f"/estudio/automacoes/{a.pk}/", {**dados, "link": ""})
        self.assertContains(r, "Coloque o link do botão 1")
        self.client.post(f"/estudio/automacoes/{a.pk}/", {**dados, "botoes": "9"})
        a.refresh_from_db()
        self.assertEqual(a.botoes, 3)  # o Instagram aceita até 3

    def test_standard_ve_o_contador_travado(self):
        c = conta(modulos="instagram", email="std@exemplo.com")
        conectada(c)
        self.entrar(c)
        a = Automacao.objects.create(conta=c, nome="a", ig_id=IG_ID, respostas="ok", texto_dm="oi", link="https://s.shopee.com.br/a")
        html = self.client.get(f"/estudio/automacoes/{a.pk}/").content.decode()
        self.assertIn('<output id="ig-botoes-num" aria-live="polite">0</output>', html)
        self.assertNotIn('name="botoes"', html)
        self.assertNotIn('name="texto_botao_2"', html)
        self.client.post(f"/estudio/automacoes/{a.pk}/", {"nome": "a", "gatilho": "comentario", "responder_comentario": "on",
                                                           "respostas": "ok", "enviar_dm": "on", "texto_dm": "oi",
                                                           "link": "https://s.shopee.com.br/a", "botoes": "3"})
        a.refresh_from_db()
        self.assertEqual(a.botoes, 1)  # fica o que estava

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
        aviso = AvisoRecebido.objects.get(ig_id=IG_ID)
        self.assertEqual(aviso.resumo, "Resposta a story (s1): 🔥")
        # a mensagem fica como veio, para conferir no admin o que o Instagram manda
        self.assertEqual(aviso.bruto["message"]["reply_to"]["story"]["id"], "s1")

    def test_admin_mostra_o_que_veio(self):
        from django.contrib.auth import get_user_model

        from .models import AvisoRecebido

        W.separar_e_processar(aviso_de_anuncio("quero", anuncio="120252364231080096", story="s-anuncio", ig_id="qualquer"))
        dono = get_user_model().objects.create_superuser("dono", "dono@exemplo.com", "senha-boa-123")
        client = Client()
        client.force_login(dono)
        aviso = AvisoRecebido.objects.get()
        self.assertEqual(aviso.resumo, "Mensagem de anúncio (120252364231080096): quero")
        r = client.get(f"/admin/instagram_painel/avisorecebido/{aviso.pk}/change/")
        self.assertContains(r, "120252364231080096")
        self.assertContains(r, "s-anuncio")
        self.assertEqual(client.get("/admin/instagram_painel/anunciovisto/").status_code, 200)


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
        # avisa a página principal (sem depender do window.opener, que o Instagram corta) e fecha
        self.assertContains(r, 'new BroadcastChannel("appfiliado-instagram").postMessage("pronto")')
        self.assertContains(r, "window.close()")
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


def aviso_de_anuncio(texto="", autor="888", mid="mid1", anuncio="120200000000000001", titulo="Garrafa térmica", story=None, post=None, ig_id=IG_ID):
    """Mensagem que veio de um anúncio: o Instagram manda o ID do anúncio no referral."""
    contexto = {"ad_title": titulo, "photo_url": "https://cdn.exemplo/garrafa.jpg"}
    if post:
        contexto["post_id"] = post
    referral = {"ref": "", "ad_id": anuncio, "source": "ADS", "type": "OPEN_THREAD", "ads_context_data": contexto}
    return aviso_mensagem(texto, autor=autor, mid=mid, story=story, ig_id=ig_id, referral=referral)


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}",
                   APPFILIADO_INSTAGRAM_APP_ID="123", APPFILIADO_INSTAGRAM_APP_SECRET=SEGREDO)
@mock.patch.object(api, "mensagem", return_value="d2")
class TestRespostaDeAnuncio(TestCase):
    """Dois anúncios de reels (que também rodam nos stories) com a mesma palavra: cada um com a sua resposta."""

    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        patcher = mock.patch.object(api, "stories_no_ar", return_value=[{"id": "s-do-perfil"}])
        self.stories = patcher.start()
        self.addCleanup(patcher.stop)

    def automacao(self, nome, midia_id="", texto="Link", palavras="quero"):
        return Automacao.objects.create(conta=self.c, nome=nome, gatilho=Automacao.STORY, midia_id=midia_id,
                                        palavras=palavras, texto_dm=texto)

    def test_cada_anuncio_responde_com_a_sua_automacao_e_fica_na_lista(self, msg):
        garrafa = self.automacao("Garrafa", "ad:111", "Link da garrafa")
        fone = self.automacao("Fone", "ad:222", "Link do fone")
        W.separar_e_processar(aviso_de_anuncio("quero", anuncio="111", titulo="Garrafa térmica"))
        W.separar_e_processar(aviso_de_anuncio("QUERO!", autor="777", mid="mid2", anuncio="222", titulo="Fone sem fio"))
        self.assertEqual(msg.call_args_list[0].args[3], "Link da garrafa")
        self.assertEqual(msg.call_args_list[1].args[3], "Link do fone")
        self.assertEqual({d.automacao for d in Disparo.objects.all()}, {garrafa, fone})
        vistos = {v.chave: v for v in AnuncioVisto.objects.all()}
        self.assertEqual(set(vistos), {"ad:111", "ad:222"})
        self.assertEqual(vistos["ad:111"].titulo, "Garrafa térmica")
        self.assertEqual(vistos["ad:111"].imagem, "https://cdn.exemplo/garrafa.jpg")
        self.stories.assert_not_called()  # com o ID do anúncio não precisa perguntar ao Instagram

    def test_anuncio_vem_antes_de_todos_os_stories_e_outro_anuncio_fica_de_fora(self, msg):
        self.automacao("Garrafa", "ad:111", "Link da garrafa")
        self.automacao("Todos", "", "Link geral")
        # resposta ao story do anúncio da garrafa
        W.separar_e_processar(aviso_de_anuncio("quero", anuncio="111", story="s-anuncio"))
        self.assertEqual(msg.call_args.args[3], "Link da garrafa")
        # outro anúncio, mandado como DM (anúncio de mensagem): nem a da garrafa nem a de todos os stories
        W.separar_e_processar(aviso_de_anuncio("quero", autor="777", mid="mid2", anuncio="333"))
        self.assertEqual(msg.call_count, 1)
        # resposta a um story do perfil: a de todos os stories
        W.separar_e_processar(aviso_mensagem("quero", autor="666", mid="mid3", story="s-do-perfil"))
        self.assertEqual(msg.call_args.args[3], "Link geral")

    def test_story_do_anuncio_sem_o_id_reconhece_pelo_que_ja_veio_antes(self, msg):
        self.automacao("Garrafa", "ad:111", "Link da garrafa")
        W.separar_e_processar(aviso_de_anuncio("oi", anuncio="111", story="s-anuncio"))  # sem a palavra: só guarda
        W.separar_e_processar(aviso_mensagem("quero", autor="777", mid="mid2", story="s-anuncio"))  # sem referral
        self.assertEqual(msg.call_args.args[3], "Link da garrafa")

    def test_story_fora_do_perfil_sem_nada_do_anuncio_tambem_entra_na_lista(self, msg):
        W.separar_e_processar(aviso_mensagem("quero", story="s-anuncio"))
        W.separar_e_processar(aviso_mensagem("quero", autor="777", mid="mid2", story="s-do-perfil"))
        fora, do_perfil = AnuncioVisto.objects.get(chave="story:s-anuncio"), AnuncioVisto.objects.get(chave="story:s-do-perfil")
        self.assertFalse(fora.do_perfil)
        self.assertTrue(do_perfil.do_perfil)
        self.automacao("Garrafa", "story:s-anuncio", "Link da garrafa")
        W.separar_e_processar(aviso_mensagem("quero", autor="555", mid="mid3", story="s-anuncio"))
        self.assertEqual(msg.call_args.args[3], "Link da garrafa")
        self.assertEqual(AnuncioVisto.objects.get(chave="story:s-anuncio").respostas, 2)
        self.assertEqual(self.stories.call_count, 2)  # uma vez por story novo

    def test_dm_de_anuncio_sem_automacao_do_anuncio_cai_na_de_dm(self, msg):
        Automacao.objects.create(conta=self.c, nome="DM", gatilho=Automacao.DIRETO, palavras="quero", texto_dm="Link da DM")
        W.separar_e_processar(aviso_de_anuncio("quero", anuncio="999"))
        self.assertEqual(msg.call_args.args[3], "Link da DM")

    def test_tela_lista_os_anuncios_e_aceita_o_id_colado(self, msg):
        AnuncioVisto.objects.create(ig_id=IG_ID, chave="ad:111", anuncio_id="111", titulo="Garrafa térmica", respostas=3, ultimo_texto="quero")
        AnuncioVisto.objects.create(ig_id=IG_ID, chave="story:s-do-perfil", story_id="s-do-perfil", do_perfil=True)
        AnuncioVisto.objects.create(ig_id="outra", chave="ad:555", anuncio_id="555")
        cache.clear()
        client = Client(HTTP_HOST=HOST)
        client.post("/entrar/", {"email": self.c.email, "senha": SENHA})
        r = client.get("/estudio/instagram/midias/?tipo=anuncio")
        self.assertEqual(r.status_code, 200, r.content[:300])
        itens = r.json()["itens"]
        self.assertEqual([i["id"] for i in itens], ["ad:111"])
        self.assertEqual(itens[0]["legenda"], "Garrafa térmica")
        self.assertIn("3 respostas", itens[0]["detalhe"])
        self.assertContains(client.get("/estudio/automacoes/nova/"), "Um anúncio")
        dados = {"nome": "Fone", "gatilho": "story", "palavras": "", "enviar_dm": "on", "texto_dm": "Aqui:",
                 "link": "https://s.shopee.com.br/abc", "ativa": "on", "anuncio_colado": " 120 2120 0000 01 "}
        r = client.post("/estudio/automacoes/nova/", dados)
        self.assertEqual(r.status_code, 302)
        a = Automacao.objects.get()
        self.assertEqual((a.midia_id, a.midia_legenda), ("ad:1202120000001", "Anúncio 1202120000001"))
        self.assertTrue(a.e_anuncio)
        self.assertContains(client.get("/estudio/automacoes/"), "Respondeu o anúncio")
