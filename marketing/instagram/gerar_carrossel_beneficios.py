"""Gera o carrossel de Instagram "Benefícios de usar o cash-b" - primeiro o
preview HTML "arrastável" (pra revisão), depois a exportação dos 7 slides em
PNG 1080x1350. Segue a skill instagram-carousel (~/.claude/skills/), com a
paleta e as fontes reais da marca (ver BRAND.md/brand.css) no lugar da
paleta genérica derivada que a skill sugere por padrão.
"""
import base64
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "carrossel-beneficios"
OUT_DIR.mkdir(exist_ok=True)

# Paleta: tokens já existentes em static/css/brand.css, mais um roxo claro
# (BRAND_LIGHT) que o brand.css não tinha - só usado aqui pro sistema de
# tags/pills sobre fundo escuro, que a skill pede.
BRAND_PRIMARY = "#6d28d9"
BRAND_LIGHT = "#a78bfa"
BRAND_DARK = "#4c1d95"
LIGHT_BG = "#f8fafc"
LIGHT_BORDER = "#e0dcef"
DARK_BG = "#111827"
SUCCESS = "#059669"
HIGHLIGHT = "#f59e0b"
PAPER = "#f8fafc"
INK_SOFT = "#374151"
MUTED = "#6b7280"

BRAND_GRADIENT = f"linear-gradient(165deg, {BRAND_DARK} 0%, {BRAND_PRIMARY} 55%, {BRAND_LIGHT} 100%)"

HANDLE = "@cash.b"
TOTAL = 7

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


def progress_bar(index, is_light):
    pct = ((index + 1) / TOTAL) * 100
    track = "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.14)"
    fill = BRAND_PRIMARY if is_light else "#fff"
    label = "rgba(0,0,0,0.35)" if is_light else "rgba(255,255,255,0.45)"
    return f"""
    <div style="position:absolute; bottom:0; left:0; right:0; padding:16px 28px 20px; z-index:10;
                display:flex; align-items:center; gap:10px;">
        <div style="flex:1; height:3px; background:{track}; border-radius:2px; overflow:hidden;">
            <div style="height:100%; width:{pct}%; background:{fill}; border-radius:2px;"></div>
        </div>
        <span style="font-family:'JB Mono'; font-size:11px; color:{label}; font-weight:500;">{index+1}/{TOTAL}</span>
    </div>
    """


def swipe_arrow(is_light):
    bg = "rgba(0,0,0,0.06)" if is_light else "rgba(255,255,255,0.10)"
    stroke = "rgba(0,0,0,0.25)" if is_light else "rgba(255,255,255,0.4)"
    return f"""
    <div style="position:absolute; right:0; top:0; bottom:0; width:48px; z-index:9;
                display:flex; align-items:center; justify-content:center;
                background:linear-gradient(to right, transparent, {bg});">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M9 6l6 6-6 6" stroke="{stroke}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    </div>
    """


def tag_label(texto, cor):
    return f'<span style="display:block; font-family:Familjen; font-size:11px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:{cor}; margin-bottom:16px;">{texto}</span>'


def check_item(titulo, texto, cor_check):
    return f"""
    <div style="display:flex; align-items:flex-start; gap:14px; padding:12px 0; border-bottom:1px solid {LIGHT_BORDER};">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex-shrink:0; margin-top:3px;">
            <path d="M4 12.5l5 5L20 6" stroke="{cor_check}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div>
            <div style="font-family:Familjen; font-size:14.5px; font-weight:700; color:{DARK_BG};">{titulo}</div>
            <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:2px; line-height:1.4;">{texto}</div>
        </div>
    </div>
    """


def numbered_step(numero, titulo, texto):
    return f"""
    <div style="display:flex; align-items:flex-start; gap:16px; padding:14px 0; border-bottom:1px solid {LIGHT_BORDER};">
        <span style="font-family:'JB Mono'; font-size:24px; font-weight:700; color:{BRAND_PRIMARY}; min-width:32px; line-height:1;">{numero}</span>
        <div>
            <div style="font-family:Familjen; font-size:14.5px; font-weight:700; color:{DARK_BG};">{titulo}</div>
            <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:2px; line-height:1.45; max-width:280px;">{texto}</div>
        </div>
    </div>
    """


