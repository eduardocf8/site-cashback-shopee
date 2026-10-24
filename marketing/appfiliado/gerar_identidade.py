"""Identidade visual do Appfiliado para redes sociais e materiais (SVG + PNG + manual em PDF).

Uso (na raiz do repositório, com Playwright, Chromium, fonttools e uharfbuzz instalados):
    python3 marketing/appfiliado/gerar_identidade.py

Sai em marketing/appfiliado/identidade/ (logo/, redes-sociais/, destaques/, paleta/,
appfiliado-identidade-visual.pdf e o .zip com tudo). Cores, símbolo e nome são os do painel
(painel/static/painel/painel.css e painel/templates/painel/_logo.html). O nome "Appfiliado"
vai em contorno vetorial (DM Sans 800), então os SVGs não dependem de fonte instalada; as
fontes ficam em identidade/fontes/ para quem for editar em Canva, Figma etc."""

import html
import shutil
import zipfile
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent / "identidade"
FONTES = RAIZ / "fontes"

VERDE, VERDE_2, VERDE_3, CREME, AMARELO, TINTA, SUAVE = "#1F3A2E", "#2D4B3D", "#17301F", "#F6F3EA", "#F2C230", "#1D2A23", "#AFC1B5"
CORES = [("Verde Appfiliado", "verde", VERDE, "Fundo principal, texto sobre creme"),
         ("Amarelo", "amarelo", AMARELO, "Símbolo, destaques e botões"),
         ("Creme", "creme", CREME, "Fundo claro e texto sobre verde"),
         ("Verde profundo", "verde-profundo", VERDE_2, "Degradês e blocos sobre o verde"),
         ("Tinta", "tinta", TINTA, "Texto corrido"),
         ("Verde claro", "verde-claro", SUAVE, "Textos de apoio sobre verde")]

# Os mesmos ícones do menu do painel (painel/modulos.py), em grade de 24.
ICONES = {
    "Bot de WhatsApp": "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z",
    "Meu site": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "Carrosséis": "M7 5h10v14H7zM3 7v10M21 7v10",
    "Notas": "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
    "Radar": "M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4",
    "Conversor": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
}


class Fonte:
    """Texto em contorno: shaping do HarfBuzz (kerning e ligaduras) + glifos do fontTools."""

    def __init__(self, caminho):
        self.ttf = TTFont(str(caminho))
        self.glifos = self.ttf.getGlyphSet()
        self.ordem = self.ttf.getGlyphOrder()
        self.upem = self.ttf["head"].unitsPerEm
        self.hb_fonte = hb.Font(hb.Face(hb.Blob.from_file_path(str(caminho))))
        self.altura_x = self.ttf["OS/2"].sxHeight
        self.altura_maiuscula = self.ttf["OS/2"].sCapHeight

    def caminho(self, texto, tamanho, x=0, base=0, espaco=0.0):
        """(d, largura) do texto com a linha de base em y=base; `espaco` em em, como o letter-spacing."""
        buf = hb.Buffer()
        buf.add_str(texto)
        buf.guess_segment_properties()
        hb.shape(self.hb_fonte, buf)
        escala, cursor, partes = tamanho / self.upem, 0.0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            caneta = SVGPathPen(self.glifos)
            self.glifos[self.ordem[info.codepoint]].draw(caneta)
            if caneta.getCommands():
                partes.append(f'<path transform="translate({x + (cursor + pos.x_offset) * escala:.2f} {base:.2f}) '
                              f'scale({escala:.5f} {-escala:.5f})" d="{caneta.getCommands()}"/>')
            cursor += pos.x_advance + espaco * self.upem
        return "".join(partes), (cursor - espaco * self.upem) * escala


NEGRITO = Fonte(FONTES / "dmsans-800.ttf")
MEDIA = Fonte(FONTES / "dmsans-500.ttf")


def simbolo(x, y, tamanho, cor, ponto=None):
    """O símbolo (anel com haste) numa caixa tamanho x tamanho, no mesmo desenho do painel (grade 36)."""
    e = tamanho / 36
    return (f'<g transform="translate({x - 3 * e:.3f} {y - 8.25 * e:.3f}) scale({e:.5f})" fill="none" stroke="{cor}" stroke-width="5" '
            f'stroke-linecap="round"><circle cx="21" cy="26" r="9.5"/><path d="M30.5 16.5V36"/>'
            f'<circle cx="21" cy="26" r="3.6" fill="{ponto or cor}" stroke="none"/></g>')


