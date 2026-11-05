"""Telas do Bot depois da revisão de layout (11/2026): cabeçalho com o estado, primeira configuração,
passos que abrem e fecham e formulários que continuam salvando."""
import re

from django.utils import timezone

from meusite.models import SiteAfiliado
from painel.tests import BasePainel

from . import entrada
from .models import CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, GrupoMonitorado, LinkEntrada

GRUPOS = [{"jid": "1@g.us", "nome": "Ofertas VIP"}, {"jid": "2@g.us", "nome": "Achadinhos"}]
ABAS = ["/whatsapp/", "/whatsapp/ofertas/", "/whatsapp/campanhas/", "/whatsapp/alertas/", "/whatsapp/mensagens/",
        "/whatsapp/membros/", "/whatsapp/entrada/", "/whatsapp/resultados/"]


class TestCabecalhoDoBot(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_conta_nova_ve_os_4_passos_em_todas_as_abas(self):
        for url in ABAS:
            html = self.client.get(url).content.decode()
            self.assertIn("Configure o bot em 4 passos", html, url)
            self.assertIn("O bot posta sozinho ofertas da Shopee com o seu link de afiliado nos seus grupos.", html, url)
            self.assertIn('<nav class="abas abas-bot"', html, url)
        html = self.client.get("/whatsapp/").content.decode()
        self.assertNotIn("<strong>Desconectado</strong>", html)  # na Conexão, a lista fica no lugar do cartão
        self.assertIn('action="/whatsapp/conectar/"', html)  # e o passo do WhatsApp já gera o QR Code
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("Para ligar as ofertas, falta:", html)
        self.assertIn("conectar a sua conta da Shopee", html)
        self.assertRegex(html, r'disabled title="Termine o que falta para ligar">Ligar ofertas')

    def test_ligado_mostra_as_pilulas_e_os_pontinhos(self):
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS, conectado_em=timezone.now())
        ConfiguracaoOfertas.objects.create(conta=self.conta, ativo=True, grupos=GRUPOS[:1])
        CampanhaBot.objects.create(conta=self.conta, ativo=False)
        html = self.client.get("/whatsapp/resultados/").content.decode()
        self.assertNotIn("Configure o bot", html)
        self.assertIn("WhatsApp conectado</a>", html)
        self.assertIn("Ofertas ligadas <small>· 0 hoje</small>", html)
        self.assertIn('<i class="pt ok" aria-hidden="true"></i>Automação', html)
        self.assertIn('<i class="pt " aria-hidden="true"></i>Campanhas', html)  # desligado: pontinho cinza
        self.assertIn('class="aba ativo" href="/whatsapp/resultados/" aria-current="page"', html)
        html = self.client.get("/whatsapp/").content.decode()
        self.assertIn('<span class="situacao">WhatsApp conectado</span>', html)
        self.assertIn('<details class="card etapa sem-numero teste-envio"', html)  # o teste de envio recolhido


class TestAutomacaoEmPassos(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS, conectado_em=timezone.now())

    def test_resumo_de_cada_passo_e_primeira_vez_abre_os_grupos(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        for titulo in ("Onde enviar", "Quais ofertas", "Mensagem", "Quando enviar", "Modo simulação"):
            self.assertIn(f"<h2>{titulo}</h2>", html)
        self.assertIn('id="onde-enviar" open', html)  # nenhum grupo salvo: já abre a escolha
        self.assertIn("Nenhum grupo escolhido ainda", html)
        ConfiguracaoOfertas.objects.filter(conta=self.conta).update(
            grupos=GRUPOS, comissao_minima=8, cupom="BIA10", intervalo_minutos=10, limite_diario=120)
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertNotIn('id="onde-enviar" open', html)
        self.assertIn("<strong>2 grupos</strong>: Ofertas VIP e Achadinhos", html)
        self.assertIn("Busca na Shopee · ofertas em geral · mais vendidos · comissão 8%+", html)
        self.assertIn("Foto com o texto · cupom BIA10", html)
        # O resumo mostra o intervalo que vale de verdade: 10 min salvo, mas o Standard começa em 15.
        self.assertIn("1 oferta a cada 15 min · até 120 por dia · das 07:00 às 23:00, todos os dias", html)
        self.assertIn('class="botao botao-principal">Ligar ofertas', html)

    def test_passo_com_erro_ja_abre(self):
        resposta = self.client.post("/whatsapp/ofertas/", {
            "modo": "shopee", "tipo_busca": "geral", "ordenacao": "mais_vendidos", "grupos": ["1@g.us"],
            "intervalo_minutos": "999", "horario_inicio": "07:00", "horario_fim": "23:00", "repetir_apos_dias": "7",
            "dias_semana": ["0"],
        })
        html = resposta.content.decode()
        self.assertIn('id="quando-enviar" open', html)
        self.assertIn('class="barra-salvar mudou"', html)  # a faixa Salvar já vem à vista


class TestLinkDeEntradaEmPassos(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        SiteAfiliado.objects.create(conta=self.conta, endereco="achadinhosdabia", publicado=False)
        self.link = LinkEntrada.objects.create(conta=self.conta, slug="grupo-vip")
        entrada.salvar_grupos(self.link, [g["jid"] for g in GRUPOS], conexao)

    def test_convites_fora_do_formulario_principal(self):
        html = self.client.get(f"/whatsapp/entrada/{self.link.pk}/").content.decode()
        principal = html[html.index('<form method="post" class="formulario" id="form-entrada">'):]
        principal = principal[:principal.index("</form>")]
        self.assertNotIn("<form", principal[5:])  # nada de formulário dentro do outro
        self.assertIn('name="convite" form="convite-1"', principal)
        self.assertIn('<form method="post" id="convite-1" hidden>', html)
        self.assertLess(html.index("Grupos do link"), html.index("<h2 id=\"titulo-pagina\">Aparência"))
        self.assertIn('etapa-num alerta">1', html)  # sem grupo com vaga: o número fica vermelho
        lista = self.client.get("/whatsapp/entrada/").content.decode()
        self.assertIn("Nenhum grupo com vaga.", lista)
        self.assertIn(f'href="/whatsapp/entrada/{self.link.pk}/#grupos-do-link">Resolver', lista)


class TestGruposSemDiasDeContagem(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        GrupoMonitorado.objects.create(conta=self.conta, jid="1@g.us", nome="Ofertas VIP", membros=100)

    def test_hoje_no_lugar_do_traco_e_colunas_escondidas(self):
        html = self.client.get("/whatsapp/membros/").content.decode()
        self.assertIn('<span class="kpi-titulo">Hoje</span>', html)
        self.assertEqual(len(re.findall(r'kpi-valor ainda">a partir de \d\d/\d\d', html)), 2)
        self.assertNotIn("<th>24 h</th>", html)
        self.assertNotIn("<th>30 dias</th>", html)
