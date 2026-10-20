"""PDF da nota (DANFSe v2.0, o leiaute nacional) gerado a partir do XML autorizado.
Usa a biblioteca BrazilFiscalReport (LGPL), a mesma estrutura do PDF do Emissor Nacional."""

import logging

logger = logging.getLogger(__name__)


def pdf(xml_nfse: str) -> bytes:
    from brazilfiscalreport.danfse import Danfse

    documento = Danfse(xml_nfse)
    return bytes(documento.output())


def nome_arquivo(nota, extensao: str) -> str:
    numero = nota.numero_nfse or nota.numero or nota.pk
    return f"NFSe-{numero}-{nota.tomador_documento}.{extensao}"
