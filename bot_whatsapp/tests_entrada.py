import io
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from django.core import mail
from django.utils import timezone

from meusite.models import SiteAfiliado
from painel.tests import BasePainel

from . import entrada, grupos_novos
from . import gerenciador as g
from .models import AcessoEntrada, ConexaoWhatsApp, ConviteGrupo, GrupoMonitorado, LinkEntrada, PedidoGrupo

GRUPOS = [{"jid": f"{i}@g.us", "nome": f"Achadinhos #{i}", "participantes": 0, "tipo": "grupo", "admin": True}
          for i in (1, 2, 10)]
NAVEGADOR = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone) Instagram 300.0"}


class BaseEntrada(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.beta_link_entrada = True
        self.conta.save()
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", numero="5511988887777", grupos=GRUPOS)
        SiteAfiliado.objects.create(conta=self.conta, endereco="achadinhosdabia", publicado=False)

    def criar_link(self, **extra):
        link = LinkEntrada.objects.create(conta=self.conta, slug="grupo-vip", pixel_id="123456789", **extra)
        entrada.salvar_grupos(link, [g["jid"] for g in GRUPOS], self.conexao)
        return link

    def membros(self, jid, quantos):
        GrupoMonitorado.objects.filter(conta=self.conta, jid=jid).update(membros=quantos)

    def convite(self, jid, link="", erro=""):
        ConviteGrupo.objects.filter(conta=self.conta, jid=jid).update(link=link, erro=erro, lido_em=timezone.now())


class TestPainel(BaseEntrada):
    def test_so_aparece_com_a_chave_beta(self):
        self.assertContains(self.client.get("/whatsapp/membros/"), "Link de entrada")
        self.conta.beta_link_entrada = False
        self.conta.save()
        self.assertNotContains(self.client.get("/whatsapp/membros/"), "Link de entrada")
        self.assertEqual(self.client.get("/whatsapp/entrada/").status_code, 404)

    def test_criar_e_configurar_um_link(self):
        resposta = self.client.post("/whatsapp/entrada/", {"acao": "novo"})
        link = LinkEntrada.objects.get()
        self.assertRedirects(resposta, f"/whatsapp/entrada/{link.pk}/", fetch_redirect_response=False)
        resposta = self.client.post(f"/whatsapp/entrada/{link.pk}/", {
            "acao": "salvar", "ativo": "on", "slug": "vip", "titulo": "Grupo VIP da Bia", "frase": "Ofertas todo dia",
            "texto_botao": "Quero entrar", "pixel_id": "1234567890", "limite_por_grupo": "1000",
            "grupos": ["10@g.us", "1@g.us", "x@g.us"], "criar_sozinho": "on", "admins_dos_novos": "(11) 97777-6666"})
        self.assertRedirects(resposta, f"/whatsapp/entrada/{link.pk}/", fetch_redirect_response=False)
        link.refresh_from_db()
        self.assertEqual((link.slug, link.titulo, link.pixel_id, link.criar_sozinho), ("vip", "Grupo VIP da Bia", "1234567890", True))
        self.assertEqual(link.grupos, ["10@g.us", "1@g.us"])  # só os do número do bot
        self.assertEqual(link.admins_dos_novos, ["5511977776666"])
        self.assertEqual(set(ConviteGrupo.objects.values_list("jid", flat=True)), {"1@g.us", "10@g.us"})
        self.assertEqual(set(GrupoMonitorado.objects.values_list("jid", flat=True)), {"1@g.us", "10@g.us"})  # vão pra aba Grupos

        html = self.client.get(f"/whatsapp/entrada/{link.pk}/").content.decode()
        self.assertIn("/s/achadinhosdabia/vip/", html)  # sem o "g/"
        self.assertLess(html.index("Achadinhos #1<"), html.index("Achadinhos #10<"))  # ordem do nome, numérica

    def test_endereco_reservado_pelo_site_nao_vale(self):
        link = self.criar_link()
        self.client.post(f"/whatsapp/entrada/{link.pk}/", {
            "acao": "salvar", "ativo": "on", "slug": "p", "titulo": "Grupo", "texto_botao": "Entrar",
            "limite_por_grupo": "1000", "grupos": list(link.grupos)})
        link.refresh_from_db()
        self.assertEqual(link.slug, "grupo-vip")

    def test_colar_o_convite_a_mao(self):
        link = self.criar_link()
        self.convite("2@g.us", erro="O número do bot não é administrador desse grupo")
        self.client.post(f"/whatsapp/entrada/{link.pk}/", {"acao": "convite", "jid": "2@g.us", "convite": "https://exemplo.com"})
        self.assertEqual(ConviteGrupo.objects.get(jid="2@g.us").link, "")
        self.client.post(f"/whatsapp/entrada/{link.pk}/", {"acao": "convite", "jid": "2@g.us", "convite": "https://chat.whatsapp.com/XYZ"})
        convite = ConviteGrupo.objects.get(jid="2@g.us")
        self.assertEqual((convite.link, convite.manual), ("https://chat.whatsapp.com/XYZ", True))


    def test_aba_chama_grupos(self):
        html = self.client.get("/whatsapp/membros/").content.decode()
        self.assertIn(">Grupos</a>", html)
        self.assertNotIn(">Membros</a>", html)

    def test_foto_propria_ou_a_do_meu_site(self):
        link = self.criar_link()
        link.ativo = True
        link.save()
        SiteAfiliado.objects.filter(conta=self.conta).update(foto=b"foto-do-site")
        publica, painel = "/s/achadinhosdabia/g/grupo-vip/foto.jpg", f"/whatsapp/entrada/{link.pk}/foto.jpg"
        self.assertEqual(self.client.get(publica).content, b"foto-do-site")  # padrão: a do Meu site
        self.assertContains(self.client.get(f"/whatsapp/entrada/{link.pk}/"), "Por enquanto é a foto do Meu site")

        arquivo = io.BytesIO()
        Image.new("RGB", (800, 500), "red").save(arquivo, "PNG")
        resposta = self.client.post(f"/whatsapp/entrada/{link.pk}/", {
            "acao": "foto", "foto": SimpleUploadedFile("f.png", arquivo.getvalue(), content_type="image/png")})
        self.assertRedirects(resposta, f"/whatsapp/entrada/{link.pk}/#titulo-pagina", fetch_redirect_response=False)
        link.refresh_from_db()
        self.assertEqual((Image.open(io.BytesIO(bytes(link.foto))).size, link.foto_versao), ((320, 320), 1))
        self.assertEqual(self.client.get(publica).content, bytes(link.foto))
        self.assertEqual(self.client.get(painel).content, bytes(link.foto))
        self.assertContains(self.client.get(f"/whatsapp/entrada/{link.pk}/"), "Usar a do Meu site")

        self.client.post(f"/whatsapp/entrada/{link.pk}/", {"acao": "remover_foto"})
        self.assertEqual(self.client.get(publica).content, b"foto-do-site")
        SiteAfiliado.objects.filter(conta=self.conta).update(foto=None)
        self.assertEqual(self.client.get(painel).status_code, 404)

    def test_excluir(self):
        link = self.criar_link()
        html = self.client.get(f"/whatsapp/entrada/{link.pk}/").content.decode()
        self.assertIn('form="form-excluir"', html)
        self.client.post(f"/whatsapp/entrada/{link.pk}/", {"acao": "excluir"})
        self.assertFalse(LinkEntrada.objects.exists())


class TestAparencia(BaseEntrada):
    def salvar(self, link, **extra):
        dados = {"acao": "salvar", "ativo": "on", "slug": link.slug, "titulo": "Grupo VIP", "frase": "", "texto_botao": "Entrar",
                 "pixel_id": "", "limite_por_grupo": "1000", "grupos": list(link.grupos), "modelo": "beneficios",
                 "cor": "outra", "cor_outra": "#123abc", "nome_exibido": "@bia", "beneficios": ["🏷️ Cupons", "", "⚡ Relâmpago", ""],
                 "selos": ["🔥 Todo dia", "", ""], "mostrar_selos": "on", "mostrar_total": "on"}
        dados.update(extra)
        return self.client.post(f"/whatsapp/entrada/{link.pk}/", dados)

    def test_salva_modelo_cor_textos_e_blocos(self):
        link = self.criar_link()
        self.salvar(link)
        link.refresh_from_db()
        self.assertEqual((link.modelo, link.cor, link.nome_exibido, link.beneficios, link.selos),
                         ("beneficios", "#123ABC", "@bia", ["🏷️ Cupons", "⚡ Relâmpago"], ["🔥 Todo dia"]))
        self.assertEqual((link.mostrar_selos, link.mostrar_total, link.mostrar_vagas), (True, True, False))
        self.salvar(link, cor="", modelo="invalido")  # a cor do Meu site; modelo desconhecido não muda
        link.refresh_from_db()
        self.assertEqual((link.modelo, link.cor), ("beneficios", ""))

    def test_previa_mostra_sem_salvar(self):
        link = self.criar_link()
        html = self.client.get(f"/whatsapp/entrada/{link.pk}/previa/", {
            "modelo": "colorido", "titulo": "Teste ao vivo", "cor": "#7048E8", "mostrar_selos": "on", "selos": ["Grátis"]}).content.decode()
        self.assertIn('class="m-colorido', html)
        self.assertIn("Teste ao vivo", html)
        self.assertIn("<span>Grátis</span>", html)
        self.assertNotIn("fbq(", html)  # a prévia não dispara o pixel
        link.refresh_from_db()
        self.assertEqual((link.modelo, link.titulo), ("classico", "Grupo VIP de Achadinhos"))

    def test_capa_propria_ou_fotos_das_ofertas(self):
        from meusite.models import ProdutoSite

        link = self.criar_link(mostrar_capa=True, modelo="vitrine")
        site = SiteAfiliado.objects.get(conta=self.conta)
        site.vitrine = "bot"
        site.save()
        for i in range(5):
            ProdutoSite.objects.create(site=site, fonte="bot", item_id=str(i), nome=f"Produto {i}", preco=10,
                                       imagem_url=f"https://cf.shopee.com.br/file/{i}", link_produto="https://shopee.com.br/x",
                                       posicao_em=timezone.now() - timedelta(minutes=i))
        html = self.client.get(f"/whatsapp/entrada/{link.pk}/previa/").content.decode()
        self.assertIn('<div class="capa">', html)  # sem capa própria: fotos das ofertas
        self.assertEqual(html.count('class="oferta"'), 4)  # modelo Vitrine
        arquivo = io.BytesIO()
        Image.new("RGB", (1600, 900), "blue").save(arquivo, "PNG")
        self.client.post(f"/whatsapp/entrada/{link.pk}/", {
            "acao": "capa", "foto": SimpleUploadedFile("c.png", arquivo.getvalue(), content_type="image/png")})
        link.refresh_from_db()
        self.assertEqual(Image.open(io.BytesIO(bytes(link.capa))).size, (1200, 600))
        self.assertIn('class="capa inteira"', self.client.get(f"/whatsapp/entrada/{link.pk}/previa/").content.decode())
        self.assertEqual(self.client.get(f"/whatsapp/entrada/{link.pk}/capa.jpg").content, bytes(link.capa))


class TestPaginaPublica(BaseEntrada):
    def setUp(self):
        super().setUp()
        self.link = self.criar_link()
        for g_ in GRUPOS:
            self.convite(g_["jid"], f"https://chat.whatsapp.com/{g_['jid'].split('@')[0]}")

    def test_pagina_conta_visita_e_tem_o_pixel(self):
        resposta = self.client.get("/s/achadinhosdabia/g/grupo-vip/?utm_campaign=black", **NAVEGADOR)
        self.assertContains(resposta, "Grupo VIP de Achadinhos")
        self.assertContains(resposta, "fbq('init', '123456789')")
        self.assertContains(resposta, 'href="entrar/?utm_campaign=black"')
        self.client.get("/s/achadinhosdabia/g/grupo-vip/", HTTP_USER_AGENT="facebookexternalhit/1.1")  # prévia do Meta
        self.assertEqual(AcessoEntrada.objects.get(campanha="black").visitas, 1)
        self.assertEqual(sum(AcessoEntrada.objects.values_list("visitas", flat=True)), 1)

    def test_blocos_de_total_e_vagas_com_os_numeros_reais(self):
        self.membros("1@g.us", 1000)
        self.membros("2@g.us", 870)
        self.membros("10@g.us", 377)
        self.link.mostrar_total = self.link.mostrar_vagas = True
        self.link.save()
        html = self.client.get("/s/achadinhosdabia/g/grupo-vip/", **NAVEGADOR).content.decode()
        self.assertIn("Mais de 2.200 pessoas já estão nos grupos", html)  # 2.247, arredondado para baixo
        self.assertIn("Vagas preenchidas no Achadinhos #2", html)
        self.assertIn("870 de 1.000 pessoas", html)

    def test_os_quatro_modelos_abrem(self):
        for modelo in ("classico", "colorido", "beneficios", "vitrine"):
            LinkEntrada.objects.filter(pk=self.link.pk).update(modelo=modelo)
            resposta = self.client.get("/s/achadinhosdabia/g/grupo-vip/", **NAVEGADOR)
            self.assertContains(resposta, f'class="m-{modelo}')
            self.assertContains(resposta, 'href="entrar/"')

    def test_endereco_sem_g_e_o_antigo_com_g(self):
        curto = self.client.get("/s/achadinhosdabia/grupo-vip/?utm_campaign=x", **NAVEGADOR)
        self.assertContains(curto, 'href="entrar/?utm_campaign=x"')
        self.assertRedirects(self.client.get("/s/achadinhosdabia/grupo-vip/entrar/", **NAVEGADOR),
                             "https://chat.whatsapp.com/1", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/s/achadinhosdabia/g/grupo-vip/", **NAVEGADOR).status_code, 200)  # links antigos
        self.assertEqual(self.client.get("/s/achadinhosdabia/nao-existe/", **NAVEGADOR).status_code, 404)

    def test_entrar_manda_pro_primeiro_com_vaga_na_ordem(self):
        self.membros("1@g.us", 1000)  # cheio
        resposta = self.client.get("/s/achadinhosdabia/g/grupo-vip/entrar/?utm_campaign=black", **NAVEGADOR)
        self.assertRedirects(resposta, "https://chat.whatsapp.com/2", fetch_redirect_response=False)
        clique = AcessoEntrada.objects.get(grupo_jid="2@g.us")
        self.assertEqual((clique.cliques, clique.campanha), (1, "black"))

        self.membros("2@g.us", 1000)
        self.convite("10@g.us", erro="não é administrador")  # sem convite: não dá pra mandar
        resposta = self.client.get("/s/achadinhosdabia/g/grupo-vip/entrar/", **NAVEGADOR)
        self.assertEqual(resposta.status_code, 503)
        self.assertContains(resposta, "Os grupos estão cheios neste momento", status_code=503)

    def test_sem_a_chave_ou_pausado_nao_abre(self):
        self.link.ativo = False
        self.link.save()
        self.assertEqual(self.client.get("/s/achadinhosdabia/g/grupo-vip/").status_code, 404)
        self.link.ativo = True
        self.link.save()
        self.conta.beta_link_entrada = False
        self.conta.save()
        self.assertEqual(self.client.get("/s/achadinhosdabia/g/grupo-vip/").status_code, 404)


class TestWorker(BaseEntrada):
    def test_le_os_convites(self):
        self.criar_link()
        cliente = mock.Mock()
        cliente.get_group_invite_link.side_effect = lambda jid: (
            "https://chat.whatsapp.com/OK" if jid.User == "1" else (_ for _ in ()).throw(RuntimeError("403 forbidden")))
        ger = g.Gerenciador()
        ger.sessoes[self.conta.pk] = mock.Mock(conectada=True, cliente=cliente)
        ger.ler_convites(timezone.now())
        self.assertEqual(ConviteGrupo.objects.get(jid="1@g.us").link, "https://chat.whatsapp.com/OK")
        self.assertIn("não é administrador", ConviteGrupo.objects.get(jid="2@g.us").erro)
        self.assertEqual(entrada.convites_para_ler(timezone.now()), [])  # só daqui a 12 h

    def test_tudo_lotando_avisa_e_cria_o_proximo(self):
        link = self.criar_link(criar_sozinho=True, admins_dos_novos=["5511977776666"])
        for g_ in GRUPOS:
            self.membros(g_["jid"], 990)
        agora = timezone.now()
        entrada.cuidar_dos_links(agora)
        pedido = PedidoGrupo.objects.get()
        self.assertEqual((pedido.nome, pedido.base_jid, pedido.link_entrada, pedido.administradores),
                         ("Achadinhos #11", "10@g.us", link, ["5511977776666"]))
        self.assertEqual(pedido.sub_ids, "achadinhos11")  # Sub ID próprio do grupo novo, sugerido sozinho
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Achadinhos #11", mail.outbox[0].body)

        entrada.cuidar_dos_links(agora + timedelta(minutes=5))  # já está criando: nem outro pedido nem outro e-mail
        self.assertEqual((PedidoGrupo.objects.count(), len(mail.outbox)), (1, 1))

        grupos_novos.concluir(pedido, "11@g.us", "https://chat.whatsapp.com/NOVO", 2, [])
        link.refresh_from_db()
        self.assertEqual(link.grupos[-1], "11@g.us")
        self.assertEqual(ConviteGrupo.objects.get(jid="11@g.us").link, "https://chat.whatsapp.com/NOVO")
        self.assertEqual(entrada.grupo_da_vez(link)["jid"], "11@g.us")

    def test_sem_criar_sozinho_so_avisa_uma_vez_por_dia(self):
        self.criar_link()
        for g_ in GRUPOS:
            self.membros(g_["jid"], 1000)
        agora = timezone.now()
        entrada.cuidar_dos_links(agora)
        entrada.cuidar_dos_links(agora + timedelta(hours=2))
        self.assertEqual((PedidoGrupo.objects.count(), len(mail.outbox)), (0, 1))
        self.assertIn("Crie o próximo grupo", mail.outbox[0].body)
        entrada.cuidar_dos_links(agora + timedelta(hours=25))
        self.assertEqual(len(mail.outbox), 2)
