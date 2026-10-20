"""Monta, assina e confere a DPS (Declaração de Prestação de Serviço): o XML que vira a
NFS-e quando é aceito pela API do governo. Leiaute 1.01 da NFS-e de Padrão Nacional.

Assinatura conforme o manual (item 7.3.3): XMLDSig "enveloped", canonicalização C14N
inclusiva, RSA-SHA1, só com o certificado em X509Data."""

import base64
import copy
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

VERSAO = "1.01"
NS = "http://www.sped.fazenda.gov.br/nfse"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
VERSAO_APLICATIVO = "Appfiliado-1.0"
PASTA_XSD = Path(__file__).resolve().parent / "xsd" / VERSAO

# opSimpNac: 2 = MEI, 3 = ME/EPP do Simples Nacional
OPCAO_SIMPLES = {"mei": "2", "simples": "3"}


class ErroDPS(ValueError):
    pass


@dataclass
class Tomador:
    tipo: str  # "cnpj", "cpf" ou "nif"
    documento: str
    nome: str
    email: str = ""
    pais: str = ""  # ISO de 2 letras, só para estrangeiro
    # Endereço nacional (opcional na emissão pela API; usado na nota da Shopee).
    municipio_ibge: str = ""
    cep: str = ""
    logradouro: str = ""
    numero: str = ""
    complemento: str = ""
    bairro: str = ""


@dataclass
class Prestador:
    cnpj: str
    municipio_ibge: str
    regime: str  # "mei" ou "simples"
    inscricao_municipal: str = ""


@dataclass
class Servico:
    codigo_tributacao: str  # cTribNac, 6 dígitos
    descricao: str
    codigo_municipal: str = ""


def id_dps(municipio_ibge: str, cnpj: str, serie: str, numero: int) -> str:
    """"DPS" + município (7) + tipo de inscrição (2 = CNPJ) + CNPJ (14) + série (5) + número (15),
    45 caracteres (Anexo I, regra E0004)."""
    return f"DPS{municipio_ibge}2{cnpj.zfill(14)}{str(serie).zfill(5)}{int(numero):015d}"


def _texto(pai, tag, valor):
    el = etree.SubElement(pai, f"{{{NS}}}{tag}")
    el.text = str(valor)
    return el


def _grupo(pai, tag):
    return etree.SubElement(pai, f"{{{NS}}}{tag}")


