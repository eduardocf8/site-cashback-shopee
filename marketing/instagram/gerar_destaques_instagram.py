"""Gera as capas dos Destaques do Instagram (ícone circular) e as artes de
cada um (os slides de story que ficam salvos dentro do destaque) - um
destaque por pasta. Reaproveita a mesma infra de gerar_posts_semeadura.py e
gerar_artes_marca.py (Playwright + fontes da marca embutidas); o texto dos
slides é adaptado dos posts de semeadura já existentes, pra manter a mesma
voz (ver VOZ.md) em vez de inventar frases novas.
"""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "destaques"
CAPAS_DIR = OUT_DIR / "capas"
CAPAS_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "ink": "#111827",
    "ink-soft": "#374151",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "brand-strong": "#4c1d95",
    "highlight": "#f59e0b",
    "success": "#059669",
    "paper": "#f8fafc",
    "paper-2": "#f1eefb",
    "line": "#e0dcef",
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


def render(body_html, out_path, width, height):
    html = f"""<html><head><style>
        {FONT_FACES}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{ width: {width}px; height: {height}px; font-family: "Familjen", Arial, sans-serif; }}
        .canvas {{ width: {width}px; height: {height}px; position: relative; overflow: hidden; display: flex; }}
    </style></head><body>{body_html}</body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
        page.set_content(html)
        page.wait_for_timeout(150)
        page.screenshot(path=str(out_path))
        browser.close()
    print("gerado:", out_path.relative_to(OUT_DIR))


# ============================================================
# CAPAS (ícone circular, 1080x1080 - o Instagram recorta em círculo)
# ============================================================

def render_capa(nome_arquivo, cor_fundo, icone_svg):
    render(f"""
    <div class="canvas" style="background:{cor_fundo}; align-items:center; justify-content:center;">
        <div style="width:400px; height:400px;">{icone_svg}</div>
    </div>
    """, CAPAS_DIR / nome_arquivo, 1080, 1080)


def render_glifo_capa(nome_arquivo, cor_fundo, glifo, transform):
    render(f"""
    <div class="canvas" style="background:{cor_fundo}; align-items:center; justify-content:center;">
        <div style="font-size:210px; line-height:1; font-weight:700; color:{COLORS['paper']}; transform:{transform};">{glifo}</div>
    </div>
    """, CAPAS_DIR / nome_arquivo, 1080, 1080)


# Ícones em SVG puro (sem depender de glifo de fonte) - mesma linguagem visual
# das ilustrações do site (static/css/brand.css): formas geométricas planas.
ICONE_PASSOS = f"""<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <line x1="90" y1="200" x2="310" y2="200" stroke="{COLORS['paper']}" stroke-width="16" stroke-linecap="round"/>
    <circle cx="90" cy="200" r="34" fill="{COLORS['paper']}"/>
    <circle cx="200" cy="200" r="34" fill="{COLORS['paper']}"/>
    <circle cx="310" cy="200" r="34" fill="{COLORS['paper']}"/>
</svg>"""

ICONE_PIX = f"""<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <polygon points="230,50 120,230 185,230 165,350 285,165 210,165" fill="{COLORS['paper']}"/>
</svg>"""

ICONE_CHECK = f"""<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <polyline points="105,210 175,278 300,125" fill="none" stroke="{COLORS['paper']}" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

ICONE_PESSOA = f"""<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
    <circle cx="200" cy="150" r="70" fill="{COLORS['paper']}"/>
    <path d="M80,340 C80,250 130,220 200,220 C270,220 320,250 320,340 Z" fill="{COLORS['paper']}"/>
</svg>"""

render_capa("01-como-funciona.png", COLORS["brand"], ICONE_PASSOS)
render_capa("02-saque-pix.png", COLORS["success"], ICONE_PIX)
render_glifo_capa("03-ofertas.png", COLORS["highlight"], "%", "translate(0px, -18px)")
render_capa("04-sem-pegadinha.png", COLORS["brand"], ICONE_CHECK)
render_capa("05-cadastre-se.png", COLORS["success"], ICONE_PESSOA)
render_glifo_capa("06-duvidas.png", COLORS["highlight"], "?", "translate(0px, -18px)")


# ============================================================
# ARTES (slides de story, 1080x1920, um por destaque)
# ============================================================

def render_story(pasta, nome_arquivo, body_html):
    render(body_html, OUT_DIR / pasta / nome_arquivo, 1080, 1920)


def eyebrow(texto, cor):
    return f'<div style="font-size:26px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; color:{cor};">{texto}</div>'


def passo(numero, titulo, texto, cor_numero=None):
    cor_numero = cor_numero or COLORS["brand"]
    return f"""
    <div style="display:flex; gap:28px; align-items:flex-start; margin-top:56px;">
        <div style="flex-shrink:0; width:72px; height:72px; border-radius:50%; background:{cor_numero};
                    color:{COLORS['paper']}; font-family:'JB Mono'; font-weight:700; font-size:32px;
                    display:flex; align-items:center; justify-content:center;">{numero}</div>
        <div>
            <div style="font-size:38px; font-weight:700; color:{COLORS['ink']};">{titulo}</div>
            <div style="font-size:28px; color:{COLORS['ink-soft']}; margin-top:8px; line-height:1.5; max-width:760px;">{texto}</div>
        </div>
    </div>
    """


