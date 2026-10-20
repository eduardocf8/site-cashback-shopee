"""Certificado digital A1 (.pfx/.p12): abrir, conferir e guardar cifrado.

O arquivo e a senha ficam cifrados no banco (painel/cripto.py) e só são abertos na
memória na hora de assinar e enviar uma nota."""

import base64
import re
from dataclasses import dataclass
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.utils import timezone

from painel import cripto

TAMANHO_MAXIMO = 64 * 1024  # um A1 tem uns 3 a 8 KB
OID_CNPJ_ICP = "2.16.76.1.3.3"  # campo "CNPJ" do e-CNPJ da ICP-Brasil


class ErroCertificado(ValueError):
    pass


@dataclass
class Certificado:
    chave: rsa.RSAPrivateKey
    certificado: x509.Certificate
    cadeia: list
    cnpj: str
    titular: str
    validade: datetime

    @property
    def vencido(self) -> bool:
        return self.validade <= timezone.now()


def _cnpj_do_certificado(cert: x509.Certificate) -> str:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for nome in san.get_values_for_type(x509.OtherName):
            if nome.type_id.dotted_string == OID_CNPJ_ICP:
                achado = re.search(rb"\d{14}", nome.value)
                if achado:
                    return achado.group().decode()
    except x509.ExtensionNotFound:
        pass
    # Plano B: o nome do titular do e-CNPJ termina em ":CNPJ" ("EMPRESA LTDA:12345678000199").
    for atributo in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME):
        achado = re.search(r":(\d{14})$", atributo.value)
        if achado:
            return achado.group(1)
    return ""


def abrir(dados: bytes, senha: str) -> Certificado:
    if not dados:
        raise ErroCertificado("Escolha o arquivo do certificado (.pfx ou .p12).")
    if len(dados) > TAMANHO_MAXIMO:
        raise ErroCertificado("Esse arquivo é grande demais para ser um certificado A1.")
    try:
        chave, cert, cadeia = pkcs12.load_key_and_certificates(dados, (senha or "").encode("utf-8"))
    except ValueError:
        raise ErroCertificado("Não consegui abrir o certificado: confira a senha e se o arquivo é o .pfx/.p12.")
    if chave is None or cert is None:
        raise ErroCertificado("Esse arquivo não tem a chave do certificado. Exporte de novo, com a chave privada.")
    if not isinstance(chave, rsa.RSAPrivateKey):
        raise ErroCertificado("Esse tipo de certificado não é aceito pelo emissor nacional (precisa ser RSA).")
    cnpj = _cnpj_do_certificado(cert)
    if not cnpj:
        raise ErroCertificado("Esse certificado não é de CNPJ (e-CNPJ). Para emitir as notas pela API, "
                              "o governo pede o certificado A1 da empresa.")
    titular = ", ".join(a.value for a in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)) or cnpj
    return Certificado(chave=chave, certificado=cert, cadeia=list(cadeia or []), cnpj=cnpj,
                       titular=titular[:200], validade=cert.not_valid_after_utc)


def guardar(empresa, dados: bytes, senha: str) -> Certificado:
    """Confere o certificado (é dessa empresa? está na validade?) e salva cifrado."""
    cert = abrir(dados, senha)
    if cert.cnpj[:8] != empresa.cnpj[:8]:
        raise ErroCertificado(f"Esse certificado é do CNPJ {cert.cnpj}, não do {empresa.cnpj_formatado}.")
    if cert.vencido:
        raise ErroCertificado("Esse certificado já venceu. Renove com a certificadora e envie o novo.")
    empresa.certificado_cifrado = cripto.cifrar(base64.b64encode(dados).decode("ascii"))
    empresa.senha_cifrada = cripto.cifrar(senha)
    empresa.certificado_titular = cert.titular
    empresa.certificado_validade = cert.validade
    empresa.emissao_pausada = ""  # certificado novo: a fila volta a andar
    empresa.save(update_fields=["certificado_cifrado", "senha_cifrada", "certificado_titular",
                                "certificado_validade", "emissao_pausada", "atualizada_em"])
    return cert


def da_empresa(empresa) -> Certificado:
    if not empresa.tem_certificado:
        raise ErroCertificado("Envie o certificado A1 da empresa antes de emitir.")
    dados_b64, senha = cripto.decifrar(empresa.certificado_cifrado), cripto.decifrar(empresa.senha_cifrada)
    if not dados_b64:
        raise ErroCertificado("Não consegui abrir o certificado guardado. Envie de novo, por favor.")
    cert = abrir(base64.b64decode(dados_b64), senha)
    if cert.vencido:
        raise ErroCertificado("O certificado da empresa venceu. Envie o novo para continuar emitindo.")
    return cert


def apagar(empresa):
    empresa.certificado_cifrado = empresa.senha_cifrada = empresa.certificado_titular = ""
    empresa.certificado_validade = None
    empresa.save(update_fields=["certificado_cifrado", "senha_cifrada", "certificado_titular",
                                "certificado_validade", "atualizada_em"])