def pill(texto, cor_texto, cor_fundo):
    return f'<span style="font-family:Familjen; font-size:11px; font-weight:600; padding:6px 14px; background:{cor_fundo}; border-radius:20px; color:{cor_texto};">{texto}</span>'


def logo_lockup(cor_texto, cor_circulo="#fff", cor_letra=None):
    cor_letra = cor_letra or BRAND_PRIMARY
    return f"""
    <div style="display:flex; align-items:center; gap:10px;">
        <div style="width:34px; height:34px; border-radius:50%; background:{cor_circulo};
                    display:flex; align-items:center; justify-content:center;">
            <span style="font-family:Familjen; font-weight:700; font-size:15px; color:{cor_letra};">cb</span>
        </div>
        <span style="font-family:Familjen; font-weight:700; font-size:15px; letter-spacing:-0.02em; color:{cor_texto};">cash-b</span>
    </div>
    """


def slide(bg, content_html, index, is_light, show_arrow=True, justify="flex-end"):
    arrow = swipe_arrow(is_light) if show_arrow else ""
    pad_bottom = "52px" if index < TOTAL - 1 or True else "36px"
    return f"""
    <div class="slide" style="background:{bg};">
        <div style="position:relative; flex:1; display:flex; flex-direction:column; justify-content:{justify};
                    padding:44px 36px {pad_bottom};">
            {content_html}
        </div>
        {arrow}
        {progress_bar(index, is_light)}
    </div>
    """


# ---------- Slide 1: Hero (LIGHT_BG) ----------
slide1 = slide(LIGHT_BG, f"""
{tag_label("cash-b explica", BRAND_PRIMARY)}
<div style="font-family:Familjen; font-size:34px; font-weight:700; line-height:1.14; letter-spacing:-0.03em; color:{DARK_BG};">
    Toda compra na Shopee gera cashback pra você.
</div>
<div style="font-family:Familjen; font-size:15px; color:{MUTED}; margin-top:16px; line-height:1.5; max-width:300px;">
    E a maioria das pessoas nem sabe disso.
</div>
""", 0, True, justify="center")

# ---------- Slide 2: Problem (DARK_BG) ----------
slide2 = slide(DARK_BG, f"""
{tag_label("o problema", "rgba(255,255,255,0.5)")}
<div style="font-family:Familjen; font-size:28px; font-weight:700; line-height:1.2; letter-spacing:-0.02em; color:#fff;">
    Toda vez que você compra, alguém ganha uma comissão.
</div>
<div style="font-family:Familjen; font-size:14px; color:rgba(255,255,255,0.65); margin-top:16px; line-height:1.55; max-width:310px;">
    A Shopee paga essa comissão pra quem te levou até o produto. Raramente ela volta pra quem realmente comprou.
</div>
""", 1, False)

# ---------- Slide 3: Solution (brand gradient) ----------
slide3 = slide(BRAND_GRADIENT, f"""
{tag_label("a solução", "rgba(255,255,255,0.75)")}
<div style="font-family:Familjen; font-size:30px; font-weight:700; line-height:1.18; letter-spacing:-0.02em; color:#fff;">
    O cash-b devolve essa comissão pra você.
</div>
<div style="font-family:Familjen; font-size:14.5px; color:rgba(255,255,255,0.88); margin-top:16px; line-height:1.55; max-width:300px;">
    Você compra do jeito que já compra na Shopee. A diferença é que parte do dinheiro cai de volta na sua conta, via PIX.
</div>
""", 2, False)

# ---------- Slide 4: Features (LIGHT_BG) ----------
slide4 = slide(LIGHT_BG, f"""
{tag_label("por que usar", BRAND_PRIMARY)}
<div style="font-family:Familjen; font-size:24px; font-weight:700; letter-spacing:-0.02em; color:{DARK_BG}; margin-bottom:8px;">
    Os benefícios, direto ao ponto
</div>
<div style="margin-top:12px;">
    {check_item("Cashback real", "Toda compra participante gera dinheiro de volta.", SUCCESS)}
    {check_item("Cadastro grátis", "Sem mensalidade, sem taxa escondida.", BRAND_PRIMARY)}
    {check_item("Saque via PIX", "Direto na sua conta, sem burocracia.", SUCCESS)}
    {check_item("Do seu jeito", "Você compra como sempre comprou na Shopee.", BRAND_PRIMARY)}
</div>
""", 3, True)

