"""Gera um kit de artes de identidade visual (logotipo "cash-b" e monograma
"cb") pra uso em redes sociais - foto de perfil, posts genéricos de marca e
capa/banner. Reaproveita a mesma infra de gerar_posts_semeadura.py (Playwright
+ fontes da marca embutidas) e os mesmos motivos de ilustração de
static/css/brand.css (sacola+selo do hero, moeda+anel das páginas de conta) -
nada de fotografia, só forma geométrica plana, conforme BRAND.md.
"""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "artes-marca"
OUT_DIR.mkdir(exist_ok=True)

COLORS = {
    "ink": "#111827",
    "brand": "#6d28d9",
    "brand-strong": "#4c1d95",
    "highlight": "#f59e0b",
    "success": "#059669",
    "paper": "#f8fafc",
    "paper-2": "#f1eefb",
}

FONT_FACES = f"""
@font-face {{
    font-family: "Familjen";
    src: url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2");
    font-weight: 400 700;
}}
@font-face {{
    font-family: "JB Mono";
    src: url(data:font/woff2;base64,{JBMONO_B64}) format("woff2");
    font-weight: 400 700;
}}
"""

# Os dois motivos de ilustração já usados no site (home.html e
# _ilustracao_auth.html) - reaproveitados aqui como estão, só trocando a cor
# de preenchimento pelas variáveis já resolvidas em COLORS.
ILUSTRACAO_SACOLA = f"""
<svg viewBox="0 0 340 340" xmlns="http://www.w3.org/2000/svg">
    <path d="M50,150 C15,95 80,20 160,28 C230,35 290,15 315,80 C340,145 315,220 255,260 C200,296 110,310 55,265 C5,225 80,180 50,150 Z" fill="{COLORS['highlight']}" opacity="0.16"/>
    <path d="M135,140 C135,100 155,80 170,80 C185,80 205,100 205,140" fill="none" stroke="{COLORS['brand-strong']}" stroke-width="10" stroke-linecap="round"/>
    <path d="M108,140 L232,140 L252,296 Q252,306 242,306 L98,306 Q88,306 88,296 Z" fill="{COLORS['paper']}"/>
    <circle cx="250" cy="270" r="40" fill="{COLORS['highlight']}"/>
    <text x="250" y="282" text-anchor="middle" font-size="32" font-family="Familjen" font-weight="700" fill="{COLORS['brand-strong']}">%</text>
</svg>
"""

ILUSTRACAO_MOEDA = f"""
<svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg">
    <path d="M42,124 C14,78 66,18 138,24 C206,30 262,14 292,72 C322,130 302,202 248,244 C196,284 116,302 66,258 C18,216 68,172 42,124 Z" fill="{COLORS['highlight']}" opacity="0.16"/>
    <circle cx="160" cy="160" r="88" fill="none" stroke="{COLORS['highlight']}" stroke-width="10" stroke-linecap="round" stroke-dasharray="430 90" transform="rotate(-40 160 160)"/>
    <circle cx="160" cy="160" r="66" fill="{COLORS['paper']}"/>
    <text x="160" y="177" text-anchor="middle" font-size="46" letter-spacing="-2" font-family="Familjen" font-weight="700" fill="{COLORS['brand-strong']}">R$</text>
</svg>
"""


def render(body_html, filename, width=1080, height=1080, destino=None, escala=2):
    html = f"""<html><head><style>
        {FONT_FACES}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: {width}px; height: {height}px; font-family: "Familjen", Arial, sans-serif; }}
        .canvas {{ width: {width}px; height: {height}px; position: relative; overflow: hidden; display: flex; }}
    </style></head><body>{body_html}</body></html>"""
    destino = destino or OUT_DIR
    destino.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=escala)
        page.set_content(html)
        page.wait_for_timeout(150)
        page.screenshot(path=str(destino / filename))
        browser.close()
    print("gerado:", (destino / filename).relative_to(REPO_ROOT))


