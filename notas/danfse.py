"""PDF da nota (DANFSe v2.0, o leiaute nacional) gerado a partir do XML autorizado.
Usa a biblioteca BrazilFiscalReport (LGPL), a mesma estrutura do PDF do Emissor Nacional."""

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Fontes para quando o nome tem letras que a Helvetica do PDF não tem (vendedor da China, da Coreia...):
# a Liberation Sans tem as mesmas medidas da Helvetica (o leiaute fica igual) e o recorte da WenQuanYi
# Zen Hei entra só nas letras que faltam (chinês e coreano). Licenças em notas/fontes/LICENCAS.txt.
FONTES = Path(__file__).resolve().parent / "fontes"


def pdf(xml_nfse: str, cancelada: bool = False) -> bytes:
    """O PDF da nota; cancelada=True põe a marca d'água "CANCELADA" do leiaute nacional."""
    from brazilfiscalreport.danfse import Danfse, DanfseConfig
    from fpdf.errors import FPDFUnicodeEncodingException

    config = DanfseConfig(watermark_cancelled=cancelada)
    try:
        return bytes(Danfse(xml_nfse, config=config).output())
    except FPDFUnicodeEncodingException:
        # A fonte padrão (Helvetica, sem embutir) só tem as letras latinas: refaz com as fontes daqui.
        return bytes(_danfse_unicode()(xml_nfse, config=config).output())


@lru_cache(maxsize=1)
def _danfse_unicode():
    from brazilfiscalreport.danfse import Danfse

    class DanfseUnicode(Danfse):
        """O mesmo DANFSe, com fontes embutidas que têm chinês e coreano (antes de desenhar a 1ª página)."""

        def add_page(self, *args, **kwargs):
            if not getattr(self, "_fontes_unicode", False):
                self._fontes_unicode = True
                self.add_font("appfiliado", "", FONTES / "LiberationSans-Regular.ttf")
                self.add_font("appfiliado", "B", FONTES / "LiberationSans-Bold.ttf")
                self.add_font("appfiliado-cjk", "", FONTES / "WenQuanYiZenHei-CJK.ttf")
                self.set_fallback_fonts(["appfiliado-cjk"], exact_match=False)  # o negrito usa a mesma
                self.default_font = "appfiliado"
            return super().add_page(*args, **kwargs)

    return DanfseUnicode


def nome_arquivo(nota, extensao: str) -> str:
    """Só letras, números, ponto e hífen: o documento de vendedor estrangeiro (NIF) vem do
    relatório como texto livre e iria para o nome do arquivo e do ZIP ("../", aspas)."""
    import re

    numero = nota.numero_nfse or nota.numero or nota.pk
    documento = re.sub(r"[^\w.-]", "_", str(nota.tomador_documento or ""), flags=re.ASCII).strip("._") or "sem-documento"
    return f"NFSe-{numero}-{documento[:40]}.{extensao}"