def ladrilho(x, y, lado, fundo, cor):
    """Símbolo dentro do quadrado arredondado, do mesmo tamanho do painel e do favicon: a caixa
    de 36 unidades do símbolo é o próprio quadrado, e o "a" ocupa uns 68% dele (commit bfe4fa7)."""
    return (f'<rect x="{x}" y="{y}" width="{lado}" height="{lado}" rx="{lado * 0.25}" fill="{fundo}"/>'
            + simbolo(x, y, lado, cor))


def logo_horizontal(x, y, altura, fundo_tile, cor_tile, cor_texto, assinatura=None, cor_assinatura=None):
    """Ladrilho + nome (+ 'Para afiliados Shopee' embaixo do nome). Devolve (svg, largura)."""
    nome_tam = altura * 0.58
    desloca = altura * 0.30
    cortes = ""
    if assinatura:
        nome_tam = altura * 0.46
    d, larg = NEGRITO.caminho("Appfiliado", nome_tam, x + altura + desloca, 0, espaco=-0.01)
    if assinatura:
        base_nome = y + altura * 0.5
        d, larg = NEGRITO.caminho("Appfiliado", nome_tam, x + altura + desloca, base_nome, espaco=-0.01)
        d2, larg2 = MEDIA.caminho(assinatura, altura * 0.24, x + altura + desloca, base_nome + altura * 0.27)
        cortes = f'<g fill="{cor_assinatura or cor_texto}">{d2}</g>'
        larg = max(larg, larg2)
    else:
        base = y + altura / 2 + NEGRITO.altura_x * (nome_tam / NEGRITO.upem) / 2
        d, larg = NEGRITO.caminho("Appfiliado", nome_tam, x + altura + desloca, base, espaco=-0.01)
    svg = ladrilho(x, y, altura, fundo_tile, cor_tile) + f'<g fill="{cor_texto}">{d}</g>' + cortes
    return svg, altura + desloca + larg


def documento(largura, altura, miolo, fundo=None, defs=""):
    plano = f'<rect width="{largura}" height="{altura}" fill="{fundo}"/>' if fundo else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}">'
            f'<defs>{defs}</defs>{plano}{miolo}</svg>')


FUNDO_DEGRADE = (f'<radialGradient id="g" cx="0.85" cy="0.12" r="1.05"><stop offset="0" stop-color="{VERDE_2}"/>'
                 f'<stop offset="0.46" stop-color="{VERDE}"/><stop offset="1" stop-color="{VERDE_3}"/></radialGradient>')


def fundo_verde(w, h):
    """O mesmo fundo das artes de produto: degradê verde com um anel amarelo apagado no canto."""
    lado = max(w, h)
    anel = (f'<circle cx="{w + lado * 0.04:.0f}" cy="{h + lado * 0.04:.0f}" r="{lado * 0.27:.0f}" fill="none" '
            f'stroke="{AMARELO}" stroke-opacity="0.08" stroke-width="{lado * 0.125:.0f}"/>')
    return f'<rect width="{w}" height="{h}" fill="url(#g)"/>{anel}'


def centralizado(w, h, largura_logo, altura_logo_svg):
    return (w - largura_logo) / 2, (h - altura_logo_svg) / 2


# ---------------------------------------------------------------- peças

def pecas_logo():
    saida = {}
    # Símbolo sozinho (para quem precisa do símbolo sem o ladrilho)
    for nome, cor in (("verde", VERDE), ("amarelo", AMARELO), ("creme", CREME), ("branco", "#FFFFFF")):
        saida[f"logo/simbolo-{nome}"] = documento(512, 512, simbolo(56, 56, 400, cor))
    # Ladrilho do app: o ícone do painel, para avatar, favicon e perfis
    saida["logo/icone-amarelo"] = documento(512, 512, ladrilho(0, 0, 512, AMARELO, VERDE))
    saida["logo/icone-verde"] = documento(512, 512, ladrilho(0, 0, 512, VERDE, AMARELO))
    saida["logo/icone-creme"] = documento(512, 512, ladrilho(0, 0, 512, CREME, VERDE))
    # Logotipo horizontal em quatro versões
    versoes = [("sobre-claro", AMARELO, VERDE, VERDE, None), ("sobre-verde", AMARELO, VERDE, CREME, None),
               ("verde-unico", VERDE, CREME, VERDE, None), ("branco-unico", "#FFFFFF", VERDE, "#FFFFFF", None)]
    for nome, tile, cor_t, texto, fundo in versoes:
        svg, larg = logo_horizontal(40, 40, 160, tile, cor_t, texto)
        saida[f"logo/logotipo-{nome}"] = documento(int(larg) + 80, 240, svg)
        sig, larg2 = logo_horizontal(40, 40, 160, tile, cor_t, texto, assinatura="Para afiliados Shopee",
                                     cor_assinatura=SUAVE if texto == CREME else (texto if texto == "#FFFFFF" else "#5C6A61"))
        saida[f"logo/logotipo-assinatura-{nome}"] = documento(int(larg2) + 80, 240, sig)
    return saida


