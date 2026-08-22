"""Base compartilhada dos carrosséis de Instagram da cash-b.

Nasceu de gerar_carrossel_beneficios.py: com mais de um carrossel, repetir as ~400
linhas de paleta, fontes embutidas, componentes de slide, moldura de preview e
exportação em cada arquivo ficaria impossível de manter (qualquer ajuste de marca
teria que ser refeito em N arquivos). Aqui fica tudo que é igual em todos; cada
carrossel só descreve o próprio conteúdo e chama gerar().

Paleta e fontes saem de static/css/brand.css e static/fonts - ver BRAND.md.
Regras de texto (a cash-b é substantivo feminino, cashback sempre afirmativo,
"pra" só quando é contração de para + a) estão em VOZ.md.
"""
import base64
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

# Paleta: tokens já existentes em static/css/brand.css, mais um roxo claro
# (BRAND_LIGHT) que o brand.css não tinha - só usado aqui pro sistema de
# tags/pills sobre fundo escuro.
BRAND_PRIMARY = "#6d28d9"
BRAND_LIGHT = "#a78bfa"
BRAND_DARK = "#4c1d95"
LIGHT_BG = "#f8fafc"
LIGHT_BORDER = "#e0dcef"
DARK_BG = "#111827"
SUCCESS = "#059669"
HIGHLIGHT = "#f59e0b"
MUTED = "#6b7280"

BRAND_GRADIENT = f"linear-gradient(165deg, {BRAND_DARK} 0%, {BRAND_PRIMARY} 55%, {BRAND_LIGHT} 100%)"

LARGURA_SLIDE = 420
ALTURA_SLIDE = 525

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


# ---------------------------------------------------------------- componentes


def tag_label(texto, cor):
    return (
        f'<span style="display:block; font-family:Familjen; font-size:11px; font-weight:700; '
        f'letter-spacing:2px; text-transform:uppercase; color:{cor}; margin-bottom:16px;">{texto}</span>'
    )


def titulo(texto, tamanho=30, cor="#fff"):
    return (
        f'<div style="font-family:Familjen; font-size:{tamanho}px; font-weight:700; line-height:1.16; '
        f'letter-spacing:-0.025em; color:{cor};">{texto}</div>'
    )


def subtitulo(texto, cor=MUTED, largura=310, tamanho=14.5):
    return (
        f'<div style="font-family:Familjen; font-size:{tamanho}px; color:{cor}; margin-top:16px; '
        f'line-height:1.55; max-width:{largura}px;">{texto}</div>'
    )


def check_item(titulo_item, texto, cor_check):
    """Item de lista com ícone de check. O ícone alinha com a linha do título e a
    descrição recua na mesma medida - sem isso, título de duas linhas desalinha tudo."""
    icone_largura, gap = 18, 14
    indent = icone_largura + gap
    return f"""
    <div style="padding:12px 0; border-bottom:1px solid {LIGHT_BORDER};">
        <div style="display:flex; align-items:center; gap:{gap}px;">
            <svg width="{icone_largura}" height="{icone_largura}" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;">
                <path d="M4 12.5l5 5L20 6" stroke="{cor_check}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span style="font-family:Familjen; font-size:14.5px; font-weight:700; color:{DARK_BG};">{titulo_item}</span>
        </div>
        <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:4px; margin-left:{indent}px; line-height:1.4;">{texto}</div>
    </div>
    """


def numbered_step(numero, titulo_item, texto):
    numero_largura, gap = 32, 16
    indent = numero_largura + gap
    return f"""
    <div style="padding:14px 0; border-bottom:1px solid {LIGHT_BORDER};">
        <div style="display:flex; align-items:center; gap:{gap}px;">
            <span style="font-family:'JB Mono'; font-size:24px; font-weight:700; color:{BRAND_PRIMARY}; min-width:{numero_largura}px; line-height:1;">{numero}</span>
            <span style="font-family:Familjen; font-size:14.5px; font-weight:700; color:{DARK_BG};">{titulo_item}</span>
        </div>
        <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:4px; margin-left:{indent}px; line-height:1.45; max-width:280px;">{texto}</div>
    </div>
    """


