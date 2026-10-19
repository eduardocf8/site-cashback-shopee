import io
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from bot_whatsapp import shopee_ofertas
from licencas.models import ContaAppfiliado
from painel import cripto
from painel.tests import HOST, BasePainel

from . import vitrine
from .forms import BotaoForm, SiteForm
from .models import BotaoSite, CliqueSite, ProdutoSite, SiteAfiliado


def produto(item_id, **extra):
    base = {"item_id": str(item_id), "nome": f"Fone Bluetooth {item_id}", "link": f"https://shopee.com.br/p-i.9.{item_id}",
            "imagem": f"https://cf.shopee.com.br/file/{item_id}", "preco": 59.9, "desconto": 70.0, "comissao": 10.0,
            "vendas": 100, "avaliacao": 4.8}
    base.update(extra)
    return base


def conta_com_site(email="bia@exemplo.com", modulos="site,whatsapp", **campos):
    conta = ContaAppfiliado.objects.create(
        email=email, modulos_cortesia=modulos, shopee_app_id="123", shopee_secret_cifrado=cripto.cifrar("s"),
        shopee_validado_em=timezone.now(),
    )
    site = SiteAfiliado.objects.create(conta=conta, endereco=campos.pop("endereco", "achadinhos"), nome="Achadinhos", **campos)
    return conta, site


class TestVitrineDoBot(TestCase):
    def test_entra_no_topo_sem_duplicar_e_fica_com_as_100_mais_recentes(self):
        conta, site = conta_com_site()
        agora = timezone.now()
        for i in range(105):
            vitrine.registrar_do_bot(conta, produto(i), agora + timedelta(seconds=i))
        self.assertEqual(site.produtos.count(), 100)
        self.assertFalse(site.produtos.filter(item_id__in=["0", "4"]).exists())  # as mais antigas saíram
        self.assertEqual(site.produtos.first().item_id, "104")
        vitrine.registrar_do_bot(conta, produto(50, preco=49.9), agora + timedelta(minutes=10))  # reenviado
        self.assertEqual(site.produtos.count(), 100)
        topo = site.produtos.first()
        self.assertEqual((topo.item_id, topo.preco, topo.preco_original, topo.desconto), ("50", Decimal("49.90"), Decimal("166.33"), 70))

    def test_so_quando_a_vitrine_e_do_bot(self):
        conta, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA)
        vitrine.registrar_do_bot(conta, produto(1))
        vitrine.registrar_do_bot(conta, None)
        self.assertFalse(ProdutoSite.objects.exists())

    def test_o_motor_do_bot_alimenta_a_vitrine_menos_na_simulacao(self):
        from bot_whatsapp import ofertas
        from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas

        conta, site = conta_com_site()
        grupos = [{"jid": "1@g.us", "nome": "VIP"}, {"jid": "2@g.us", "nome": "Achados"}]
        ConexaoWhatsApp.objects.create(conta=conta, estado="conectado", grupos=grupos)
        config = ConfiguracaoOfertas.objects.create(conta=conta, ativo=True, grupos=grupos, intervalo_minutos=5)
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x"), \
                mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(7)], False)):
            ofertas.Motor().uma_volta()
        self.assertEqual(list(site.produtos.values_list("item_id", flat=True)), ["7"])  # 2 grupos, 1 produto
        ConfiguracaoOfertas.objects.filter(pk=config.pk).update(simulacao=True, proximo_envio_em=None)
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x"), \
                mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(8)], False)):
            ofertas.Motor().uma_volta()
        self.assertFalse(site.produtos.filter(item_id="8").exists())


class TestVitrineDoWorker(TestCase):
    def test_busca_refaz_e_troca_os_produtos(self):
        conta, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA, pedido_vitrine_em=timezone.now())
        with mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(1), produto(2)], False)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/site") as link:
            vitrine.uma_volta()
        self.assertEqual(sorted(site.produtos.values_list("item_id", flat=True)), ["1", "2"])
        self.assertEqual(set(site.produtos.values_list("link_afiliado", flat=True)), {"https://s.shopee.com.br/site"})
        self.assertEqual(link.call_args.args[3], ["site"])  # com o Sub ID do site
        site.refresh_from_db()
        self.assertFalse(site.vitrine_pedida)
        # 3 h depois, a busca vence e é refeita
        with mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(3)], False)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="x"):
            vitrine.uma_volta(timezone.now() + timedelta(hours=4))
        self.assertEqual(list(site.produtos.values_list("item_id", flat=True)), ["3"])

    def test_manual_na_ordem_e_avisa_o_que_nao_achou(self):
        conta, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_MANUAL, pedido_vitrine_em=timezone.now(),
                                     links_manuais="https://shopee.com.br/a-i.1.11\nhttps://shopee.com.br/b-i.1.22\nhttps://amazon.com/x")
        achados = {"11": produto(11), "22": produto(22)}
        with mock.patch("bot_whatsapp.copia.identificar_produto", side_effect=lambda l: l.rsplit(".", 1)[-1] if "shopee" in l else ""), \
                mock.patch.object(shopee_ofertas, "buscar_produto_por_item", side_effect=lambda a, s, i: achados.get(i)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="x"):
            vitrine.uma_volta()
        self.assertEqual(list(site.produtos.values_list("item_id", flat=True)), ["11", "22"])
        site.refresh_from_db()
        self.assertIn("Não achei 1 produto", site.vitrine_erro)