def _valor(v) -> str:
    return str(Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _limpa(texto: str, maximo: int) -> str:
    return " ".join(str(texto or "").split())[:maximo]


def montar(*, ambiente: str, emitida_em: datetime, serie: str, numero: int, competencia: date,
           prestador: Prestador, tomador: Tomador, servico: Servico, valor) -> etree._Element:
    if prestador.regime not in OPCAO_SIMPLES:
        raise ErroDPS("Regime da empresa não aceito (só MEI ou Simples Nacional, por enquanto).")
    if Decimal(valor) <= 0:
        raise ErroDPS("O valor da nota precisa ser maior que zero.")
    if emitida_em.tzinfo is None:
        raise ErroDPS("Data de emissão sem fuso horário.")

    raiz = etree.Element(f"{{{NS}}}DPS", nsmap={None: NS}, versao=VERSAO)
    inf = _grupo(raiz, "infDPS")
    inf.set("Id", id_dps(prestador.municipio_ibge, prestador.cnpj, serie, numero))
    _texto(inf, "tpAmb", ambiente)
    _texto(inf, "dhEmi", emitida_em.replace(microsecond=0).isoformat())
    _texto(inf, "verAplic", VERSAO_APLICATIVO)
    _texto(inf, "serie", str(serie).zfill(5))
    _texto(inf, "nDPS", int(numero))
    _texto(inf, "dCompet", competencia.isoformat())
    _texto(inf, "tpEmit", 1)  # 1 = o próprio prestador emite
    _texto(inf, "cLocEmi", prestador.municipio_ibge)

    prest = _grupo(inf, "prest")
    _texto(prest, "CNPJ", prestador.cnpj)
    if prestador.inscricao_municipal:
        _texto(prest, "IM", prestador.inscricao_municipal)
    reg = _grupo(prest, "regTrib")
    _texto(reg, "opSimpNac", OPCAO_SIMPLES[prestador.regime])
    if prestador.regime == "simples":
        _texto(reg, "regApTribSN", 1)  # ISS e tributos federais apurados no próprio Simples
    _texto(reg, "regEspTrib", 0)  # nenhum regime especial (obrigatório para MEI, regra E0174)

    toma = _grupo(inf, "toma")
    if tomador.tipo == "cnpj":
        _texto(toma, "CNPJ", tomador.documento)
    elif tomador.tipo == "cpf":
        _texto(toma, "CPF", tomador.documento)
    elif tomador.tipo == "nif":
        _texto(toma, "NIF", _limpa(tomador.documento, 40))
    else:
        raise ErroDPS("Tipo de documento do tomador desconhecido.")
    _texto(toma, "xNome", _limpa(tomador.nome, 300))
    if tomador.tipo == "nif":
        # Vendedor do exterior: a API exige o endereço no exterior (regra E0242). O relatório
        # da Shopee não traz o endereço separado em campos, então vai só o país, com "-" no
        # resto, do mesmo jeito que as notas para o exterior já autorizadas hoje.
        if not re.fullmatch(r"[A-Z]{2}", tomador.pais or "") or tomador.pais == "BR":
            raise ErroDPS("Falta o país do vendedor do exterior.")
        end = _grupo(toma, "end")
        ext = _grupo(end, "endExt")
        _texto(ext, "cPais", tomador.pais)
        for tag in ("cEndPost", "xCidade", "xEstProvReg"):
            _texto(ext, tag, "-")
        for tag in ("xLgr", "nro", "xBairro"):
            _texto(end, tag, "-")
    elif tomador.municipio_ibge and tomador.cep and tomador.logradouro:
        end = _grupo(toma, "end")
        nac = _grupo(end, "endNac")
        _texto(nac, "cMun", tomador.municipio_ibge)
        _texto(nac, "CEP", tomador.cep)
        _texto(end, "xLgr", _limpa(tomador.logradouro, 255))
        _texto(end, "nro", _limpa(tomador.numero or "S/N", 60))
        if tomador.complemento:
            _texto(end, "xCpl", _limpa(tomador.complemento, 156))
        _texto(end, "xBairro", _limpa(tomador.bairro, 60))
    if tomador.email:
        _texto(toma, "email", _limpa(tomador.email, 80))

    serv = _grupo(inf, "serv")
    _texto(_grupo(serv, "locPrest"), "cLocPrestacao", prestador.municipio_ibge)
    cserv = _grupo(serv, "cServ")
    _texto(cserv, "cTribNac", servico.codigo_tributacao)
    if servico.codigo_municipal:
        _texto(cserv, "cTribMun", servico.codigo_municipal)
    _texto(cserv, "xDescServ", _limpa(servico.descricao, 2000))

    valores = _grupo(inf, "valores")
    _texto(_grupo(valores, "vServPrest"), "vServ", _valor(valor))
    trib = _grupo(valores, "trib")
    trib_mun = _grupo(trib, "tribMun")
    _texto(trib_mun, "tribISSQN", 1)  # operação tributável
    _texto(trib_mun, "tpRetISSQN", 1)  # ISS não retido (MEI não pode ter retenção, regra E0583)
    tot = _grupo(trib, "totTrib")
    _texto(tot, "indTotTrib", 0)  # não informa o valor aproximado dos tributos (MEI: regra E0710)
    return raiz


def c14n(elemento: etree._Element) -> bytes:
    """C14N 1.0 inclusiva de um pedaço do documento. A cópia é de propósito: o lxml, ao
    canonicalizar um elemento que não é a raiz, solta xmlns="" nos netos quando o namespace
    padrão vem de um ancestral, e aí a assinatura não bate do lado do governo. Copiado, o
    elemento vira raiz do próprio documento (levando os namespaces em uso) e sai certo."""
    return etree.tostring(copy.deepcopy(elemento), method="c14n")


def assinar(raiz: etree._Element, chave, certificado) -> etree._Element:
    """Assina o infDPS (ou o elemento com Id do evento) e põe a <Signature> no fim da raiz."""
    alvo = raiz[0]
    ident = alvo.get("Id")
    digest = base64.b64encode(hashlib.sha1(c14n(alvo)).digest()).decode()

    assinatura = etree.SubElement(raiz, f"{{{DS}}}Signature", nsmap={None: DS})
    info = etree.SubElement(assinatura, f"{{{DS}}}SignedInfo")
    etree.SubElement(info, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm=DS + "rsa-sha1")
    ref = etree.SubElement(info, f"{{{DS}}}Reference", URI=f"#{ident}")
    transformacoes = etree.SubElement(ref, f"{{{DS}}}Transforms")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=DS + "enveloped-signature")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=C14N)
    etree.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm=DS + "sha1")
    etree.SubElement(ref, f"{{{DS}}}DigestValue").text = digest

    valor = chave.sign(c14n(info), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(assinatura, f"{{{DS}}}SignatureValue").text = base64.b64encode(valor).decode()
    der = certificado.public_bytes(serialization.Encoding.DER)
    x509 = etree.SubElement(etree.SubElement(assinatura, f"{{{DS}}}KeyInfo"), f"{{{DS}}}X509Data")
    etree.SubElement(x509, f"{{{DS}}}X509Certificate").text = base64.b64encode(der).decode()
    return raiz


@lru_cache(maxsize=None)
def _esquema(arquivo: str) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(PASTA_XSD / arquivo)))


def validar(raiz: etree._Element, arquivo: str = f"DPS_v{VERSAO}.xsd"):
    """Confere o XML com o esquema oficial antes de mandar (o governo recusa o que não bate)."""
    esquema = _esquema(arquivo)
    if not esquema.validate(raiz):
        erros = "; ".join(f"{e.path}: {e.message}" for e in list(esquema.error_log)[:3])
        raise ErroDPS(f"A nota ficou fora do padrão oficial ({erros}).")


def para_bytes(raiz: etree._Element) -> bytes:
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8")
