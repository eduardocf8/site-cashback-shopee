import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "posts-semeadura"
SIZE = 1080

COLORS = {
    "ink": "#12211a",
    "ink-soft": "#3c4a41",
    "muted": "#667069",
    "brand": "#1b5e44",
    "brand-strong": "#123e2d",
    "highlight": "#d8ff5e",
    "paper": "#f6f7f1",
    "paper-2": "#eef1e8",
    "line": "#cdd6c5",
}

BASE_CSS = f"""
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
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {SIZE}px; height: {SIZE}px; font-family: "Familjen", Arial, sans-serif; }}
.canvas {{
    width: {SIZE}px; height: {SIZE}px; position: relative; overflow: hidden;
    display: flex; flex-direction: column; padding: 88px;
}}
.badge {{
    position: absolute; left: 88px; bottom: 64px; font-size: 30px; font-weight: 700;
    letter-spacing: -0.01em;
}}
.eyebrow {{
    font-size: 22px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    margin-bottom: 20px;
}}
.headline {{ font-size: 64px; font-weight: 700; line-height: 1.12; letter-spacing: -0.02em; }}
.body {{ font-size: 32px; line-height: 1.5; margin-top: 28px; max-width: 820px; }}
.mark {{ position: relative; z-index: 0; display: inline-block; white-space: nowrap; padding: 0 0.1em; color: {COLORS['ink']}; }}
.mark::before {{
    content: ""; position: absolute; left: -0.06em; right: -0.06em; top: 0.08em; bottom: 0;
    background: {COLORS['highlight']}; z-index: -1;
}}
"""

def render(name, body_html, filename):
    html = f"<html><head><style>{BASE_CSS}</style></head><body>{body_html}</body></html>"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE}, device_scale_factor=2)
        page.set_content(html)
        page.wait_for_timeout(150)
        page.screenshot(path=str(OUT_DIR / filename))
        browser.close()
    print("gerado:", filename)

# ---------- Post 1: O que é o cash-b (cover) ----------
render("cover", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; justify-content:center; align-items:center; text-align:center;">
    <div style="font-size:130px; font-weight:700; letter-spacing:-0.02em;">cash-b</div>
    <div style="font-size:36px; margin-top:24px; max-width:760px; color:{COLORS['paper']}; opacity:0.92; line-height:1.4;">
        Um jeito simples de ganhar dinheiro de volta comprando na Shopee.
    </div>
</div>
""", "01-o-que-e-cashb.png")

# ---------- Post 2: Como funciona (steps) ----------
def step_row(numero, titulo, texto):
    return f"""
    <div style="display:flex; gap:28px; align-items:flex-start; margin-top:44px;">
        <div style="flex-shrink:0; width:64px; height:64px; border-radius:50%; background:{COLORS['brand']};
                    color:{COLORS['paper']}; font-family:'JB Mono'; font-weight:700; font-size:30px;
                    display:flex; align-items:center; justify-content:center;">{numero}</div>
        <div>
            <div style="font-size:34px; font-weight:700; color:{COLORS['ink']};">{titulo}</div>
            <div style="font-size:26px; color:{COLORS['ink-soft']}; margin-top:6px; line-height:1.45; max-width:640px;">{texto}</div>
        </div>
    </div>
    """

render("steps", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; justify-content:center;">
    <div class="eyebrow" style="color:{COLORS['brand']};">cash-b explica</div>
    <div class="headline">Como funciona<br>o cashback?</div>
    {step_row('1', 'Gere seu link (ou vá direto)', 'Cole o link do produto que quer comprar ou clique em “Ir para a Shopee”.')}
    {step_row("2", "Compre normalmente", "Você compra do jeito que sempre comprou, sem passo a mais.")}
    {step_row("3", "Receba parte de volta", "Depois que a Shopee confirma o pedido, seu cashback cai no seu saldo.")}
    <div class="badge" style="color:{COLORS['brand']};">cash-b</div>
</div>
""", "02-como-funciona.png")

# ---------- Post 3: Venda direta x indireta (split) ----------
def split_card(etiqueta, cor_etiqueta, titulo, texto, destaque=False):
    borda = COLORS['brand'] if destaque else COLORS['line']
    largura_borda = "3px" if destaque else "2px"
    return f"""
    <div style="flex:1; background:{COLORS['paper']}; border:{largura_borda} solid {borda}; border-radius:20px; padding:36px;">
        <div style="display:inline-block; font-size:18px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase;
                    padding:6px 14px; border-radius:12px; background:{cor_etiqueta}; color:{COLORS['ink']}; margin-bottom:18px;">{etiqueta}</div>
        <div style="font-size:32px; font-weight:700; color:{COLORS['ink']}; line-height:1.25;">{titulo}</div>
        <div style="font-size:23px; color:{COLORS['ink-soft']}; margin-top:14px; line-height:1.5;">{texto}</div>
    </div>
    """

