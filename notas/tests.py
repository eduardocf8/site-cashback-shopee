import base64
import json
import io
import datetime as dt
import gzip
import hashlib
import re
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core.cache import cache
from django.db import connection
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings

from licencas.models import ContaAppfiliado
from painel import modulos as mod

from . import certificado, dps, endereco, receita, servicos
from .models import AMBIENTE_TESTE, EmpresaNotas, NotaFiscal
from .sefin import ErroSefin, Resposta

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
CNPJ = "12345678000195"
FUSO = ZoneInfo("America/Sao_Paulo")
_CHAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # uma só, para os testes serem rápidos


CEPS_FALSOS = {
    "08555300": {"municipio_ibge": "3539806", "uf": "SP", "cidade": "Poá", "bairro": "Jardim América",
                 "logradouro": "Rua Quintino Bocaiúva"},
    "37538050": {"municipio_ibge": "3159605", "uf": "MG", "cidade": "Santa Rita do Sapucaí", "bairro": "Família Andrade",
                 "logradouro": "Rua Eliza Ribeiro da Costa"},
    "37540000": {},  # CEP antigo, que não existe mais (o governo recusa com E0240)
}


def cep_falso(cep):
    return CEPS_FALSOS.get(cep, {"municipio_ibge": "3550308", "uf": "SP", "cidade": "São Paulo", "bairro": "Centro",
                                 "logradouro": "Rua Qualquer"})


def setUpModule():
    # Nenhum teste consulta CEP de verdade.
    global _cep_sem_internet
    _cep_sem_internet = mock.patch.object(endereco, "_consultar_cep", side_effect=cep_falso)
    _cep_sem_internet.start()


def tearDownModule():
    _cep_sem_internet.stop()


def gerar_pfx(cnpj=CNPJ, senha="senha-do-pfx", vence=None, com_san=True, chave=None) -> bytes:
    chave = chave or _CHAVE
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"LOJA TESTE LTDA:{cnpj}" if not com_san else "LOJA TESTE LTDA")])
    construtor = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
                  .serial_number(1).not_valid_before(dt.datetime(2025, 1, 1))
                  .not_valid_after(vence or dt.datetime(2036, 1, 1)))
    if com_san:
        valor = b"\x04\x0e" + cnpj.encode()
        construtor = construtor.add_extension(
            x509.SubjectAlternativeName([x509.OtherName(x509.ObjectIdentifier(certificado.OID_CNPJ_ICP), valor)]), False)
    cert = construtor.sign(chave, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b"t", chave, cert, None,
                                                 serialization.BestAvailableEncryption(senha.encode()))


def criar_conta(email="bia@exemplo.com", modulos="notas"):
    conta = ContaAppfiliado.objects.create(email=email, modulos_cortesia=modulos)
    conta.definir_senha(SENHA)
    conta.save()
    return conta


def criar_empresa(conta, **kw):
    dados = dict(conta=conta, cnpj=CNPJ, razao_social="LOJA TESTE LTDA", municipio_ibge="3550308",
                 municipio_nome="São Paulo", uf="SP", regime="mei", codigo_tributacao="170601",
                 descricao_servico="Divulgação de produtos em mídias sociais")
    dados.update(kw)
    return EmpresaNotas.objects.create(**dados)


def dps_exemplo(regime="mei", tomador=None):
    return dps.montar(
        ambiente="2", emitida_em=dt.datetime(2026, 10, 20, 9, 0, tzinfo=FUSO), serie="1", numero=7,
        competencia=dt.date(2026, 9, 30), prestador=dps.Prestador(CNPJ, "3550308", regime),
        tomador=tomador or dps.Tomador("cnpj", "35635824000112", "SHPS TECNOLOGIA E SERVICOS LTDA.", "nf@ex.com"),
        servico=dps.Servico("170601", "Divulgação de produtos em mídias sociais"), valor="12.5")


def xml_nfse(numero="42") -> str:
    return (f'<NFSe xmlns="{dps.NS}" versao="1.01"><infNFSe Id="NFS1"><nNFSe>{numero}</nNFSe></infNFSe></NFSe>')


class TestCertificado(TestCase):
    def test_abre_e_le_o_cnpj_do_ecnpj(self):
        cert = certificado.abrir(gerar_pfx(), "senha-do-pfx")
        self.assertEqual(cert.cnpj, CNPJ)
        self.assertFalse(cert.vencido)

    def test_le_o_cnpj_pelo_nome_quando_nao_tem_o_campo_icp(self):
        self.assertEqual(certificado.abrir(gerar_pfx(com_san=False), "senha-do-pfx").cnpj, CNPJ)

    def test_senha_errada_e_arquivo_vazio(self):
        with self.assertRaisesMessage(certificado.ErroCertificado, "confira a senha"):
            certificado.abrir(gerar_pfx(), "outra")
        with self.assertRaises(certificado.ErroCertificado):
            certificado.abrir(b"", "x")

    def test_certificado_que_nao_e_rsa(self):
        chave_ec = ec.generate_private_key(ec.SECP256R1())
        with self.assertRaisesMessage(certificado.ErroCertificado, "RSA"):
            certificado.abrir(gerar_pfx(chave=chave_ec), "senha-do-pfx")

    def test_guarda_cifrado_e_abre_de_novo(self):
        empresa = criar_empresa(criar_conta())
        pfx = gerar_pfx()
        certificado.guardar(empresa, pfx, "senha-do-pfx")
        empresa.refresh_from_db()
        self.assertTrue(empresa.tem_certificado)
        self.assertNotIn(base64.b64encode(pfx).decode()[:40], empresa.certificado_cifrado)
        self.assertNotIn("senha-do-pfx", empresa.senha_cifrada)
        self.assertEqual(certificado.da_empresa(empresa).cnpj, CNPJ)
        certificado.apagar(empresa)
        self.assertFalse(EmpresaNotas.objects.get(pk=empresa.pk).tem_certificado)

    def test_recusa_certificado_de_outro_cnpj_e_vencido(self):
        empresa = criar_empresa(criar_conta())
        with self.assertRaisesMessage(certificado.ErroCertificado, "não do"):
            certificado.guardar(empresa, gerar_pfx(cnpj="11222333000181"), "senha-do-pfx")
        with self.assertRaisesMessage(certificado.ErroCertificado, "venceu"):
            certificado.guardar(empresa, gerar_pfx(vence=dt.datetime(2025, 6, 1)), "senha-do-pfx")
        self.assertFalse(EmpresaNotas.objects.get(pk=empresa.pk).tem_certificado)


