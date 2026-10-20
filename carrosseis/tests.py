import json
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from licencas.models import ContaAppfiliado
from painel import cripto
from painel import modulos as mod

from . import ia, servicos
from . import roteiro as R
from .models import Carrossel, PadraoCarrossel, UsoCarrossel

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
PRODUTO = {"nome": "Garrafa Térmica Inox 1 Litro Quente Frio", "preco": 47.9, "de": 89.9, "desconto": 47, "nota": 4.8,
           "vendas": 5400, "imagem": "https://down-br.img.susercontent.com/file/x", "loja": "Loja", "link": "https://s.shopee.com.br/abc"}
ACHADO = {"item_id": "123", "shop_id": "9", "nome": "Garrafa Térmica Inox 1 Litro", "link": "https://shopee.com.br/p-i.9.123",
          "imagem": "https://down-br.img.susercontent.com/file/x", "preco": 50.0, "comissao": 10, "desconto": 50, "vendas": 900,
          "avaliacao": 4.73, "loja": "Loja"}


def resposta_da_ia(**extra) -> str:
    dados = {
        "nome_curto": "Garrafa Térmica 1L", "arte": "cozinha",
        "capa": {"selo": "Achado da semana", "titulo": "Café quente o dia *inteiro*"},
        "problema": {"rotulo": "Sabe quando", "titulo": "O café *esfria* rápido?", "texto": "Com ela não."},
        "chips": ["1 litro", "Aço inox", "Leve"], "prova": {"titulo": "Quem comprou *aprovou*", "texto": "Nota 4,8."},
        "cta": {"titulo": "Quer a sua?"}, "final": {"titulo": "*Salva* esse post", "texto": "Siga para mais."},
        "vantagens": {"rotulo": "Por que vale", "titulo": "Feita para *durar*", "itens": ["Inox", "Tampa copo", "Leve"]},
        # "24h" não está no nome nem nos dados: tem que sair
        "numeros": {"rotulo": "Em números", "titulo": "Em *números*", "numeros": [{"valor": "1 litro", "legenda": "de café"}, {"valor": "24h", "legenda": "gelado"}]},
        "qualidades": {"rotulo": "Detalhes", "titulo": "Os *detalhes*", "itens": ["Tampa", "Alça", "Inox", "Copo"]},
        "legenda": "Achei essa garrafa ✨ link na bio", "hashtags": ["#garrafatermica", "café", "#shopee"],
    }
    dados.update(extra)
    return json.dumps(dados, ensure_ascii=False)


class TestRoteiro(TestCase):
    def test_tira_campo_desconhecido_e_corta_no_tamanho(self):
        s = R.limpar_slide({"tipo": "capa", "titulo": "x" * 200, "selo": "a\nb", "script": "<b>", "semFoto": True}, R.PADRAO, premium=True)
        self.assertEqual(set(s), {"tipo", "titulo", "selo"})
        self.assertEqual(len(s["titulo"]), 60)
        self.assertEqual(s["selo"], "a b")

    def test_sem_foto_so_no_premium_e_nos_modelos_premium(self):
        slide = {"tipo": "vantagens", "titulo": "T", "itens": ["a"], "semFoto": True, "posicao": "lado", "alinhar": "centro"}
        self.assertNotIn("semFoto", R.limpar_slide(slide, R.PREMIUM, premium=False))
        limpo = R.limpar_slide(slide, R.PREMIUM, premium=True)
        self.assertEqual((limpo["semFoto"], limpo["posicao"], limpo["alinhar"]), (True, "meio", "centro"))

    def test_tipo_de_outra_familia_some(self):
        self.assertIsNone(R.limpar_slide({"tipo": "vantagens"}, R.PADRAO, premium=True))

    def test_capa_primeiro_e_minimo_de_slides(self):
        with self.assertRaises(ValueError):
            R.limpar_roteiro([{"tipo": "preco"}, {"tipo": "capa", "titulo": "a"}], R.PADRAO, premium=False)
        with self.assertRaises(ValueError):
            R.limpar_roteiro([{"tipo": "capa", "titulo": "a"}], R.PADRAO, premium=False)
        self.assertEqual(len(R.limpar_roteiro([{"tipo": "capa"}] + [{"tipo": "preco"}] * 20, R.PADRAO, premium=False)), R.MAXIMO_SLIDES)


