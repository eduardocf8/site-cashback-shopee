import base64
import json
import io
import datetime as dt
import gzip
import hashlib
import re
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
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from licencas.models import ContaAppfiliado
from painel import modulos as mod

from . import certificado, dps, receita, servicos
from .models import AMBIENTE_TESTE, EmpresaNotas, NotaFiscal
from .sefin import ErroSefin, Resposta

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
CNPJ = "12345678000195"
FUSO = ZoneInfo("America/Sao_Paulo")
_CHAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # uma só, para os testes serem rápidos


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