def logo_centro(w, h, altura, assinatura=None, cor_texto=CREME, cor_ass=SUAVE):
    svg, larg = logo_horizontal(0, 0, altura, AMARELO, VERDE, cor_texto, assinatura=assinatura, cor_assinatura=cor_ass)
    x, y = centralizado(w, h, larg, altura)
    return f'<g transform="translate({x:.1f} {y:.1f})">{svg}</g>'


def linha_de_texto(fonte, texto, tamanho, cor, w, y, espaco=0.0):
    d, larg = fonte.caminho(texto, tamanho, (w - 0) / 2, y, espaco)
    d, larg = fonte.caminho(texto, tamanho, (w - larg) / 2, y, espaco)
    return f'<g fill="{cor}">{d}</g>'


def capa(w, h, altura_logo, frase=None, deslocamento=0):
    meio = logo_centro(w, h, altura_logo, cor_texto=CREME)
    extra = ""
    if frase:
        extra = linha_de_texto(MEDIA, frase, altura_logo * 0.25, SUAVE, w, h / 2 + altura_logo * 0.78 + deslocamento)
        meio = f'<g transform="translate(0 {-altura_logo * 0.12:.1f})">{meio}</g>' + f'<g transform="translate(0 {-altura_logo * 0.12:.1f})">{extra}</g>'
    return documento(w, h, fundo_verde(w, h) + meio, defs=FUNDO_DEGRADE)


def pecas_redes():
    f = "redes-sociais/"
    saida = {}
    # Avatares: o ícone sozinho. Redes cortam em círculo, então o símbolo fica na área central.
    saida[f + "avatar-amarelo-1080"] = documento(1080, 1080, ladrilho(0, 0, 1080, AMARELO, VERDE))
    saida[f + "avatar-verde-1080"] = documento(1080, 1080, f'<rect width="1080" height="1080" fill="{VERDE}"/>'
                                               + simbolo(180, 180, 720, AMARELO))
    saida[f + "avatar-amarelo-redondo-1080"] = documento(
        1080, 1080, f'<rect width="1080" height="1080" fill="{AMARELO}"/>' + simbolo(180, 180, 720, VERDE))
    # Capas: o logotipo fica dentro da área segura de cada rede
    saida[f + "capa-youtube-2560x1440"] = capa(2560, 1440, 230, "Para afiliados Shopee")
    saida[f + "capa-facebook-1640x624"] = capa(1640, 624, 150, "Para afiliados Shopee")
    saida[f + "capa-linkedin-1584x396"] = capa(1584, 396, 120)
    saida[f + "capa-x-1500x500"] = capa(1500, 500, 130, "Para afiliados Shopee")
    saida[f + "capa-grupo-whatsapp-1080x1080"] = capa(1080, 1080, 130, "Para afiliados Shopee")
    saida[f + "imagem-de-compartilhamento-1200x630"] = capa(1200, 630, 150, "Para afiliados Shopee")
    # Fundos para post e story, com o logotipo discreto no rodapé
    for nome, w, h in (("post-quadrado-1080x1080", 1080, 1080), ("post-retrato-1080x1350", 1080, 1350),
                       ("story-1080x1920", 1080, 1920)):
        logo, larg = logo_horizontal(0, 0, 76, AMARELO, VERDE, CREME)
        y = h - (250 if h == 1920 else 130)
        saida[f + nome] = documento(w, h, fundo_verde(w, h) + f'<g transform="translate({(w - larg) / 2:.1f} {y})">{logo}</g>',
                                    defs=FUNDO_DEGRADE)
    return saida


