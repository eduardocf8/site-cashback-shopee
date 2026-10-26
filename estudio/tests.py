import base64
import io
import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import ia
from .admin import _modelos
from .models import ImagemEstudio, Projeto, ProjetoAppfiliado, ProjetoCashb

MIDIA = tempfile.mkdtemp()


def _jpeg_b64():
    buf = io.BytesIO()
    Image.new("RGB", (36, 36), "#1F3A2E").save(buf, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "#6d28d9").save(buf, "PNG")
    return buf.getvalue()


def _resposta(dados):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=dados)], stop_reason="tool_use")


@override_settings(MEDIA_ROOT=MIDIA)
class EstudioTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MIDIA, ignore_errors=True)

    def setUp(self):
        self.dono = get_user_model().objects.create_superuser("dono", "dono@x.com", "senha-forte-123")
        self.client.force_login(self.dono)

    def _post(self, nome, dados):
        return self.client.post(reverse(nome), data=json.dumps(dados), content_type="application/json")

    def test_editor_abre_nas_duas_marcas(self):
        for url, marca in (("admin:estudio_projetoappfiliado_add", "Appfiliado"), ("admin:estudio_projetocashb_add", "cash-b")):
            r = self.client.get(reverse(url))
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, f"Estúdio de posts · {marca}")
            self.assertContains(r, "estudio/marca-cashb")
            self.assertContains(r, 'id="es-config"')

    def test_so_quem_e_da_equipe_entra(self):
        self.client.logout()
        r = self.client.get(reverse("admin:estudio_projetoappfiliado_add"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self._post("admin:estudio_projetocashb_salvar", {"nome": "x"}).status_code, 302)

    def test_atalho_e_grupo_no_admin(self):
        r = self.client.get(reverse("admin:index"))
        self.assertContains(r, "🎨 Estúdio de posts", count=2)
        self.assertContains(r, "Posts e stories do Appfiliado")
        self.assertContains(r, "Posts e stories da cash-b")

    def test_salvar_cria_limpa_e_atualiza(self):
        slides = [{"tipo": "capa", "titulo": "Oi *você*", "chapeu": "x" * 100, "fundo": {"modo": "arte", "arte": "halo", "tom": "claro"},
                   "capa": True, "ajustes": {"titulo": 1.3, "lateral": 999, "posicao": "meio", "alinhar": "torto"}, "lixo": "<script>"},
                  {"tipo": "inexistente"}]
        r = self._post("admin:estudio_projetoappfiliado_salvar", {"nome": "Teste", "formato": "story", "slides": slides,
                                                                  "legenda": "Legenda", "miniatura": _jpeg_b64()})
        self.assertEqual(r.status_code, 200)
        p = Projeto.objects.get(pk=r.json()["id"])
        self.assertEqual((p.marca, p.formato, p.nome, p.legenda), ("appfiliado", "story", "Teste", "Legenda"))
        self.assertEqual(len(p.slides), 1)
        s = p.slides[0]
        self.assertNotIn("lixo", s)
        self.assertEqual(len(s["chapeu"]), 40)
        self.assertTrue(s["capa"])
        self.assertEqual(s["ajustes"], {"titulo": 1.3, "lateral": 200, "posicao": "meio"})
        self.assertEqual(s["fundo"], {"modo": "arte", "arte": "halo", "tom": "claro"})
        self.assertTrue(p.miniatura.name.endswith(".jpg"))
        # atualiza o mesmo post
        r = self._post("admin:estudio_projetoappfiliado_salvar", {"id": p.pk, "nome": "Novo nome", "formato": "quadrado", "slides": p.slides})
        p.refresh_from_db()
        self.assertEqual((p.nome, p.formato), ("Novo nome", "quadrado"))
        self.assertEqual(Projeto.objects.count(), 1)

    def test_nao_mistura_as_marcas(self):
        p = ProjetoCashb.objects.create(marca="cashb", formato="retrato", nome="da cash-b")
        r = self._post("admin:estudio_projetoappfiliado_salvar", {"id": p.pk, "nome": "invadido", "slides": []})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:estudio_projetoappfiliado_change", args=[p.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:estudio_projetocashb_change", args=[p.pk])).status_code, 200)
        self.assertEqual(list(ProjetoAppfiliado.objects.all()), [])

    def test_miniatura_que_nao_e_jpeg_e_ignorada(self):
        r = self._post("admin:estudio_projetocashb_salvar", {"nome": "x", "slides": [], "miniatura": "data:image/jpeg;base64,PHN2Zz4="})
        self.assertFalse(Projeto.objects.get(pk=r.json()["id"]).miniatura)

    def test_imagens_envia_e_lista(self):
        url = reverse("admin:estudio_projetocashb_imagens")
        r = self.client.post(url, {"arquivo": SimpleUploadedFile("foto.png", _png(), content_type="image/png")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["imagens"][0]["nome"], "foto.png")
        r = self.client.post(url, {"arquivo": SimpleUploadedFile("x.png", b"nao e imagem", content_type="image/png")})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(ImagemEstudio.objects.count(), 1)
        # a outra marca não vê
        self.assertEqual(self.client.get(reverse("admin:estudio_projetoappfiliado_imagens")).json()["imagens"], [])

    def test_duplicar(self):
        p = ProjetoAppfiliado.objects.create(marca="appfiliado", formato="quadrado", nome="Original", slides=[{"tipo": "capa"}])
        self.client.post(reverse("admin:estudio_projetoappfiliado_changelist"), {"action": "duplicar", "_selected_action": [p.pk]})
        self.assertTrue(ProjetoAppfiliado.objects.filter(nome="Original (cópia)", slides=[{"tipo": "capa"}]).exists())

    def test_ia_monta_post_e_so_deixa_passar_o_que_o_editor_conhece(self):
        cliente = mock.Mock()
        cliente.beta.messages.create.return_value = _resposta({
            "nome": "Black Friday", "legenda": "Legenda #appfiliado",
            "slides": [
                {"tipo": "capa", "titulo": "Black *Friday*", "icone": "inventado", "fundo": {"modo": "arte", "arte": "nao-existe"}},
                {"tipo": "tela", "titulo": "Tela", "print": "nao-existe", "recorte": "abc", "fundo": {"modo": "cor", "cor": "creme"}},
                {"tipo": "lista", "titulo": "Lista", "itens": [{"titulo": "a"}] * 9, "fundo": {"modo": "cor", "cor": "verde"}},
                {"tipo": "foto", "titulo": "tipo que não existe"},
            ]})
        post = ia.gerar("appfiliado", "quadrado", "post de black friday", cliente=cliente)
        self.assertEqual(post["nome"], "Black Friday")
        self.assertEqual([s["tipo"] for s in post["slides"]], ["capa", "tela", "lista"])
        capa, tela, lista = post["slides"]
        self.assertEqual(capa["icone"], "")
        self.assertEqual(capa["fundo"]["modo"], "cor")
        self.assertIn(tela["print"], ia.MARCAS["appfiliado"]["prints"])
        self.assertEqual(tela["recorte"], 0)
        self.assertEqual(len(lista["itens"]), 5)
        kwargs = cliente.beta.messages.create.call_args.kwargs
        # Opus 5.5 e Sonnet 5.5 recusam tool_choice "tool": vai "auto", com a instrução no sistema (em cache)
        self.assertEqual(kwargs["tool_choice"], {"type": "auto"})
        sistema = kwargs["system"][0]
        self.assertEqual(sistema["cache_control"], {"type": "ephemeral"})
        self.assertIn("chamando a ferramenta montar_post", sistema["text"])
        self.assertIn('"pra/pro/pras/pros" só como contração', sistema["text"])
        self.assertIn("afiliado Shopee", sistema["text"])

    def test_ia_da_cashb_usa_o_material_do_site(self):
        cliente = mock.Mock()
        cliente.beta.messages.create.return_value = _resposta({"nome": "x", "legenda": "", "slides": [{"tipo": "cta", "titulo": "Bora", "fundo": {"modo": "cor", "cor": "roxo"}}]})
        ia.gerar("cashb", "retrato", "post", cliente=cliente)
        sistema = cliente.beta.messages.create.call_args.kwargs["system"][0]["text"]
        self.assertIn("cash-b", sistema)
        self.assertIn("Perguntas frequentes", sistema)
        self.assertIn("'Pix', nunca 'PIX'", sistema)

    def test_ia_sem_slides_validos_avisa(self):
        cliente = mock.Mock()
        cliente.beta.messages.create.return_value = _resposta({"nome": "x", "legenda": "", "slides": [{"tipo": "nada"}]})
        with self.assertRaises(ia.ErroIA):
            ia.gerar("cashb", "retrato", "post", cliente=cliente)
        with self.assertRaises(ia.ErroIA):
            ia.gerar("cashb", "retrato", "   ", cliente=cliente)

    def test_api_ia_ajustar_manda_o_post_atual(self):
        with mock.patch.object(ia, "gerar", return_value={"nome": "n", "legenda": "l", "slides": [{"tipo": "capa"}]}) as gerar:
            r = self._post("admin:estudio_projetocashb_ia", {"pedido": "mais curto", "formato": "story", "ajustar": True,
                                                            "slides": [{"tipo": "capa"}], "legenda": "antiga"})
        self.assertEqual(r.status_code, 200)
        gerar.assert_called_once_with("cashb", "story", "mais curto", {"slides": [{"tipo": "capa"}], "legenda": "antiga"})
        with mock.patch.object(ia, "gerar", side_effect=ia.ErroIA("A IA não respondeu agora.")):
            r = self._post("admin:estudio_projetocashb_ia", {"pedido": "x"})
        self.assertEqual((r.status_code, r.json()["erro"]), (400, "A IA não respondeu agora."))

    def test_modelos_passam_pela_validacao_sem_perder_slide(self):
        for marca in ("appfiliado", "cashb"):
            modelos = _modelos(marca)
            self.assertTrue(modelos)
            for m in modelos:
                limpos = [ia.limpar_slide(marca, s) for s in m["slides"]]
                self.assertTrue(all(limpos), (marca, m["nome"]))
                self.assertIn(m["formato"], ("quadrado", "retrato", "story"))