class TestDPS(TestCase):
    def test_mei_segue_o_esquema_oficial_e_as_regras(self):
        raiz = dps_exemplo()
        dps.validar(raiz)
        xml = dps.para_bytes(raiz).decode()
        self.assertIn("<opSimpNac>2</opSimpNac>", xml)
        self.assertNotIn("regApTribSN", xml)  # MEI não informa (E0162)
        self.assertNotIn("pTotTribSN", xml)  # MEI nunca informa (E0710)
        self.assertNotIn("pAliq", xml)  # MEI não informa alíquota (E0600)
        self.assertIn("<serie>00001</serie>", xml)
        self.assertEqual(len(raiz[0].get("Id")), 45)
        self.assertEqual(raiz[0].get("Id"), "DPS3550308" + "2" + CNPJ + "00001" + "7".zfill(15))

    def test_simples_informa_o_regime_de_apuracao(self):
        raiz = dps_exemplo(regime="simples")
        dps.validar(raiz)
        self.assertIn("<regApTribSN>1</regApTribSN>", dps.para_bytes(raiz).decode())

    def test_tomador_estrangeiro_e_cpf(self):
        raiz = dps_exemplo(tomador=dps.Tomador("nif", "202602050G", "SHOPEE CHOICE II PRIVATE LIMITED", pais="SG"))
        dps.validar(raiz)
        xml = dps.para_bytes(raiz).decode()
        self.assertIn("<NIF>202602050G</NIF>", xml)
        # Igual à nota para o exterior autorizada em produção (Manda Notas, out/2026).
        self.assertIn("<endExt><cPais>SG</cPais><cEndPost>-</cEndPost><xCidade>-</xCidade><xEstProvReg>-</xEstProvReg>"
                      "</endExt><xLgr>-</xLgr><nro>-</nro><xBairro>-</xBairro></end>", xml)
        self.assertIn("<comExt><mdPrestacao>2</mdPrestacao><vincPrest>0</vincPrest><tpMoeda>986</tpMoeda>"
                      "<vServMoeda>12.50</vServMoeda><mecAFComexP>01</mecAFComexP><mecAFComexT>01</mecAFComexT>"
                      "<movTempBens>1</movTempBens><mdic>0</mdic></comExt>", xml)
        self.assertNotIn("comExt", dps.para_bytes(dps_exemplo()).decode())
        with self.assertRaises(dps.ErroDPS):
            dps_exemplo(tomador=dps.Tomador("nif", "X1", "SEM PAIS"))
        dps.validar(dps_exemplo(tomador=dps.Tomador("cpf", "12345678909", "Maria")))

    def test_valor_zero_e_regime_desconhecido(self):
        with self.assertRaises(dps.ErroDPS):
            dps.montar(ambiente="2", emitida_em=dt.datetime(2026, 10, 20, tzinfo=FUSO), serie="1", numero=1,
                       competencia=dt.date(2026, 9, 30), prestador=dps.Prestador(CNPJ, "3550308", "mei"),
                       tomador=dps.Tomador("cnpj", "35635824000112", "X"), servico=dps.Servico("170601", "abc"), valor=0)
        with self.assertRaises(dps.ErroDPS):
            dps_exemplo(regime="lucro_real")

    def test_assinatura_confere_por_fora_do_lxml(self):
        """Confere com o canonicalizador da biblioteca padrão do Python (independente do lxml).
        Protege contra o defeito do lxml que soltava xmlns="" nos netos e invalidava a assinatura."""
        cert = certificado.abrir(gerar_pfx(), "senha-do-pfx")
        raiz = dps.assinar(dps_exemplo(), cert.chave, cert.certificado)
        dps.validar(raiz)
        texto = dps.para_bytes(raiz).decode()
        self.assertNotIn('xmlns=""', dps.c14n(raiz[0]).decode())
        inf = re.search(r"<infDPS.*?</infDPS>", texto, re.S).group(0).replace("<infDPS", f'<infDPS xmlns="{dps.NS}"', 1)
        info = re.search(r"<SignedInfo>.*?</SignedInfo>", texto, re.S).group(0).replace(
            "<SignedInfo>", f'<SignedInfo xmlns="{dps.DS}">', 1)
        digest = base64.b64encode(hashlib.sha256(ET.canonicalize(inf).encode()).digest()).decode()
        self.assertIn(f"<DigestValue>{digest}</DigestValue>", texto)
        valor = base64.b64decode(re.search(r"<SignatureValue>(.*?)</SignatureValue>", texto).group(1))
        cert.certificado.public_key().verify(valor, ET.canonicalize(info).encode(), padding.PKCS1v15(), hashes.SHA256())
        self.assertIn("xmldsig-more#rsa-sha256", texto)
        self.assertNotIn("X509SubjectName", texto)  # o manual pede só o X509Certificate


class TestReceitaEResposta(TestCase):
    def test_cnpj_valido(self):
        self.assertTrue(receita.cnpj_valido("35.635.824/0001-12"))
        self.assertTrue(receita.cnpj_valido(CNPJ))
        self.assertFalse(receita.cnpj_valido("35635824000113"))
        self.assertFalse(receita.cnpj_valido("11111111111111"))

    def test_consulta_preenche_o_cadastro(self):
        retorno = mock.Mock(status_code=200, json=lambda: {
            "razao_social": "LOJA TESTE LTDA", "codigo_municipio_ibge": 3550308, "municipio": "SAO PAULO",
            "uf": "SP", "opcao_pelo_mei": True, "opcao_pelo_simples": True, "descricao_situacao_cadastral": "ATIVA"})
        with mock.patch.object(receita.requests, "get", return_value=retorno):
            dados = receita.consultar(CNPJ)
        self.assertEqual((dados["municipio_ibge"], dados["regime"], dados["municipio_nome"], dados["ativa"]),
                         ("3550308", "mei", "Sao Paulo", True))

    def test_mensagens_do_governo(self):
        r = Resposta(400, {"erros": [{"Codigo": "E0014", "Descricao": "DPS já existe.", "Complemento": "série 1"}]})
        self.assertEqual(r.mensagens, [{"codigo": "E0014", "descricao": "DPS já existe. série 1"}])
        self.assertEqual(Resposta(403, {}).mensagens[0]["codigo"], "403")
        xml = xml_nfse()
        ok = Resposta(201, {"chaveAcesso": "X" * 50, "nfseXmlGZipB64": base64.b64encode(gzip.compress(xml.encode())).decode()})
        self.assertEqual(ok.xml_nfse(), xml)


class ClienteFalso:
    """Faz o papel da API do governo nos testes."""

    def __init__(self, emitir=None, consultar_dps=None, erro=None):
        self._emitir, self._consultar_dps, self._erro = emitir, consultar_dps, erro
        self.emitidas = []

    def __call__(self, ambiente, cert):
        return self

    def emitir(self, dps_assinada):
        self.emitidas.append(dps_assinada)
        if self._erro:
            raise self._erro
        return self._emitir

    def consultar_dps(self, dps_id):
        return self._consultar_dps or Resposta(404, {})

    def consultar_nfse(self, chave):
        return Resposta(200, {"nfseXmlGZipB64": base64.b64encode(gzip.compress(xml_nfse("99").encode())).decode()})


def autorizada():
    return Resposta(201, {"chaveAcesso": "3550308" + "1" * 43,
                          "nfseXmlGZipB64": base64.b64encode(gzip.compress(xml_nfse().encode())).decode()})