# ---------- Slide 5: Details (DARK_BG) ----------
slide5 = slide(DARK_BG, f"""
{tag_label("sem complicação", "rgba(255,255,255,0.5)")}
<div style="font-family:Familjen; font-size:30px; font-weight:700; line-height:1.18; letter-spacing:-0.02em; color:#fff;">
    Sem letra miúda.<br>Sem pegadinha.
</div>
<div style="font-family:Familjen; font-size:14px; color:rgba(255,255,255,0.7); margin-top:16px; line-height:1.5; max-width:300px;">
    Sem mensalidade. Sem taxa escondida. Você só ganha.
</div>
<div style="display:flex; gap:10px; margin-top:24px; flex-wrap:wrap;">
    {pill("Sem mensalidade", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
    {pill("Sem taxa", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
    {pill("Sem burocracia", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
</div>
""", 4, False)

# ---------- Slide 6: How-to (LIGHT_BG) ----------
slide6 = slide(LIGHT_BG, f"""
{tag_label("como funciona", BRAND_PRIMARY)}
<div style="font-family:Familjen; font-size:24px; font-weight:700; letter-spacing:-0.02em; color:{DARK_BG}; margin-bottom:4px;">
    3 passos e pronto
</div>
<div style="margin-top:14px;">
    {numbered_step("01", "Encontre o produto", 'Converta o link, acesse pela vitrine ou clique em "Ir pra Shopee".')}
    {numbered_step("02", "Compre normalmente", "Do jeito que você já compra, sem nada a mais.")}
    {numbered_step("03", "Receba cashback", "Depois que o pedido for validado, o dinheiro vai pro seu saldo liberado.")}
</div>
""", 5, True)

# ---------- Slide 7: CTA (brand gradient, sem seta) ----------
slide7 = slide(BRAND_GRADIENT, f"""
<div style="display:flex; justify-content:center; margin-bottom:28px;">
    {logo_lockup("#fff")}
</div>
<div style="font-family:Familjen; font-size:32px; font-weight:700; line-height:1.15; letter-spacing:-0.02em; color:#fff; text-align:center;">
    Bora começar?
</div>
<div style="font-family:Familjen; font-size:14.5px; color:rgba(255,255,255,0.88); margin-top:14px; line-height:1.5; text-align:center; max-width:290px; margin-left:auto; margin-right:auto;">
    Cadastro grátis. Compre na Shopee do jeito que já compra.
</div>
<div style="display:flex; justify-content:center; margin-top:28px;">
    <div style="display:inline-flex; align-items:center; padding:13px 30px; background:{LIGHT_BG};
                color:{BRAND_DARK}; font-family:Familjen; font-weight:700; font-size:14.5px; border-radius:28px;">
        cash-b.com
    </div>
</div>
""", 6, False, show_arrow=False, justify="center")

SLIDES = [slide1, slide2, slide3, slide4, slide5, slide6, slide7]

# ---------- Moldura de preview no estilo Instagram ----------
DOTS = "".join(
    f'<div class="ig-dot" data-i="{i}" style="width:6px; height:6px; border-radius:50%; '
    f'background:{"#111827" if i == 0 else "rgba(17,24,39,0.2)"}; transition:background .2s;"></div>'
    for i in range(TOTAL)
)

