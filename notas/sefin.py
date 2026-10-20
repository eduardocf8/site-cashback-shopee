"""Cliente da API do Emissor Nacional (Sefin Nacional) da NFS-e.

Autenticação por TLS mútuo com o certificado A1 da empresa. A chave privada só passa
pelo disco no instante de montar a conexão (numa pasta temporária, de preferência em
memória, /dev/shm) e é apagada logo em seguida.

Endereços oficiais: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao"""

import base64
import gzip
import json
import logging
import os
import re
import ssl
import tempfile
from dataclasses import dataclass, field

import requests
from cryptography.hazmat.primitives import serialization
from requests.adapters import HTTPAdapter

from .models import AMBIENTE_PRODUCAO, AMBIENTE_TESTE

logger = logging.getLogger(__name__)

ENDERECOS = {
    AMBIENTE_PRODUCAO: "https://sefin.nfse.gov.br/SefinNacional",
    AMBIENTE_TESTE: "https://sefin.producaorestrita.nfse.gov.br/API/SefinNacional",
}
TEMPO_LIMITE = (10, 40)  # conectar, esperar a resposta (segundos)


class ErroSefin(Exception):
    """Falha de comunicação (sem resposta clara): a nota pode ou não ter sido gerada."""


@dataclass
class Resposta:
    status: int
    corpo: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def campo(self, *nomes, padrao=""):
        """Lê um campo do JSON sem depender de maiúsculas/minúsculas."""
        baixo = {str(k).lower(): v for k, v in self.corpo.items()}
        for nome in nomes:
            if nome.lower() in baixo and baixo[nome.lower()] not in (None, ""):
                return baixo[nome.lower()]
        return padrao

    @property
    def mensagens(self) -> list[dict]:
        """Erros e alertas do governo como [{"codigo", "descricao"}]."""
        saida = []
        for chave in ("erros", "erro", "alertas", "mensagens"):
            itens = self.campo(chave, padrao=[])
            if isinstance(itens, dict):
                itens = [itens]
            for item in itens if isinstance(itens, list) else []:
                if isinstance(item, dict):
                    b = {str(k).lower(): v for k, v in item.items()}
                    descricao = " ".join(str(b.get(k) or "") for k in ("descricao", "complemento")).strip()
                    saida.append({"codigo": str(b.get("codigo") or ""), "descricao": descricao[:500]})
                elif item:
                    saida.append({"codigo": "", "descricao": str(item)[:500]})
        if not saida and not self.ok:
            texto = self.campo("message", "mensagem", "title", "detail", padrao="")
            saida.append({"codigo": str(self.status), "descricao": str(texto or "Resposta sem detalhes.")[:500]})
        return saida

    def xml_nfse(self) -> str:
        bruto = self.campo("nfseXmlGZipB64", padrao="")
        return gzip.decompress(base64.b64decode(bruto)).decode("utf-8") if bruto else ""


def compactar(xml: bytes) -> str:
    return base64.b64encode(gzip.compress(xml)).decode("ascii")


class _AdaptadorTLS(HTTPAdapter):
    def __init__(self, contexto: ssl.SSLContext, **kwargs):
        self._contexto = contexto
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._contexto
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self._contexto
        return super().proxy_manager_for(*args, **kwargs)


def _contexto_tls(chave, certificado, cadeia) -> ssl.SSLContext:
    cafile = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or requests.certs.where()
    contexto = ssl.create_default_context(cafile=cafile)
    pem = certificado.public_bytes(serialization.Encoding.PEM)
    pem += b"".join(c.public_bytes(serialization.Encoding.PEM) for c in cadeia)
    chave_pem = chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    base = "/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None
    with tempfile.TemporaryDirectory(dir=base) as pasta:  # criada com permissão 0700
        caminho_cert, caminho_chave = os.path.join(pasta, "c.pem"), os.path.join(pasta, "k.pem")
        for caminho, conteudo in ((caminho_cert, pem), (caminho_chave, chave_pem)):
            fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as arquivo:
                arquivo.write(conteudo)
        contexto.load_cert_chain(caminho_cert, caminho_chave)
    return contexto


class ClienteSefin:
    def __init__(self, ambiente: str, cert):
        self.base = ENDERECOS[ambiente]
        self.sessao = requests.Session()
        self.sessao.headers.update({"Accept": "application/json"})
        self.sessao.mount("https://", _AdaptadorTLS(_contexto_tls(cert.chave, cert.certificado, cert.cadeia)))

    def _pedir(self, metodo: str, caminho: str, **kwargs) -> Resposta:
        try:
            r = self.sessao.request(metodo, self.base + caminho, timeout=TEMPO_LIMITE, **kwargs)
        except requests.RequestException as erro:
            raise ErroSefin(f"Sem resposta do emissor nacional ({erro.__class__.__name__}).") from erro
        try:
            corpo = r.json() if r.content else {}
        except (ValueError, json.JSONDecodeError):
            titulo = re.search(r"<title>(.*?)</title>", r.text or "", re.S | re.I)
            corpo = {"mensagem": (titulo.group(1).strip() if titulo else (r.text or "")[:200])}
        if r.status_code in (401, 403):
            corpo = {"erros": [{"codigo": str(r.status_code), "descricao": "O governo recusou o acesso com esse "
                                "certificado. Confira se é o A1 (e-CNPJ) da empresa e se está dentro da validade."}]}
        if r.status_code >= 500 or r.status_code == 429:
            raise ErroSefin(f"O emissor nacional está instável agora (HTTP {r.status_code}).")
        return Resposta(status=r.status_code, corpo=corpo if isinstance(corpo, dict) else {"itens": corpo})

    def emitir(self, dps_assinada: bytes) -> Resposta:
        """POST /nfse: transforma a DPS em NFS-e na hora (resposta 201 com o XML da nota)."""
        return self._pedir("POST", "/nfse", json={"dpsXmlGZipB64": compactar(dps_assinada)})

    def consultar_dps(self, dps_id: str) -> Resposta:
        """GET /dps/{id}: diz se essa DPS já virou nota (para não emitir duas vezes)."""
        return self._pedir("GET", f"/dps/{dps_id}")

    def consultar_nfse(self, chave: str) -> Resposta:
        return self._pedir("GET", f"/nfse/{chave}")