class TestServicos(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def test_numeracao_por_ambiente_so_no_envio(self):
        t = dps.Tomador("cnpj", servicos.SHOPEE_CNPJ, servicos.SHOPEE_NOME)
        notas = [servicos.criar_nota(self.empresa, ambiente=amb, tipo="teste", competencia=dt.date(2026, 10, 1),
                                     tomador=t, valor=1) for amb in ("2", "2", "1")]
        self.assertTrue(all(n.numero is None for n in notas))  # prévia descartada não queima número
        for n in notas:
            servicos._garantir_numero(n)
        self.assertEqual([n.numero for n in notas], [1, 2, 1])
        self.assertTrue(notas[1].dps_id.endswith("000000000000002"))

    def test_teste_autorizado(self):
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso):
            nota = servicos.emitir_teste(self.empresa)
        self.assertEqual((nota.situacao, nota.numero_nfse, nota.ambiente, nota.valor), ("autorizada", "42", AMBIENTE_TESTE, Decimal("1.00")))
        self.assertEqual(len(falso.emitidas), 1)
        enviada = falso.emitidas[0].decode()
        self.assertIn("<tpAmb>2</tpAmb>", enviada)
        self.assertIn("<Signature", enviada)

    def test_recusada_guarda_o_motivo_e_pode_tentar_de_novo(self):
        falso = ClienteFalso(emitir=Resposta(400, {"erros": [{"codigo": "E0041", "descricao": "Município errado"}]}))
        with mock.patch.object(servicos, "ClienteSefin", falso):
            nota = servicos.emitir_teste(self.empresa)
        self.assertEqual(nota.situacao, "recusada")
        self.assertEqual(nota.mensagens[0]["codigo"], "E0041")
        with mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")

    def test_sem_resposta_confere_antes_de_reenviar(self):
        with mock.patch.object(servicos, "ClienteSefin", ClienteFalso(erro=ErroSefin("caiu"))):
            nota = servicos.emitir_teste(self.empresa)
        self.assertEqual(nota.situacao, "erro")
        # Na segunda tentativa o governo diz que aquela DPS já virou nota: não manda de novo.
        falso = ClienteFalso(emitir=autorizada(), consultar_dps=Resposta(200, {"chaveAcesso": "C" * 50}))
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual((nota.situacao, nota.chave, nota.numero_nfse), ("autorizada", "C" * 50, "99"))
        self.assertEqual(falso.emitidas, [])

    def test_nao_testa_sem_certificado_ou_servico(self):
        certificado.apagar(self.empresa)
        with self.assertRaisesMessage(servicos.ErroNotas, "certificado"):
            servicos.emitir_teste(self.empresa)
        self.assertFalse(NotaFiscal.objects.exists())

    def test_erro_inesperado_nao_estoura(self):
        with mock.patch.object(servicos, "ClienteSefin", side_effect=RuntimeError("x")):
            nota = servicos.emitir_teste(self.empresa)
        self.assertEqual(nota.situacao, "erro")

    def test_servico_valida_o_codigo(self):
        with self.assertRaises(servicos.ErroNotas):
            servicos.salvar_servico(self.empresa, "1706", "", "Divulgação de produtos", "")
        servicos.salvar_servico(self.empresa, "17.06.01", "", "  Divulgação   de produtos  ", "12.345")
        self.empresa.refresh_from_db()
        self.assertEqual((self.empresa.codigo_tributacao, self.empresa.descricao_servico, self.empresa.inscricao_municipal),
                         ("170601", "Divulgação de produtos", "12345"))


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestTelas(TestCase):
    def setUp(self):
        # A tela confere o regime na Receita antes de emitir: aqui, sem internet.
        receita_falsa = mock.patch.object(receita, "consultar", return_value={"regime": "mei"})
        receita_falsa.start()
        self.addCleanup(receita_falsa.stop)
        cache.clear()
        self.conta = criar_conta()
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})

    def test_menu_e_convite(self):
        self.assertEqual(mod.estado(mod.POR_SLUG["notas"], ["notas"]), "liberado")
        self.assertEqual(mod.estado(mod.POR_SLUG["notas"], ["whatsapp"]), "bloqueado")
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        self.assertNotContains(self.client.get("/notas/"), "Sua empresa")

    def test_cadastra_empresa_pelo_cnpj(self):
        self.assertContains(self.client.get("/notas/"), "Sua empresa")
        dados = {"cnpj": CNPJ, "razao_social": "LOJA TESTE LTDA", "municipio_ibge": "3550308", "municipio_nome": "Sao Paulo",
                 "uf": "SP", "regime": "mei", "ativa": True}
        with mock.patch.object(receita, "consultar", return_value=dados):
            self.client.post("/notas/", {"acao": "empresa", "cnpj": "12.345.678/0001-95"})
        empresa = EmpresaNotas.objects.get(conta=self.conta)
        self.assertEqual((empresa.razao_social, empresa.regime), ("LOJA TESTE LTDA", "mei"))
        # O serviço já vem com o padrão, e o que a pessoa salva não é trocado depois.
        self.assertEqual((empresa.codigo_tributacao, empresa.descricao_servico), ("170601", "Divulgação e venda de produtos"))
        servicos.salvar_servico(empresa, "100801", "", "Agenciamento de publicidade", "")
        servicos.aplicar_servico_padrao(empresa)
        empresa.refresh_from_db()
        self.assertEqual(empresa.codigo_tributacao, "100801")
        self.assertContains(self.client.get("/notas/"), "Enviar o certificado digital A1")

    def test_recusa_lucro_presumido(self):
        dados = {"cnpj": CNPJ, "razao_social": "X", "municipio_ibge": "3550308", "municipio_nome": "", "uf": "SP",
                 "regime": "", "ativa": True}
        with mock.patch.object(receita, "consultar", return_value=dados):
            r = self.client.post("/notas/", {"acao": "empresa", "cnpj": CNPJ}, follow=True)
        self.assertContains(r, "MEI e do Simples")
        self.assertFalse(EmpresaNotas.objects.exists())

    def test_certificado_servico_e_teste(self):
        empresa = criar_empresa(self.conta, codigo_tributacao="", descricao_servico="")
        arquivo = SimpleUploadedFile("cert.pfx", gerar_pfx(), content_type="application/x-pkcs12")
        r = self.client.post("/notas/", {"acao": "certificado", "arquivo": arquivo, "senha": "errada"}, follow=True)
        self.assertContains(r, "confira a senha")
        arquivo.seek(0)
        self.client.post("/notas/", {"acao": "certificado", "arquivo": arquivo, "senha": "senha-do-pfx"})
        empresa.refresh_from_db()
        self.assertTrue(empresa.tem_certificado)
        self.client.post("/notas/", {"acao": "servico", "codigo_tributacao": "170601", "codigo_municipal": "",
                                     "inscricao_municipal": "", "descricao_servico": "Divulgação de produtos em mídias sociais"})
        empresa.refresh_from_db()
        self.assertEqual(empresa.codigo_tributacao, "170601")
        with mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            r = self.client.post("/notas/", {"acao": "testar"}, follow=True)
        self.assertContains(r, "Deu certo")
        nota = NotaFiscal.objects.get()
        self.assertEqual(self.client.get(f"/notas/{nota.pk}/xml/").content.decode(), xml_nfse())

    def test_outra_conta_nao_ve_a_nota(self):
        empresa = criar_empresa(criar_conta(email="outra@exemplo.com"))
        nota = NotaFiscal.objects.create(empresa=empresa, tipo="teste", competencia=dt.date(2026, 10, 1),
                                         tomador_documento="1", tomador_nome="X", valor=1, serie="1", numero=1,
                                         dps_id="D", xml_nfse="<x/>", situacao="recusada")
        self.assertEqual(self.client.get(f"/notas/{nota.pk}/xml/").status_code, 404)
        self.assertEqual(self.client.post(f"/notas/{nota.pk}/reenviar/").status_code, 404)


class TestCliente(TestCase):
    def test_monta_a_conexao_sem_deixar_a_chave_no_disco(self):
        import os

        from . import sefin
        antes = set(os.listdir("/dev/shm")) if os.path.isdir("/dev/shm") else set()
        cliente = sefin.ClienteSefin("2", certificado.abrir(gerar_pfx(), "senha-do-pfx"))
        depois = set(os.listdir("/dev/shm")) if os.path.isdir("/dev/shm") else set()
        self.assertEqual(antes, depois)
        self.assertTrue(cliente.base.startswith("https://sefin.producaorestrita.nfse.gov.br"))

    def test_acesso_negado_vira_mensagem_clara(self):
        from . import sefin
        cliente = sefin.ClienteSefin("2", certificado.abrir(gerar_pfx(), "senha-do-pfx"))
        html = mock.Mock(status_code=403, content=b"<html>", text="<html><title>403 - Forbidden</title></html>",
                         json=mock.Mock(side_effect=ValueError))
        with mock.patch.object(cliente.sessao, "request", return_value=html):
            r = cliente.consultar_dps("DPS1")
        self.assertIn("certificado", r.mensagens[0]["descricao"])
        with mock.patch.object(cliente.sessao, "request", return_value=mock.Mock(status_code=503, content=b"", text="")):
            with self.assertRaises(ErroSefin):
                cliente.emitir(b"<x/>")


CABECALHO = ("Mês de conclusão,Nome da loja,ID da Loja,Comissão Total do Vendedor,CNPJ do Vendedor,CPF do Vendedor,"
             "Identificação Fiscal Estrangeira,Razão social do vendedor,Endereço do Vendedor,País do Vendedor,"
             "Inscrição Estadual,E-mail")


def relatorio_csv(linhas=None, mes="Sep 2026") -> bytes:
    linhas = linhas if linhas is not None else [
        (mes, "loja_um", "1001", "R$0,86", "11222333000181", "", "", "LOJA UM LTDA", "Rua A, 1 - Centro, São Paulo - SP", "BR", "1", "um@loja.com"),
        (mes, "Loja Dois", "1002", "R$1.234,56", "11444777000161", "", "", "LOJA DOIS LTDA", "", "BR", "", ""),
        (mes, "china_shop", "1003", "R$5,22", "", "", "91310000MA1FL0000X", "SHENZHEN CO", "Somewhere", "CN", "", "cn@shop.com"),
        (mes, "Loja Ruim", "1004", "R$2,00", "11222333000100", "", "", "LOJA RUIM", "", "BR", "", "x@y.com"),
    ]
    texto = CABECALHO + "\n" + "\n".join(",".join(f'"{c}"' for c in l) for l in linhas) + "\n"
    return "﻿".encode() + texto.encode("utf-8")


class TestRelatorio(TestCase):
    def test_le_o_relatorio_padrao(self):
        from . import relatorio
        linhas = relatorio.ler(relatorio_csv(), "MonthlyReport.csv")
        self.assertEqual(len(linhas), 4)
        um, dois, china, ruim = linhas
        self.assertEqual((um.mes, um.valor, um.tipo_documento, um.email), (dt.date(2026, 9, 1), Decimal("0.86"), "cnpj", "um@loja.com"))
        self.assertEqual(dois.valor, Decimal("1234.56"))
        self.assertTrue(china.estrangeira)
        self.assertEqual(china.tipo_documento, "nif")
        self.assertIn("CNPJ inválido", ruim.problemas)

    def test_meses_e_valores(self):
        from . import relatorio
        for texto, esperado in [("Sep 2026", (2026, 9)), ("set/2026", (2026, 9)), ("09/2026", (2026, 9)),
                                ("2026-10", (2026, 10)), ("Dezembro 2026", (2026, 12))]:
            self.assertEqual(relatorio.ler_mes(texto), dt.date(*esperado, 1), texto)
        self.assertIsNone(relatorio.ler_mes("qualquer"))
        self.assertEqual(relatorio.ler_valor("R$ 11.712,09"), Decimal("11712.09"))
        self.assertEqual(relatorio.ler_valor(12.5), Decimal("12.50"))

    def test_variante_mcn_e_xlsx(self):
        from openpyxl import Workbook

        from . import relatorio
        planilha = Workbook()
        aba = planilha.active
        aba.append(["Mês de conclusão", "Nome da loja", "ID da Loja", "Taxa Total da MCN", "CNPJ do Vendedor",
                    "CPF do Vendedor", "Razão social do vendedor", "Endereço do Vendedor", "Inscrição Estadual", "E-mail de contato"])
        aba.append(["Sep 2026", "Loja", "77", 3.5, "11222333000181", "", "LOJA LTDA", "", "", "a@b.com"])
        arquivo = io.BytesIO()
        planilha.save(arquivo)
        linha = relatorio.ler(arquivo.getvalue(), "relatorio.xlsx")[0]
        self.assertEqual((linha.valor, linha.email, linha.loja_id), (Decimal("3.50"), "a@b.com", "77"))

    def test_arquivo_errado(self):
        from . import relatorio
        with self.assertRaisesMessage(relatorio.ErroRelatorio, "Relatório Mensal"):
            relatorio.ler(b"nome,valor\nx,1\n", "x.csv")
        with self.assertRaises(relatorio.ErroRelatorio):
            relatorio.ler(b"", "x.csv")


