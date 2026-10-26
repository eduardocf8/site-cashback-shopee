"""Estúdio Instagram no painel do afiliado (em teste: só para contas com a chave ligada)."""

import io
import json
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from carrosseis.models import UsoCarrossel
from licencas.models import ContaAppfiliado
from painel import cripto
from painel import modulos as mod

from . import afiliados as A
from . import ia
from .models import ImagemAfiliado, MarcaAfiliado, PostInstagram

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
PRODUTO = {"nome": "Garrafa Térmica Inox 1 Litro", "preco": 47.9, "de": 89.9, "desconto": 47, "nota": 4.8, "vendas": 5400,
           "imagem": "https://down-br.img.susercontent.com/file/x", "loja": "Loja", "link": "https://s.shopee.com.br/abc",
           "item_id": "1", "link_original": "https://shopee.com.br/x"}


def conta(modulos="carrosseis_premium", beta=True, email="bia@exemplo.com"):
    c = ContaAppfiliado.objects.create(email=email, modulos_cortesia=modulos, beta_estudio_instagram=beta,
                                       shopee_app_id="123", shopee_secret_cifrado=cripto.cifrar("segredo"))
    c.definir_senha(SENHA)
    c.save()
    return c


def png(tamanho=(40, 30), modo="RGB", nome="foto.png"):
    saida = io.BytesIO()
    Image.new(modo, tamanho, (200, 30, 30, 120) if modo == "RGBA" else (200, 30, 30)).save(saida, "PNG")
    return SimpleUploadedFile(nome, saida.getvalue(), content_type="image/png")


def resposta_ia(dados):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=dados)])


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST=HOST)

    def entrar(self, c):
        self.client.post("/entrar/", {"email": c.email, "senha": SENHA})

    def salvar(self, post, dados):
        return self.client.post(f"/estudio/{post.pk}/salvar/", json.dumps(dados), content_type="application/json")