def pecas_destaques():
    """Capas dos destaques do Instagram (1080x1920; o círculo central de cerca de 600 px é o que aparece)."""
    saida = {}
    for nome, caminho in ICONES.items():
        icone = (f'<circle cx="540" cy="860" r="300" fill="rgba(246,243,234,0.10)" stroke="rgba(246,243,234,0.16)" stroke-width="6"/>'
                 f'<g transform="translate({540 - 12 * 14:.0f} {860 - 12 * 14:.0f}) scale(14)" fill="none" stroke="{AMARELO}" '
                 f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="{caminho}"/></g>')
        saida[f"destaques/destaque-{nome.lower().replace(' ', '-').replace('é', 'e').replace('ó', 'o')}"] = documento(
            1080, 1920, fundo_verde(1080, 1920) + icone, defs=FUNDO_DEGRADE)
    return saida


def pecas_paleta():
    cartoes, x = "", 0
    larg_c, alt_c, gap = 360, 520, 24
    for i, (nome, _, hexa, uso) in enumerate(CORES):
        px = 60 + i * (larg_c + gap)
        escuro = hexa in (VERDE, VERDE_2, TINTA)
        cartoes += (f'<rect x="{px}" y="60" width="{larg_c}" height="{alt_c}" rx="28" fill="{hexa}" stroke="#D3CCB4" stroke-width="2"/>'
                    f'<g fill="{CREME if escuro else TINTA}">{NEGRITO.caminho(nome, 34, px + 32, 60 + alt_c - 118)[0]}'
                    f'{MEDIA.caminho(hexa, 30, px + 32, 60 + alt_c - 72)[0]}</g>')
    w = 60 + len(CORES) * (larg_c + gap)
    return {"paleta/paleta-appfiliado": documento(w, 640, cartoes, fundo="#FFFFFF")}


# ---------------------------------------------------------------- saída

def rasterizar(svgs):
    from playwright.sync_api import Error
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for caminho, svg in svgs.items():
            largura = int(svg.split('width="')[1].split('"')[0])
            altura = int(svg.split('height="')[1].split('"')[0])
            pagina = navegador.new_page(viewport={"width": largura, "height": altura})
            pagina.set_content(f'<body style="margin:0;background:transparent">{svg}</body>')
            pagina.screenshot(path=str(RAIZ / f"{caminho}.png"), omit_background=True)
            pagina.close()
        navegador.close()


def manual():
    """Página única do manual em PDF: logotipo, ícone, cores, fontes e uso."""
    logo_claro, _ = logo_horizontal(0, 0, 120, AMARELO, VERDE, VERDE)
    logo_escuro, _ = logo_horizontal(0, 0, 120, AMARELO, VERDE, CREME)
    paleta = "".join(
        f'<div class="cor"><i style="background:{hexa}"></i><b>{nome}</b><span>{hexa}</span><small>{uso}</small></div>'
        for nome, _, hexa, uso in CORES)
    fonte_b = FONTES / "dmsans-800.ttf"
    import base64
    b64 = lambda p: base64.b64encode(p.read_bytes()).decode()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family:"DM"; src:url(data:font/ttf;base64,{b64(FONTES / 'dmsans-500.ttf')}); font-weight:500; }}