def badge_marca(cor):
    return f'<div style="position:absolute; right:100px; bottom:80px; font-size:32px; font-weight:700; letter-spacing:-0.01em; color:{cor};">cash-b</div>'


# ---------- Destaque 1: Como funciona (4 slides) ----------
render_story("01-como-funciona", "01-intro.png", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; flex-direction:column;
     justify-content:center; align-items:center; text-align:center; padding:0 110px;">
    <div style="font-size:80px; font-weight:700; line-height:1.15; letter-spacing:-0.02em;">Como funciona<br>o cashback?</div>
    <div style="font-size:36px; margin-top:32px; max-width:760px; opacity:0.92; line-height:1.5;">
        3 passos simples pra ganhar dinheiro comprando na Shopee.
    </div>
</div>
""")

render_story("01-como-funciona", "02-passo-1.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('Passo 1 de 3', COLORS['brand'])}
    <div style="font-size:64px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">Encontre<br>o produto</div>
    <div style="font-size:34px; color:{COLORS['ink-soft']}; margin-top:32px; line-height:1.55; max-width:820px;">
        Converta o link do produto, acesse pela nossa vitrine de ofertas ou simplesmente clique em "Ir pra Shopee".
    </div>
    {badge_marca(COLORS['brand'])}
</div>
""")

render_story("01-como-funciona", "03-passo-2.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('Passo 2 de 3', COLORS['brand'])}
    <div style="font-size:64px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">Compre<br>normalmente</div>
    <div style="font-size:34px; color:{COLORS['ink-soft']}; margin-top:32px; line-height:1.55; max-width:820px;">
        Você compra do jeito que sempre comprou, sem precisar fazer nada a mais.
    </div>
    {badge_marca(COLORS['brand'])}
</div>
""")

render_story("01-como-funciona", "04-passo-3.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('Passo 3 de 3', COLORS['brand'])}
    <div style="font-size:64px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">Receba<br>cashback</div>
    <div style="font-size:34px; color:{COLORS['ink-soft']}; margin-top:32px; line-height:1.55; max-width:820px;">
        Depois que o pedido for validado, o dinheiro vai pro seu saldo liberado e você pode sacar direto pra sua conta.
    </div>
    <div style="margin-top:56px; display:inline-flex; padding:22px 40px; border-radius:32px; background:{COLORS['brand']};
                color:{COLORS['paper']}; font-weight:700; font-size:30px; align-self:flex-start;">Link na bio pra começar</div>
</div>
""")

# ---------- Destaque 2: Saque PIX (3 slides) ----------
render_story("02-saque-pix", "01-principal.png", f"""
<div class="canvas" style="background:{COLORS['success']}; color:{COLORS['paper']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('cash-b explica', COLORS['paper'])}
    <div style="font-size:72px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">Saque fácil,<br>direto no PIX</div>
    <div style="font-size:34px; margin-top:32px; opacity:0.92; line-height:1.55; max-width:800px;">
        Assim que seu saldo é liberado, é só cadastrar sua chave PIX e pedir o saque. Sem burocracia, direto na sua conta.
    </div>
</div>
""")

render_story("02-saque-pix", "02-passos.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('Como sacar', COLORS['success'])}
    <div style="font-size:56px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">É só isso:</div>
    {passo("1", "Cadastre sua chave PIX", "Uma vez só, no seu perfil.", COLORS['success'])}
    {passo("2", "Peça o saque", "Direto pelo seu painel, quando quiser.", COLORS['success'])}
    {passo("3", "Acompanhe o status", "Do pedido pendente até o dinheiro cair na conta.", COLORS['success'])}
</div>
""")

render_story("02-saque-pix", "03-acompanhe.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('cash-b explica', COLORS['success'])}
    <div style="font-size:60px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">Acompanhe tudo<br>pelo seu painel</div>
    <div style="font-size:34px; color:{COLORS['ink-soft']}; margin-top:32px; line-height:1.55; max-width:800px;">
        Veja o status de cada pedido - pendente, validado ou liberado - direto no seu dashboard, sem precisar perguntar pra ninguém.
    </div>
    {badge_marca(COLORS['success'])}
</div>
""")

# ---------- Destaque 3: Ofertas (1 slide - intro fixo; o resto do
# destaque vai sendo alimentado com reposts de ofertas do dia a dia) ----------
render_story("03-ofertas", "01-intro.png", f"""
<div class="canvas" style="background:{COLORS['highlight']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; align-items:center; text-align:center; padding:0 100px;">
    <div style="font-size:74px; font-weight:700; line-height:1.15; letter-spacing:-0.02em;">As melhores<br>ofertas da Shopee</div>
    <div style="font-size:34px; margin-top:32px; opacity:0.85; line-height:1.55; max-width:760px;">
        Direto na nossa vitrine, com cashback incluso.
    </div>
    <div style="margin-top:48px; display:inline-flex; padding:22px 44px; border-radius:32px; background:{COLORS['ink']};
                color:{COLORS['paper']}; font-weight:700; font-size:30px;">Toque no link</div>
</div>
""")

