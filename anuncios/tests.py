import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from bot_whatsapp.models import AcessoEntrada, LinkEntrada
from painel import cripto
from painel.models import ResultadoSubIdDiario
from painel.tests import BasePainel

from . import meta, servico
from .models import CampanhaMeta, ConexaoMeta, ContaAnuncios, DiaCampanha

META = {"APPFILIADO_META_ADS_APP_ID": "1022809654196010", "APPFILIADO_META_ADS_APP_SECRET": "segredo",
        "APPFILIADO_META_ADS_CONFIG_ID": "4136729949793642"}


@override_settings(**META)
class BaseMeta(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.beta_campanhas_meta = True
        self.conta.save()

    def conexao(self, **extra):
        conexao = ConexaoMeta.objects.create(conta=self.conta, usuario_id="777", nome="Bia Souza",
                                             token_cifrado=cripto.cifrar("token-longo"),
                                             token_expira_em=timezone.now() + timedelta(days=50), **extra)
        ContaAnuncios.objects.create(conexao=conexao, account_id="111", nome="Conta da Bia", moeda="BRL")
        return conexao


class TestConexao(BaseMeta):
    def test_so_aparece_com_a_chave_beta(self):
        self.assertContains(self.client.get("/resultados/campanhas/"), "Conectar Meta Ads")
        self.assertContains(self.client.get("/resultados/"), "Campanhas da Meta")
        self.conta.beta_campanhas_meta = False
        self.conta.save()
        self.assertEqual(self.client.get("/resultados/campanhas/").status_code, 404)
        self.assertNotContains(self.client.get("/resultados/"), "Campanhas da Meta")

    def test_login_do_facebook_para_empresas_e_volta(self):
        resposta = self.client.get("/anuncios/meta/conectar/?janela=1")
        destino = resposta["Location"]
        self.assertTrue(destino.startswith("https://www.facebook.com/v26.0/dialog/oauth?"))
        self.assertIn("config_id=4136729949793642", destino)
        state = self.client.session["meta_ads_state"]
        with mock.patch.object(meta, "trocar_codigo", return_value={"access_token": "curto"}), \
                mock.patch.object(meta, "token_longo", return_value={"access_token": "longo", "expires_in": 5184000}), \
                mock.patch.object(meta, "eu", return_value={"id": "777", "name": "Bia Souza"}), \
                mock.patch.object(meta, "contas_de_anuncios", return_value=[
                    {"account_id": "111", "name": "Conta da Bia", "currency": "BRL"},
                    {"account_id": "222", "name": "Conta 2", "currency": "BRL"}]):
            resposta = self.client.get(f"/anuncios/meta/retorno/?code=abc&state={state}")
        self.assertContains(resposta, "appfiliado-meta")  # a janela avisa a página e fecha
        conexao = ConexaoMeta.objects.get()
        self.assertEqual((conexao.token, conexao.usuario_id, conexao.contas.count()), ("longo", "777", 2))
        self.assertIsNotNone(conexao.pedido_em)  # o worker lê em seguida

    def test_state_errado_nao_conecta(self):
        self.client.get("/anuncios/meta/conectar/")
        self.client.get("/anuncios/meta/retorno/?code=abc&state=outro")
        self.assertFalse(ConexaoMeta.objects.exists())

    def test_desconectar_apaga_tudo(self):
        conexao = self.conexao()
        campanha = CampanhaMeta.objects.create(conta_anuncios=conexao.contas.get(), campanha_id="9", nome="X")
        DiaCampanha.objects.create(campanha=campanha, dia=timezone.localdate(), gasto=10)
        self.client.post("/anuncios/meta/desconectar/")
        self.assertFalse(ConexaoMeta.objects.exists() or DiaCampanha.objects.exists())

    def test_avisos_da_meta_com_assinatura(self):
        self.conexao()
        corpo = base64.urlsafe_b64encode(json.dumps({"user_id": "777", "algorithm": "HMAC-SHA256"}).encode()).decode().rstrip("=")
        assinatura = base64.urlsafe_b64encode(hmac.new(b"segredo", corpo.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        self.assertEqual(self.client.post("/anuncios/meta/desautorizar/", {"signed_request": "x.y"}).status_code, 400)
        resposta = self.client.post("/anuncios/meta/apagar-dados/", {"signed_request": f"{assinatura}.{corpo}"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("confirmation_code", resposta.json())
        self.assertFalse(ConexaoMeta.objects.exists())


class TestLeitura(BaseMeta):
    def test_le_campanhas_e_gastos_de_hora_em_hora(self):
        conexao = self.conexao()
        hoje = timezone.localdate()
        gastos = [{"campaign_id": "9", "campaign_name": "FONEBT1011", "date_start": hoje.isoformat(), "spend": "98.40",
                   "impressions": "12000", "inline_link_clicks": "1412"},
                  {"campaign_id": "8", "campaign_name": "Apagada", "date_start": hoje.isoformat(), "spend": "5"}]
        with mock.patch.object(meta, "campanhas", return_value=[{"id": "9", "name": "FONEBT1011", "effective_status": "ACTIVE"}]), \
                mock.patch.object(meta, "gastos_por_dia", return_value=gastos) as ler:
            self.assertEqual(len(servico.sincronizar()), 1)
            self.assertEqual(servico.sincronizar(), [])  # só daqui a 1 hora
        self.assertEqual((ler.call_args.args[2], ler.call_args.args[3]), (hoje - timedelta(days=29), hoje))  # 1ª vez: 30 dias
        dia = DiaCampanha.objects.get(campanha__campanha_id="9")
        self.assertEqual((dia.gasto, dia.impressoes, dia.cliques), (Decimal("98.40"), 12000, 1412))
        self.assertEqual(CampanhaMeta.objects.get(campanha_id="8").situacao, "DELETED")
        conexao.refresh_from_db()
        self.assertEqual(conexao.erro, "")

    def test_acesso_vencido_avisa(self):
        conexao = self.conexao()
        with mock.patch.object(meta, "campanhas", side_effect=meta.ErroMeta("Session has expired", 190)):
            servico.ler(conexao)
        conexao.refresh_from_db()
        self.assertIn("Conecte de novo", conexao.erro)

    def test_so_quem_tem_a_chave_beta(self):
        self.conexao()
        self.conta.beta_campanhas_meta = False
        self.conta.save()
        self.assertEqual(servico.para_ler(timezone.now()), [])


class TestTela(BaseMeta):
    def setUp(self):
        super().setUp()
        self.con = self.conexao()
        self.hoje = timezone.localdate()
        self.ontem = self.hoje - timedelta(days=1)
        conta_anuncios = self.con.contas.get()
        self.campanha = CampanhaMeta.objects.create(conta_anuncios=conta_anuncios, campanha_id="9", nome="FONEBT1011", situacao="ACTIVE")
        DiaCampanha.objects.create(campanha=self.campanha, dia=self.ontem, gasto=Decimal("100.00"), cliques=1000)
        # A venda veio de um link com dois Sub IDs: "FONEBT1011-story".
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=self.ontem, sub_id="FONEBT1011-story", vendas=16,
                                            comissao_estimada=Decimal("150.00"))
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=self.ontem, sub_id="OUTRO", vendas=3, comissao_estimada=Decimal(20))

    def test_lucro_da_campanha_pelo_nome_com_imposto(self):
        dados = servico.tela(self.con, 7, self.hoje)
        linha = dados["linhas"][0]
        self.assertEqual((linha["sub_id"], linha["manual"]), ("FONEBT1011", False))
        self.assertEqual(linha["investimento"], Decimal("112.15"))  # 100 + 12,15% de imposto
        self.assertEqual((linha["vendas"], linha["comissao"], linha["margem"]), (16, Decimal("150.00"), Decimal("37.85")))
        self.assertEqual(round(linha["roas"], 2), Decimal("1.34"))
        self.assertEqual(dados["total"]["comissao"], Decimal("150.00"))  # o OUTRO não entra

    def test_sub_id_escolhido_a_mao_e_imposto(self):
        self.client.post("/resultados/campanhas/", {"acao": "sub_id", "campanha": self.campanha.pk, "sub_id": "OUTRO"})
        self.client.post("/resultados/campanhas/", {"acao": "imposto", "imposto": "0"})
        self.con.refresh_from_db()
        linha = servico.tela(self.con, 7, self.hoje)["linhas"][0]
        self.assertEqual((linha["sub_id"], linha["manual"], linha["comissao"], linha["investimento"]),
                         ("OUTRO", True, Decimal(20), Decimal("100.00")))

    def test_campanha_do_link_de_entrada_mostra_o_custo_por_clique_no_grupo(self):
        link = LinkEntrada.objects.create(conta=self.conta, slug="grupo-vip")
        AcessoEntrada.objects.create(link=link, dia=self.ontem, grupo_jid="1@g.us", campanha="fonebt1011", cliques=40)
        linha = servico.tela(self.con, 7, self.hoje)["linhas"][0]
        self.assertEqual((linha["cliques_grupo"], linha["custo_grupo"]), (40, Decimal("112.15") / 40))

    def test_tela_mostra_os_numeros(self):
        html = self.client.get("/resultados/campanhas/?dias=7").content.decode()
        self.assertIn("FONEBT1011", html)
        self.assertIn("R$ 112,15", html)
        self.assertIn("R$ 37,85", html)
        self.assertIn("(mesmo nome da campanha)", html)