class TestFormularios(TestCase):
    def setUp(self):
        self.conta, self.site = conta_com_site()

    def dados(self, **extra):
        base = {"endereco": "biaofertas", "publicado": "on", "nome": "Bia", "frase": "", "cor": "#E8541E",
                "mostrar_conversor": "on", "sub_id": "site", "vitrine": "bot", "busca_tipo": "geral",
                "ordenacao": "mais_vendidos", "links_manuais": ""}
        base.update(extra)
        return base

    def test_endereco(self):
        self.assertTrue(SiteForm(self.dados(endereco="Bia-Ofertas"), instance=self.site).is_valid())
        for ruim in ("ab", "bia ofertas", "bia_ofertas", "-bia", "bia--x", "app", "www", "ação"):
            with self.subTest(ruim):
                self.assertFalse(SiteForm(self.dados(endereco=ruim), instance=self.site).is_valid())
        conta_com_site(email="outra@exemplo.com", endereco="ocupado")
        self.assertIn("já está em uso", str(SiteForm(self.dados(endereco="ocupado"), instance=self.site).errors))

    def test_vitrine_sem_bot_e_campos_da_busca(self):
        form = SiteForm(self.dados(vitrine="bot"), instance=self.site, tem_bot=False)
        self.assertIn("vitrine", form.errors)
        form = SiteForm(self.dados(vitrine="busca", busca_tipo="palavra_chave"), instance=self.site)
        self.assertIn("palavra_chave", form.errors)
        self.assertIn("links_manuais", SiteForm(self.dados(vitrine="manual"), instance=self.site).errors)

    def test_redes_aceitam_link_ou_arroba(self):
        form = SiteForm(self.dados(rede_instagram="@achadinhos", rede_tiktok="bia.ofertas", rede_whatsapp="(11) 99999-8888",
                                   rede_youtube="youtube.com/@bia", rede_x=""), instance=self.site)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.site.refresh_from_db()
        self.assertEqual(self.site.redes, {
            "instagram": "https://instagram.com/achadinhos", "tiktok": "https://tiktok.com/@bia.ofertas",
            "youtube": "https://youtube.com/@bia", "whatsapp": "https://wa.me/5511999998888",
        })
        self.assertEqual([r["rede"] for r in self.site.lista_de_redes()], ["instagram", "tiktok", "youtube", "whatsapp"])
        ruim = SiteForm(self.dados(rede_instagram="nome com espaço", rede_whatsapp="123"), instance=self.site)
        self.assertFalse(ruim.is_valid())
        self.assertIn("rede_instagram", ruim.errors)
        self.assertIn("rede_whatsapp", ruim.errors)

    def test_botao_completa_o_https(self):
        form = BotaoForm({"texto": "Grupo", "url": "chat.whatsapp.com/abc"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["url"], "https://chat.whatsapp.com/abc")
        self.assertFalse(BotaoForm({"texto": "x", "url": "javascript:alert(1)"}).is_valid())


class TestEditor(BasePainel):
    def setUp(self):
        super().setUp()
        self.conta.modulos_cortesia = "site,whatsapp"
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        self.entrar()

    def test_sem_o_modulo_mostra_o_bloqueio(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        resposta = self.client.get("/meu-site/")
        self.assertNotContains(resposta, 'id="form-site"')
        self.assertFalse(SiteAfiliado.objects.exists())

    def test_primeira_vez_sugere_o_endereco_e_salva(self):
        html = self.client.get("/meu-site/").content.decode()
        site = SiteAfiliado.objects.get(conta=self.conta)
        self.assertEqual((site.endereco, site.nome), ("biasouza", "Bia Souza"))
        self.assertIn('src="/s/biasouza/?previa=1"', html)
        resposta = self.client.post("/meu-site/", {
            "acao": "salvar", "endereco": "achadinhosdabia", "publicado": "on", "nome": "Achadinhos da Bia",
            "frase": "Ofertas todo dia", "cor": "#2F6FDE", "sub_id": "site", "vitrine": "busca",
            "busca_tipo": "palavra_chave", "palavra_chave": "fone", "ordenacao": "mais_vendidos",
        })
        self.assertRedirects(resposta, "/meu-site/", fetch_redirect_response=False)
        site.refresh_from_db()
        self.assertEqual((site.endereco, site.cor, site.mostrar_conversor, site.vitrine), ("achadinhosdabia", "#2F6FDE", False, "busca"))
        self.assertTrue(site.vitrine_pedida)  # o worker monta a vitrine

    def test_botoes(self):
        self.client.get("/meu-site/")
        for texto in ("Grupo", "Canal", "Insta"):
            self.client.post("/meu-site/", {"acao": "botao_novo", "texto": texto, "url": f"https://x.com/{texto}"})
        site = SiteAfiliado.objects.get(conta=self.conta)
        self.assertEqual(list(site.botoes.values_list("texto", flat=True)), ["Grupo", "Canal", "Insta"])
        insta = site.botoes.get(texto="Insta")
        self.client.post("/meu-site/", {"acao": "botao_subir", "botao": insta.pk})
        self.assertEqual(list(site.botoes.values_list("texto", flat=True)), ["Grupo", "Insta", "Canal"])
        self.client.post("/meu-site/", {"acao": "botao_editar", "botao": insta.pk, "texto": "📸 Instagram",
                                        "url": "instagram.com/bia", "destaque": "on"})
        insta.refresh_from_db()
        self.assertEqual((insta.texto, insta.url, insta.destaque), ("📸 Instagram", "https://instagram.com/bia", True))
        self.client.post("/meu-site/", {"acao": "botao_apagar", "botao": insta.pk})
        self.assertEqual(site.botoes.count(), 2)

    def test_foto_vira_jpeg_quadrado(self):
        self.client.get("/meu-site/")
        imagem = io.BytesIO()
        Image.new("RGB", (800, 500), "red").save(imagem, "PNG")
        self.client.post("/meu-site/", {"acao": "foto", "foto": SimpleUploadedFile("f.png", imagem.getvalue(), "image/png")})
        site = SiteAfiliado.objects.get(conta=self.conta)
        foto = Image.open(io.BytesIO(bytes(site.foto)))
        self.assertEqual((foto.format, foto.size, site.foto_versao), ("JPEG", (320, 320), 1))
        resposta = self.client.get(f"/s/{site.endereco}/foto.jpg?previa=1")
        self.assertEqual(resposta["Content-Type"], "image/jpeg")


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestSitePublico(TestCase):
    def setUp(self):
        cache.clear()
        self.client = self.client_class(HTTP_HOST=HOST)  # /s/<endereco>/ fica no domínio do painel
        self.conta, self.site = conta_com_site(frase="Ofertas todo dia")
        self.botao = BotaoSite.objects.create(site=self.site, texto="Grupo VIP", url="https://chat.whatsapp.com/abc", destaque=True)
        self.produto = ProdutoSite.objects.create(
            site=self.site, fonte="bot", item_id="1", nome="Fone TWS", preco=Decimal("59.90"), desconto=70,
            categoria="eletronicos", link_produto="https://shopee.com.br/p-i.9.1", link_afiliado="https://s.shopee.com.br/fone",
            posicao_em=timezone.now(),
        )

    def test_pagina_conta_a_visita_e_mostra_a_marca(self):
        html = self.client.get("/s/achadinhos/").content.decode()
        for trecho in ("Achadinhos", "Ofertas todo dia", "Grupo VIP", "Fone TWS", "R$ 59,90", "-70%", "Feito com Appfiliado",
                       'href="/s/achadinhos/b/', 'action="/s/achadinhos/ir/"'):
            self.assertIn(trecho, html)
        self.assertEqual(CliqueSite.objects.get(tipo="visita").total, 1)

    def test_formato_da_vitrine(self):
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertIn('class="grade" id="lista-vitrine"', html)  # lista (padrão)
        SiteAfiliado.objects.filter(pk=self.site.pk).update(vitrine_formato="carrossel")
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertIn('class="grade carrossel" id="lista-vitrine"', html)
        self.assertIn("em-carrossel", html)

    def test_textos_do_conversor(self):
        self.assertContains(self.client.get("/s/achadinhos/"), "Achou algo na Shopee?")  # padrão
        SiteAfiliado.objects.filter(pk=self.site.pk).update(
            conversor_titulo="Viu algo legal?", conversor_texto="Cola o link aqui embaixo!", conversor_botao="Bora!",
        )
        html = self.client.get("/s/achadinhos/").content.decode()
        for trecho in ("Viu algo legal?", "Cola o link aqui embaixo!", "Bora!"):
            self.assertIn(trecho, html)
        self.assertNotIn("Achou algo na Shopee?", html)

    def test_sem_marca_com_o_adicional(self):
        self.conta.modulos_cortesia = "site,site_sem_marca"
        self.conta.save()
        self.assertNotContains(self.client.get("/s/achadinhos/"), "Feito com Appfiliado")

    def test_fora_do_ar_ou_sem_modulo_da_404(self):
        self.site.publicado = False
        self.site.save()
        self.assertEqual(self.client.get("/s/achadinhos/").status_code, 404)
        self.assertEqual(self.client.get("/s/achadinhos/?previa=1").status_code, 404)  # prévia só para o dono
        self.site.publicado = True
        self.site.save()
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        self.assertEqual(self.client.get("/s/achadinhos/").status_code, 404)
        self.assertEqual(self.client.get("/s/naoexiste/").status_code, 404)

    def test_cliques_em_botao_e_produto(self):
        resposta = self.client.get(f"/s/achadinhos/b/{self.botao.pk}/")
        self.assertRedirects(resposta, "https://chat.whatsapp.com/abc", fetch_redirect_response=False)
        resposta = self.client.get(f"/s/achadinhos/p/{self.produto.pk}/")
        self.assertRedirects(resposta, "https://s.shopee.com.br/fone", fetch_redirect_response=False)
        self.assertEqual(dict(CliqueSite.objects.values_list("tipo", "total")), {"botao": 1, "produto": 1})

    def test_icones_das_redes(self):
        SiteAfiliado.objects.filter(pk=self.site.pk).update(redes={"instagram": "https://instagram.com/bia"})
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertIn('href="/s/achadinhos/r/instagram/"', html)
        resposta = self.client.get("/s/achadinhos/r/instagram/")
        self.assertRedirects(resposta, "https://instagram.com/bia", fetch_redirect_response=False)
        self.assertEqual(CliqueSite.objects.get(tipo="rede").total, 1)
        self.assertEqual(self.client.get("/s/achadinhos/r/tiktok/").status_code, 404)

    def test_produto_sem_link_gera_na_hora(self):
        ProdutoSite.objects.filter(pk=self.produto.pk).update(link_afiliado="")
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/novo"):
            resposta = self.client.get(f"/s/achadinhos/p/{self.produto.pk}/")
        self.assertRedirects(resposta, "https://s.shopee.com.br/novo", fetch_redirect_response=False)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.link_afiliado, "https://s.shopee.com.br/novo")

    def test_conversor(self):
        resposta = self.client.get("/s/achadinhos/ir/", {"link": "https://amazon.com.br/x"})
        self.assertRedirects(resposta, "/s/achadinhos/?erro=link#conversor", fetch_redirect_response=False)
        with mock.patch("bot_whatsapp.copia.identificar_produto", return_value="22"), \
                mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=produto(22)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/meu") as gerar:
            resposta = self.client.get("/s/achadinhos/ir/", {"link": "https://s.shopee.com.br/deOutroAfiliado"})
        self.assertRedirects(resposta, "https://s.shopee.com.br/meu", fetch_redirect_response=False)
        self.assertEqual(gerar.call_args.args[2:], ("https://shopee.com.br/p-i.9.22", ["site"]))  # link limpo + Sub ID
        self.assertEqual(CliqueSite.objects.get(tipo="conversor").total, 1)

    def test_conversor_tem_limite_por_visitante(self):
        with mock.patch("bot_whatsapp.copia.identificar_produto", return_value=""), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/meu"):
            for _ in range(20):
                self.client.get("/s/achadinhos/ir/", {"link": "https://shopee.com.br/x"})
            resposta = self.client.get("/s/achadinhos/ir/", {"link": "https://shopee.com.br/x"})
        self.assertRedirects(resposta, "/s/achadinhos/?erro=limite#conversor", fetch_redirect_response=False)

    @override_settings(APPFILIADO_SITES_DOMINIO="appfiliado.com.br", ALLOWED_HOSTS=[".appfiliado.com.br", "testserver"])
    def test_subdominio(self):
        html = self.client.get("/", HTTP_HOST="achadinhos.appfiliado.com.br").content.decode()
        self.assertIn("Grupo VIP", html)
        self.assertIn('href="/b/', html)  # na raiz do subdomínio
        resposta = self.client.get(f"/p/{self.produto.pk}/", HTTP_HOST="achadinhos.appfiliado.com.br")
        self.assertRedirects(resposta, "https://s.shopee.com.br/fone", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/", HTTP_HOST="naoexiste.appfiliado.com.br").status_code, 404)
        # reservado: não vira site
        self.assertNotIn("Grupo VIP", self.client.get("/", HTTP_HOST="www.appfiliado.com.br").content.decode())
