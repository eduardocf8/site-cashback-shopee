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
from licencas import planos
from licencas.models import ContaAppfiliado
from painel import cripto
from painel.tests import HOST, BasePainel

from . import vitrine
from .forms import BotaoForm, SiteForm
from .models import BotaoSite, CategoriaProdutoSite, CliqueSite, ProdutoSite, SiteAfiliado


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
    def test_entra_no_topo_sem_duplicar_e_fica_com_as_200_mais_recentes(self):
        conta, site = conta_com_site()  # Standard: até 200
        agora = timezone.now()
        for i in range(205):
            vitrine.registrar_do_bot(conta, produto(i), agora + timedelta(seconds=i))
        self.assertEqual(site.produtos.count(), 200)
        self.assertFalse(site.produtos.filter(item_id__in=["0", "4"]).exists())  # as mais antigas saíram
        self.assertEqual(site.produtos.first().item_id, "204")
        vitrine.registrar_do_bot(conta, produto(50, preco=49.9), agora + timedelta(minutes=10))  # reenviado
        self.assertEqual(site.produtos.count(), 200)
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


@mock.patch.dict(planos.SITE[False], {"ofertas": 100})  # contas mais fáceis de conferir
class TestVitrineEquilibrada(TestCase):
    """As categorias não podem ficar com 40 ofertas de uma e 1 de outra."""

    def contagem(self, site):
        from collections import Counter

        return Counter(site.produtos.values_list("categoria", flat=True))

    def test_ofertas_em_geral_no_maximo_15_por_categoria(self):
        _, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA)
        # Os mais vendidos: as 3 primeiras páginas só de Beleza, depois de tudo um pouco.
        cats = ["100631", "100636", "100013", "100639", "100637", "100010", "100638", "100001"]

        def pagina(app_id, secret, config, n):
            if n <= 3:
                return [produto(n * 100 + i, categoria_id=100630) for i in range(50)], True
            return [produto(n * 100 + i, categoria_id=int(cats[i % len(cats)])) for i in range(50)], n < 6

        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=pagina):
            vitrine.atualizar_busca(site, timezone.now())
        contagem = self.contagem(site)
        self.assertEqual(site.produtos.count(), 100)
        self.assertEqual(contagem["100630"], 15)
        self.assertEqual(max(contagem.values()), 15)

    def test_ofertas_em_geral_completa_com_o_que_passou_do_teto(self):
        _, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA)
        with mock.patch.object(shopee_ofertas, "buscar_produtos",
                               side_effect=lambda a, s, c, n: ([produto(n * 100 + i, categoria_id=100630) for i in range(50)], n < 2)):
            vitrine.atualizar_busca(site, timezone.now())
        self.assertEqual(site.produtos.count(), 100)  # só tinha Beleza: não deixa a vitrine com 15

    def test_categorias_buscadas_uma_a_uma_e_divididas_por_igual(self):
        _, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA, busca_tipo=SiteAfiliado.BUSCA_CATEGORIA,
                                     categorias=["beleza", "pet"])
        pedidas = []

        def busca(app_id, secret, config, n):
            pedidas.append((config.categoria_shopee, config.tipo_busca))
            pet = config.categoria_shopee == "100631"  # Pet só tem 30
            return [produto(int(config.categoria_shopee) * 1000 + n * 100 + i, categoria_id=int(config.categoria_shopee))
                    for i in range(30 if pet else 50)], not pet and n < 2

        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca):
            vitrine.atualizar_busca(site, timezone.now())
        self.assertEqual({c for c, _ in pedidas}, {"100630", "100631"})
        self.assertEqual({t for _, t in pedidas}, {"geral"})  # sem o filtro pelo nome
        contagem = self.contagem(site)
        self.assertEqual(site.produtos.count(), 100)
        self.assertEqual((contagem["100631"], contagem["100630"]), (30, 70))  # Pet só tinha 30: Beleza completa
        ordem = list(site.produtos.order_by("-posicao_em").values_list("categoria", flat=True)[:4])
        self.assertEqual(ordem, ["100630", "100631", "100630", "100631"])  # intercaladas

    def test_tres_categorias_com_bastante_dividem_por_igual(self):
        _, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA, busca_tipo=SiteAfiliado.BUSCA_CATEGORIA,
                                     categorias=["beleza", "pet", "casa"])
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=lambda a, s_, c, n: (
                [produto(int(c.categoria_shopee) * 1000 + n * 100 + i, categoria_id=int(c.categoria_shopee)) for i in range(50)], n < 2)):
            vitrine.atualizar_busca(site, timezone.now())
        self.assertEqual(sorted(self.contagem(site).values()), [33, 33, 34])

    def test_vitrine_do_bot_tira_da_categoria_com_mais(self):
        conta, site = conta_com_site()
        agora = timezone.now()
        for i in range(10):
            vitrine.registrar_do_bot(conta, produto(1000 + i, categoria_id=100631), agora + timedelta(seconds=i))
        for i in range(120):  # depois, o bot só manda Beleza
            vitrine.registrar_do_bot(conta, produto(i, categoria_id=100630), agora + timedelta(minutes=1, seconds=i))
        contagem = self.contagem(site)
        self.assertEqual(site.produtos.count(), 100)
        self.assertEqual((contagem["100631"], contagem["100630"]), (10, 90))  # as 10 de Pet ficaram
        self.assertFalse(site.produtos.filter(item_id__in=["0", "29"]).exists())  # saíram as de Beleza mais antigas
        self.assertTrue(site.produtos.filter(item_id="30").exists())


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
        conta, site = conta_com_site(modulos="site,site_sem_marca,whatsapp", vitrine=SiteAfiliado.VITRINE_MANUAL,
                                     pedido_vitrine_em=timezone.now(), links_manuais="https://shopee.com.br/a-i.1.11\nhttps://shopee.com.br/b-i.1.22\nhttps://amazon.com/x")
        achados = {"11": produto(11), "22": produto(22)}
        with mock.patch("bot_whatsapp.copia.identificar_produto", side_effect=lambda l: l.rsplit(".", 1)[-1] if "shopee" in l else ""), \
                mock.patch.object(shopee_ofertas, "buscar_produto_por_item", side_effect=lambda a, s, i: achados.get(i)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="x"):
            vitrine.uma_volta()
        self.assertEqual(list(site.produtos.values_list("item_id", flat=True)), ["11", "22"])
        site.refresh_from_db()
        self.assertIn("Não achei 1 produto", site.vitrine_erro)