def linha_valor(rotulo, valor, cor_valor=SUCCESS, escuro=False):
    """Linha de tabela "rótulo à esquerda, número à direita" - usada nas escalas de
    valor (quanto você gasta -> quanto volta)."""
    cor_rotulo = "rgba(255,255,255,0.72)" if escuro else DARK_BG
    borda = "rgba(255,255,255,0.12)" if escuro else LIGHT_BORDER
    return f"""
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding:11px 0; border-bottom:1px solid {borda};">
        <span style="font-family:Familjen; font-size:14px; color:{cor_rotulo};">{rotulo}</span>
        <span style="font-family:'JB Mono'; font-size:16px; font-weight:700; color:{cor_valor};">{valor}</span>
    </div>
    """


def numero_gigante(valor, legenda, cor=HIGHLIGHT, cor_legenda="rgba(255,255,255,0.6)"):
    return f"""
    <div style="font-family:'JB Mono'; font-size:56px; font-weight:700; line-height:1; color:{cor}; letter-spacing:-0.03em;">{valor}</div>
    <div style="font-family:Familjen; font-size:14px; color:{cor_legenda}; margin-top:12px; line-height:1.5; max-width:300px;">{legenda}</div>
    """


def realce(texto):
    """Marca-texto no estilo da marca (equivalente ao .mark do brand.css). Usar no
    máximo uma vez por slide - o efeito só funciona enquanto for exceção."""
    return (
        f'<span style="background:{HIGHLIGHT}; color:{DARK_BG}; padding:0 0.1em; '
        f'border-radius:3px; box-decoration-break:clone; -webkit-box-decoration-break:clone;">{texto}</span>'
    )


def caso(situacao, resultado, escuro=False):
    """Bloco "situação -> resultado", para comparar cenários lado a lado (ex: comprar
    direto na Shopee x comprar pelo link de alguém)."""
    cor_situacao = "rgba(255,255,255,0.55)" if escuro else MUTED
    cor_resultado = "#fff" if escuro else DARK_BG
    borda = "rgba(255,255,255,0.12)" if escuro else LIGHT_BORDER
    return f"""
    <div style="padding:13px 0; border-bottom:1px solid {borda};">
        <div style="font-family:Familjen; font-size:12.5px; color:{cor_situacao}; line-height:1.4;">{situacao}</div>
        <div style="font-family:Familjen; font-size:15px; font-weight:700; color:{cor_resultado}; margin-top:4px; line-height:1.35;">{resultado}</div>
    </div>
    """


def destaque(texto, escuro=False, cor=HIGHLIGHT):
    """Caixa de destaque com barra colorida à esquerda. Para a informação que não pode
    passar batida - nota em cinza pequeno no rodapé do slide quase ninguém lê."""
    fundo = "rgba(245,158,11,0.16)" if escuro else "rgba(245,158,11,0.14)"
    cor_texto = "#fff" if escuro else DARK_BG
    return f"""
    <div style="margin-top:18px; padding:13px 16px; background:{fundo};
                border-left:3px solid {cor}; border-radius:6px; font-family:Familjen;
                font-size:13.5px; color:{cor_texto}; line-height:1.5;">
        {texto}
    </div>
    """


def fonte(texto, escuro=False):
    """Crédito da fonte, em corpo bem pequeno no pé do slide. Todo slide que mostra
    número de pesquisa externa leva um - dado sem origem é o tipo de coisa que
    derruba a confiança justamente em quem lê com atenção."""
    cor = "rgba(255,255,255,0.4)" if escuro else "rgba(17,24,39,0.35)"
    return (
        f'<div style="font-family:Familjen; font-size:9.5px; color:{cor}; margin-top:20px; '
        f'line-height:1.4; letter-spacing:0.01em;">{texto}</div>'
    )


def pill(texto, cor_texto, cor_fundo):
    return (
        f'<span style="font-family:Familjen; font-size:11px; font-weight:600; padding:6px 14px; '
        f'background:{cor_fundo}; border-radius:20px; color:{cor_texto};">{texto}</span>'
    )


