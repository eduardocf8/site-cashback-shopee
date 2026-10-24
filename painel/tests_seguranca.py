"""Testes das brechas encontradas na auditoria de segurança (para nenhuma voltar)."""

import io
import socket
import zipfile
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from accounts.ratelimit import _obter_ip
from bot_whatsapp import ofertas, rede, servico
from bot_whatsapp.formatador import remover_links
from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas
from licencas.models import ContaAppfiliado
from notas import relatorio, servicos
from notas.models import EmpresaNotas, NotaFiscal

from .exportar import texto_sem_formula
from .tests import HOST, SENHA, BasePainel


class TestRede(TestCase):
    def endereco(self, ip):
        return mock.patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, (ip, 443))])

    def test_so_baixa_de_endereco_publico(self):
        for ip in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"):
            with self.endereco(ip):
                self.assertFalse(rede.endereco_publico("https://qualquer.com/a.jpg"), ip)
        with self.endereco("93.184.216.34"):
            self.assertTrue(rede.endereco_publico("https://exemplo.com/a.jpg"))
            self.assertFalse(rede.endereco_publico("https://user@exemplo.com/a.jpg"))
            self.assertFalse(rede.endereco_publico("https://exemplo.com:8080/a.jpg"))
        self.assertFalse(rede.endereco_publico("/etc/hostname"))
        self.assertFalse(rede.endereco_publico("file:///etc/passwd"))

    def test_bomba_de_pixels_recusada(self):
        grande = io.BytesIO()
        Image.new("1", (6000, 6000)).save(grande, "PNG")  # 36 MP em poucos KB
        with self.assertRaises(Exception):
            rede.abrir_imagem(grande.getvalue())


class TestMensagemDeTeste(BasePainel):
    def test_link_da_imagem_precisa_ser_https(self):
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=[{"jid": "1@g.us", "nome": "G"}])
        for ruim in ("/tmp/appfiliado-fotos/2-1.jpg", "file:///etc/passwd", "http://169.254.169.254/",
                     "https://shopee.com.br@127.0.0.1/x"):
            envio, motivo = servico.enfileirar_envio(self.conta, "1@g.us", "oi", imagem_url=ruim)
            self.assertIsNone(envio, ruim)
            self.assertIn("https://", motivo)
        envio, _ = servico.enfileirar_envio(self.conta, "1@g.us", "oi", imagem_url="https://cf.shopee.com.br/file/1")
        self.assertIsNotNone(envio)


class TestBotSemAssinatura(TestCase):
    def test_bot_para_quando_o_modulo_acaba(self):
        conta = ContaAppfiliado.objects.create(email="x@x.com", modulos_cortesia="")
        config = ConfiguracaoOfertas.objects.create(conta=conta, ativo=True, grupos=[{"jid": "1@g.us"}])
        motivo = ofertas.motivo_para_esperar(config, None, timezone.now())
        self.assertIn("não está no seu plano", motivo)


class TestLinksCopiados(TestCase):
    def test_nenhum_link_de_terceiro_sobra(self):
        texto = "Fone bit.ly/golpe e HTTPS://chat.whatsapp.com/X www.golpe.com golpe.com.br R$ 39,90"
        self.assertEqual(remover_links(texto), "Fone e R$ 39,90")


