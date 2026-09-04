"""Gera um kit de artes de identidade visual (logotipo "cash-b" e monograma
"cb") pra uso em redes sociais - foto de perfil, posts genéricos de marca e
capa/banner. Reaproveita a mesma infra de gerar_posts_semeadura.py (Playwright
+ fontes da marca embutidas) e os mesmos motivos de ilustração de
static/css/brand.css (sacola+selo do hero, moeda+anel das páginas de conta) -
nada de fotografia, só forma geométrica plana, conforme BRAND.md.

Cada arte quadrada sai em duas versões: o arquivo normal e um `-zoom`, com o
desenho maior, para foto de perfil (que o Instagram recorta em círculo). Ver o
comentário em "Artes quadradas" para o porquê dos fatores.
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


def render(body_html, filename, width=1080, height=1080, destino=None, escala=2,
           transparente=False):
    """transparente=True tira o fundo branco padrão do navegador (omit_background) e
    depois recorta o PNG justo na tinta. As duas coisas juntas: sem o omit_background o
    arquivo sai com fundo branco chapado, e sem o recorte ele sai com uma moldura enorme
    de pixels vazios, que atrapalha na hora de posicionar o logo em cima de outra coisa."""
    html = f"""<html><head><style>
        {FONT_FACES}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: {width}px; height: {height}px; font-family: "Familjen", Arial, sans-serif;
                      {"background: transparent;" if transparente else ""} }}
        .canvas {{ width: {width}px; height: {height}px; position: relative; overflow: hidden; display: flex; }}
    </style></head><body>{body_html}</body></html>"""
    destino = destino or OUT_DIR
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / filename
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=escala)
        page.set_content(html)
        page.wait_for_timeout(150)
        page.screenshot(path=str(caminho), omit_background=transparente)
        browser.close()
    if transparente:
        _recortar_na_tinta(caminho)
    print("gerado:", caminho.relative_to(REPO_ROOT))


def _recortar_na_tinta(caminho):
    """Corta a moldura transparente em volta do desenho, usando o canal alfa."""
    from PIL import Image

    img = Image.open(caminho).convert("RGBA")
    caixa = img.getchannel("A").getbbox()
    if caixa:
        img.crop(caixa).save(caminho)


# ---------- Artes quadradas (perfil / marca) ----------
# Cada arte é função de um fator de escala k porque a mesma peça é gerada duas vezes:
# em k=1 (o arquivo original, para uso geral) e num k maior, para foto de perfil.
#
# O motivo do k maior: a foto de perfil do Instagram é recortada em CÍRCULO, e o
# desenho dessas artes foi dimensionado para um quadrado. Medindo a tinta renderizada,
# elas ocupavam de 38% a 56% da diagonal do círculo - por isso "ficava pequeno". Os
# valores de ZOOM abaixo levam cada uma para ~75%, que enche o círculo sem encostar
# na borda. Ampliar na mão pelo app perde qualidade e desalinha; aqui o desenho é
# rasterizado já no tamanho certo.
#
# Um k único não serviria: cada arte parte de uma ocupação diferente, então cada uma
# precisa do seu fator para todas chegarem no mesmo destino.

def _glifo_cb(k, cor=None):
    """O monograma "cb" com o centro óptico corrigido.

    O flex centraliza a CAIXA da linha de texto, não a tinta do glifo - como "cb" não
    tem descendente, sobra espaço embaixo (reservado pra letras como "g"/"p") e o "cb"
    fica visualmente baixo e um pouco à direita. line-height:1 reduz a caixa e o
    transform compensa o resto (medido em pixel real via screenshot).

    Virou função compartilhada porque a correção existia só na arte do anel: a versão
    verde saía 49px baixo e 10px à direita, o que num recorte circular aparece."""
    cor = cor or COLORS["paper"]
    return (
        f'<div style="font-size:{340*k:.0f}px; line-height:1; font-weight:700; '
        f'letter-spacing:-0.03em; color:{cor}; '
        f'transform:translate({-5*k:.0f}px, {-25*k:.0f}px);">cb</div>'
    )


def arte_perfil_cb_anel(k=1):
    return f"""
    <div class="canvas" style="background:{COLORS['brand']}; align-items:center; justify-content:center;">
        <div style="position:absolute; width:{760*k:.0f}px; height:{760*k:.0f}px; border-radius:50%; border:{26*k:.0f}px solid {COLORS['highlight']}; opacity:0.9;"></div>
        {_glifo_cb(k)}
    </div>
    """


def arte_perfil_cb_roxo(k=1):
    """Igual à do anel, sem o anel - o monograma sozinho sobre o roxo da marca."""
    return f"""
    <div class="canvas" style="background:{COLORS['brand']}; align-items:center; justify-content:center;">
        {_glifo_cb(k)}
    </div>
    """


def arte_perfil_cb_verde(k=1):
    return f"""
    <div class="canvas" style="background:{COLORS['success']}; align-items:center; justify-content:center;">
        {_glifo_cb(k)}
    </div>
    """


def arte_wordmark_roxo(k=1):
    return f"""
    <div class="canvas" style="background:{COLORS['brand']}; align-items:center; justify-content:center;">
        <div style="font-size:{200*k:.0f}px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
    </div>
    """


def arte_wordmark_claro(k=1):
    return f"""
    <div class="canvas" style="background:{COLORS['paper']}; align-items:center; justify-content:center; flex-direction:column;">
        <div style="font-size:{200*k:.0f}px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['brand']};">cash-b</div>
        <div style="width:{280*k:.0f}px; height:{14*k:.0f}px; border-radius:{7*k:.0f}px; background:{COLORS['highlight']}; margin-top:{28*k:.0f}px;"></div>
    </div>
    """


def arte_lockup_sacola(k=1):
    return f"""
    <div class="canvas" style="background:linear-gradient(160deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; justify-content:center; flex-direction:column; gap:{56*k:.0f}px;">
        <div style="width:{460*k:.0f}px;">{ILUSTRACAO_SACOLA}</div>
        <div style="font-size:{120*k:.0f}px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
    </div>
    """


def arte_lockup_moeda(k=1):
    return f"""
    <div class="canvas" style="background:linear-gradient(160deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; justify-content:center; flex-direction:column; gap:{56*k:.0f}px;">
        <div style="width:{420*k:.0f}px;">{ILUSTRACAO_MOEDA}</div>
        <div style="font-size:{120*k:.0f}px; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
    </div>
    """


# (função, nome base, fator de zoom da versão para foto de perfil)
ARTES_QUADRADAS = [
    (arte_perfil_cb_anel, "01-perfil-cb-roxo-ambar", 1.21),
    (arte_perfil_cb_verde, "02-perfil-cb-verde", 1.98),
    (arte_wordmark_roxo, "03-wordmark-roxo", 1.39),
    (arte_wordmark_claro, "04-wordmark-claro", 1.33),
    (arte_lockup_sacola, "05-lockup-sacola", 1.44),
    (arte_lockup_moeda, "06-lockup-moeda", 1.35),
    # Mesmo glifo e mesmo corpo da versão verde, então mesmo fator de zoom.
    (arte_perfil_cb_roxo, "08-perfil-cb-roxo", 1.98),
]

for construir, nome, zoom in ARTES_QUADRADAS:
    render(construir(), f"{nome}.png")
    render(construir(zoom), f"{nome}-zoom.png")


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

# ---------- 9. Capa do canal do YouTube (@usecashb) ----------
# 2560x1440 é o tamanho recomendado, mas só a faixa central de 1546x423 aparece em
# TODOS os aparelhos - no celular o resto some, na TV aparece tudo. Então a marca e a
# tagline ficam dentro dessa faixa, e as laterais levam só decoração: enriquecem a
# visualização grande sem fazer falta nenhuma quando o corte acontece.
# Escala 1 de propósito - 2560x1440 já é o tamanho final, e o YouTube limita em 6 MB.
CAPA_YT_SEGURA_L, CAPA_YT_SEGURA_A = 1546, 423


def _anel_decorativo(lado, tamanho, opacidade):
    """Anel âmbar solto no fundo, fora da área segura. Some no celular por definição -
    serve só para a capa não ficar um retângulo chapado em TV e desktop."""
    return (
        f'<div style="position:absolute; {lado}; width:{tamanho}px; height:{tamanho}px; '
        f'border-radius:50%; border:{tamanho*0.055:.0f}px solid {COLORS["highlight"]}; '
        f'opacity:{opacidade};"></div>'
    )


render(f"""
<div class="canvas" style="background:linear-gradient(120deg, {COLORS['brand-strong']}, {COLORS['brand']}); align-items:center; justify-content:center;">
    {_anel_decorativo("left:-150px; top:120px", 620, 0.16)}
    {_anel_decorativo("left:60px; bottom:-190px", 420, 0.10)}
    {_anel_decorativo("right:-190px; bottom:80px", 700, 0.16)}
    {_anel_decorativo("right:120px; top:-160px", 400, 0.10)}
    <div style="width:{CAPA_YT_SEGURA_L}px; height:{CAPA_YT_SEGURA_A}px; display:flex;
                align-items:center; justify-content:center; gap:90px; position:relative;">
        <div style="width:310px; flex-shrink:0;">{ILUSTRACAO_SACOLA}</div>
        <div>
            <div style="font-size:165px; line-height:1; font-weight:700; letter-spacing:-0.02em; color:{COLORS['paper']};">cash-b</div>
            <div style="font-size:50px; color:{COLORS['paper']}; opacity:0.92; margin-top:24px;">Compre na Shopee. Receba dinheiro de volta.</div>
        </div>
    </div>