def cta_pill(texto="cash-b.com"):
    return f"""
    <div style="display:flex; justify-content:center; margin-top:28px;">
        <div style="display:inline-flex; align-items:center; padding:13px 30px; background:{LIGHT_BG};
                    color:{BRAND_DARK}; font-family:Familjen; font-weight:700; font-size:14.5px; border-radius:28px;">
            {texto}
        </div>
    </div>
    """


# ------------------------------------------------------------------- moldura


def _progress_bar(index, total, is_light):
    pct = ((index + 1) / total) * 100
    track = "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.14)"
    fill = BRAND_PRIMARY if is_light else "#fff"
    label = "rgba(0,0,0,0.35)" if is_light else "rgba(255,255,255,0.45)"
    return f"""
    <div style="position:absolute; bottom:0; left:0; right:0; padding:16px 28px 20px; z-index:10;
                display:flex; align-items:center; gap:10px;">
        <div style="flex:1; height:3px; background:{track}; border-radius:2px; overflow:hidden;">
            <div style="height:100%; width:{pct}%; background:{fill}; border-radius:2px;"></div>
        </div>
        <span style="font-family:'JB Mono'; font-size:11px; color:{label}; font-weight:500;">{index+1}/{total}</span>
    </div>
    """


def _swipe_arrow(is_light):
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


# Recorte da grade do perfil no Instagram: a miniatura NÃO é o 4:5 inteiro. O app
# recorta primeiro um quadrado central e depois pega um 3:4 desse quadrado, o que come
# 138px de cada lado e 135px em cima/baixo de um PNG 1080x1350 - medido comparando a
# célula real da grade com o nosso slide, bate pixel a pixel (ver _simular_grade).
# Em coordenadas do slide (420x525) isso dá ~54px nas laterais e ~52px em cima/baixo.
# Só o primeiro slide aparece na grade, então só ele precisa dessa margem: usar isso
# em todos deixaria os internos apertados à toa, já que abertos eles aparecem inteiros.
PADDING_PADRAO = "44px 36px 52px"
PADDING_CAPA = "64px 70px 64px"


class Slide:
    """Um slide do carrossel. Guarda o conteúdo e o fundo; a numeração (barra de
    progresso e seta) é resolvida na hora de montar, quando o total já é conhecido.

    capa=True usa margens maiores, para o conteúdo sobreviver ao recorte da grade do
    perfil - ver PADDING_CAPA acima."""

    def __init__(self, bg, conteudo, is_light, justify="center", seta=True, capa=False):
        self.bg = bg
        self.conteudo = conteudo
        self.is_light = is_light
        self.justify = justify
        self.seta = seta
        self.capa = capa

    def render(self, index, total):
        arrow = _swipe_arrow(self.is_light) if self.seta else ""
        padding = PADDING_CAPA if self.capa else PADDING_PADRAO
        return f"""
        <div class="slide" style="background:{self.bg};">
            <div style="position:relative; flex:1; display:flex; flex-direction:column; justify-content:{self.justify};
                        padding:{padding};">
                {self.conteudo}
            </div>
            {arrow}
            {_progress_bar(index, total, self.is_light)}
        </div>
        """


ACTION_ICONS = """
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 21s-7.5-4.6-10-9.3C.5 8 2.2 4.5 5.7 4c2.1-.3 4 .8 5 2.4C11.7 4.8 13.6 3.7 15.7 4c3.5.5 5.2 4 3.7 7.7C16.9 16.4 12 21 12 21z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 11.5a8.4 8.4 0 01-8.9 8.4 8.6 8.6 0 01-3.8-.9L3 20l1-5.3a8.4 8.4 0 1117-3.2z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
"""


