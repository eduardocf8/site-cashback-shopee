"""PDF da nota (DANFSe v2.0, o leiaute nacional) gerado a partir do XML autorizado.
Usa a biblioteca BrazilFiscalReport (LGPL), a mesma estrutura do PDF do Emissor Nacional."""

import logging

logger = logging.getLogger(__name__)


def pdf(xml_nfse: str, cancelada: bool = False) -> bytes:
    """O PDF da nota; cancelada=True põe a marca d'água "CANCELADA" do leiaute nacional."""
    from brazilfiscalreport.danfse import Danfse, DanfseConfig

    documento = Danfse(xml_nfse, config=DanfseConfig(watermark_cancelled=cancelada))
    return bytes(documento.output())


def nome_arquivo(nota, extensao: str) -> str:
    """Só letras, números, ponto e hífen: o documento de vendedor estrangeiro (NIF) vem do
    relatório como texto livre e iria para o nome do arquivo e do ZIP ("../", aspas)."""
    import re

    numero = nota.numero_nfse or nota.numero or nota.pk
    documento = re.sub(r"[^\w.-]", "_", str(nota.tomador_documento or ""), flags=re.ASCII).strip("._") or "sem-documento"
    return f"NFSe-{numero}-{documento[:40]}.{extensao}"