class TestLimitesPorPlano(TestCase):
    def busca(self, a, s, config, n):
        return [produto(n * 100 + i, categoria_id=100630 + i % 9) for i in range(50)], True

    def test_busca_com_200_no_standard_e_1000_no_premium(self):
        _, site = conta_com_site(vitrine=SiteAfiliado.VITRINE_BUSCA)
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=self.busca):
            vitrine.atualizar_busca(site, timezone.now())
        self.assertEqual(site.produtos.count(), 200)
        _, premium = conta_com_site("leo@exemplo.com", "site,site_sem_marca", endereco="leo", vitrine=SiteAfiliado.VITRINE_BUSCA)
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=self.busca):
            vitrine.atualizar_busca(premium, timezone.now())
        self.assertEqual(premium.produtos.count(), 1000)

    def test_escolhidos_aos_poucos_ate_terminar(self):
        links = "\n".join(f"https://shopee.com.br/p-i.1.{i}" for i in range(1, 121)) + "\nhttps://amazon.com/x"
        _, site = conta_com_site(modulos="site,site_sem_marca", vitrine=SiteAfiliado.VITRINE_MANUAL,
                                 pedido_vitrine_em=timezone.now(), links_manuais=links)
        ProdutoSite.objects.create(site=site, fonte=SiteAfiliado.VITRINE_MANUAL, item_id="999", nome="Saiu da lista",
                                   link_produto="https://shopee.com.br/x", posicao_em=timezone.now())
        with mock.patch("bot_whatsapp.copia.identificar_produto", side_effect=lambda l: l.rsplit(".", 1)[-1] if "shopee" in l else ""), \
                mock.patch.object(shopee_ofertas, "buscar_produto_por_item", side_effect=lambda a, s, i: produto(i)), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="x"):
            agora = timezone.now()
            for volta in range(1, 3):
                vitrine.uma_volta(agora + timedelta(seconds=volta))
                site.refresh_from_db()
                self.assertTrue(site.vitrine_pedida)  # ainda montando
                self.assertEqual(site.manuais_rodada["feitos"], 50 * volta)
            self.assertTrue(ProdutoSite.objects.filter(item_id="999").exists())  # só sai no fim
            vitrine.uma_volta(agora + timedelta(seconds=3))
        site.refresh_from_db()
        self.assertFalse(site.vitrine_pedida)
        self.assertEqual(site.manuais_rodada, {})
        self.assertIn("Não achei 1 produto", site.vitrine_erro)
        itens = list(site.produtos.values_list("item_id", flat=True))
        self.assertEqual((len(itens), itens[0], itens[-1]), (120, "1", "120"))  # na ordem dos links

    def test_formulario_barra_mais_de_1000_links(self):
        conta, site = conta_com_site(modulos="site,site_sem_marca")
        form = SiteForm({"endereco": "achadinhos", "publicado": "on", "nome": "Bia", "cor": "#E8541E", "sub_id": "site",
                         "vitrine": "manual", "busca_tipo": "geral", "ordenacao": "mais_vendidos",
                         "links_manuais": "\n".join(f"https://shopee.com.br/p-i.1.{i}" for i in range(1001))},
                        instance=site, tem_bot=False, regras=planos.site(conta))
        self.assertFalse(form.is_valid())
        self.assertIn("São até 1.000 produtos. Você colou 1.001.", form.errors["links_manuais"][0])


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

    def test_cor_pronta_ou_outra_e_estilo(self):
        form = SiteForm(self.dados(cor="outra", cor_outra="#ffcc00", layout="claro"), instance=self.site)
        self.assertTrue(form.is_valid(), form.errors)
        site = form.save()
        self.assertEqual((site.cor, site.layout), ("#FFCC00", "claro"))
        self.assertEqual(SiteForm(instance=site)["cor"].value(), "outra")  # volta marcada a "outra cor"
        self.assertIn("cor", SiteForm(self.dados(cor="outra", cor_outra="amarelo"), instance=self.site).errors)
        self.assertIn("cor", SiteForm(self.dados(cor="#123456"), instance=self.site).errors)  # fora das prontas
        form = SiteForm(self.dados(), instance=site)  # sem o campo do estilo: mantém
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().layout, "claro")

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

    def test_previa_ao_vivo_e_emojis(self):
        self.client.get("/meu-site/")
        site = SiteAfiliado.objects.get(conta=self.conta)
        site.redes = {"instagram": "https://instagram.com/bia"}
        site.mostrar_conversor = False
        site.save()
        BotaoSite.objects.create(site=site, texto="Grupo", url="https://chat.whatsapp.com/x")
        html = self.client.get("/meu-site/").content.decode()
        self.assertIn('data-botao-texto="novo"', html)
        self.assertIn("painel/emojis", html)
        self.assertIn("data-emoji", html)
        self.assertLess(html.index('id="titulo-cliques"'), html.index('id="titulo-previa"'))  # prévia embaixo, presa na tela
        previa = self.client.get(f"/s/{site.endereco}/?previa=1").content.decode()
        self.assertIn('data-botao="novo" hidden', previa)
        self.assertIn('data-rede="instagram"', previa)
        self.assertIn('data-rede="tiktok"', previa)  # na prévia vão todos, escondidos os vazios
        self.assertIn('id="conversor" hidden', previa)
        publico = self.client.get(f"/s/{site.endereco}/").content.decode()
        self.assertNotIn('data-rede="tiktok"', publico)

    def test_corrigir_categoria_do_produto(self):
        self.client.get("/meu-site/")
        site = SiteAfiliado.objects.get(conta=self.conta)
        site.vitrine = "bot"
        site.save()
        p = ProdutoSite.objects.create(site=site, fonte="bot", item_id="77", nome="Fone de ouvido", categoria="eletronicos",
                                       link_produto="https://shopee.com.br/p-i.1.77", posicao_em=timezone.now())
        html = self.client.get("/meu-site/").content.decode()
        self.assertIn("corrigir as categorias", html)
        self.assertIn('<option value="100636">Casa e Decoração</option>', html)  # as categorias da Shopee
        self.assertEqual(self.client.post(f"/meu-site/produto/{p.pk}/categoria/", {"categoria": "100630"}).json()["categoria"], "100630")
        p.refresh_from_db()
        self.assertEqual(p.categoria, "100630")  # Beleza
        # A escolha vale nas próximas atualizações da vitrine.
        vitrine.registrar_do_bot(self.conta, produto("77", nome="Fone de ouvido", categoria_id=100535))
        p.refresh_from_db()
        self.assertEqual(p.categoria, "100630")
        self.assertEqual(CategoriaProdutoSite.objects.get(site=site).categoria, "100630")
        self.assertEqual(self.client.post(f"/meu-site/produto/{p.pk}/categoria/", {"categoria": "inventada"}).json()["categoria"], "")
        outra = ContaAppfiliado.objects.create(email="outra@exemplo.com")
        outro_site = SiteAfiliado.objects.create(conta=outra, endereco="outra")
        q = ProdutoSite.objects.create(site=outro_site, fonte="bot", item_id="9", nome="X", link_produto="https://shopee.com.br/x",
                                       posicao_em=timezone.now())
        self.assertEqual(self.client.post(f"/meu-site/produto/{q.pk}/categoria/", {"categoria": "100630"}).status_code, 404)

    def test_categoria_vem_da_shopee_e_os_antigos_sao_atualizados(self):
        self.assertEqual(vitrine.categoria_do_produto({"nome": "Batom", "categoria_id": 100636}), "100636")
        self.assertEqual(vitrine.categoria_do_produto({"nome": "Batom matte vermelho"}), "100630")  # sem categoria: pelo nome
        self.assertEqual(vitrine.categoria_do_produto({"nome": "Coisa sem pista nenhuma"}), "")
        self.assertEqual(vitrine.nome_curto_da_categoria("100535"), "Áudio")
        self.assertEqual(vitrine.nome_curto_da_categoria("eletronicos"), "Eletrônicos")  # guardado antes da troca
        self.client.get("/meu-site/")
        site = SiteAfiliado.objects.get(conta=self.conta)
        self.conta.shopee_app_id = "1"
        self.conta.shopee_secret_cifrado = cripto.cifrar("s")
        self.conta.save()
        antigo = ProdutoSite.objects.create(site=site, fonte="bot", item_id="5", nome="Fone", categoria="eletronicos",
                                            link_produto="https://shopee.com.br/p-i.1.5", posicao_em=timezone.now())
        corrigido = ProdutoSite.objects.create(site=site, fonte="bot", item_id="6", nome="Fone 2", categoria="eletronicos",
                                               link_produto="https://shopee.com.br/p-i.1.6", posicao_em=timezone.now())
        CategoriaProdutoSite.objects.create(site=site, item_id="6", categoria="")
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=produto("5", categoria_id=100535)) as buscar:
            self.assertEqual(vitrine.atualizar_categorias_antigas(), 1)
        buscar.assert_called_once()  # o corrigido pela pessoa não é buscado
        antigo.refresh_from_db()
        corrigido.refresh_from_db()
        self.assertEqual((antigo.categoria, corrigido.categoria), ("100535", "eletronicos"))
        self.assertEqual(shopee_ofertas.normalizar_produto({"itemId": 1, "productCatIds": [100630, 101, 102]})["categoria_id"], 100630)
        self.assertEqual(shopee_ofertas.normalizar_produto({"itemId": 1})["categoria_id"], 0)

    def test_sub_id_separado_para_a_vitrine(self):
        self.client.get("/meu-site/")
        site = SiteAfiliado.objects.get(conta=self.conta)
        self.conta.shopee_app_id = "1"
        self.conta.shopee_secret_cifrado = cripto.cifrar("s")
        self.conta.save()
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x") as gerar:
            vitrine.link_do_site(site, "https://shopee.com.br/p", vitrine=True)
            self.assertEqual(gerar.call_args[0][3], ["site"])  # em branco: o mesmo do conversor
            site.sub_id_vitrine = "vitrine"
            vitrine.link_do_site(site, "https://shopee.com.br/p", vitrine=True)
            self.assertEqual(gerar.call_args[0][3], ["vitrine"])
            vitrine.link_do_site(site, "https://shopee.com.br/p")
            self.assertEqual(gerar.call_args[0][3], ["site"])  # conversor
        self.assertIn('name="sub_id_vitrine"', self.client.get("/meu-site/").content.decode())

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

    def test_vitrine_grande_aparece_de_60_em_60(self):
        agora = timezone.now()
        ProdutoSite.objects.bulk_create([ProdutoSite(
            site=self.site, fonte="bot", item_id=str(100 + i), nome=f"Produto {i}", link_produto="https://shopee.com.br/x",
            posicao_em=agora - timedelta(minutes=i)) for i in range(250)])
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertEqual(html.count('class="produto"'), 200)  # Standard: até 200
        self.assertEqual(html.count('class="produto"') - html.count('" hidden>'), 60)
        self.assertIn('id="ver-mais" data-por-vez="60">Ver mais ofertas', html)

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

    def test_estilo_e_contraste_da_cor(self):
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertIn('<body class="tema-colorido">', html)
        self.assertIn("--tinta: #FFFFFF", html)  # laranja: texto branco
        SiteAfiliado.objects.filter(pk=self.site.pk).update(layout="claro", cor="#FFE066")
        html = self.client.get("/s/achadinhos/").content.decode()
        self.assertIn('<body class="tema-claro">', html)
        self.assertIn("--sobre-cor: #1C2B23", html)  # amarelo claro: texto escuro por cima
        self.assertIn("--tinta: #1C2B23", html)

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