ACTION_ICONS = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 21s-7.5-4.6-10-9.3C.5 8 2.2 4.5 5.7 4c2.1-.3 4 .8 5 2.4C11.7 4.8 13.6 3.7 15.7 4c3.5.5 5.2 4 3.7 7.7C16.9 16.4 12 21 12 21z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 11.5a8.4 8.4 0 01-8.9 8.4 8.6 8.6 0 01-3.8-.9L3 20l1-5.3a8.4 8.4 0 1117-3.2z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
"""

HTML = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
{FONT_FACES}
* {{ box-sizing:border-box; }}
body {{
    margin:0; padding:48px 16px; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#efeef2; font-family:Familjen, Arial, sans-serif;
}}
.ig-frame {{
    width:420px; background:#fff; border-radius:16px; overflow:hidden;
    box-shadow:0 12px 40px rgba(17,24,39,0.16); border:1px solid #e5e7eb;
}}
.ig-header {{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-bottom:1px solid #f0f0f0; }}
.ig-avatar {{ width:34px; height:34px; border-radius:50%; background:{BRAND_PRIMARY}; display:flex; align-items:center; justify-content:center; }}
.ig-header-text .handle {{ font-size:13px; font-weight:700; color:#111827; }}
.ig-header-text .sub {{ font-size:11px; color:#8a8a8a; margin-top:1px; }}
.carousel-viewport {{ width:420px; height:525px; overflow:hidden; position:relative; cursor:grab; }}
.carousel-viewport.dragging {{ cursor:grabbing; }}
.carousel-track {{ display:flex; width:{420*TOTAL}px; height:525px; transition:transform .3s ease; }}
.slide {{ width:420px; height:525px; flex-shrink:0; position:relative; overflow:hidden; display:flex; flex-direction:column; }}
.ig-dots {{ display:flex; justify-content:center; gap:5px; padding:10px 0 4px; }}
.ig-actions {{ display:flex; align-items:center; gap:14px; padding:10px 14px 4px; }}
.ig-actions .spacer {{ flex:1; }}
.ig-caption {{ padding:6px 14px 16px; font-size:13px; line-height:1.5; color:#111827; }}
.ig-caption b {{ font-weight:700; }}
.ig-caption .time {{ display:block; margin-top:6px; font-size:11px; color:#a0a0a0; letter-spacing:0.03em; text-transform:uppercase; }}
</style>
</head>
<body>
<div class="ig-frame">
    <div class="ig-header">
        <div class="ig-avatar">
            <span style="font-family:Familjen; font-weight:700; font-size:14px; color:#fff;">cb</span>
        </div>
        <div class="ig-header-text">
            <div class="handle">cash.b</div>
            <div class="sub">Cashback pra suas compras na Shopee</div>
        </div>
    </div>
    <div class="carousel-viewport" id="viewport">
        <div class="carousel-track" id="track">
            {"".join(SLIDES)}
        </div>
    </div>
    <div class="ig-dots" id="dots">{DOTS}</div>
    <div class="ig-actions">
        {ACTION_ICONS}
        <div class="spacer"></div>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M6 4h12v17l-6-4-6 4V4z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
    </div>
    <div class="ig-caption">
        <b>cash.b</b> Os benefícios de usar o cash-b, direto ao ponto. Cadastro grátis, link na bio.
        <span class="time">2 horas atrás</span>
    </div>
</div>
<script>
const track = document.getElementById('track');
const viewport = document.getElementById('viewport');
const dots = [...document.querySelectorAll('.ig-dot')];
const SLIDE_W = 420, TOTAL = {TOTAL};
let current = 0, startX = 0, deltaX = 0, dragging = false;

function goTo(i) {{
    current = Math.max(0, Math.min(TOTAL - 1, i));
    track.style.transform = `translateX(${{-current * SLIDE_W}}px)`;
    dots.forEach((d, idx) => d.style.background = idx === current ? '#111827' : 'rgba(17,24,39,0.2)');
}}

viewport.addEventListener('pointerdown', e => {{
    dragging = true; startX = e.clientX; deltaX = 0;
    track.style.transition = 'none';
    viewport.classList.add('dragging');
    viewport.setPointerCapture(e.pointerId);
}});
viewport.addEventListener('pointermove', e => {{
    if (!dragging) return;
    deltaX = e.clientX - startX;
    track.style.transform = `translateX(${{-current * SLIDE_W + deltaX}}px)`;
}});
viewport.addEventListener('pointerup', () => {{
    dragging = false;
    track.style.transition = 'transform .3s ease';
    viewport.classList.remove('dragging');
    if (deltaX < -60) goTo(current + 1);
    else if (deltaX > 60) goTo(current - 1);
    else goTo(current);
}});
dots.forEach(d => d.addEventListener('click', () => goTo(parseInt(d.dataset.i))));
</script>
</body></html>
"""

preview_path = OUT_DIR / "preview.html"
preview_path.write_text(HTML, encoding="utf-8")
print("preview gerado:", preview_path)