class TestRelatorioGigante(TestCase):
    def test_planilha_que_declara_um_milhao_de_linhas(self):
        folha = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 '<dimension ref="A1:XFD1048576"/><sheetData>'
                 '<row r="1"><c r="A1" t="inlineStr"><is><t>x</t></is></c></row>'
                 '<row r="1048576"><c r="A1048576" t="inlineStr"><is><t>y</t></is></c></row></sheetData></worksheet>')
        arquivo = io.BytesIO()
        ns = "http://schemas.openxmlformats.org"
        with zipfile.ZipFile(arquivo, "w") as z:
            z.writestr("[Content_Types].xml", f'<Types xmlns="{ns}/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                       '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            z.writestr("_rels/.rels", f'<Relationships xmlns="{ns}/package/2006/relationships"><Relationship Id="rId1" '
                       f'Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships">'
                       '<sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{ns}/package/2006/relationships"><Relationship Id="rId1" '
                       f'Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", folha)
        with self.assertRaisesMessage(relatorio.ErroRelatorio, "mais de 20.000 linhas"):
            relatorio.ler(arquivo.getvalue(), "r.xlsx")

    def test_csv_com_linhas_demais(self):
        dados = ("a;b\n" + "1;2\n" * (relatorio.MAXIMO_LINHAS + 5)).encode()
        with self.assertRaisesMessage(relatorio.ErroRelatorio, "mais de"):
            relatorio.ler(dados, "r.csv")


class TestPlanoNaoEscapa(TestCase):
    def test_recusada_antiga_reenviada_conta_no_mes_atual(self):
        conta = ContaAppfiliado.objects.create(email="n@x.com", modulos_cortesia="notas")
        empresa = EmpresaNotas.objects.create(conta=conta, cnpj="12345678000195", razao_social="X", municipio_ibge="3550308",
                                              uf="SP", regime="mei")
        mes_passado = timezone.localdate() - timedelta(days=40)
        nota = NotaFiscal.objects.create(empresa=empresa, ambiente="1", tipo="vendedor", situacao="recusada",
                                         competencia=mes_passado, tomador_documento="1", tomador_nome="L", valor=Decimal("1"))
        servicos.reenviar_nota(nota)
        nota.refresh_from_db()
        self.assertEqual((nota.situacao, nota.competencia), ("fila", timezone.localdate()))
        self.assertEqual(servicos.uso_do_plano(empresa)["usadas"], 1)


class TestPlanilhas(TestCase):
    def test_formula_vira_texto_no_csv(self):
        self.assertEqual(texto_sem_formula('=HYPERLINK("x")'), '\'=HYPERLINK("x")')
        self.assertEqual(texto_sem_formula("Loja"), "Loja")
        self.assertEqual(texto_sem_formula(10), 10)


@override_settings(APPFILIADO_SITES_DOMINIO="appfiliado.com.br", ALLOWED_HOSTS=[".appfiliado.com.br", "testserver"],
                   APPFILIADO_PAINEL_HOSTS=[HOST])
class TestSubdominios(TestCase):
    def test_subdominio_sem_site_nao_mostra_a_cash_b(self):
        for host in ("admin.appfiliado.com.br", "www.appfiliado.com.br", "a.b.appfiliado.com.br", "appfiliado.com.br"):
            resposta = Client(HTTP_HOST=host).get("/admin/login/")
            self.assertEqual(resposta.status_code, 404, host)


class TestLogin(BasePainel):
    def test_mesma_mensagem_com_ou_sem_conta(self):
        sem_senha = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        respostas = [self.client.post("/entrar/", {"email": e, "senha": "errada-123"}).content.decode()
                     for e in ("ninguem@exemplo.com", sem_senha.email, "bia@exemplo.com")]
        for html in respostas:
            self.assertIn("E-mail ou senha incorretos", html)
            self.assertNotIn("Você ainda não criou sua senha", html)

    def test_outra_pessoa_nao_trava_a_sua_conta(self):
        atacante = Client(HTTP_HOST=HOST, REMOTE_ADDR="203.0.113.9")
        for _ in range(10):
            atacante.post("/entrar/", {"email": "bia@exemplo.com", "senha": "errada-123"})
        dona = Client(HTTP_HOST=HOST, REMOTE_ADDR="198.51.100.7")
        resposta = dona.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})
        self.assertEqual(resposta.status_code, 302)

    @override_settings(NUMERO_DE_PROXIES=1)
    def test_ip_real_atras_do_proxy(self):
        pedido = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(_obter_ip(pedido), "198.51.100.7")  # o da direita, que o proxy pôs (o resto o visitante inventa)