class TestCores(TestCase):
    def test_contas(self):
        from . import cores

        self.assertEqual(cores.misturar("#FFFFFF", "#000000", 0.5), "#808080")
        self.assertEqual(cores.tinta_sobre("#111111"), "#FFFFFF")
        self.assertEqual(cores.tinta_sobre("#F2B705"), cores.TINTA_ESCURA)
        self.assertLessEqual(cores.luminancia(cores.para_texto("#F2B705")), 0.3)  # preço legível no branco
        self.assertEqual(cores.para_texto("#1F3A2E"), "#1F3A2E")
        self.assertEqual(cores.tema("nada")["cor"], "#E8541E")


class TestLimitesDoPlano(BasePainel):
    """Standard: até 3 botões e vitrine do bot ou da busca. Premium (site_sem_marca): até 10
    botões, vitrine com os produtos escolhidos e sem a marca."""

    def setUp(self):
        super().setUp()
        self.conta.modulos_cortesia = "site,whatsapp"
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        self.entrar()
        self.client.get("/meu-site/")
        self.site = SiteAfiliado.objects.get(conta=self.conta)

    def novo_botao(self, texto):
        return self.client.post("/meu-site/", {"acao": "botao_novo", "texto": texto, "url": f"https://x.com/{texto}"}, follow=True)

    def test_botoes_por_plano(self):
        for i in range(3):
            self.novo_botao(f"b{i}")
        resposta = self.novo_botao("quarto")
        self.assertContains(resposta, "No seu plano dá para ter até 3 botões. No plano Premium são até 10.")
        self.assertEqual(self.site.botoes.count(), 3)
        self.assertContains(resposta, "3 de 3")

        self.conta.modulos_cortesia = "site,site_sem_marca"
        self.conta.save()
        for i in range(3, 12):
            self.novo_botao(f"b{i}")
        self.assertEqual(self.site.botoes.count(), 10)

        # Voltou para o Standard: o site mostra só os 3 primeiros e o editor avisa.
        self.conta.modulos_cortesia = "site"
        self.conta.save()
        self.site.publicado = True
        self.site.save()
        html = self.client.get("/s/biasouza/").content.decode()
        self.assertIn(">b2</a>", html)
        self.assertNotIn(">b3</a>", html)
        self.assertContains(self.client.get("/meu-site/"), "os de baixo ficam escondidos")

    def test_produtos_escolhidos_so_no_premium(self):
        html = self.client.get("/meu-site/").content.decode()
        self.assertRegex(html, r'value="manual" disabled><span>Produtos que eu escolher <small class="selo-premium">Premium')
        dados = {"acao": "salvar", "endereco": "biasouza", "nome": "Bia", "cor": "#2F6FDE", "sub_id": "site",
                 "vitrine": "manual", "links_manuais": "https://shopee.com.br/a-i.1.11", "ordenacao": "mais_vendidos",
                 "busca_tipo": "geral"}
        resposta = self.client.post("/meu-site/", dados)
        self.assertContains(resposta, "A vitrine com os produtos que você escolher é do plano Premium.")
        self.site.refresh_from_db()
        self.assertNotEqual(self.site.vitrine, "manual")

        self.conta.modulos_cortesia = "site,site_sem_marca"
        self.conta.save()
        self.assertNotContains(self.client.get("/meu-site/"), 'class="selo-premium"')
        resposta = self.client.post("/meu-site/", dados)
        self.assertRedirects(resposta, "/meu-site/", fetch_redirect_response=False)
        self.site.refresh_from_db()
        self.assertEqual(self.site.vitrine, "manual")

    def test_vitrine_manual_sem_premium_fica_vazia_e_o_worker_avisa(self):
        self.site.vitrine, self.site.publicado = SiteAfiliado.VITRINE_MANUAL, True
        self.site.links_manuais, self.site.pedido_vitrine_em = "https://shopee.com.br/a-i.1.11", timezone.now()
        self.site.save()
        ProdutoSite.objects.create(site=self.site, fonte="manual", item_id="11", nome="Produto escolhido",
                                   link_produto="https://shopee.com.br/a-i.1.11", posicao_em=timezone.now())
        vitrine.uma_volta()
        self.site.refresh_from_db()
        self.assertIn("plano Premium", self.site.vitrine_erro)
        self.assertNotContains(self.client.get("/s/biasouza/"), "Produto escolhido")
