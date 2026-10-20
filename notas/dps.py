"""Monta, assina e confere a DPS (Declaração de Prestação de Serviço): o XML que vira a
NFS-e quando é aceito pela API do governo. Leiaute 1.01 da NFS-e de Padrão Nacional.

Assinatura XMLDSig "enveloped", canonicalização C14N inclusiva e só o certificado em
X509Data (manual, item 7.3.3). O manual fala em RSA-SHA1, mas o emissor nacional aceita
RSA-SHA256, que é o que as notas autorizadas em produção hoje usam: vai SHA-256."""

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
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
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
    _texto(toma, "xNome", _limpa(tomador.nome, 150))  # 150 é o limite do leiaute novo
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
    if tomador.tipo == "nif":
        # Comércio exterior (regra E0330), com os mesmos valores das notas para o exterior já
        # autorizadas em produção: modo 2 (consumo no Brasil), sem vínculo, real (986),
        # sem mecanismo de apoio (01/01), sem movimentação de bens (1), sem envio ao MDIC (0).
        com = _grupo(serv, "comExt")
        for tag, conteudo in (("mdPrestacao", 2), ("vincPrest", 0), ("tpMoeda", 986), ("vServMoeda", _valor(valor)),
                              ("mecAFComexP", "01"), ("mecAFComexT", "01"), ("movTempBens", 1), ("mdic", 0)):
            _texto(com, tag, conteudo)

    valores = _grupo(inf, "valores")
    _texto(_grupo(valores, "vServPrest"), "vServ", _valor(valor))
    trib = _grupo(valores, "trib")
    trib_mun = _grupo(trib, "tribMun")
    _texto(trib_mun, "tribISSQN", 1)  # operação tributável
    _texto(trib_mun, "tpRetISSQN", 1)  # ISS não retido (MEI não pode ter retenção, regra E0583)
    tot = _grupo(trib, "totTrib")
    _texto(tot, "indTotTrib", 0)  # não informa o valor aproximado dos tributos (MEI: regra E0710)
    return raiz


# Campos novos da reforma tributária (NT 009). Os ambientes do governo vão ganhando esses
# campos aos poucos (em out/2026 o de testes já pede "finNFSe", mas ainda não aceita
# "indDest"; a produção não aceita nenhum). Cada ambiente usa um conjunto, ajustado sozinho
# pelas recusas de esquema (E1235) - ver ajuste_de_campos.
CAMPOS_NOVOS = ("finNFSe", "indDest", "IBSCBS", "regApIBSCBSSN", "indFinal")

# IBS/CBS (reforma): exigido pelo governo a partir da competência 01/10/2026 no ambiente de
# testes (regra E0855); para MEI e Simples a obrigação em produção é a partir de 2027.
# Serviço de divulgação para empresa: tributação integral (CST 000 / cClassTrib 000001) e
# "demais serviços, operação onerosa" (cIndOp 100301: local = domicílio do tomador).
# O valor do imposto não vai na nota de MEI/Simples (é pago no DAS).
IBSCBS_CST, IBSCBS_CLASSIFICACAO, IBSCBS_INDICADOR = "000", "000001", "100301"
REGRA_IBSCBS_OBRIGATORIO = "E0855"


def com_campos_novos(raiz: etree._Element, campos) -> etree._Element:
    """Põe na DPS (já validada no leiaute 1.01) os campos novos pedidos: "finNFSe"
    (0 = nota regular) depois de tpEmit/cMotivoEmisTI e "indDest" (0 = o destinatário é o
    próprio tomador) depois de "toma"."""
    inf = raiz[0]
    if "finNFSe" in campos:
        ancora = inf.find(f"{{{NS}}}cMotivoEmisTI")
        if ancora is None:
            ancora = inf.find(f"{{{NS}}}tpEmit")
        fin = etree.Element(f"{{{NS}}}finNFSe")
        fin.text = "0"
        ancora.addnext(fin)
    if "indDest" in campos:
        toma = inf.find(f"{{{NS}}}toma")
        dest = etree.Element(f"{{{NS}}}indDest")
        dest.text = "0"
        (toma if toma is not None else inf.find(f"{{{NS}}}prest")).addnext(dest)
    if "regApIBSCBSSN" in campos or "IBSCBS" in campos:
        reg = inf.find(f"{{{NS}}}prest/{{{NS}}}regTrib")
        if reg.findtext(f"{{{NS}}}opSimpNac") == "3":  # só ME/EPP do Simples; MEI não informa
            ap = etree.Element(f"{{{NS}}}regApIBSCBSSN")
            ap.text = "1"  # IBS e CBS apurados pelo Simples Nacional
            ancora = reg.find(f"{{{NS}}}regApTribSN")
            (ancora if ancora is not None else reg.find(f"{{{NS}}}opSimpNac")).addnext(ap)
    if "IBSCBS" in campos:
        grupo = etree.SubElement(inf, f"{{{NS}}}IBSCBS")
        if "indFinal" in campos:  # opcional; só se o governo pedir (0 = não é consumo pessoal)
            _texto(grupo, "indFinal", 0)
        _texto(grupo, "cIndOp", IBSCBS_INDICADOR)
        trib = _grupo(_grupo(grupo, "valores"), "trib")
        _texto(trib, "CST", IBSCBS_CST)
        _texto(trib, "cClassTrib", IBSCBS_CLASSIFICACAO)
    return raiz


def ajuste_de_campos(mensagens: list[dict], campos) -> frozenset | None:
    """Se o governo recusou pelo esquema por causa de um campo novo, devolve o conjunto
    corrigido (tira o que veio "invalid", põe o que veio em "expected"); senão, None.
    Ex: E1235 "...invalid child element 'cLocEmi'... expected: 'cMotivoEmisTI, finNFSe'" -> põe finNFSe.
        E1235 "...invalid child element 'indDest'... expected: 'interm, serv'" -> tira indDest."""
    atual = set(campos)
    for m in mensagens:
        if m.get("codigo") == REGRA_IBSCBS_OBRIGATORIO:
            atual.add("IBSCBS")
            continue
        if m.get("codigo") != "E1235":
            continue
        texto = m.get("descricao", "")
        invalido = re.search(r"invalid child element '(\w+)'", texto)
        esperados = re.search(r"expected:\s*'([^']*)'", texto)
        if invalido and invalido.group(1) in CAMPOS_NOVOS:
            atual.discard(invalido.group(1))
        elif esperados:
            atual |= {c.strip() for c in esperados.group(1).split(",")} & set(CAMPOS_NOVOS)
    novo = frozenset(atual)
    return novo if novo != frozenset(campos) else None


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
    digest = base64.b64encode(hashlib.sha256(c14n(alvo)).digest()).decode()

    assinatura = etree.SubElement(raiz, f"{{{DS}}}Signature", nsmap={None: DS})
    info = etree.SubElement(assinatura, f"{{{DS}}}SignedInfo")
    etree.SubElement(info, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    etree.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm=RSA_SHA256)
    ref = etree.SubElement(info, f"{{{DS}}}Reference", URI=f"#{ident}")
    transformacoes = etree.SubElement(ref, f"{{{DS}}}Transforms")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=DS + "enveloped-signature")
    etree.SubElement(transformacoes, f"{{{DS}}}Transform", Algorithm=C14N)
    etree.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm=SHA256)
    etree.SubElement(ref, f"{{{DS}}}DigestValue").text = digest

    valor = chave.sign(c14n(info), padding.PKCS1v15(), hashes.SHA256())
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
