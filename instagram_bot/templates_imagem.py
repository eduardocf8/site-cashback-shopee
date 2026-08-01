"""Geração de imagens do bot via Pillow (mais leve que o Playwright usado nas
artes de semeadura - ver marketing/instagram/gerar_posts_semeadura.py -, mais
adequado pra rodar dentro do processo web no plano gratuito da Render).

Reaproveita as mesmas cores/fontes de static/css/brand.css e static/fonts/.
"""
import io
from pathlib import Path

import requests
from PIL import Image, ImageColor, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN = FONT_DIR / "familjen-grotesk.woff2"
JB_MONO = FONT_DIR / "jetbrains-mono.woff2"

CORES = {
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


def _fonte(tamanho: int, mono: bool = False, negrito: bool = False) -> ImageFont.FreeTypeFont:
    """Familjen Grotesk e JetBrains Mono são fontes variáveis (eixo Weight) - o peso
    padrão é Regular (400), então negrito precisa ser selecionado explicitamente."""
    fonte = ImageFont.truetype(str(JB_MONO if mono else FAMILJEN), tamanho)
    if negrito:
        fonte.set_variation_by_name("Bold")
    return fonte


def _quebrar_texto(draw: ImageDraw.ImageDraw, texto: str, fonte, largura_max: int) -> list[str]:
    palavras = texto.split()
    linhas, linha_atual = [], ""
    for palavra in palavras:
        candidata = f"{linha_atual} {palavra}".strip()
        if draw.textlength(candidata, font=fonte) <= largura_max:
            linha_atual = candidata
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def _desenhar_bloco_texto(draw, linhas, fonte, x, y, cor, espacamento=1.25):
    altura_linha = int(fonte.size * espacamento)
    for i, linha in enumerate(linhas):
        draw.text((x, y + i * altura_linha), linha, font=fonte, fill=cor)
    return y + len(linhas) * altura_linha


def _badge_marca(draw, tamanho_canvas, cor, margem=88):
    fonte = _fonte(30, negrito=True)
    draw.text((margem, tamanho_canvas[1] - margem - 30), "cash-b", font=fonte, fill=cor)


def _rounded_mask(size, raio):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), size], radius=raio, fill=255)
    return mask


def _baixar_imagem(url: str, timeout: int = 8):
    try:
        resposta = requests.get(url, timeout=timeout)
        resposta.raise_for_status()
        return Image.open(io.BytesIO(resposta.content)).convert("RGB")
    except Exception:
        return None


def _misturar_cor(cor_a: str, cor_b: str, t: float) -> tuple[int, int, int]:
    """Interpola entre duas cores hex (t=0 -> cor_a, t=1 -> cor_b). Usado pra criar um
    tom bem sutil da própria paleta, sem depender de canal alpha."""
    a = ImageColor.getrgb(cor_a)
    b = ImageColor.getrgb(cor_b)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _textura_de_fundo(draw, tamanho, bg: str, cor_texto: str):
    """Dois círculos enormes e bem sutis, um em cada canto oposto, só pra dar textura
    de marca e preencher o fundo - em vez de deixar uma área vazia lisa acima/abaixo
    do texto."""
    tom = _misturar_cor(bg, cor_texto, 0.06)
    raio = int(tamanho[0] * 0.85)
    cx, cy = tamanho[0] - int(tamanho[0] * 0.15), int(tamanho[1] * 0.08)
    draw.ellipse([(cx - raio, cy - raio), (cx + raio, cy + raio)], fill=tom)

    raio2 = int(tamanho[0] * 0.55)
    cx2, cy2 = int(tamanho[0] * 0.05), tamanho[1] - int(tamanho[1] * 0.06)
    draw.ellipse([(cx2 - raio2, cy2 - raio2), (cx2 + raio2, cy2 + raio2)], fill=tom)