</div>
""", "09-capa-youtube.png", width=2560, height=1440, escala=1)

# ---------- 10. Kit sem fundo (PNG transparente) ----------
# Para usar o logo em cima de foto, vídeo, papel timbrado ou material de terceiro, onde
# um retângulo de fundo denunciaria a colagem. Cada peça sai em duas cores: a de marca
# (para fundo claro) e a clara (para fundo escuro) - com fundo transparente não dá para
# ter uma versão só, porque a tinta precisa contrastar com o que estiver atrás.
#
# Renderiza numa tela folgada e deixa o recorte automático achar os limites: acertar a
# moldura na mão mudaria a cada ajuste de corpo de fonte.
SEM_FUNDO_DIR = OUT_DIR / "sem-fundo"


def _wordmark_livre(cor):
    return f"""
    <div class="canvas" style="align-items:center; justify-content:center;">
        <div style="font-size:400px; line-height:1; font-weight:700; letter-spacing:-0.02em; color:{cor};">cash-b</div>
    </div>
    """


def _glifo_livre(cor, com_anel=False):
    anel = (
        f'<div style="position:absolute; width:760px; height:760px; border-radius:50%; '
        f'border:26px solid {COLORS["highlight"]};"></div>'
        if com_anel else ""
    )
    return f"""
    <div class="canvas" style="align-items:center; justify-content:center;">
        {anel}
        {_glifo_cb(1, cor)}
    </div>
    """


for cor, sufixo in [(COLORS["brand"], "roxo"), (COLORS["paper"], "claro"), (COLORS["ink"], "preto")]:
    render(_wordmark_livre(cor), f"wordmark-{sufixo}.png",
           width=2200, height=700, destino=SEM_FUNDO_DIR, transparente=True)

for cor, sufixo in [(COLORS["brand"], "roxo"), (COLORS["paper"], "claro")]:
    render(_glifo_livre(cor), f"cb-{sufixo}.png",
           width=1080, height=1080, destino=SEM_FUNDO_DIR, transparente=True)
    render(_glifo_livre(cor, com_anel=True), f"cb-{sufixo}-anel.png",
           width=1080, height=1080, destino=SEM_FUNDO_DIR, transparente=True)


print("todas as artes geradas")