class TestIA(TestCase):
    def test_sem_chave_sai_o_roteiro_simples(self):
        with mock.patch.object(ia.gemini, "disponivel", return_value=False):
            roteiros, usou = ia.gerar(PRODUTO)
        self.assertFalse(usou)
        self.assertEqual(roteiros["padrao"][0]["tipo"], "capa")
        self.assertIn("47% off", roteiros["padrao"][0]["titulo"])
        numeros = next(s for s in roteiros["premium"] if s["tipo"] == "numeros")["numeros"]
        self.assertEqual([n["valor"] for n in numeros], ["-47%", "4,8", "5,4 mil"])

    def test_com_ia_monta_os_dois_roteiros_e_tira_numero_inventado(self):
        with mock.patch.object(ia.gemini, "disponivel", return_value=True), \
                mock.patch.object(ia.gemini, "_chamar", return_value=resposta_da_ia()) as chamar:
            roteiros, usou = ia.gerar(PRODUTO)
        self.assertTrue(usou)
        self.assertTrue(chamar.call_args.kwargs["json_saida"])
        self.assertEqual([s["tipo"] for s in roteiros["padrao"]], ["capa", "texto", "produto", "preco", "prova", "cta", "final"])
        self.assertEqual([s["tipo"] for s in roteiros["premium"]], ["capa", "vantagens", "numeros", "anotado", "preco", "cta"])
        valores = [n["valor"] for n in roteiros["premium"][2]["numeros"]]
        self.assertIn("1 litro", valores)
        self.assertNotIn("24h", valores)
        self.assertEqual(roteiros["hashtags"].split()[:3], ["#garrafatermica", "#café", "#shopee"])
        self.assertEqual(roteiros["padrao"][1]["arte"], "cozinha")
        ids = [s["_id"] for f in ("padrao", "premium") for s in roteiros[f]]
        self.assertEqual(len(ids), len(set(ids)))  # as duas famílias não repetem número

    def test_resposta_quebrada_cai_no_simples(self):
        with mock.patch.object(ia.gemini, "disponivel", return_value=True), \
                mock.patch.object(ia.gemini, "_chamar", return_value="isso não é json"):
            _, usou = ia.gerar(PRODUTO)
        self.assertFalse(usou)

    def test_erro_do_gemini_cai_no_simples(self):
        with mock.patch.object(ia.gemini, "disponivel", return_value=True), \
                mock.patch.object(ia.gemini, "_chamar", side_effect=ia.gemini.ErroDaIA("sobrecarga", 503)):
            roteiros, usou = ia.gerar(PRODUTO)
        self.assertFalse(usou)
        self.assertTrue(roteiros["padrao"])

    def test_nome_curto(self):
        self.assertEqual(ia.nome_curto("Garrafa Térmica 1 Litro [ENVIO IMEDIATO] - Aço"), "Garrafa Térmica 1 Litro")


def conta_premium(**kw):
    conta = ContaAppfiliado.objects.create(email=kw.get("email", "bia@exemplo.com"), modulos_cortesia=kw.get("modulos", "carrosseis_premium"),
                                           shopee_app_id="123", shopee_secret_cifrado=cripto.cifrar("segredo"))
    conta.definir_senha(SENHA)
    conta.save()
    return conta