@font-face {{ font-family:"DM"; src:url(data:font/ttf;base64,{b64(fonte_b)}); font-weight:800; }}
@page {{ size:A4; margin:0 }} * {{ box-sizing:border-box; margin:0 }}
body {{ font-family:"DM",Arial,sans-serif; font-weight:500; color:{TINTA}; background:{CREME}; width:210mm; }}
.pg {{ height:297mm; padding:18mm 16mm; page-break-after:always; position:relative; overflow:hidden }}
.pg.verde {{ background:{VERDE}; color:{CREME} }}
h1 {{ font-weight:800; font-size:34pt; letter-spacing:-.02em; line-height:1.05; margin:10mm 0 4mm }}
h2 {{ font-weight:800; font-size:17pt; letter-spacing:-.01em; margin:11mm 0 4mm }}
p {{ font-size:11pt; line-height:1.5; max-width:150mm }} small {{ color:#5C6A61 }}
.verde small {{ color:{SUAVE} }}
.cartao {{ border-radius:5mm; padding:9mm; display:flex; align-items:center; justify-content:center; border:.4mm solid #D3CCB4; margin-top:4mm }}
.par {{ display:grid; grid-template-columns:1fr 1fr; gap:4mm }}
.cores {{ display:grid; grid-template-columns:repeat(3,1fr); gap:4mm; margin-top:4mm }}
.cor {{ display:flex; flex-direction:column; gap:1.4mm; font-size:10pt }} .cor i {{ height:24mm; border-radius:4mm; border:.4mm solid #D3CCB4; display:block; margin-bottom:1mm }}
.cor b {{ font-weight:800 }} .cor small {{ font-size:8.5pt }}
ul {{ margin:3mm 0 0 5mm; font-size:11pt; line-height:1.7 }}
.amostra {{ font-weight:800; font-size:48pt; letter-spacing:-.02em; line-height:1 }}
</style></head><body>
<div class="pg verde"><div style="margin-top:70mm">
<svg viewBox="0 0 640 170" width="130mm">{logo_horizontal(0,10,150,AMARELO,VERDE,CREME,assinatura='Para afiliados Shopee',cor_assinatura=SUAVE)[0]}</svg>
<h1>Identidade visual</h1><p style="color:{SUAVE}">Logotipo, ícone, cores e fontes do Appfiliado para redes sociais, anúncios e materiais.</p></div></div>
<div class="pg"><h2 style="margin-top:0">Logotipo</h2>
<p>O logotipo é o ícone (anel com haste) ao lado do nome <b>Appfiliado</b>, escrito junto, com A maiúsculo e o resto em minúsculas. A assinatura "Para afiliados Shopee" é opcional.</p>
<div class="par"><div class="cartao" style="background:{CREME}"><svg viewBox="0 0 660 120" width="100%">{logo_claro}</svg></div>
<div class="cartao" style="background:{VERDE}"><svg viewBox="0 0 660 120" width="100%">{logo_escuro}</svg></div></div>
<h2>Ícone</h2><p>Use o ícone sozinho onde o nome não cabe: foto de perfil, favicon e destaques. Mantenha o símbolo sempre dentro do quadrado arredondado ou sobre fundo liso verde ou amarelo.</p>
<div class="par"><div class="cartao" style="background:#fff"><svg viewBox="0 0 140 140" width="40mm">{ladrilho(0,0,140,AMARELO,VERDE)}</svg></div>
<div class="cartao" style="background:#fff"><svg viewBox="0 0 140 140" width="40mm">{ladrilho(0,0,140,VERDE,AMARELO)}</svg></div></div>
<h2>Respiro e tamanho mínimo</h2><ul><li>Deixe em volta do logotipo uma folga igual à altura do ícone dividida por quatro.</li>
<li>Logotipo horizontal: nunca menos de 90 px de largura na tela ou 25 mm impresso.</li>
<li>Não estique, não gire, não troque as cores do ícone e não coloque sobre fotos sem uma camada escura.</li></ul></div>
<div class="pg"><h2 style="margin-top:0">Cores</h2><div class="cores">{paleta}</div>
<p style="margin-top:8mm">O verde e o creme sustentam quase tudo. O amarelo é o destaque: ícone, botão, selo e uma palavra-chave por peça. Evite usar o amarelo como fundo de textos longos.</p>
<h2>Fonte</h2><div class="amostra">DM Sans</div><p style="margin-top:3mm">Títulos e o nome da marca em <b style="font-weight:800">DM Sans ExtraBold (800)</b>, textos em <b>DM Sans Medium (500)</b>. Gratuita (licença OFL) no Google Fonts; os arquivos vêm na pasta <b>fontes</b>.</p>
<h2>Arquivos deste kit</h2><ul><li><b>logo/</b> — ícone e logotipo em SVG (vetor) e PNG com fundo transparente.</li>
<li><b>redes-sociais/</b> — avatares, capas (YouTube, Facebook, LinkedIn, X, grupo do WhatsApp), imagem de compartilhamento, fundos de post e story.</li>
<li><b>destaques/</b> — capas dos destaques do Instagram com os ícones dos módulos.</li>
<li><b>paleta/</b> — as cores em imagem; <b>fontes/</b> — DM Sans.</li></ul></div>
</body></html>"""


def main():
    for pasta in ("logo", "redes-sociais", "destaques", "paleta"):
        shutil.rmtree(RAIZ / pasta, ignore_errors=True)
        (RAIZ / pasta).mkdir(parents=True)
    pecas = {**pecas_logo(), **pecas_redes(), **pecas_destaques(), **pecas_paleta()}
    for caminho, svg in pecas.items():
        if caminho.startswith(("logo/", "paleta/")):
            (RAIZ / f"{caminho}.svg").write_text(svg, encoding="utf-8")
    rasterizar(pecas)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page()
        pagina.set_content(manual())
        pagina.pdf(path=str(RAIZ / "appfiliado-identidade-visual.pdf"), prefer_css_page_size=True, print_background=True)
        navegador.close()
    zip_path = RAIZ.parent / "appfiliado-identidade-visual.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for arquivo in sorted(RAIZ.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(RAIZ))
    print(f"{len(pecas)} peças em {RAIZ}; kit: {zip_path}")


if __name__ == "__main__":
    main()