# ---------- Destaque 4: Sem pegadinha (2 slides) ----------
render_story("04-sem-pegadinha", "01-principal.png", f"""
<div class="canvas" style="background:{COLORS['ink']}; color:{COLORS['paper']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    <div style="font-size:80px; font-weight:700; line-height:1.15; letter-spacing:-0.02em;">
        Sem
        <span style="position:relative; display:inline-block; padding:0 0.1em; z-index:0;">
            pegadinha
            <span style="position:absolute; left:-0.06em; right:-0.06em; top:0.14em; bottom:0.02em; background:{COLORS['highlight']}; z-index:-1;"></span>
        </span>.
    </div>
    <div style="font-size:36px; margin-top:32px; opacity:0.85; line-height:1.55;">
        Sem mensalidade. Sem letra miúda.<br>Você só ganha.
    </div>
</div>
""")

render_story("04-sem-pegadinha", "02-reforco.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('cash-b explica', COLORS['brand'])}
    <div style="font-size:56px; font-weight:700; line-height:1.2; letter-spacing:-0.02em; margin-top:20px;">
        Toda compra que você já ia fazer
    </div>
    <div style="font-size:34px; color:{COLORS['ink-soft']}; margin-top:28px; line-height:1.55; max-width:800px;">
        agora te devolve uma parte do dinheiro - sem mudar seu jeito de comprar.
    </div>
    {badge_marca(COLORS['brand'])}
</div>
""")

# ---------- Destaque 5: Cadastre-se (3 slides) ----------
render_story("05-cadastre-se", "01-intro.png", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; flex-direction:column;
     justify-content:center; align-items:center; text-align:center; padding:0 100px;">
    <div style="font-size:80px; font-weight:700; line-height:1.15; letter-spacing:-0.02em;">Bora<br>começar?</div>
    <div style="font-size:34px; margin-top:32px; opacity:0.92; line-height:1.55; max-width:760px;">
        Cadastro grátis. Compre na Shopee do jeito que já compra e comece a receber cashback de verdade.
    </div>
</div>
""")

render_story("05-cadastre-se", "02-passos.png", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
     justify-content:center; padding:0 100px;">
    {eyebrow('Como começar', COLORS['brand'])}
    <div style="font-size:56px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; margin-top:20px;">3 passos e pronto:</div>
    {passo("1", "Acesse cash-b.com", "Direto do link na bio.")}
    {passo("2", "Crie sua conta", "Rápido e sem custo.")}
    {passo("3", "Comece a comprar e ganhar", "Do jeito que você já compra na Shopee.")}
</div>
""")

render_story("05-cadastre-se", "03-cta.png", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; flex-direction:column;
     justify-content:center; align-items:center; text-align:center; padding:0 100px;">
    <div style="font-size:56px; font-weight:700; line-height:1.2; letter-spacing:-0.02em;">Toque no link<br>da bio</div>
    <div style="margin-top:48px; padding:24px 52px; border-radius:36px; background:{COLORS['paper']};
                color:{COLORS['brand']}; font-weight:700; font-size:36px;">cash-b.com</div>
</div>
""")

# ---------- Destaque 6: Dúvidas (3 slides, formato pergunta/resposta) ----------
def pergunta_resposta(pasta, arquivo, pergunta, resposta):
    render_story(pasta, arquivo, f"""
    <div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; flex-direction:column;
         justify-content:center; padding:0 100px;">
        {eyebrow('Pergunta frequente', COLORS['highlight'])}
        <div style="font-size:52px; font-weight:700; line-height:1.25; letter-spacing:-0.02em; margin-top:24px; color:{COLORS['ink']};">
            {pergunta}
        </div>
        <div style="width:96px; height:8px; border-radius:4px; background:{COLORS['highlight']}; margin:36px 0;"></div>
        <div style="font-size:36px; color:{COLORS['ink-soft']}; line-height:1.55; max-width:820px;">{resposta}</div>
        {badge_marca(COLORS['highlight'])}
    </div>
    """)

pergunta_resposta(
    "06-duvidas", "01-toda-compra-gera-cashback.png",
    "Toda compra gera cashback?",
    "Sim. O valor muda conforme a comissão da Shopee, mas toda compra participante gera cashback.",
)
pergunta_resposta(
    "06-duvidas", "02-tem-taxa.png",
    "Tem alguma taxa ou mensalidade?",
    "Não. Cadastro grátis, sem mensalidade e sem letra miúda.",
)
pergunta_resposta(
    "06-duvidas", "03-como-recebo.png",
    "Como eu recebo o dinheiro?",
    "Direto no PIX, na chave que você cadastrar no seu perfil.",
)

print("\ntodas as capas e artes dos destaques foram geradas")