render("split", f"""
<div class="canvas" style="background:{COLORS['paper-2']}; color:{COLORS['ink']}; justify-content:center;">
    <div class="eyebrow" style="color:{COLORS['brand']};">cash-b explica</div>
    <div class="headline">2 formas de<br>ganhar cashback</div>
    <div style="display:flex; gap:28px; margin-top:56px;">
        {split_card("Venda direta", COLORS['highlight'], "Link de um produto específico", "Cola o link do produto e converte. Se tiver campanha de comissão extra ativa, só essa forma tem acesso ao bônus.", destaque=True)}
        {split_card("Venda indireta", COLORS['line'], 'Botão "Ir para a Shopee"', "Você entra pela home e compra o que quiser. Cashback garantido, sem escolher produto antes.")}
    </div>
    <div class="badge" style="color:{COLORS['brand']};">cash-b</div>
</div>
""", "03-venda-direta-indireta.png")

# ---------- Post 4: Da compra ao PIX (timeline) ----------
def status_pill(nome, cor_fundo, cor_texto):
    return f"""
    <div style="flex:1; text-align:center;">
        <div style="display:inline-block; padding:14px 0; width:100%; border-radius:16px; background:{cor_fundo};
                    color:{cor_texto}; font-weight:700; font-size:26px;">{nome}</div>
    </div>
    """

render("timeline", f"""
<div class="canvas" style="background:{COLORS['paper']}; color:{COLORS['ink']}; justify-content:center;">
    <div class="eyebrow" style="color:{COLORS['brand']};">cash-b explica</div>
    <div class="headline">Do clique<br>ao PIX</div>
    <div class="body" style="color:{COLORS['ink-soft']};">Depois da compra, seu cashback passa por 3 fases até virar dinheiro de verdade:</div>
    <div style="display:flex; align-items:center; gap:16px; margin-top:64px;">
        {status_pill("Pendente", COLORS['line'], COLORS['ink-soft'])}
        <div style="font-size:34px; color:{COLORS['muted']};">&rarr;</div>
        {status_pill("Validado", "#e8f2fa", "#1a6fb0")}
        <div style="font-size:34px; color:{COLORS['muted']};">&rarr;</div>
        {status_pill("Liberado", "#e3f3ea", COLORS['brand'])}
    </div>
    <div style="margin-top:36px; font-size:22px; color:{COLORS['muted']}; line-height:1.5; max-width:820px;">
        Pendente: aguardando confirmação da Shopee. Validado: compra confirmada, aguardando prazo. Liberado: já pode sacar via PIX.
    </div>
    <div class="badge" style="color:{COLORS['brand']};">cash-b</div>
</div>
""", "04-do-clique-ao-pix.png")

# ---------- Post 5: Como sacar via PIX ----------
render("saque", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; justify-content:center;">
    <div class="eyebrow" style="color:{COLORS['highlight']};">cash-b explica</div>
    <div class="headline">Saque fácil,<br>direto no PIX</div>
    <div class="body" style="color:{COLORS['paper']}; opacity:0.92;">
        Assim que seu saldo é liberado, é só cadastrar sua chave PIX e pedir o saque. Sem burocracia, direto na sua conta.
    </div>
    <div class="badge" style="color:{COLORS['paper']}; opacity:0.85;">cash-b</div>
</div>
""", "05-saque-pix.png")

# ---------- Post 6: Sem pegadinha (statement ink) ----------
render("pegadinha", f"""
<div class="canvas" style="background:{COLORS['ink']}; color:{COLORS['paper']}; justify-content:center;">
    <div class="headline" style="font-size:76px;">Sem <span class="mark">pegadinha</span>.</div>
    <div class="body" style="color:{COLORS['paper']}; opacity:0.85; font-size:34px;">
        Sem mensalidade. Sem letra miúda.<br>Você só ganha.
    </div>
    <div class="badge" style="color:{COLORS['paper']}; opacity:0.85;">cash-b</div>
</div>
""", "06-sem-pegadinha.png")

# ---------- Post 7: Quanto dá pra economizar (highlight statement) ----------
render("economizar", f"""
<div class="canvas" style="background:{COLORS['highlight']}; color:{COLORS['ink']}; justify-content:center;">
    <div class="eyebrow" style="color:{COLORS['ink']};">cash-b explica</div>
    <div class="headline" style="font-size:58px;">Toda compra que você já ia fazer,<br>agora te devolve uma parte do dinheiro.</div>
    <div class="body" style="color:{COLORS['ink']}; opacity:0.85;">
        Sem mudar seu jeito de comprar — só ganhando mais no final.
    </div>
    <div class="badge" style="color:{COLORS['ink']};">cash-b</div>
</div>
""", "07-quanto-economizar.png")

# ---------- Post 8: Cadastre-se agora (CTA) ----------
render("cta", f"""
<div class="canvas" style="background:{COLORS['brand']}; color:{COLORS['paper']}; justify-content:center; align-items:center; text-align:center;">
    <div class="headline" style="font-size:72px; text-align:center;">Bora<br>começar?</div>
    <div class="body" style="color:{COLORS['paper']}; opacity:0.92; text-align:center;">
        Cadastro grátis. Compre na Shopee do jeito que já compra e comece a receber cashback de verdade.
    </div>
    <div style="margin-top:44px; padding:20px 44px; border-radius:32px; background:{COLORS['paper']};
                color:{COLORS['brand']}; font-weight:700; font-size:32px;">cash-b.com</div>
</div>
""", "08-cadastre-se.png")

print("todos gerados")