class TestSoParaQuemTesta(Base):
    def test_sem_a_chave_nada_aparece(self):
        c = conta(beta=False)
        self.entrar(c)
        self.assertNotContains(self.client.get("/"), "Estúdio Instagram")
        self.assertEqual(self.client.get("/estudio/").status_code, 404)
        self.assertEqual(self.client.get("/m/estudio_instagram/").status_code, 404)
        post = PostInstagram.objects.create(conta=c, slides=[{"tipo": "capa", "fundo": {"modo": "cor", "cor": "tema"}}])
        for url in (f"/estudio/{post.pk}/", "/estudio/minha-marca/", "/estudio/imagens/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(self.salvar(post, {"nome": "x"}).status_code, 404)

    def test_com_a_chave_aparece_no_menu(self):
        self.entrar(conta())
        resposta = self.client.get("/estudio/")
        self.assertContains(resposta, "Estúdio Instagram")
        self.assertContains(resposta, "Achado do dia")  # os modelos
        item = mod.POR_SLUG["estudio_instagram"]
        self.assertTrue(mod.ve_beta(item, SimpleNamespace(beta_estudio_instagram=True)))
        self.assertFalse(mod.ve_beta(item, None))

    def test_lancamento_troca_carrosseis_pelo_estudio_e_automacoes(self):
        estudio, automacoes, carrosseis = (mod.POR_SLUG[s] for s in ("estudio_instagram", "automacoes_instagram", "carrosseis"))
        testa, cliente = SimpleNamespace(beta_estudio_instagram=True), SimpleNamespace(beta_estudio_instagram=False)
        # antes do lançamento: quem testa já vê como vai ficar; o cliente segue com o Carrosséis
        self.assertEqual([mod.ve_beta(i, testa) for i in (estudio, automacoes, carrosseis)], [True, True, False])
        self.assertEqual([mod.ve_beta(i, cliente) for i in (estudio, automacoes, carrosseis)], [False, False, True])
        with self.settings(APPFILIADO_LANCAMENTO_INSTAGRAM=True):
            self.assertEqual([mod.ve_beta(i, cliente) for i in (estudio, automacoes, carrosseis)], [True, True, False])

    def test_sem_o_modulo_mostra_o_convite(self):
        c = conta(modulos="whatsapp")
        self.entrar(c)
        self.assertContains(self.client.get("/estudio/"), "Não incluso no seu plano")
        post = PostInstagram.objects.create(conta=c)
        self.assertEqual(self.salvar(post, {"nome": "x"}).status_code, 403)

    def test_post_de_outra_conta_nao_abre(self):
        outro = PostInstagram.objects.create(conta=conta(email="outra@exemplo.com"))
        self.entrar(conta())
        self.assertEqual(self.client.get(f"/estudio/{outro.pk}/").status_code, 404)


class TestCriarEEditar(Base):
    def test_de_um_modelo_abre_o_editor(self):
        c = conta()
        self.entrar(c)
        resposta = self.client.post("/estudio/novo/", {"como": "modelo", "modelo": "achado"})
        post = PostInstagram.objects.get(conta=c)
        self.assertRedirects(resposta, f"/estudio/{post.pk}/", fetch_redirect_response=False)
        self.assertEqual((post.nome, post.formato, post.tema, len(post.slides)), ("Achado do dia", "retrato", "verde", 4))
        editor = self.client.get(f"/estudio/{post.pk}/")
        self.assertContains(editor, "marca-afiliado")
        self.assertContains(editor, '"modo": "completo"')

    @override_settings(ANTHROPIC_API_KEY="")
    def test_do_link_sem_ia_sai_do_modelo_com_os_dados_do_produto(self):
        c = conta()
        self.entrar(c)
        with mock.patch("carrosseis.servicos.produto_do_link", return_value=dict(PRODUTO)):
            self.client.post("/estudio/novo/", {"como": "produto", "link": "https://s.shopee.com.br/abc"})
        post = PostInstagram.objects.get(conta=c)
        preco = next(s for s in post.slides if s["tipo"] == "preco")
        self.assertEqual((preco["preco"], preco["de"], preco["desconto"]), ("R$ 47,90", "R$ 89,90", "-47%"))
        self.assertEqual(post.slides[0]["foto"], PRODUTO["imagem"])
        self.assertNotIn("item_id", post.produto)

    @override_settings(ANTHROPIC_API_KEY="chave-de-teste")
    def test_do_link_com_ia_conta_o_uso_e_nao_deixa_inventar_preco(self):
        c = conta()
        self.entrar(c)
        feito = {"nome": "Garrafa", "legenda": "Achei!", "slides": [
            {"tipo": "capa", "fundo": {"modo": "cor", "cor": "tema"}, "titulo": "Café *quente*"},
            {"tipo": "preco", "fundo": {"modo": "cor", "cor": "tema"}, "titulo": "Preço", "preco": "R$ 1,00"}]}
        cliente = mock.Mock()
        cliente.beta.messages.create.return_value = resposta_ia(feito)
        with mock.patch("carrosseis.servicos.produto_do_link", return_value=dict(PRODUTO)), mock.patch.object(ia, "_cliente", return_value=cliente):
            self.client.post("/estudio/novo/", {"como": "produto", "link": "https://s.shopee.com.br/abc"})
        post = PostInstagram.objects.get(conta=c)
        self.assertEqual(post.slides[1]["preco"], "R$ 47,90")
        self.assertEqual(post.slides[0]["foto"], PRODUTO["imagem"])
        self.assertEqual(UsoCarrossel.objects.get(conta=c).geracoes, 1)
        pedido = cliente.beta.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Preço agora: R$ 47,90", pedido)  # o produto vai na mensagem; o sistema fica em cache

    def test_standard_salva_sem_ajustes_nem_imagem_de_fundo_nem_cor_da_marca(self):
        c = conta(modulos="carrosseis")
        self.entrar(c)
        post = PostInstagram.objects.create(conta=c, slides=[{"tipo": "capa", "fundo": {"modo": "cor", "cor": "tema"}}])
        self.assertContains(self.client.get(f"/estudio/{post.pk}/"), '"modo": "simples"')
        self.salvar(post, {"nome": "Meu post", "tema": "marca", "slides": [
            {"tipo": "capa", "titulo": "Oi", "capa": True, "ajustes": {"titulo": 1.4},
             "fundo": {"modo": "imagem", "imagem": "/estudio/imagens/1/", "veu": 0.4}}]})
        post.refresh_from_db()
        self.assertEqual(post.nome, "Meu post")
        self.assertEqual(post.tema, "verde")
        self.assertEqual(post.slides[0]["fundo"], {"modo": "cor", "cor": "tema"})
        self.assertNotIn("ajustes", post.slides[0])
        self.assertNotIn("capa", post.slides[0])

    def test_premium_salva_tudo_e_a_miniatura(self):
        c = conta()
        MarcaAfiliado.objects.create(conta=c, cor="#123456")
        self.entrar(c)
        post = PostInstagram.objects.create(conta=c)
        jpeg = io.BytesIO()
        Image.new("RGB", (20, 20)).save(jpeg, "JPEG")
        import base64
        resposta = self.salvar(post, {"nome": "P", "tema": "marca", "formato": "story", "miniatura": "data:image/jpeg;base64," + base64.b64encode(jpeg.getvalue()).decode(),
                                      "slides": [{"tipo": "produto", "titulo": "T", "foto": "javascript:alert(1)", "ajustes": {"titulo": 1.4},
                                                  "fundo": {"modo": "arte", "arte": "ondas", "tom": "claro"}}]})
        self.assertEqual(resposta.status_code, 200)
        post.refresh_from_db()
        self.assertEqual((post.tema, post.formato), ("marca", "story"))
        self.assertEqual(post.slides[0]["ajustes"], {"titulo": 1.4})
        self.assertEqual(post.slides[0]["foto"], "")  # endereço estranho não passa
        self.assertEqual(self.client.get(f"/estudio/{post.pk}/miniatura/")["Content-Type"], "image/jpeg")

    def test_duplicar_e_apagar(self):
        c = conta()
        self.entrar(c)
        post = PostInstagram.objects.create(conta=c, nome="Original")
        self.client.post(f"/estudio/{post.pk}/duplicar/")
        self.assertTrue(PostInstagram.objects.filter(conta=c, nome="Original (cópia)").exists())
        self.client.post(f"/estudio/{post.pk}/apagar/")
        self.assertFalse(PostInstagram.objects.filter(pk=post.pk).exists())


class TestImagensEMarca(Base):
    def test_envia_e_serve_a_imagem_so_para_a_dona(self):
        c = conta(modulos="carrosseis")
        self.entrar(c)
        j = self.client.post("/estudio/imagens/", {"arquivo": png()}).json()
        url = j["imagens"][0]["url"]
        self.assertEqual(self.client.get(url)["Content-Type"], "image/jpeg")
        self.client = Client(HTTP_HOST=HOST)
        self.entrar(conta(email="outra@exemplo.com"))
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_recusa_o_que_nao_e_imagem(self):
        self.entrar(conta())
        resposta = self.client.post("/estudio/imagens/", {"arquivo": SimpleUploadedFile("x.png", b"<svg onload=alert(1)>")})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(ImagemAfiliado.objects.exists())

    def test_png_transparente_continua_png(self):
        self.entrar(conta())
        self.client.post("/estudio/imagens/", {"arquivo": png(modo="RGBA")})
        self.assertEqual(ImagemAfiliado.objects.get().tipo, "image/png")

    def test_standard_so_muda_o_arroba(self):
        c = conta(modulos="carrosseis")
        self.entrar(c)
        self.client.post("/estudio/minha-marca/", {"arroba": "achados.da.bia", "cor": "#FF0000", "nome": "Bia"})
        marca = MarcaAfiliado.objects.get(conta=c)
        self.assertEqual((marca.arroba, marca.cor, marca.nome), ("@achados.da.bia", "#1F3A2E", ""))
        self.assertNotIn("marca", A.temas(c))

    def test_premium_muda_cores_fonte_e_logo(self):
        c = conta()
        self.entrar(c)
        self.client.post("/estudio/minha-marca/", {"arroba": "@bia", "cor": "#ff0000", "cor_destaque": "#00ff00", "fonte": "impacto",
                                                   "logo": png(modo="RGBA", nome="logo.png")})
        marca = MarcaAfiliado.objects.get(conta=c)
        self.assertEqual((marca.cor, marca.cor_destaque, marca.fonte), ("#FF0000", "#00FF00", "impacto"))
        self.assertEqual(self.client.get("/estudio/minha-marca/logo/")["Content-Type"], "image/png")
        self.assertEqual(A.temas(c)["marca"]["a"], "#FF0000")
        self.client.post("/estudio/minha-marca/", {"arroba": "bia com espaço"})
        self.assertEqual(MarcaAfiliado.objects.get(conta=c).arroba, "@bia")


class TestModelosProprios(Base):
    def post_de_produto(self, c):
        foto = PRODUTO["imagem"]
        return PostInstagram.objects.create(conta=c, nome="Garrafa", tema="azul", formato="retrato", produto=dict(PRODUTO), slides=[
            {"tipo": "capa", "fundo": {"modo": "cor", "cor": "tema"}, "titulo": "Café *quente*", "foto": foto, "sem_fundo": True, "desconto": "-47%"},
            {"tipo": "preco", "fundo": {"modo": "cor", "cor": "tema"}, "titulo": "Preço", "preco": "R$ 47,90", "de": "R$ 89,90", "desconto": "-47%"}])

    def test_salva_sem_os_dados_do_produto_e_cria_post_com_ele(self):
        c = conta()
        self.entrar(c)
        post = self.post_de_produto(c)
        j = self.client.post(f"/estudio/{post.pk}/salvar-modelo/", json.dumps({"nome": "Meu achado"}), content_type="application/json").json()
        m = c.modelos_instagram.get()
        self.assertEqual((j["nome"], m.tema, m.produto), ("Meu achado", "azul", True))
        self.assertEqual((m.slides[0]["foto"], m.slides[0]["desconto"]), ("", ""))
        self.assertNotIn("sem_fundo", m.slides[0])
        self.assertEqual(m.slides[1]["preco"], "R$ 0,00")
        self.assertContains(self.client.get("/estudio/"), "Meu achado")
        self.client.post("/estudio/novo/", {"como": "modelo", "modelo": j["codigo"]})
        novo = PostInstagram.objects.exclude(pk=post.pk).get()
        self.assertEqual((novo.nome, novo.tema, novo.slides[0]["titulo"]), ("Meu achado", "azul", "Café *quente*"))

    def test_standard_nao_salva_nem_usa_modelo_proprio(self):
        c = conta(modulos="carrosseis")
        self.entrar(c)
        post = self.post_de_produto(c)
        self.assertEqual(self.client.post(f"/estudio/{post.pk}/salvar-modelo/", "{}", content_type="application/json").status_code, 400)
        from .models import ModeloAfiliado
        m = ModeloAfiliado.objects.create(conta=c, nome="Antigo", slides=post.slides)
        self.assertNotIn(f"meu-{m.pk}", [x["codigo"] for x in A.modelos(c)])
        self.client.post("/estudio/novo/", {"como": "modelo", "modelo": f"meu-{m.pk}"})
        self.assertEqual(PostInstagram.objects.filter(conta=c).count(), 1)

    def test_apaga_so_o_proprio_modelo(self):
        from .models import ModeloAfiliado
        outro = ModeloAfiliado.objects.create(conta=conta(email="outra@exemplo.com"), nome="Dela")
        c = conta()
        self.entrar(c)
        meu = ModeloAfiliado.objects.create(conta=c, nome="Meu")
        self.assertEqual(self.client.post(f"/estudio/modelos/{outro.pk}/apagar/").status_code, 404)
        self.client.post(f"/estudio/modelos/{meu.pk}/apagar/")
        self.assertEqual(list(ModeloAfiliado.objects.values_list("nome", flat=True)), ["Dela"])

    def test_produto_solto_e_do_premium(self):
        for modulos, esperado in (("carrosseis_premium", True), ("carrosseis", None)):
            c = conta(modulos=modulos, email=f"{modulos}@exemplo.com")
            slides = A.limpar_slides([{"tipo": "produto", "fundo": {"modo": "cor", "cor": "claro"}, "foto": "/estudio/imagens/1/", "sem_fundo": True}],
                                     A.eh_premium(c))
            self.assertEqual(slides[0].get("sem_fundo"), esperado)


class TestHalo(TestCase):
    """A arte "halo" (círculos no meio) só fica com pouquíssimo texto, centralizado."""

    def test_texto_demais_vira_canto_e_pouco_texto_vai_para_o_meio(self):
        halo = {"modo": "arte", "arte": "halo", "tom": "escuro"}
        post = ia.limpar("afiliado", {"nome": "x", "legenda": "", "slides": [
            {"tipo": "cta", "fundo": dict(halo), "titulo": "Quer a sua? *Link na bio*",
             "texto": "Toque no link da bio para ver a garrafa e conferir o preço atualizado.", "botao": "Ver no link da bio"},
            {"tipo": "cta", "fundo": dict(halo), "titulo": "Link na *bio*", "botao": "Ver agora"},
            {"tipo": "lista", "fundo": dict(halo), "titulo": "Lista", "itens": [{"titulo": "a"}]}]})
        longo, curto, lista = post["slides"]
        self.assertEqual(longo["fundo"]["arte"], "canto")
        self.assertEqual(lista["fundo"]["arte"], "canto")
        self.assertEqual(curto["fundo"]["arte"], "halo")
        self.assertEqual(curto["ajustes"], {"alinhar": "centro", "posicao": "meio"})

    def test_regras_novas_no_prompt(self):
        guia = ia.conhecimento("afiliado")
        self.assertIn("voz de quem achou o produto", guia)
        self.assertIn("Não repita a mesma informação", guia)
        self.assertIn('A arte "halo"', ia._sistema("afiliado", "retrato"))