def gerar_imagem_texto_simples(
    eyebrow: str,
    headline: str,
    body: str,
    bg: str,
    cor_texto: str,
    cor_eyebrow: str | None = None,
    tamanho=(1080, 1080),
) -> Image.Image:
    """Layout "statement": eyebrow em pílula + título + corpo. As fontes e espaçamentos
    escalam com a altura do canvas - story (1080x1920) tem quase o dobro de altura do
    feed (1080x1080), e usar os mesmos tamanhos fixos deixava o texto perdido numa área
    vazia enorme em vez de preencher o espaço."""
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 88
    largura_max = tamanho[0] - margem * 2
    escala = tamanho[1] / 1080
    cor_eyebrow = cor_eyebrow or cor_texto

    _textura_de_fundo(draw, tamanho, bg, cor_texto)

    fonte_eyebrow = _fonte(int(26 * escala), negrito=True)
    fonte_headline = _fonte(int(64 * escala), negrito=True)
    fonte_body = _fonte(int(38 * escala))

    linhas_headline = _quebrar_texto(draw, headline, fonte_headline, largura_max) if headline else []
    linhas_body = _quebrar_texto(draw, body, fonte_body, largura_max) if body else []

    pad_pilula = int(16 * escala)
    altura_pilula = fonte_eyebrow.size + pad_pilula * 2
    altura_headline = len(linhas_headline) * int(fonte_headline.size * 1.2)
    altura_body = (int(fonte_body.size * 0.7) + len(linhas_body) * int(fonte_body.size * 1.45)) if linhas_body else 0
    altura_conteudo = altura_headline + altura_body

    # A pílula fica ancorada perto do topo e a linha/selo perto do rodapé - o
    # título+corpo ficam centralizados no espaço que sobra entre os dois, em vez de
    # tudo virar um único bloco flutuando no meio de uma tela vazia.
    linha_y = tamanho[1] - int(margem * 1.6)
    y_pilula = int(tamanho[1] * 0.13)
    y = y_pilula
    if eyebrow:
        texto_eyebrow = eyebrow.upper()
        largura_pilula = draw.textlength(texto_eyebrow, font=fonte_eyebrow) + pad_pilula * 2
        draw.rounded_rectangle(
            [(margem, y), (margem + largura_pilula, y + altura_pilula)],
            radius=altura_pilula // 2, outline=cor_eyebrow, width=max(2, int(2 * escala)),
        )
        draw.text((margem + pad_pilula, y + pad_pilula), texto_eyebrow, font=fonte_eyebrow, fill=cor_eyebrow)
        y += altura_pilula

    y_conteudo_inicio = y + int(56 * escala)
    espaco_disponivel = (linha_y - int(48 * escala)) - y_conteudo_inicio
    y = y_conteudo_inicio + max(0, (espaco_disponivel - altura_conteudo) // 2)

    y = _desenhar_bloco_texto(draw, linhas_headline, fonte_headline, margem, y, cor_texto, espacamento=1.2)
    if linhas_body:
        y += int(fonte_body.size * 0.7)
        y = _desenhar_bloco_texto(draw, linhas_body, fonte_body, margem, y, cor_texto, espacamento=1.45)

    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=cor_eyebrow, width=max(2, int(2 * escala)))
    _badge_marca(draw, tamanho, cor_texto, margem)
    return img


def gerar_imagem_ofertas(ofertas, titulo="Ofertas de hoje", tamanho=(1080, 1920)) -> Image.Image:
    """Layout com cartões de produto empilhados - usado pro destaque diário de ofertas
    (formato story, 9:16) e pro resumo semanal (chamar com tamanho=(1080, 1080))."""
    bg = CORES["paper"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 72

    fonte_eyebrow = _fonte(26, negrito=True)
    fonte_titulo = _fonte(56, negrito=True)
    fonte_nome = _fonte(30, negrito=True)
    fonte_preco = _fonte(34, mono=True, negrito=True)
    fonte_desconto = _fonte(24, negrito=True)

    y = 100
    draw.text((margem, y), "CASH-B", font=fonte_eyebrow, fill=CORES["brand"])
    y += 46
    for linha in _quebrar_texto(draw, titulo, fonte_titulo, tamanho[0] - margem * 2):
        draw.text((margem, y), linha, font=fonte_titulo, fill=CORES["ink"])
        y += int(fonte_titulo.size * 1.15)
    y += 40

    largura_card = tamanho[0] - margem * 2
    espaco_entre_cards = 28
    ofertas_exibidas = ofertas[:3]

    # A altura de cada cartão se ajusta ao espaço disponível, pra caber tanto no
    # formato quadrado (feed) quanto no vertical (story) sem estourar o canvas.
    reserva_rodape = margem + 90  # espaço pro selo "cash-b" no rodapé
    espaco_disponivel = tamanho[1] - y - reserva_rodape - espaco_entre_cards * (len(ofertas_exibidas) - 1)
    altura_imagem = max(140, min(260, espaco_disponivel // max(len(ofertas_exibidas), 1) - 40))

    for oferta in ofertas_exibidas:
        altura_card = altura_imagem + 40
        draw.rounded_rectangle(
            [(margem, y), (margem + largura_card, y + altura_card)], radius=20, outline=CORES["line"], width=2
        )

        imagem_produto = _baixar_imagem(oferta.imagem_url) if oferta.imagem_url else None
        area_imagem = altura_imagem
        if imagem_produto:
            imagem_produto = imagem_produto.resize((area_imagem, area_imagem))
            mask = _rounded_mask((area_imagem, area_imagem), 16)
            img.paste(imagem_produto, (margem + 20, y + 20), mask)
        else:
            draw.rounded_rectangle(
                [(margem + 20, y + 20), (margem + 20 + area_imagem, y + 20 + area_imagem)],
                radius=16, fill=CORES["paper-2"],
            )

        x_texto = margem + 20 + area_imagem + 32
        largura_texto = largura_card - (20 + area_imagem + 32 + 20)

        if oferta.percentual_desconto:
            selo = f"-{oferta.percentual_desconto}%"
            draw.rounded_rectangle(
                [(x_texto, y + 20), (x_texto + draw.textlength(selo, font=fonte_desconto) + 24, y + 20 + 40)],
                radius=12, fill=CORES["highlight"],
            )
            draw.text((x_texto + 12, y + 28), selo, font=fonte_desconto, fill=CORES["ink"])

        nome_linhas = _quebrar_texto(draw, oferta.nome, fonte_nome, largura_texto)[:2]
        y_nome = y + 76
        for linha in nome_linhas:
            draw.text((x_texto, y_nome), linha, font=fonte_nome, fill=CORES["ink"])
            y_nome += int(fonte_nome.size * 1.3)

        preco = f"R$ {oferta.preco_min:.2f}".replace(".", ",")
        draw.text((x_texto, y + altura_card - 56), preco, font=fonte_preco, fill=CORES["brand"])

        y += altura_card + espaco_entre_cards

    _badge_marca(draw, tamanho, CORES["brand"], margem)
    return img
