"""Exporta o BRAND.md para PDF e TXT.

Existe porque o Markdown não é aceito como anexo em várias ferramentas (outras IAs,
sistemas de upload, e-mail corporativo). O conteúdo continua sendo escrito em
`BRAND.md` - este script só converte, nunca é a fonte.

O PDF sai com as fontes e as cores da própria marca, não com o padrão de um conversor
genérico: um manual de marca que não parece a marca é uma contradição em si.

O TXT é o mesmo arquivo com outra extensão. Markdown já é texto puro, então nada se
perde - e é o formato que praticamente todo sistema de upload aceita.

Rodar sempre que o BRAND.md mudar:
    python3 marketing/exportar_brand.py
"""
import base64
import re
import shutil
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
ORIGEM = REPO_ROOT / "BRAND.md"
DESTINO = REPO_ROOT / "marketing" / "brand-exportado"
FONT_DIR = REPO_ROOT / "static" / "fonts"

FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

CORES = {
    "ink": "#111827",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "brand-strong": "#4c1d95",
    "highlight": "#f59e0b",
    "paper-2": "#f1eefb",
    "line": "#e0dcef",
}

ESTILO = f"""
@font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
@font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}

@page {{ size:A4; margin:18mm 16mm; }}
/* Título de seção não fica órfão no pé da página, e tabela não parte no meio. */
h2, h3 {{ break-after:avoid; }}
table, tr {{ break-inside:avoid; }}

* {{ box-sizing:border-box; }}
body {{
    font-family:"Familjen", Arial, sans-serif; color:{CORES['ink']};
    font-size:10.5pt; line-height:1.55; margin:0;
}}
h1 {{
    font-size:30pt; font-weight:700; letter-spacing:-0.03em; color:{CORES['brand']};
    margin:0 0 4mm; line-height:1.1;
}}
h2 {{
    font-size:16pt; font-weight:700; letter-spacing:-0.02em; color:{CORES['brand-strong']};
    margin:10mm 0 3mm; padding-bottom:2mm; border-bottom:2px solid {CORES['line']};
}}
h3 {{ font-size:12pt; font-weight:700; color:{CORES['ink']}; margin:6mm 0 2mm; }}
p {{ margin:0 0 3mm; }}
ul, ol {{ margin:0 0 3mm; padding-left:6mm; }}
li {{ margin-bottom:1.5mm; }}
strong {{ font-weight:700; }}
em {{ color:{CORES['muted']}; }}
a {{ color:{CORES['brand']}; text-decoration:none; }}
hr {{ border:none; border-top:1px solid {CORES['line']}; margin:8mm 0; }}

code {{
    font-family:"JB Mono", monospace; font-size:9pt;
    background:{CORES['paper-2']}; padding:0.5mm 1.5mm; border-radius:2mm;
}}
pre {{
    font-family:"JB Mono", monospace; font-size:8.5pt; line-height:1.5;
    background:{CORES['paper-2']}; padding:3mm 4mm; border-radius:2mm;
    border-left:3px solid {CORES['brand']}; overflow-wrap:break-word;
}}
pre code {{ background:none; padding:0; }}

table {{ width:100%; border-collapse:collapse; margin:0 0 4mm; font-size:9.5pt; }}
th {{
    text-align:left; font-weight:700; font-size:8.5pt; text-transform:uppercase;
    letter-spacing:0.08em; color:{CORES['muted']};
    border-bottom:2px solid {CORES['line']}; padding:2mm 3mm 1.5mm;
}}
td {{ border-bottom:1px solid {CORES['line']}; padding:2mm 3mm; vertical-align:top; }}
tr:nth-child(even) td {{ background:#faf9fe; }}

blockquote {{
    margin:0 0 3mm; padding:2mm 4mm; border-left:3px solid {CORES['highlight']};
    background:#fffbeb; color:{CORES['ink']};
}}
"""

RODAPE = f"""
<div style="width:100%; font-family:Arial, sans-serif; font-size:7pt;
            color:{CORES['muted']}; padding:0 16mm; display:flex;
            justify-content:space-between;">
    <span>cash-b &mdash; manual de marca</span>
    <span class="pageNumber"></span>
</div>
"""


def _html(texto_md: str) -> str:
    corpo = markdown.markdown(
        texto_md, extensions=["tables", "fenced_code", "toc", "sane_lists"]
    )
    return f"<html><head><meta charset='utf-8'><style>{ESTILO}</style></head><body>{corpo}</body></html>"


def _sem_indice(texto_md: str) -> str:
    """Tira o índice de âncoras do Markdown.

    Num arquivo de repositório ele é navegação útil; no PDF vira uma lista de links
    que não levam a lugar nenhum, ocupando meia página logo na abertura.
    """
    return re.sub(r"\n## Índice\n.*?\n---\n", "\n", texto_md, flags=re.DOTALL)


def gerar():
    DESTINO.mkdir(parents=True, exist_ok=True)
    texto = ORIGEM.read_text(encoding="utf-8")

    pdf = DESTINO / "cash-b-manual-de-marca.pdf"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page()
        pagina.set_content(_html(_sem_indice(texto)))
        pagina.wait_for_timeout(400)
        pagina.pdf(
            path=str(pdf), format="A4", print_background=True,
            display_header_footer=True, header_template="<div></div>",
            footer_template=RODAPE,
            margin={"top": "18mm", "bottom": "18mm", "left": "0", "right": "0"},
        )
        navegador.close()
    print("gerado:", pdf.relative_to(REPO_ROOT), f"({pdf.stat().st_size // 1024} KB)")

    # Markdown já é texto puro: trocar a extensão basta, e nada se perde.
    txt = DESTINO / "cash-b-manual-de-marca.txt"
    shutil.copyfile(ORIGEM, txt)
    print("gerado:", txt.relative_to(REPO_ROOT))


if __name__ == "__main__":
    gerar()