class TestLote(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def importar(self, ambiente="1", dados=None):
        return servicos.importar_relatorio(self.empresa, dados or relatorio_csv(), "MonthlyReport.csv", ambiente)

    def test_previa_uma_nota_por_loja_valida(self):
        lote = self.importar()
        self.assertEqual(lote.mes_referencia, dt.date(2026, 9, 1))
        self.assertEqual(sorted(lote.notas.values_list("loja_id", flat=True)), ["1001", "1002", "1003"])
        china = lote.notas.get(loja_id="1003")
        self.assertEqual((china.tomador_tipo, china.tomador_pais), ("nif", "CN"))
        self.assertTrue(all(n.situacao == "previa" and n.numero is None for n in lote.notas.all()))
        motivos = {i["linha"]: i["motivo"] for i in lote.ignoradas}
        self.assertEqual(list(motivos), [5])
        self.assertIn("CNPJ inválido", motivos[5])
        # Importar de novo antes de confirmar troca a prévia (não duplica).
        self.importar()
        self.assertEqual(NotaFiscal.objects.count(), 3)

    def test_confirmar_coloca_na_fila_e_marca_os_emails(self):
        lote = self.importar()
        self.assertEqual(servicos.confirmar_lote(lote), 3)
        situacoes = dict(lote.notas.values_list("loja_id", "email_situacao"))
        self.assertEqual(situacoes, {"1001": "pendente", "1002": "sem_email", "1003": "pendente"})
        self.assertEqual(set(lote.notas.values_list("situacao", flat=True)), {"fila"})
        lote.refresh_from_db()
        self.assertEqual(lote.estado, "emitindo")
        # Mesmo mês importado de novo: quem já tem nota fica de fora.
        outro = self.importar()
        self.assertEqual(outro.notas.count(), 0)
        self.assertIn("já tem nota", " ".join(i["motivo"] for i in outro.ignoradas))

    def test_no_ambiente_de_testes_nao_manda_email(self):
        lote = self.importar(ambiente="2")
        servicos.confirmar_lote(lote)
        self.assertEqual(set(lote.notas.values_list("email_situacao", flat=True)), {"nao_envia"})

    def test_fila_emite_manda_email_e_fecha_o_lote(self):
        from django.core import mail

        from . import fila
        lote = self.importar()
        servicos.confirmar_lote(lote)
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(fila, "ClienteSefin", falso):
            self.assertEqual(fila.emitir(), 3)
        self.assertEqual(len(falso.emitidas), 3)
        self.assertEqual(sorted(lote.notas.values_list("numero", flat=True)), [1, 2, 3])
        self.assertIn("<endExt><cPais>CN</cPais>", falso.emitidas[2].decode())
        with mock.patch("notas.danfse.pdf", return_value=b"%PDF-falso"):
            self.assertEqual(fila.enviar_emails(), 2)
        enviado = next(m for m in mail.outbox if m.to == ["um@loja.com"])
        self.assertEqual(enviado.to, ["um@loja.com"])
        self.assertEqual(enviado.reply_to, ["bia@exemplo.com"])
        self.assertEqual(sorted(a[2] for a in enviado.attachments), ["application/pdf", "application/xml"])
        self.assertIn("setembro de 2026", enviado.body)
        fila.fechar_lotes()
        lote.refresh_from_db()
        self.assertEqual(lote.estado, "concluido")

    def test_nota_ja_pega_nao_e_enviada_de_novo(self):
        from . import fila
        lote = self.importar()
        servicos.confirmar_lote(lote)
        nota = lote.notas.first()
        self.assertTrue(fila._pegar(nota.pk))
        self.assertFalse(fila._pegar(nota.pk))

    def test_dps_ja_existente_recupera_a_nota(self):
        nota = servicos.emitir_nota_shopee(self.empresa, "11.712,09")
        self.assertEqual((nota.valor, nota.tipo, nota.situacao), (Decimal("11712.09"), "shopee", "fila"))
        falso = ClienteFalso(emitir=Resposta(400, {"erros": [{"codigo": "E0014", "descricao": "já existe"}]}),
                             consultar_dps=Resposta(200, {"chaveAcesso": "K" * 50}))
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual((nota.situacao, nota.chave), ("autorizada", "K" * 50))
        enviada = falso.emitidas[0].decode()
        self.assertIn("<cMun>3550308</cMun>", enviada)  # endereço da Shopee, como na nota de hoje
        self.assertIn("ANDAR 22 E 23", enviada)

    def test_valor_da_nota_da_shopee(self):
        with self.assertRaises(servicos.ErroNotas):
            servicos.emitir_nota_shopee(self.empresa, "abc")
        with self.assertRaises(servicos.ErroNotas):
            servicos.emitir_nota_shopee(self.empresa, "0")


class TestFilaProtecoes(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")
        lote = servicos.importar_relatorio(self.empresa, relatorio_csv(), "r.csv", "1")
        servicos.confirmar_lote(lote)

    def test_governo_fora_do_ar_para_a_volta(self):
        from . import fila
        falso = ClienteFalso(erro=ErroSefin("caiu"))
        with mock.patch.object(fila, "ClienteSefin", falso):
            fila.emitir()
        self.assertEqual(len(falso.emitidas), 1)  # não sai queimando a fila inteira
        self.assertEqual(NotaFiscal.objects.filter(situacao="fila").count(), 2)

    def test_certificado_recusado_pausa_a_empresa(self):
        from . import fila
        negado = Resposta(403, {"erros": [{"codigo": "403", "descricao": "O governo recusou o acesso."}]})
        falso = ClienteFalso(emitir=negado)
        with mock.patch.object(fila, "ClienteSefin", falso):
            fila.emitir()
            fila.emitir()
        self.assertEqual(len(falso.emitidas), 1)
        self.empresa.refresh_from_db()
        self.assertIn("recusou", self.empresa.emissao_pausada)
        self.assertEqual(NotaFiscal.objects.filter(situacao="fila").count(), 2)
        # Certificado novo: volta a andar.
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.emissao_pausada, "")


    def test_certificado_vencido_pausa_sem_recusar_as_notas(self):
        from . import fila
        with mock.patch.object(fila.certificado, "da_empresa", side_effect=certificado.ErroCertificado("venceu")):
            fila.emitir()
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.emissao_pausada, "venceu")
        self.assertEqual(NotaFiscal.objects.filter(situacao="fila").count(), 3)


