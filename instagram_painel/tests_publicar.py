import io
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from estudio.models import PostInstagram

from . import api
from . import publicar as P
from .models import ImagemPublicacao, Publicacao
from .tests import HOST, SEGREDO, SENHA, conectada, conta


def jpeg(largura=1080, altura=1350, nome="01.jpg", formato="JPEG"):
    from PIL import Image

    saida = io.BytesIO()
    Image.new("RGB", (largura, altura), "#1F3A2E").save(saida, formato)
    return SimpleUploadedFile(nome, saida.getvalue(), content_type="image/jpeg")


def post_de(c, formato="retrato", slides=2, legenda="Achado do dia! Link na bio."):
    return PostInstagram.objects.create(conta=c, formato=formato, nome="Garrafa térmica",
                                        slides=[{"tipo": "capa"}] * slides, legenda=legenda)


def com_imagens(post, n=None):
    return [jpeg(altura=1920 if post.formato == "story" else 1350, nome=f"{i}.jpg") for i in range(n or len(post.slides))]


@override_settings(APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestFila(TestCase):
    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        P.dormir = lambda s: None

    def test_agendar_guarda_as_imagens_e_marca_o_post(self):
        post = post_de(self.c)
        pub = P.agendar(post, com_imagens(post))
        self.assertEqual(pub.tipo, Publicacao.FEED)
        self.assertEqual(pub.legenda, post.legenda)
        self.assertEqual(pub.imagens.count(), 2)
        self.assertTrue(pub.agora)
        post.refresh_from_db()
        self.assertEqual(post.estado, "agendado")

    def test_story_vai_sem_legenda(self):
        post = post_de(self.c, formato="story", slides=1)
        pub = P.agendar(post, com_imagens(post))
        self.assertEqual((pub.tipo, pub.legenda), (Publicacao.STORY, ""))

    def test_recusa_sem_instagram_imagem_errada_ou_quantidade_diferente(self):
        post = post_de(self.c)
        with self.assertRaisesMessage(P.ErroPublicacao, "não batem"):
            P.agendar(post, com_imagens(post, 1))
        with self.assertRaisesMessage(P.ErroPublicacao, "JPEG"):
            P.agendar(post, [jpeg(formato="GIF"), jpeg()])
        with self.assertRaisesMessage(P.ErroPublicacao, "quebrada"):
            P.agendar(post, [SimpleUploadedFile("a.jpg", b"nada"), jpeg()])
        with self.assertRaisesMessage(P.ErroPublicacao, "tamanho"):
            P.agendar(post, [jpeg(largura=100, altura=100), jpeg()])
        self.ig.delete()
        with self.assertRaisesMessage(P.ErroPublicacao, "Conecte"):
            P.agendar(post, com_imagens(post))
        self.assertFalse(Publicacao.objects.exists())

    def test_horario_do_agendamento(self):
        agora = timezone.now()
        with self.assertRaisesMessage(P.ErroPublicacao, "5 minutos"):
            P.quando_de(timezone.localtime(agora).strftime("%Y-%m-%dT%H:%M"), agora)
        with self.assertRaisesMessage(P.ErroPublicacao, "60 dias"):
            P.quando_de(timezone.localtime(agora + timedelta(days=70)).strftime("%Y-%m-%dT%H:%M"), agora)
        with self.assertRaisesMessage(P.ErroPublicacao, "dia e a hora"):
            P.quando_de("amanhã", agora)
        quando = P.quando_de(timezone.localtime(agora + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"), agora)
        self.assertAlmostEqual((quando - agora).total_seconds(), 7200, delta=60)
        # com fuso (o navegador manda em UTC)
        quando = P.quando_de((agora + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), agora)
        self.assertAlmostEqual((quando - agora).total_seconds(), 3 * 3600, delta=2)

    @mock.patch.object(api, "link_da_midia", return_value="https://www.instagram.com/p/abc/")
    @mock.patch.object(api, "publicar_container", return_value="midia1")
    @mock.patch.object(api, "estado_container", side_effect=["IN_PROGRESS", "FINISHED", "FINISHED", "FINISHED"])
    @mock.patch.object(api, "criar_container", side_effect=["f1", "f2", "carrossel"])
    def test_carrossel_publica_e_apaga_as_imagens(self, criar, estado, publicar, link):
        post = post_de(self.c)
        pub = P.agendar(post, com_imagens(post))
        tokens = list(pub.imagens.values_list("token", flat=True))
        linhas = P.uma_volta()
        self.assertIn("publicada", linhas[0])
        primeira = criar.call_args_list[0]
        self.assertEqual(primeira.kwargs["image_url"], f"https://{HOST}/instagram/midia/{tokens[0]}.jpg")
        self.assertTrue(primeira.kwargs["is_carousel_item"])
        ultima = criar.call_args_list[2].kwargs
        self.assertEqual((ultima["media_type"], ultima["children"], ultima["caption"]), ("CAROUSEL", "f1,f2", post.legenda))
        publicar.assert_called_once_with("tok", self.ig.ig_id, "carrossel")
        pub.refresh_from_db()
        self.assertEqual((pub.estado, pub.midias, pub.permalink), (Publicacao.PUBLICADA, ["midia1"], "https://www.instagram.com/p/abc/"))
        self.assertFalse(ImagemPublicacao.objects.exists())
        post.refresh_from_db()
        self.assertEqual(post.estado, "publicado")

    @mock.patch.object(api, "publicar_container", side_effect=["s1", api.ErroInstagram("limite"), "s2"])
    @mock.patch.object(api, "estado_container", return_value="FINISHED")
    @mock.patch.object(api, "criar_container", side_effect=["c1", "c2", "c3"])
    def test_stories_um_por_um_e_tentar_de_novo_nao_repete(self, criar, estado, publicar):
        post = post_de(self.c, formato="story", slides=2)
        pub = P.agendar(post, com_imagens(post))
        P.uma_volta()
        pub.refresh_from_db()
        self.assertEqual((pub.estado, pub.midias), (Publicacao.ERRO, ["s1"]))
        self.assertIn("limite", pub.erro)
        self.assertEqual(criar.call_args_list[0].kwargs["media_type"], "STORIES")
        self.assertTrue(P.tentar_de_novo(pub))
        P.uma_volta()
        pub.refresh_from_db()
        self.assertEqual((pub.estado, pub.midias), (Publicacao.PUBLICADA, ["s1", "s2"]))
        self.assertEqual(criar.call_count, 3)  # o primeiro story não foi de novo

    @mock.patch.object(api, "criar_container")
    def test_agendada_so_sai_na_hora_e_cancelada_nao_sai(self, criar):
        post = post_de(self.c, slides=1)
        quando = timezone.now() + timedelta(hours=1)
        pub = P.agendar(post, com_imagens(post), quando)
        self.assertEqual(P.uma_volta(), [])
        self.assertTrue(P.cancelar(pub))
        self.assertEqual(P.uma_volta(quando + timedelta(minutes=1)), [])
        criar.assert_not_called()
        self.assertFalse(ImagemPublicacao.objects.exists())
        post.refresh_from_db()
        self.assertEqual(post.estado, "rascunho")

    @mock.patch.object(api, "criar_container")
    def test_instagram_desconectado_ou_fora_do_plano_vira_erro(self, criar):
        post = post_de(self.c, slides=1)
        pub = P.agendar(post, com_imagens(post))
        self.ig.delete()
        P.uma_volta()
        pub.refresh_from_db()
        self.assertEqual(pub.estado, Publicacao.ERRO)
        self.assertIn("desconectado", pub.erro)
        conectada(self.c)
        self.c.modulos_cortesia = "whatsapp"
        self.c.save()
        P.tentar_de_novo(pub)
        P.uma_volta()
        pub.refresh_from_db()
        self.assertIn("plano", pub.erro)
        criar.assert_not_called()

    def test_so_um_processo_pega_cada_publicacao(self):
        post = post_de(self.c, slides=1)
        pub = P.agendar(post, com_imagens(post))
        agora = timezone.now()
        self.assertTrue(P.pegar(pub, agora))
        self.assertFalse(P.pegar(pub, agora))  # o objeto em memória ainda diz "pendente"


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}",
                   APPFILIADO_INSTAGRAM_APP_ID="123", APPFILIADO_INSTAGRAM_APP_SECRET=SEGREDO)
class TestTelasPublicar(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST=HOST)
        self.c = conta(modulos="carrosseis")  # Standard também publica
        self.client.post("/entrar/", {"email": self.c.email, "senha": SENHA})
        self.post = post_de(self.c)

    def test_sem_instagram_oferece_conectar_na_janela(self):
        j = self.client.get(f"/estudio/{self.post.pk}/publicar/").json()
        self.assertIsNone(j["ig"])
        self.assertEqual(j["conectar"], "/estudio/instagram/conectar/?janela=ficar")
        self.client.get("/estudio/instagram/conectar/?janela=ficar")
        self.assertEqual(self.client.session["instagram_janela"], "ficar")

    def test_publicar_agora_e_agendar(self):
        conectada(self.c)
        r = self.client.post(f"/estudio/{self.post.pk}/publicar/", {"quando": "agora", "imagem_0": jpeg(), "imagem_1": jpeg()})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("em instantes", r.json()["mensagem"])
        quando = timezone.localtime(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        r = self.client.post(f"/estudio/{self.post.pk}/publicar/", {"quando": "agendar", "data": quando, "imagem_0": jpeg(), "imagem_1": jpeg()})
        self.assertIn("Agendado para", r.json()["mensagem"])
        j = self.client.get(f"/estudio/{self.post.pk}/publicar/").json()
        self.assertEqual(j["ig"]["username"], "achadosdabia")
        self.assertEqual(len(j["publicacoes"]), 2)
        r = self.client.get("/estudio/publicacoes/")
        self.assertContains(r, "Garrafa térmica", count=2)
        self.assertContains(r, "Cancelar")

    def test_erro_volta_como_json(self):
        r = self.client.post(f"/estudio/{self.post.pk}/publicar/", {"quando": "agora", "imagem_0": jpeg()})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Conecte", r.json()["erro"])

    def test_post_de_outra_conta_nao(self):
        outra = conta(email="outra@exemplo.com")
        alheio = post_de(outra)
        self.assertEqual(self.client.get(f"/estudio/{alheio.pk}/publicar/").status_code, 404)

    def test_imagem_publica_so_enquanto_nao_saiu(self):
        conectada(self.c)
        pub = P.agendar(self.post, com_imagens(self.post))
        token = pub.imagens.first().token
        anonimo = Client(HTTP_HOST=HOST)
        r = anonimo.get(f"/instagram/midia/{token}.jpg")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(anonimo.get("/instagram/midia/nao-existe.jpg").status_code, 404)
        P.cancelar(pub)
        self.assertEqual(anonimo.get(f"/instagram/midia/{token}.jpg").status_code, 404)

    def test_cancelar_e_tentar_de_novo_pela_tela(self):
        conectada(self.c)
        pub = P.agendar(self.post, com_imagens(self.post), timezone.now() + timedelta(hours=3))
        r = self.client.post(f"/estudio/publicacoes/{pub.pk}/cancelar/", HTTP_ACCEPT="application/json")
        self.assertEqual(r.json()["mensagem"], "Publicação cancelada.")
        pub.refresh_from_db()
        self.assertEqual(pub.estado, Publicacao.CANCELADA)
        r = self.client.post(f"/estudio/publicacoes/{pub.pk}/tentar/")
        self.assertRedirects(r, "/estudio/publicacoes/", fetch_redirect_response=False)