def _montar_html(slides, legenda):
    total = len(slides)
    # HTML engole quebra de linha; sem isso a legenda com hashtags e chamada aparece
    # tudo grudado no preview, diferente de como o Instagram vai mostrar.
    legenda = legenda.strip().replace("\n", "<br>")
    corpo = "".join(s.render(i, total) for i, s in enumerate(slides))
    dots = "".join(
        f'<div class="ig-dot" data-i="{i}" style="width:6px; height:6px; border-radius:50%; '
        f'background:{"#111827" if i == 0 else "rgba(17,24,39,0.2)"}; transition:background .2s;"></div>'
        for i in range(total)
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
{FONT_FACES}
* {{ box-sizing:border-box; }}
html {{ overflow-x:hidden; }}
body {{
    margin:0; padding:24px 12px; min-height:100vh; display:flex; align-items:flex-start; justify-content:center;
    background:#efeef2; font-family:Familjen, Arial, sans-serif; overflow-x:hidden;
}}
.frame-wrap {{ position:relative; }}
.ig-frame {{
    width:{LARGURA_SLIDE}px; background:#fff; border-radius:16px; overflow:hidden;
    box-shadow:0 12px 40px rgba(17,24,39,0.16); border:1px solid #e5e7eb;
    transform-origin: top left;
}}
.ig-header {{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-bottom:1px solid #f0f0f0; }}
.ig-avatar {{ width:34px; height:34px; border-radius:50%; background:{BRAND_PRIMARY}; display:flex; align-items:center; justify-content:center; }}
.ig-header-text .handle {{ font-size:13px; font-weight:700; color:#111827; }}
.ig-header-text .sub {{ font-size:11px; color:#8a8a8a; margin-top:1px; }}
.carousel-viewport {{ width:{LARGURA_SLIDE}px; height:{ALTURA_SLIDE}px; overflow:hidden; position:relative; cursor:grab; }}
.carousel-viewport.dragging {{ cursor:grabbing; }}
.carousel-track {{ display:flex; width:{LARGURA_SLIDE*total}px; height:{ALTURA_SLIDE}px; transition:transform .3s ease; }}
.slide {{ width:{LARGURA_SLIDE}px; height:{ALTURA_SLIDE}px; flex-shrink:0; position:relative; overflow:hidden; display:flex; flex-direction:column; }}
.ig-dots {{ display:flex; justify-content:center; gap:5px; padding:10px 0 4px; }}
.ig-actions {{ display:flex; align-items:center; gap:14px; padding:10px 14px 4px; }}
.ig-actions .spacer {{ flex:1; }}
.ig-caption {{ padding:6px 14px 16px; font-size:13px; line-height:1.5; color:#111827; }}
.ig-caption b {{ font-weight:700; }}
.ig-caption .time {{ display:block; margin-top:6px; font-size:11px; color:#a0a0a0; letter-spacing:0.03em; text-transform:uppercase; }}
</style>
</head>
<body>
<div class="frame-wrap" id="frameWrap">
<div class="ig-frame" id="igFrame">
    <div class="ig-header">
        <div class="ig-avatar">
            <span style="font-family:Familjen; font-weight:700; font-size:14px; color:#fff;">cb</span>
        </div>
        <div class="ig-header-text">
            <div class="handle">usecashb</div>
            <div class="sub">Cashback para suas compras na Shopee</div>
        </div>
    </div>
    <div class="carousel-viewport" id="viewport">
        <div class="carousel-track" id="track">{corpo}</div>
    </div>
    <div class="ig-dots" id="dots">{dots}</div>
    <div class="ig-actions">
        {ACTION_ICONS}
        <div class="spacer"></div>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M6 4h12v17l-6-4-6 4V4z" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>
    </div>
    <div class="ig-caption">
        <b>usecashb</b> {legenda}
        <span class="time">2 horas atrás</span>
    </div>
</div>
</div>
<script>
const track = document.getElementById('track');
const viewport = document.getElementById('viewport');
const dots = [...document.querySelectorAll('.ig-dot')];
const SLIDE_W = {LARGURA_SLIDE}, TOTAL = {total};
let current = 0, startX = 0, deltaX = 0, dragging = false;

// Em telas estreitas (celular), escala o quadro pra caber sem cortar nem precisar
// rolar de lado - transform:scale (não zoom) pra não afetar a quebra de linha do
// texto, só o tamanho visual.
const frameWrap = document.getElementById('frameWrap');
const igFrame = document.getElementById('igFrame');
function ajustarEscala() {{
    const larguraDisponivel = window.innerWidth - 24;
    const escala = Math.min(1, larguraDisponivel / SLIDE_W);
    igFrame.style.transform = `scale(${{escala}})`;
    frameWrap.style.width = (SLIDE_W * escala) + 'px';
    frameWrap.style.height = (igFrame.offsetHeight * escala) + 'px';
}}
ajustarEscala();
window.addEventListener('resize', ajustarEscala);

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


def _exportar(preview_path, out_dir, total):
    """Exporta cada slide como PNG 1080x1350 (4:5), a resolução padrão de carrossel
    do Instagram."""
    from playwright.sync_api import sync_playwright

    escala = 1080 / LARGURA_SLIDE
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        # viewport da página bem maior que o quadro: o cartão inteiro (cabeçalho +
        # carrossel + rodapé) é mais alto que só o slide, e precisa caber todo na
        # área visível pra recortar certo com clip=
        page = browser.new_page(viewport={"width": 500, "height": 1000}, device_scale_factor=escala)
        page.goto(f"file://{preview_path}")
        page.wait_for_timeout(300)
        # desliga o ajuste de escala pra celular (que travou frameWrap num tamanho
        # calculado pro innerWidth do carregamento) e a transição de swipe, pra
        # exportar no tamanho real e sem animação no meio do print
        page.evaluate("""
            igFrame.style.transform = 'none';
            frameWrap.style.width = '';
            frameWrap.style.height = '';
            track.style.transition = 'none';
        """)
        page.wait_for_timeout(50)
        box = page.query_selector("#viewport").bounding_box()

        for i in range(total):
            page.evaluate(f"goTo({i})")
            page.wait_for_timeout(150)
            destino = out_dir / f"slide_{i+1}.png"
            page.screenshot(path=str(destino), clip=box)
            print("  exportado:", destino.name)

        browser.close()


def _simular_grade(out_dir):
    """Gera grade.png: como o slide 1 aparece na grade do perfil, já recortado.

    Existe porque o recorte só dava para conferir postando de verdade e olhando no
    celular - agora dá para ver antes. Reproduz o recorte medido: quadrado central,
    depois 3:4 dele."""
    from PIL import Image

    capa = Image.open(out_dir / "slide_1.png")
    largura, altura = capa.size
    lado = min(largura, altura)
    topo = (altura - lado) // 2
    quadrado = capa.crop((0, topo, largura, topo + lado))

    largura_3x4 = int(quadrado.height * 3 / 4)
    esquerda = (quadrado.width - largura_3x4) // 2
    recorte = quadrado.crop((esquerda, 0, esquerda + largura_3x4, quadrado.height))

    destino = out_dir / "grade.png"
    recorte.save(destino)
    print("  grade simulada:", destino.name)


def gerar(nome_pasta, slides, legenda, exportar=False):
    """Escreve o preview HTML, a legenda em texto e, com exportar=True, os PNGs.

    A legenda vai para legenda.txt na mesma pasta dos slides de propósito: na hora de
    postar, tudo que o post precisa está junto, sem ter que abrir o script e caçar a
    variável. Todo carrossel novo já nasce com esse arquivo."""
    out_dir = Path(__file__).resolve().parent / nome_pasta
    out_dir.mkdir(exist_ok=True)

    preview_path = out_dir / "preview.html"
    preview_path.write_text(_montar_html(slides, legenda), encoding="utf-8")
    print("preview gerado:", preview_path.relative_to(REPO_ROOT))

    legenda_path = out_dir / "legenda.txt"
    legenda_path.write_text(legenda.strip() + "\n", encoding="utf-8")
    print("legenda gerada:", legenda_path.relative_to(REPO_ROOT))

    if exportar:
        _exportar(preview_path, out_dir, len(slides))
        _simular_grade(out_dir)
    return preview_path
