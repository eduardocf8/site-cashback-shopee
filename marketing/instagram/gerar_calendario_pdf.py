"""PDF do calendário da campanha 10.10, a partir de `calendario-campanha-10-10.md`.

O .md é a fonte: para mudar o calendário, edite o .md e rode este script de novo. O PDF
sai em A4 paisagem, com a fonte e as cores da marca, e o cabeçalho da tabela repete em
cada página.

    python3 gerar_calendario_pdf.py
"""
import base64
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

AQUI = Path(__file__).resolve().parent
REPO_ROOT = AQUI.parents[1]
ORIGEM = AQUI / "calendario-campanha-10-10.md"
DESTINO = AQUI / "calendario-campanha-10-10.pdf"
FONTE_B64 = base64.b64encode((REPO_ROOT / "static" / "fonts" / "familjen-grotesk.woff2").read_bytes()).decode()

CSS = f"""
@font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FONTE_B64}) format("woff2"); font-weight:400 700; }}
@page {{ size:A4 landscape; margin:12mm 12mm 14mm; }}
* {{ box-sizing:border-box; }}
body {{ font-family:"Familjen", Arial, sans-serif; color:#111827; font-size:10pt; line-height:1.4; }}
h1 {{ font-size:20pt; color:#4c1d95; margin:0 0 6mm; letter-spacing:-0.02em; }}
h2 {{ font-size:13pt; color:#6d28d9; margin:7mm 0 3mm; break-after:avoid; }}
p {{ margin:0 0 3mm; }}
code {{ font-family:"JetBrains Mono", Consolas, monospace; font-size:8.5pt; background:#f1eefb; padding:1px 4px; border-radius:3px; }}
table {{ width:100%; border-collapse:collapse; font-size:9pt; }}
thead {{ display:table-header-group; }}
th {{ background:#4c1d95; color:#fff; text-align:left; padding:2.2mm 3mm; font-weight:700; }}
td {{ padding:2mm 3mm; vertical-align:top; border-bottom:1px solid #e0dcef; }}
tr {{ break-inside:avoid; }}
tbody tr:has(td:first-child strong) td {{ border-top:2px solid #6d28d9; }}
tbody tr:has(td:first-child strong) td:first-child {{ color:#4c1d95; }}
td:first-child, td:nth-child(2) {{ white-space:nowrap; }}
td:nth-child(4) {{ color:#6b7280; font-size:8pt; word-break:break-word; }}
ol, ul {{ margin:0 0 3mm; padding-left:6mm; }}
li {{ margin-bottom:1.5mm; }}
"""


def gerar():
    corpo = markdown.markdown(ORIGEM.read_text(encoding="utf-8"), extensions=["tables"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{corpo}</body></html>"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page()
        pagina.set_content(html)
        pagina.wait_for_timeout(300)
        pagina.pdf(path=str(DESTINO), prefer_css_page_size=True, print_background=True)
        navegador.close()
    print("gerado:", DESTINO.relative_to(REPO_ROOT))


if __name__ == "__main__":
    gerar()