class TestServicos(TestCase):
    def setUp(self):
        self.conta = conta_premium()

    def _mocks(self):
        return (mock.patch.object(servicos.copia, "identificar_produto", return_value="123"),
                mock.patch.object(servicos.shopee_ofertas, "buscar_produto_por_item", return_value=dict(ACHADO)),
                mock.patch.object(servicos.shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/af"),
                mock.patch.object(ia.gemini, "disponivel", return_value=False))

    def test_produto_do_link_com_sub_id_instagram_e_preco_antigo(self):
        a, b, c, d = self._mocks()
        with a, b, c as gerar_link, d:
            produto = servicos.produto_do_link(self.conta, "olha https://s.shopee.com.br/xyz")
        self.assertEqual(gerar_link.call_args.args[3], ["instagram"])
        self.assertEqual((produto["de"], produto["desconto"], produto["nota"]), (100.0, 50, 4.7))
        self.assertEqual(produto["link"], "https://s.shopee.com.br/af")

    def test_link_que_nao_e_da_shopee(self):
        with self.assertRaises(servicos.ErroGerador):
            servicos.produto_do_link(self.conta, "https://google.com")

    def test_sem_shopee_conectada(self):
        self.conta.shopee_app_id = ""
        self.conta.save()
        with self.assertRaisesMessage(servicos.ErroGerador, "Conecte"):
            servicos.produto_do_link(self.conta, "https://s.shopee.com.br/xyz")

    def test_criar_conta_o_uso_e_respeita_o_limite(self):
        a, b, c, d = self._mocks()
        with a, b, c, d:
            carrossel = servicos.criar(self.conta, "https://s.shopee.com.br/xyz")
            self.assertEqual(carrossel.produto["link"], "https://s.shopee.com.br/af")
            self.assertEqual(UsoCarrossel.objects.get(conta=self.conta).geracoes, 1)
            limite = servicos.restantes(self.conta)["limite"]
            UsoCarrossel.objects.filter(conta=self.conta).update(geracoes=limite)
            with self.assertRaisesMessage(servicos.ErroGerador, f"Você já gerou os {limite} carrosséis de hoje"):
                servicos.criar(self.conta, "https://s.shopee.com.br/xyz")

    def test_limite_por_plano(self):
        from licencas import planos
        self.assertEqual(planos.carrosseis(["carrosseis"])["geracoes"], 3)
        self.assertEqual(planos.carrosseis(["carrosseis", "carrosseis_premium"])["geracoes"], 10)

    def test_link_ruim_nao_gasta_o_limite(self):
        with self.assertRaises(servicos.ErroGerador):
            servicos.criar(self.conta, "sem link nenhum")
        self.assertEqual(servicos.uso_de_hoje(self.conta).geracoes, 0)

    def test_opcoes_do_standard_ignoram_as_do_premium(self):
        limpo = servicos.limpar_opcoes({"modelo": "vitrine", "cor": "#123456", "fonte": "serifa", "mostraNota": False, "arroba": "@bia.achados"}, premium=False)
        self.assertEqual((limpo["modelo"], limpo["cor"], limpo["fonte"], limpo["mostraNota"], limpo["arroba"]), ("destaque", "", "modelo", True, "@bia.achados"))
        limpo = servicos.limpar_opcoes({"modelo": "vitrine", "cor": "#123456", "fonte": "serifa", "mostraNota": False, "arroba": "bia achados"}, premium=True)
        self.assertEqual((limpo["modelo"], limpo["cor"], limpo["fonte"], limpo["mostraNota"], limpo["arroba"]), ("vitrine", "#123456", "serifa", False, ""))


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestTelas(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(HTTP_HOST=HOST)
        self.conta = conta_premium()
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})
        with mock.patch.object(ia.gemini, "disponivel", return_value=False):
            roteiros, _ = ia.gerar(PRODUTO)
        self.carrossel = Carrossel.objects.create(
            conta=self.conta, link_original="https://shopee.com.br/x", produto=PRODUTO,
            roteiros={f: roteiros[f] for f in (R.PADRAO, R.PREMIUM)},
            originais={f: {str(s["_id"]): s for s in roteiros[f]} for f in (R.PADRAO, R.PREMIUM)},
            opcoes=servicos.opcoes_iniciais(self.conta), legenda="L", hashtags="#a")

    def salvar(self, dados, carrossel=None):
        return self.client.post(f"/carrosseis/{(carrossel or self.carrossel).pk}/salvar/", json.dumps(dados), content_type="application/json")

    def test_menu_libera_com_o_premium_sozinho(self):
        item = mod.POR_SLUG["carrosseis"]
        self.assertEqual(mod.estado(item, ["carrosseis_premium"]), "liberado")
        self.assertEqual(mod.estado(item, ["carrosseis"]), "liberado")
        self.assertEqual(mod.estado(item, ["whatsapp"]), "bloqueado")

    def test_sem_o_modulo_mostra_o_convite(self):
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        resposta = self.client.get("/carrosseis/")
        self.assertContains(resposta, "Não incluso no seu plano")

    def test_lista_e_editor(self):
        self.assertContains(self.client.get("/carrosseis/"), self.carrossel.produto["nome"])
        resposta = self.client.get(f"/carrosseis/{self.carrossel.pk}/")
        self.assertContains(resposta, 'id="dados-carrossel"')
        self.assertContains(resposta, "/static/painel/carrossel/editor.")

    def test_criar_pelo_formulario(self):
        with mock.patch.object(servicos, "criar", return_value=self.carrossel) as criar:
            resposta = self.client.post("/carrosseis/", {"link": "https://s.shopee.com.br/xyz"})
        self.assertRedirects(resposta, f"/carrosseis/{self.carrossel.pk}/", fetch_redirect_response=False)
        criar.assert_called_once()

    def test_erro_ao_criar_vira_aviso(self):
        with mock.patch.object(servicos, "criar", side_effect=servicos.ErroGerador("Cole um link")):
            resposta = self.client.post("/carrosseis/", {"link": "x"}, follow=True)
        self.assertContains(resposta, "Cole um link")

    def test_carrossel_de_outra_conta_nao_abre(self):
        outra = conta_premium(email="outra@exemplo.com")
        alheio = Carrossel.objects.create(conta=outra, link_original="https://shopee.com.br/y", produto=PRODUTO)
        self.assertEqual(self.client.get(f"/carrosseis/{alheio.pk}/").status_code, 404)
        self.assertEqual(self.salvar({}, alheio).status_code, 404)

    def test_salvar_edicao_e_opcoes(self):
        roteiro = self.carrossel.roteiros["premium"]
        roteiro[0]["titulo"] = "A caneca para quem ama *Harry Potter*"
        roteiro[0]["semFoto"] = True
        resposta = self.salvar({"roteiros": {"premium": roteiro}, "opcoes": {"modelo": "ficha", "cor": "#7B3FA0"}, "legenda": "Nova", "hashtags": "#um #dois"})
        self.assertEqual(resposta.status_code, 200)
        self.carrossel.refresh_from_db()
        self.assertEqual(self.carrossel.roteiros["premium"][0]["titulo"], "A caneca para quem ama *Harry Potter*")
        self.assertTrue(self.carrossel.roteiros["premium"][0]["semFoto"])
        self.assertEqual((self.carrossel.opcoes["modelo"], self.carrossel.opcoes["cor"], self.carrossel.legenda), ("ficha", "#7B3FA0", "Nova"))

    def test_salvar_roteiro_sem_capa_da_erro(self):
        resposta = self.salvar({"roteiros": {"padrao": [{"tipo": "preco"}, {"tipo": "preco"}]}})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("capa", resposta.json()["erro"])

    def test_standard_nao_duplica_slide_nem_salva_premium(self):
        self.conta.modulos_cortesia = "carrosseis"
        self.conta.save()
        roteiro = self.carrossel.roteiros["padrao"]
        resposta = self.salvar({"roteiros": {"padrao": roteiro + [dict(roteiro[1], _id=999)]}})
        self.assertEqual(resposta.status_code, 400)
        premium_antes = self.carrossel.roteiros["premium"]
        mexido = [dict(premium_antes[0], titulo="Mexido")] + premium_antes[1:]
        self.assertEqual(self.salvar({"roteiros": {"padrao": roteiro[:-1], "premium": mexido}, "opcoes": {"modelo": "vitrine"}}).status_code, 200)
        self.carrossel.refresh_from_db()
        self.assertEqual(self.carrossel.roteiros["premium"], premium_antes)
        self.assertEqual(len(self.carrossel.roteiros["padrao"]), len(roteiro) - 1)
        self.assertEqual(self.carrossel.opcoes["modelo"], "destaque")

    def test_reescrever_so_no_premium(self):
        slide = self.carrossel.roteiros["premium"][0]
        novo = dict(slide, titulo="Outro *título*")
        with mock.patch.object(ia, "reescrever", return_value=novo):
            resposta = self.client.post(f"/carrosseis/{self.carrossel.pk}/reescrever/", json.dumps({"slide": slide, "familia": "premium"}), content_type="application/json")
        self.assertEqual(resposta.json()["slide"]["titulo"], "Outro *título*")
        self.assertEqual(UsoCarrossel.objects.get(conta=self.conta).reescritas, 1)
        self.conta.modulos_cortesia = "carrosseis"
        self.conta.save()
        resposta = self.client.post(f"/carrosseis/{self.carrossel.pk}/reescrever/", json.dumps({"slide": slide, "familia": "premium"}), content_type="application/json")
        self.assertEqual(resposta.status_code, 400)

    def test_reescrever_com_erro_devolve_o_uso(self):
        slide = self.carrossel.roteiros["premium"][0]
        with mock.patch.object(ia, "reescrever", side_effect=ia.gemini.ErroDaIA("x", 503)):
            resposta = self.client.post(f"/carrosseis/{self.carrossel.pk}/reescrever/", json.dumps({"slide": slide, "familia": "premium"}), content_type="application/json")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(UsoCarrossel.objects.get(conta=self.conta).reescritas, 0)

    def test_padrao_salva_para_os_proximos(self):
        self.client.post("/carrosseis/padrao/", json.dumps({"opcoes": {"modelo": "etiqueta", "tema": "rosa", "arroba": "@bia"}}), content_type="application/json")
        self.assertEqual(PadraoCarrossel.objects.get(conta=self.conta).opcoes["modelo"], "etiqueta")
        self.assertEqual(servicos.opcoes_iniciais(self.conta)["tema"], "rosa")

    def test_foto_propria(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        arquivo = io.BytesIO()
        Image.new("RGB", (2000, 1500), "red").save(arquivo, "PNG")
        foto = SimpleUploadedFile("f.png", arquivo.getvalue(), content_type="image/png")
        resposta = self.client.post(f"/carrosseis/{self.carrossel.pk}/foto/", {"foto": foto})
        self.assertEqual(resposta.status_code, 200)
        imagem = self.client.get(resposta.json()["url"])
        self.assertEqual(imagem["Content-Type"], "image/jpeg")
        self.assertEqual(Image.open(io.BytesIO(imagem.content)).size, (1080, 810))
        self.client.post(f"/carrosseis/{self.carrossel.pk}/foto/", {"remover": "1"})
        self.assertEqual(self.client.get(f"/carrosseis/{self.carrossel.pk}/foto/").status_code, 404)

    def test_apagar(self):
        self.client.post(f"/carrosseis/{self.carrossel.pk}/apagar/")
        self.assertFalse(Carrossel.objects.filter(pk=self.carrossel.pk).exists())