class TestEmailServico(TestCase):
    def setUp(self):
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")
        lote = servicos.importar_relatorio(self.empresa, relatorio_csv(), "r.csv", "1")
        servicos.confirmar_lote(lote)
        from . import fila
        with mock.patch.object(fila, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            fila.emitir()

    def test_teto_por_dia(self):
        from . import fila
        with self.settings(NOTAS_EMAILS_POR_DIA=1), mock.patch("notas.danfse.pdf", return_value=b"%PDF"):
            self.assertEqual(fila.enviar_emails(), 1)
            self.assertEqual(fila.enviar_emails(), 0)  # o outro fica para amanhã
        self.assertEqual(NotaFiscal.objects.filter(email_situacao="pendente").count(), 1)

    def test_limite_do_servico_nao_marca_como_falho(self):
        from cashback_shopee.ses_email_backend import LimiteDeEnvio

        from . import fila
        with mock.patch("notas.danfse.pdf", return_value=b"%PDF"), \
                mock.patch("django.core.mail.EmailMessage.send", side_effect=LimiteDeEnvio("devagar")):
            self.assertEqual(fila.enviar_emails(), 0)
        self.assertEqual(NotaFiscal.objects.filter(email_situacao="pendente").count(), 2)
        self.assertFalse(NotaFiscal.objects.filter(email_situacao="falhou").exists())

    def test_ses_monta_o_pedido_assinado(self):
        from cashback_shopee import ses_email_backend as ses
        from . import email
        nota = NotaFiscal.objects.filter(email_situacao="pendente").first()
        with self.settings(AWS_SES_ACCESS_KEY_ID="AKIDEXAMPLE", AWS_SES_SECRET_ACCESS_KEY="segredo", AWS_SES_REGIAO="sa-east-1",
                           AWS_SES_CONFIGURATION_SET="notas"), mock.patch("notas.danfse.pdf", return_value=b"%PDF"):
            backend = ses.SESEmailBackend()
            with mock.patch.object(backend.sessao, "post", return_value=mock.Mock(status_code=200)) as post:
                self.assertEqual(backend.send_messages([email.montar(nota)]), 1)
            url, kwargs = post.call_args[0][0], post.call_args[1]
            self.assertEqual(url, "https://email.sa-east-1.amazonaws.com/v2/email/outbound-emails")
            self.assertTrue(kwargs["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/"))
            pedido = json.loads(kwargs["data"])
            self.assertEqual(pedido["Destination"]["ToAddresses"], [nota.tomador_email])
            self.assertEqual(pedido["ConfigurationSetName"], "notas")
            bruto = base64.b64decode(pedido["Content"]["Raw"]["Data"]).decode()
            self.assertIn("application/pdf", bruto)
            self.assertIn("Reply-To: bia@exemplo.com", bruto)
            with mock.patch.object(backend.sessao, "post", return_value=mock.Mock(status_code=429, text="Throttling")):
                with self.assertRaises(ses.LimiteDeEnvio):
                    backend.send_messages([email.montar(nota)])

    def test_assinatura_v4_igual_ao_exemplo_da_aws(self):
        from cashback_shopee.ses_email_backend import assinar_v4
        cab = assinar_v4("GET", "https://iam.amazonaws.com/?Action=ListUsers&Version=2010-05-08",
                         {"content-type": "application/x-www-form-urlencoded; charset=utf-8"}, b"",
                         regiao="us-east-1", servico="iam", access_key="AKIDEXAMPLE",
                         secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                         agora=dt.datetime(2015, 8, 30, 12, 36, tzinfo=dt.timezone.utc))
        self.assertTrue(cab["Authorization"].endswith(
            "Signature=5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"))


ERRO_LEIAUTE_REAL = ("Falha no esquema XML do DF-e. The element 'infDPS' in namespace 'http://www.sped.fazenda.gov.br/nfse' "
                     "has invalid child element 'cLocEmi' in namespace 'http://www.sped.fazenda.gov.br/nfse'. List of possible "
                     "elements expected: 'cMotivoEmisTI, finNFSe' in namespace 'http://www.sped.fazenda.gov.br/nfse'.")


class ClienteEmSequencia(ClienteFalso):
    """Responde cada envio com a próxima resposta da lista."""

    def __init__(self, respostas):
        super().__init__()
        self.respostas = list(respostas)

    def emitir(self, dps_assinada):
        self.emitidas.append(dps_assinada)
        return self.respostas.pop(0)


ERRO_INDDEST_REAL = ("Falha no esquema XML do DF-e. The element 'infDPS' in namespace 'http://www.sped.fazenda.gov.br/nfse' "
                     "has invalid child element 'indDest' in namespace 'http://www.sped.fazenda.gov.br/nfse'. List of possible "
                     "elements expected: 'interm, serv' in namespace 'http://www.sped.fazenda.gov.br/nfse'.")


def recusa_de_esquema(texto):
    return Resposta(400, {"erros": [{"Codigo": "E1235", "Descricao": texto}]})


class TestCamposNovos(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def test_campos_novos_no_lugar_certo_e_assinatura_confere(self):
        cert = certificado.abrir(gerar_pfx(), "senha-do-pfx")
        raiz = dps_exemplo()
        dps.validar(raiz)
        dps.com_campos_novos(raiz, {"finNFSe", "indDest"})
        dps.assinar(raiz, cert.chave, cert.certificado)
        nomes = [etree_local(e) for e in raiz[0]]
        self.assertEqual(nomes[nomes.index("tpEmit") + 1], "finNFSe")
        self.assertEqual(nomes[nomes.index("finNFSe") + 1], "cLocEmi")
        self.assertEqual(nomes[nomes.index("toma") + 1], "indDest")
        texto = dps.para_bytes(raiz).decode()
        inf = re.search(r"<infDPS.*?</infDPS>", texto, re.S).group(0).replace("<infDPS", f'<infDPS xmlns="{dps.NS}"', 1)
        digest = base64.b64encode(hashlib.sha256(ET.canonicalize(inf).encode()).digest()).decode()
        self.assertIn(f"<DigestValue>{digest}</DigestValue>", texto)

    def test_le_as_recusas_reais_do_governo(self):
        erro = lambda t: [{"codigo": "E1235", "descricao": t}]  # noqa: E731
        self.assertEqual(dps.ajuste_de_campos(erro(ERRO_LEIAUTE_REAL), frozenset()), {"finNFSe"})
        self.assertEqual(dps.ajuste_de_campos(erro(ERRO_INDDEST_REAL), {"finNFSe", "indDest"}), {"finNFSe"})
        self.assertIsNone(dps.ajuste_de_campos(erro(ERRO_LEIAUTE_REAL), {"finNFSe"}))  # nada a mudar
        self.assertIsNone(dps.ajuste_de_campos([{"codigo": "E0041", "descricao": "Município errado"}], frozenset()))

    def test_ambiente_de_testes_com_finNFSe_e_producao_sem_nada(self):
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.emitir_teste(self.empresa)
            nota = servicos.emitir_nota_shopee(self.empresa, "10,00")
            servicos.processar(nota)
        teste, producao = (x.decode() for x in falso.emitidas)
        self.assertIn("<finNFSe>0</finNFSe>", teste)
        self.assertNotIn("</toma><indDest>", teste)  # na raiz, o ambiente de testes recusa
        self.assertNotIn("finNFSe", producao)

    def test_se_ajusta_sozinho_ate_passar(self):
        # O que aconteceu hoje: o governo pede finNFSe, e depois recusa o indDest.
        cache.set("notas:campos2:2", ["indDest"])
        falso = ClienteEmSequencia([recusa_de_esquema(ERRO_LEIAUTE_REAL), recusa_de_esquema(ERRO_INDDEST_REAL), autorizada()])
        with mock.patch.object(servicos, "ClienteSefin", falso):
            nota = servicos.emitir_teste(self.empresa)
        self.assertEqual(nota.situacao, "autorizada")
        ultima = falso.emitidas[-1].decode()
        self.assertIn("<finNFSe>0</finNFSe>", ultima)
        self.assertNotIn("</toma><indDest>", ultima)
        self.assertEqual(servicos.campos_novos("2"), {"finNFSe"})  # as próximas já saem certas

    def test_producao_ganha_o_campo_quando_o_governo_mudar(self):
        nota = servicos.emitir_nota_shopee(self.empresa, "10,00")
        falso = ClienteEmSequencia([recusa_de_esquema(ERRO_LEIAUTE_REAL), autorizada()])
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertEqual(servicos.campos_novos("1"), {"finNFSe"})


def etree_local(elemento) -> str:
    return elemento.tag.split("}")[1]


ERRO_IBSCBS_REAL = "É obrigatório declarar informações de IBS/CBS quando a data de competência for igual ou posterior a 01/10/2026."
DADOS_RECEITA_LOJA = {
    "cnpj": "11222333000181", "razao_social": "LOJA UM LTDA", "municipio_ibge": "3550308", "municipio_nome": "Sao Paulo",
    "uf": "SP", "regime": "simples", "ativa": True,
    "endereco": {"municipio_ibge": "3550308", "cep": "01310100", "logradouro": "AVENIDA PAULISTA", "numero": "1000",
                 "complemento": "", "bairro": "BELA VISTA"},
}


class TestIBSCBS(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def test_grupo_ibscbs_e_recusa_e0855(self):
        raiz = dps_exemplo()
        dps.com_campos_novos(raiz, {"finNFSe", "IBSCBS"})
        xml = dps.para_bytes(raiz).decode()
        self.assertIn("<IBSCBS><cIndOp>100301</cIndOp><valores><trib><CST>000</CST>"
                      "<cClassTrib>000001</cClassTrib></trib></valores></IBSCBS></infDPS>", xml)
        self.assertNotIn("regApIBSCBSSN", xml)  # MEI não informa
        simples = dps_exemplo(regime="simples")
        dps.com_campos_novos(simples, {"IBSCBS"})
        self.assertIn("<regApTribSN>1</regApTribSN><regApIBSCBSSN>1</regApIBSCBSSN>", dps.para_bytes(simples).decode())
        self.assertEqual(dps.ajuste_de_campos([{"codigo": "E0855", "descricao": ERRO_IBSCBS_REAL}], {"finNFSe"}),
                         {"finNFSe", "IBSCBS"})

    def test_nota_de_teste_para_a_shopee_vai_com_ibscbs_e_endereco(self):
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.emitir_teste(self.empresa)
        xml = falso.emitidas[0].decode()
        self.assertIn("<cIndOp>100301</cIndOp>", xml)
        self.assertIn("<endNac><cMun>3550308</cMun><CEP>04538132</CEP></endNac>", xml)

    def test_vendedor_ganha_o_endereco_da_receita_uma_vez_so(self):
        lote = servicos.importar_relatorio(self.empresa, relatorio_csv(), "r.csv", "2")
        servicos.confirmar_lote(lote)
        nota = lote.notas.get(loja_id="1001")
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(receita, "consultar", return_value=DADOS_RECEITA_LOJA) as consulta, \
                mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
            outra = servicos.criar_nota(self.empresa, ambiente="2", tipo="vendedor", competencia=nota.competencia,
                                        tomador=dps.Tomador("cnpj", "11222333000181", "LOJA UM LTDA"), valor=2)
            servicos.processar(outra)
        self.assertEqual(consulta.call_count, 1)  # a segunda nota usa o endereço guardado
        xml = falso.emitidas[0].decode()
        self.assertIn("<end><endNac><cMun>3550308</cMun><CEP>01310100</CEP></endNac><xLgr>AVENIDA PAULISTA</xLgr>"
                      "<nro>1000</nro><xBairro>BELA VISTA</xBairro></end>", xml)

    def test_sem_endereco_na_receita_e_receita_fora_do_ar(self):
        lote = servicos.importar_relatorio(self.empresa, relatorio_csv(), "r.csv", "2")
        servicos.confirmar_lote(lote)
        nota = lote.notas.get(loja_id="1001")
        incompleto = {**DADOS_RECEITA_LOJA, "endereco": {"municipio_ibge": "", "cep": "", "logradouro": ""}}
        with mock.patch.object(receita, "consultar", return_value=incompleto), \
                mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "recusada")
        self.assertIn("endereço válido", nota.mensagens[0]["descricao"])
        outra = lote.notas.get(loja_id="1002")
        with mock.patch.object(receita, "consultar", side_effect=receita.ReceitaFora("fora")), \
                mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            servicos.processar(outra)
        self.assertEqual(outra.situacao, "erro")  # tenta de novo sozinho depois

    def test_producao_aprende_o_ibscbs_quando_o_governo_exigir(self):
        nota = servicos.emitir_nota_shopee(self.empresa, "10,00")
        falso = ClienteEmSequencia([Resposta(400, {"erros": [{"Codigo": "E0855", "Descricao": ERRO_IBSCBS_REAL}]}), autorizada()])
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertIn("<IBSCBS>", falso.emitidas[1].decode())
        self.assertEqual(servicos.campos_novos("1"), {"IBSCBS"})


class TestRegime(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def receita(self, regime):
        return {**DADOS_RECEITA_LOJA, "cnpj": CNPJ, "regime": regime}

    def test_atualiza_o_regime_pela_receita(self):
        with mock.patch.object(receita, "consultar", return_value=self.receita("simples")):
            aviso = servicos.atualizar_cadastro(self.empresa)
        self.assertIn("de MEI para Simples", aviso)
        self.assertEqual(EmpresaNotas.objects.get(pk=self.empresa.pk).regime, "simples")
        with mock.patch.object(receita, "consultar", return_value=self.receita("simples")):
            self.assertEqual(servicos.atualizar_cadastro(self.empresa), "")
        with mock.patch.object(receita, "consultar", return_value=self.receita("")):
            with self.assertRaisesMessage(servicos.ErroNotas, "não está mais no MEI"):
                servicos.atualizar_cadastro(self.empresa)
        with mock.patch.object(receita, "consultar", side_effect=receita.ReceitaFora("fora")):
            self.assertEqual(servicos.atualizar_cadastro(self.empresa), "")  # não trava a emissão

    def test_recusa_e0160_troca_o_regime_e_reenvia(self):
        nota = servicos.emitir_nota_shopee(self.empresa, "10,00")
        e0160 = Resposta(400, {"erros": [{"Codigo": "E0160", "Descricao": "Opção do Simples não confere."}]})
        falso = ClienteEmSequencia([e0160, autorizada()])
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertIn("<opSimpNac>2</opSimpNac>", falso.emitidas[0].decode())
        self.assertIn("<opSimpNac>3</opSimpNac>", falso.emitidas[1].decode())
        self.assertEqual(EmpresaNotas.objects.get(pk=self.empresa.pk).regime, "simples")

    def test_e0160_que_nao_resolve_mantem_o_regime(self):
        nota = servicos.emitir_nota_shopee(self.empresa, "10,00")
        e0160 = Resposta(400, {"erros": [{"Codigo": "E0160", "Descricao": "Opção do Simples não confere."}]})
        with mock.patch.object(servicos, "ClienteSefin", ClienteEmSequencia([e0160, e0160])):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "recusada")
        self.assertEqual(EmpresaNotas.objects.get(pk=self.empresa.pk).regime, "mei")


class TestCamposPorGrupo(TestCase):
    def erro(self, texto):
        return [{"codigo": "E1235", "descricao": texto}]

    def test_campo_pedido_dentro_do_ibscbs_vai_para_dentro(self):
        pedido = ("The element 'IBSCBS' in namespace 'http://www.sped.fazenda.gov.br/nfse' has invalid child element 'valores' "
                  "in namespace 'http://www.sped.fazenda.gov.br/nfse'. List of possible elements expected: 'tpOper, gRefNFSe, "
                  "tpEnteGov, indDest' in namespace 'http://www.sped.fazenda.gov.br/nfse'.")
        self.assertEqual(dps.ajuste_de_campos(self.erro(pedido), {"finNFSe", "IBSCBS"}), {"finNFSe", "IBSCBS", "IBSCBS.indDest"})
        sobra = ("The element 'IBSCBS' in namespace 'x' has invalid child element 'indDest' in namespace 'x'. "
                 "List of possible elements expected: 'dest, imovel, valores' in namespace 'x'.")
        self.assertEqual(dps.ajuste_de_campos(self.erro(sobra), {"IBSCBS", "IBSCBS.indDest"}), {"IBSCBS"})
        subgrupo = ("The element 'trib' in namespace 'x' has invalid child element 'CST' in namespace 'x'. "
                    "List of possible elements expected: 'gIBSCBS' in namespace 'x'.")
        self.assertEqual(dps.ajuste_de_campos(self.erro(subgrupo), {"IBSCBS"}), {"IBSCBS", "IBSCBS.gIBSCBS"})
        # o erro real de hoje: indDest na raiz é recusado -> sai da raiz (e não mexe no de dentro)
        self.assertEqual(dps.ajuste_de_campos(self.erro(ERRO_INDDEST_REAL), {"indDest", "IBSCBS", "IBSCBS.indDest"}),
                         {"IBSCBS", "IBSCBS.indDest"})

    def test_monta_o_ibscbs_no_formato_de_dezembro(self):
        raiz = dps_exemplo()
        dps.com_campos_novos(raiz, {"IBSCBS", "IBSCBS.finNFSe", "IBSCBS.indFinal", "IBSCBS.indDest", "IBSCBS.gIBSCBS"})
        self.assertIn("<IBSCBS><finNFSe>0</finNFSe><indFinal>0</indFinal><cIndOp>100301</cIndOp><indDest>0</indDest>"
                      "<valores><trib><gIBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib></gIBSCBS></trib></valores>"
                      "</IBSCBS>", dps.para_bytes(raiz).decode())

    def test_ambiente_de_testes_comeca_com_indDest_dentro_do_ibscbs(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.assertEqual(servicos.campos_novos("2"), {"finNFSe", "IBSCBS", "IBSCBS.indDest"})


class TestNBSeCertificado(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.empresa = criar_empresa(criar_conta(), codigo_tributacao="", descricao_servico="")
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def test_nbs_padrao_e_so_vai_com_ibscbs(self):
        servicos.aplicar_servico_padrao(self.empresa)
        self.assertEqual(self.empresa.codigo_nbs, "114061100")
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.emitir_teste(self.empresa)  # ambiente de testes: com IBS/CBS
            nota = servicos.emitir_nota_shopee(self.empresa, "10,00")  # produção: sem IBS/CBS por enquanto
            servicos.processar(nota)
        teste, producao = (x.decode() for x in falso.emitidas)
        self.assertIn("<xDescServ>Divulgação e venda de produtos</xDescServ><cNBS>114061100</cNBS>", teste)
        self.assertNotIn("cNBS", producao)

    def test_nbs_editavel_e_validado(self):
        servicos.salvar_servico(self.empresa, "170601", "", "Divulgação e venda de produtos", "", "1.1406.19.00")
        self.assertEqual(EmpresaNotas.objects.get(pk=self.empresa.pk).codigo_nbs, "114061900")
        with self.assertRaisesMessage(servicos.ErroNotas, "NBS"):
            servicos.salvar_servico(self.empresa, "170601", "", "Divulgação e venda de produtos", "", "1.1406")

    def test_cnbs_troca_de_lado_quando_o_governo_recusa(self):
        erro = [{"codigo": "E1235", "descricao": "The element 'cServ' in namespace 'x' has invalid child element 'cNBS' "
                 "in namespace 'x'. List of possible elements expected: 'cIntContrib' in namespace 'x'."}]
        self.assertEqual(dps.ajuste_de_campos(erro, {"IBSCBS"}), {"IBSCBS", "cServ.cNBS_antes"})
        self.assertEqual(dps.ajuste_de_campos(erro, {"IBSCBS", "cServ.cNBS_antes"}), {"IBSCBS"})
        raiz = dps.montar(ambiente="2", emitida_em=dt.datetime(2026, 10, 20, 9, 0, tzinfo=FUSO), serie="1", numero=7,
                          competencia=dt.date(2026, 10, 20), prestador=dps.Prestador(CNPJ, "3550308", "mei"),
                          tomador=dps.Tomador("cnpj", "35635824000112", "SHPS"),
                          servico=dps.Servico("170601", "Divulgação", nbs="114061100"), valor="1")
        dps.validar(raiz)  # cNBS depois da descrição passa no esquema oficial 1.01
        dps.com_campos_novos(raiz, {"cServ.cNBS_antes"})
        self.assertIn("<cTribNac>170601</cTribNac><cNBS>114061100</cNBS><xDescServ>", dps.para_bytes(raiz).decode())

    def test_certificado_e_guardado_em_der(self):
        import warnings

        guardado = base64.b64decode(painel_cripto().decifrar(EmpresaNotas.objects.get(pk=self.empresa.pk).certificado_cifrado))
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            pkcs12.load_key_and_certificates(guardado, b"senha-do-pfx")
        self.assertFalse([a for a in avisos if "BER" in str(a.message)])
        self.assertEqual(certificado.da_empresa(self.empresa).cnpj, CNPJ)


def painel_cripto():
    from painel import cripto
    return cripto


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestAndamento(TestCase):
    def setUp(self):
        cache.clear()
        self.conta = criar_conta()
        self.empresa = criar_empresa(self.conta)
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})
        self.lote = servicos.importar_relatorio(self.empresa, relatorio_csv(), "r.csv", "2")
        servicos.confirmar_lote(self.lote)

    def test_resumo_do_lote_e_situacao_de_cada_nota(self):
        primeira = self.lote.notas.order_by("pk").first()
        NotaFiscal.objects.filter(pk=primeira.pk).update(situacao="autorizada", numero_nfse="7")
        ids = ",".join(str(n.pk) for n in self.lote.notas.all())
        dados = self.client.get(f"/notas/andamento/?ids={ids}&lote={self.lote.pk}").json()
        self.assertEqual(dados["notas"][str(primeira.pk)], {"situacao": "autorizada", "rotulo": "Autorizada nº 7",
                                                            "classe": "selo-concluido"})
        self.assertEqual((dados["lote"]["autorizadas"], dados["lote"]["feitas"], dados["lote"]["fila"], dados["lote"]["progresso"]),
                         (1, 1, 2, 33))

    def test_outra_conta_nao_ve_nada(self):
        outra = criar_conta(email="outra@exemplo.com")
        cliente = Client(HTTP_HOST=HOST)
        cliente.post("/entrar/", {"email": outra.email, "senha": SENHA})
        ids = ",".join(str(n.pk) for n in self.lote.notas.all())
        dados = cliente.get(f"/notas/andamento/?ids={ids}&lote={self.lote.pk}").json()
        self.assertEqual(dados, {"notas": {}})

    def test_paginas_ligam_o_acompanhamento_so_quando_precisa(self):
        pagina = self.client.get(f"/notas/lote/{self.lote.pk}/")
        self.assertContains(pagina, 'data-acompanhar="/notas/andamento/"')
        self.assertContains(pagina, 'data-campo="barra"')
        self.assertContains(pagina, "painel/notas")
        with mock.patch.object(receita, "consultar", return_value={"regime": "mei"}):
            self.assertNotContains(self.client.get("/notas/"), "data-acompanhar")
            servicos.emitir_nota_shopee(self.empresa, "10,00")
            inicio = self.client.get("/notas/")
        self.assertContains(inicio, "data-acompanhar")
        self.assertContains(inicio, "se atualiza sozinha")


@unittest.skipUnless(connection.vendor == "postgresql", "envio simultâneo só roda com PostgreSQL")
@override_settings(NOTAS_ENVIOS_SIMULTANEOS=6, NOTAS_EMAILS_SIMULTANEOS=4)
class TestEnvioSimultaneo(TransactionTestCase):
    """Várias threads na mesma fila: cada nota sai uma vez só e nenhum número de DPS se repete."""

    def test_cada_nota_uma_vez_e_numeros_unicos(self):
        from . import fila

        empresa = criar_empresa(criar_conta())
        t = dps.Tomador("cnpj", "35635824000112", "LOJA", "loja@ex.com")
        for _ in range(60):
            servicos.criar_nota(empresa, ambiente=AMBIENTE_TESTE, tipo="vendedor", competencia=dt.date(2026, 9, 30),
                                tomador=t, valor=1)
        vezes, trava, threads = {}, threading.Lock(), set()

        def processar_falso(nota, cert=None, cliente=None):
            with trava:
                vezes[nota.pk] = vezes.get(nota.pk, 0) + 1
                threads.add(threading.get_ident())
            servicos._garantir_numero(nota)
            time.sleep(0.02)
            servicos._autorizar(nota, "chave", xml_nfse())
            nota.email_situacao = NotaFiscal.EMAIL_PENDENTE
            nota.save()

        enviados = []

        class EmailFalso:
            def send(self):
                time.sleep(0.01)
                with trava:
                    enviados.append(1)

        with mock.patch.object(servicos, "processar", processar_falso), \
                mock.patch.object(certificado, "da_empresa", return_value=object()), \
                mock.patch.object(fila, "ClienteSefin"), \
                mock.patch("notas.email.montar", return_value=EmailFalso()):
            self.assertEqual(fila.emitir(limite_segundos=30), 60)
            self.assertEqual(fila.enviar_emails(limite_segundos=30), 60)
        self.assertEqual(set(vezes.values()), {1})
        self.assertGreater(len(threads), 1)
        numeros = list(NotaFiscal.objects.values_list("numero", flat=True))
        self.assertEqual(sorted(numeros), list(range(1, 61)))
        self.assertEqual(len(enviados), 60)
        self.assertFalse(NotaFiscal.objects.exclude(email_situacao=NotaFiscal.EMAIL_ENVIADO).exists())


ENDERECO_POA = "Rua Quintino Bocaiúva, 457,  - Jardim América, Poá - São Paulo, 08555300"


class TestEnderecoDoRelatorio(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.empresa = criar_empresa(criar_conta())
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")

    def test_le_os_formatos_reais(self):
        ler = endereco.ler_do_relatorio
        self.assertEqual(ler(ENDERECO_POA), {"logradouro": "Rua Quintino Bocaiúva", "numero": "457", "complemento": "",
                                             "bairro": "Jardim América", "cidade": "Poá", "uf": "SP", "cep": "08555300"})
        rural = ler("A Rural, SN, Fabrica Talisma - Área Rural de Tabatinga, Tabatinga - São Paulo, 14918899")
        self.assertEqual((rural["logradouro"], rural["numero"], rural["complemento"], rural["bairro"], rural["uf"]),
                         ("A Rural", "SN", "Fabrica Talisma", "Área Rural de Tabatinga", "SP"))
        casa = ler("Rio do Ouro, 217, Casa 1 - Quinta dos Açorianos, Barra Velha - Santa Catarina, 88390000")
        self.assertEqual((casa["complemento"], casa["bairro"], casa["cidade"], casa["uf"]),
                         ("Casa 1", "Quinta dos Açorianos", "Barra Velha", "SC"))
        self.assertIsNone(ler("佛山市南海区大沥镇城南二路钟边铁村新区2337号自编1809之三(住所申报)"))
        self.assertIsNone(ler("Rua A, 1 - Centro, São Paulo - SP"))  # sem CEP
        self.assertIsNone(ler(""))

    def test_municipio_pela_lista_do_ibge_e_cep_so_quando_preciso(self):
        with mock.patch.object(endereco, "_consultar_cep") as consulta:
            end = endereco.do_relatorio(ENDERECO_POA)
        consulta.assert_not_called()  # a cidade está na lista: nenhuma consulta
        self.assertEqual((end["municipio_ibge"], end["cep"], end["numero"]), ("3539806", "08555300", "457"))
        self.assertEqual(endereco.municipio("SANTA BARBARA D OESTE", "sp"), endereco.municipio("Santa Bárbara d'Oeste", "SP"))
        self.assertEqual(endereco.municipio("Santa Rita do Sapucaí", "MG"), "3159605")
        # Cidade fora da lista: vai pelo CEP; CEP que não existe deixa o endereço de fora.
        self.assertEqual(endereco.do_relatorio("Rua X, 1, - Centro, Cidade Nova Inventada - Minas Gerais, 37538050")
                         ["municipio_ibge"], "3159605")
        self.assertIsNone(endereco.do_relatorio("Rua X, 1, - Centro, Cidade Nova Inventada - Minas Gerais, 37540000"))
        self.assertIsNone(endereco.do_relatorio("Rua X, 1, - Centro, Santa Rita do Sapucaí - Minas Gerais, 37540000",
                                                conferir_cep=True))

    def test_teste_com_cep_recusado_tenta_o_cep_da_receita_e_nao_repete_o_mesmo(self):
        nota = self._nota("2", texto="Rua A, 10, - Centro, Araçariguama - São Paulo, 18147350")
        e0240 = Resposta(400, {"erros": [{"Codigo": "E0240", "Descricao": "O CEP informado não existe."}]})
        falso = ClienteEmSequencia([e0240, autorizada()])
        outro = {**DADOS_RECEITA_LOJA, "endereco": {"municipio_ibge": "3502754", "cep": "18147000",
                                                    "logradouro": "RUA A", "numero": "10", "bairro": "CENTRO"}}
        with mock.patch.object(endereco, "_consultar_cep", return_value={"municipio_ibge": "3502754"}), \
                mock.patch.object(receita, "consultar", return_value=outro), mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertEqual(len(falso.emitidas), 2)  # o relatório com o município do CEP daria o mesmo: pulou
        self.assertIn("<CEP>18147000</CEP>", falso.emitidas[1].decode())
        # Nada diferente para tentar: fica com a recusa do governo, sem reenviar à toa.
        from .models import CadastroCNPJ
        CadastroCNPJ.objects.all().delete()
        nota2 = self._nota("2", texto="Rua A, 10, - Centro, Araçariguama - São Paulo, 18147350")
        falso2 = ClienteEmSequencia([e0240])
        mesmo = {**outro, "endereco": {**outro["endereco"], "cep": "18147350"}}
        with mock.patch.object(endereco, "_consultar_cep", return_value={"municipio_ibge": "3502754"}), \
                mock.patch.object(receita, "consultar", return_value=mesmo), mock.patch.object(servicos, "ClienteSefin", falso2):
            servicos.processar(nota2)
        self.assertEqual((nota2.situacao, nota2.mensagens[0]["codigo"], len(falso2.emitidas)), ("recusada", "E0240", 1))

    def test_teste_com_cep_recusado_confere_o_cep_e_usa_a_receita(self):
        nota = self._nota("2", texto="Rua X, 1, - Centro, Santa Rita do Sapucaí - Minas Gerais, 37540000")
        e0240 = Resposta(400, {"erros": [{"Codigo": "E0240", "Descricao": "O CEP informado não existe."}]})
        falso = ClienteEmSequencia([e0240, autorizada()])
        novo = {**DADOS_RECEITA_LOJA, "endereco": {"municipio_ibge": "3159605", "cep": "37538050",
                                                   "logradouro": "ELISA RIBEIRO COSTA", "numero": "148", "bairro": "X"}}
        with mock.patch.object(receita, "consultar", return_value=novo), mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertIn("<CEP>37540000</CEP>", falso.emitidas[0].decode())
        self.assertIn("<CEP>37538050</CEP>", falso.emitidas[1].decode())

    def _nota(self, ambiente, texto=ENDERECO_POA, **kw):
        return servicos.criar_nota(self.empresa, ambiente=ambiente, tipo="vendedor", competencia=dt.date(2026, 10, 1),
                                   tomador=dps.Tomador("cnpj", "52213651000163", "VICTOR CORREA SILVA"), valor=1,
                                   tomador_endereco=texto, **kw)

    def test_teste_com_ibscbs_usa_o_endereco_do_relatorio_e_nao_a_receita(self):
        nota = self._nota("2")
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(receita, "consultar") as consulta, mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        consulta.assert_not_called()
        self.assertIn("<end><endNac><cMun>3539806</cMun><CEP>08555300</CEP></endNac><xLgr>Rua Quintino Bocaiúva</xLgr>"
                      "<nro>457</nro><xBairro>Jardim América</xBairro></end>", falso.emitidas[0].decode())

    def test_cep_antigo_da_receita_nao_vai_para_a_nota(self):
        nota = self._nota("2", texto="")
        antigo = {**DADOS_RECEITA_LOJA, "endereco": {"municipio_ibge": "3159605", "cep": "37540000",
                                                     "logradouro": "ELISA RIBEIRO COSTA", "numero": "148", "bairro": "X"}}
        with mock.patch.object(receita, "consultar", return_value=antigo), \
                mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=autorizada())):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "recusada")
        self.assertIn("endereço válido", nota.mensagens[0]["descricao"])

    def test_producao_manda_o_endereco_e_se_o_governo_recusar_vai_sem(self):
        nota = self._nota("1")
        e0240 = Resposta(400, {"erros": [{"Codigo": "E0240", "Descricao": "O CEP informado para o endereço nacional do "
                                                                           "tomador do serviço não existe."}]})
        falso = ClienteEmSequencia([e0240, autorizada()])
        with mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertIn("<CEP>08555300</CEP>", falso.emitidas[0].decode())
        self.assertNotIn("<end>", falso.emitidas[1].decode())
        self.assertNotIn("<IBSCBS>", falso.emitidas[0].decode())

    def test_producao_sem_conseguir_consultar_o_cep_vai_sem_endereco(self):
        nota = self._nota("1", texto="Rua X, 1, - Centro, Cidade Nova Inventada - Minas Gerais, 37538050")
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(endereco, "_consultar_cep", side_effect=receita.ReceitaFora("fora")), \
                mock.patch.object(servicos, "ClienteSefin", falso):
            servicos.processar(nota)
        self.assertEqual(nota.situacao, "autorizada")
        self.assertNotIn("<end>", falso.emitidas[0].decode())

    def test_estrangeiro_vai_como_exportacao(self):
        raiz = dps_exemplo(tomador=dps.Tomador("nif", "92440605MACAK63G3K", "LOJA CHINESA", "a@b.cn", "CN"))
        dps.com_campos_novos(raiz, {"IBSCBS"})
        xml = dps.para_bytes(raiz).decode()
        self.assertIn("<CST>410</CST><cClassTrib>410004</cClassTrib>", xml)
        self.assertNotIn("cIndOp", xml)  # sem tributação, cIndOp não pode ir (E0859)

    def test_importar_de_novo_completa_o_endereco_das_notas_ja_criadas(self):
        linha = ("Sep 2026", "Casa Prática", "2001", "R$0,39", "52213651000163", "", "", "VICTOR CORREA SILVA",
                 ENDERECO_POA, "BR", "", "v@ex.com")
        lote = servicos.importar_relatorio(self.empresa, relatorio_csv([linha]), "r.csv", "2")
        servicos.confirmar_lote(lote)
        nota = lote.notas.get()
        self.assertEqual(nota.tomador_endereco, " ".join(ENDERECO_POA.split()))
        NotaFiscal.objects.filter(pk=nota.pk).update(tomador_endereco="", situacao=NotaFiscal.RECUSADA)  # nota antiga
        servicos.importar_relatorio(self.empresa, relatorio_csv([linha]), "r.csv", "2")
        nota.refresh_from_db()
        self.assertEqual(nota.tomador_endereco, " ".join(ENDERECO_POA.split()))


class TestPrioridadeDaEmissao(TestCase):
    def test_emails_esperam_a_fila_esvaziar(self):
        from . import fila

        with mock.patch.object(fila, "emitir", return_value=0), mock.patch.object(fila, "tem_fila", return_value=True), \
                mock.patch.object(fila, "enviar_emails") as emails:
            fila.uma_volta()
        emails.assert_not_called()
        with mock.patch.object(fila, "emitir", return_value=0), mock.patch.object(fila, "tem_fila", return_value=False), \
                mock.patch.object(fila, "enviar_emails", return_value=3) as emails:
            self.assertIn("Notas fiscais: 3 e-mail(s) enviado(s).", fila.uma_volta())