# ---------- 1. Foto de perfil - "cb" sobre roxo com anel âmbar (paleta mesclada) ----------
# O flex centraliza a CAIXA da linha de texto, não a tinta do glifo - como "cb" não tem
# descendente, sobra espaço embaixo (reservado pra letras como "g"/"p") e o "cb" fica
# visualmente baixo/deslocado. line-height:1 reduz a caixa, e o transform compensa o
# resto (medido em pixel real via screenshot até a tinta ficar centralizada no anel).
render(f"""
<div class="canvas" style="background:{COLORS['brand']}; align-items:center; justify-content:center;">
    <div style="position:absolute; width:760px; height:760px; border-radius:50%; border:26px solid {COLORS['highlight']}; opacity:0.9;"></div>
    <div style="font-size:340px; line-height:1; font-weight:700; letter-spacing:-0.03em; color:{COLORS['paper']}; transform:translate(-5px, -25px);">cb</div>
</div>
""", "01-perfil-cb-roxo-ambar.png")

# ---------- 2. Foto de perfil - "cb" sobre verde (variante dinheiro/cashback) ----------
render(f"""
<div class="canvas" style="background:{COLORS['success']}; align-items:center; justify-content:center;">
    <div style="font-size:340px; font-weight:700; letter-spacing:-0.03em; color:{COLORS['paper']};">cb</div>
</div>
""", "02-perfil-cb-verde.png")

# ---------- 3. Wordmark limpo sobre roxo sólido ----------
render(f"""
<div class="canvas" style="background:{COLORS['brand']}; align-items:center; justify-content:center;">
    <div style="font-size:200px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
</div>
""", "03-wordmark-roxo.png")

# ---------- 4. Wordmark sobre fundo claro, com sublinhado âmbar (paleta mesclada) ----------
render(f"""
<div class="canvas" style="background:{COLORS['paper']}; align-items:center; justify-content:center; flex-direction:column;">
    <div style="font-size:200px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['brand']};">cash-b</div>
    <div style="width:280px; height:14px; border-radius:7px; background:{COLORS['highlight']}; margin-top:28px;"></div>
</div>
""", "04-wordmark-claro.png")

# ---------- 5. Lockup com a ilustração da sacola (hero), degradê roxo ----------
render(f"""
<div class="canvas" style="background:linear-gradient(160deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; justify-content:center; flex-direction:column; gap:56px;">
    <div style="width:460px;">{ILUSTRACAO_SACOLA}</div>
    <div style="font-size:120px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
</div>
""", "05-lockup-sacola.png")

# ---------- 6. Lockup com a ilustração da moeda (contas), degradê roxo ----------
render(f"""
<div class="canvas" style="background:linear-gradient(160deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; justify-content:center; flex-direction:column; gap:56px;">
    <div style="width:420px;">{ILUSTRACAO_MOEDA}</div>
    <div style="font-size:120px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
</div>
""", "06-lockup-moeda.png")

# ---------- 7. Capa horizontal (header/banner) - wordmark + tagline + ilustração ----------
render(f"""
<div class="canvas" style="background:linear-gradient(120deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; padding:0 100px; gap:80px;">
    <div style="flex:1;">
        <div style="font-size:150px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
        <div style="font-size:38px; color:{COLORS['paper']}; opacity:0.92; margin-top:12px;">Compre na Shopee. Receba dinheiro de volta.</div>
    </div>
    <div style="width:340px; flex-shrink:0;">{ILUSTRACAO_SACOLA}</div>
</div>
""", "07-capa-horizontal.png", width=1600, height=900)

# ---------- 8. Imagem de compartilhamento (Open Graph) ----------
# Vai direto pro static/ porque é servida pelo site, não é peça de social. 1200x630 é o
# tamanho que WhatsApp/Facebook/Twitter esperam; escala 1 de propósito, pra manter o
# arquivo leve (a prévia do link precisa carregar rápido) - eles reduzem a imagem de
# qualquer jeito.
render(f"""
<div class="canvas" style="background:linear-gradient(120deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; padding:0 90px; gap:60px;">
    <div style="flex:1;">
        <div style="font-size:118px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
        <div style="font-size:32px; color:{COLORS['paper']}; opacity:0.92; margin-top:14px; line-height:1.35;">
            Compre na Shopee do jeito que você já compra<br>e receba parte do dinheiro de volta.
        </div>
    </div>
    <div style="width:260px; flex-shrink:0;">{ILUSTRACAO_SACOLA}</div>
</div>
""", "og-cash-b.png", width=1200, height=630, destino=REPO_ROOT / "static" / "images", escala=1)

print("todas as artes geradas")
