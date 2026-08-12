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
    "ink": "#111827",
    "ink-soft": "#374151",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "brand-strong": "#4c1d95",
    "highlight": "#f59e0b",
    "paper": "#f8fafc",
    "paper-2": "#f1eefb",
    "line": "#e0dcef",
    "danger": "#dc2626",
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
    """y é o topo do bloco. Cada linha usa anchor="lm" (baseado nas métricas reais da
    fonte) pra ficar centralizada dentro da sua própria fatia de altura_linha, em vez
    de só encostada no topo - o que deixava o texto com aparência desalinhada."""
    altura_linha = int(fonte.size * espacamento)
    for i, linha in enumerate(linhas):
        draw.text((x, y + i * altura_linha + altura_linha / 2), linha, font=fonte, fill=cor, anchor="lm")
    return y + len(linhas) * altura_linha


def _badge_marca(draw, tamanho_canvas, cor, margem=88):
    """Selo "cash-b" no rodapé, alinhado à direita."""
    fonte = _fonte(30, negrito=True)
    draw.text(
        (tamanho_canvas[0] - margem, tamanho_canvas[1] - margem - 15), "cash-b", font=fonte, fill=cor, anchor="rm",
    )


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


def _ajustar_fonte_ao_espaco(draw, texto, largura_max, altura_max, escala, tamanho_max=72, tamanho_min=32):
    """Reduz o tamanho da fonte até o texto (já quebrado em linhas) caber dentro de
    altura_max. Sem isso, uma frase curta (lembrete) e uma longa (dica) usando o
    mesmo tamanho fixo davam resultados opostos: uma sobrava, a outra estourava."""
    for tamanho in range(int(tamanho_max * escala), int(tamanho_min * escala) - 1, -4):
        fonte = _fonte(tamanho, negrito=True)
        linhas = _quebrar_texto(draw, texto, fonte, largura_max)
        if len(linhas) * int(fonte.size * 1.25) <= altura_max:
            return fonte, linhas
    fonte = _fonte(int(tamanho_min * escala), negrito=True)
    return fonte, _quebrar_texto(draw, texto, fonte, largura_max)


def gerar_imagem_texto_simples(
    texto: str,
    bg: str,
    cor_texto: str,
    cor_acento: str | None = None,
    tamanho=(1080, 1080),
) -> Image.Image:
    """Layout "statement": uma frase em destaque, centralizada no espaço acima do
    rodapé - sem selo/etiqueta no topo, pra não repetir "cash-b" várias vezes na
    mesma imagem (o selo do rodapé já basta). O tamanho da fonte se ajusta ao
    tamanho da frase e à altura do canvas, em vez de um valor fixo que sobrava
    pra frases curtas e estourava pra frases longas."""
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 88
    largura_max = tamanho[0] - margem * 2
    escala = tamanho[1] / 1080
    cor_acento = cor_acento or cor_texto

    _textura_de_fundo(draw, tamanho, bg, cor_texto)

    linha_y = tamanho[1] - int(margem * 1.6)
    reserva = int(margem * 0.7)
    area_util = linha_y - reserva
    fonte_texto, linhas = _ajustar_fonte_ao_espaco(
        draw, texto, largura_max, altura_max=int(area_util * 0.62), escala=escala,
    )
    altura_conteudo = len(linhas) * int(fonte_texto.size * 1.25)

    y = reserva + max(0, (area_util - altura_conteudo) // 2)
    _desenhar_bloco_texto(draw, linhas, fonte_texto, margem, y, cor_texto, espacamento=1.25)

    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=cor_acento, width=max(2, int(2 * escala)))
    _badge_marca(draw, tamanho, cor_texto, margem)
    return img


def gerar_imagem_oferta_carrossel(oferta, indice: int, total: int, tamanho=(1080, 1080)) -> Image.Image:
    """Um slide de carrossel com uma oferta só em destaque - foto grande, nome, preço. Usado no
    resumo semanal de ofertas (um slide por oferta, em vez de todas espremidas numa imagem só)."""
    bg = CORES["paper"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 72

    fonte_nome = _fonte(38, negrito=True)
    fonte_preco = _fonte(46, mono=True, negrito=True)
    fonte_desconto = _fonte(26, negrito=True)
    fonte_indice = _fonte(24, mono=True)

    reserva_texto = 250
    reserva_rodape = 96
    lado_imagem = min(tamanho[0] - margem * 2, tamanho[1] - margem - reserva_texto - reserva_rodape)
    x_imagem = (tamanho[0] - lado_imagem) // 2
    y_imagem = margem

    imagem_produto = _baixar_imagem(oferta.imagem_url) if oferta.imagem_url else None
    if imagem_produto:
        imagem_produto = imagem_produto.resize((lado_imagem, lado_imagem))
        mask = _rounded_mask((lado_imagem, lado_imagem), 24)
        img.paste(imagem_produto, (x_imagem, y_imagem), mask)
    else:
        draw.rounded_rectangle(
            [(x_imagem, y_imagem), (x_imagem + lado_imagem, y_imagem + lado_imagem)],
            radius=24, fill=CORES["paper-2"],
        )
    draw.rounded_rectangle(
        [(x_imagem, y_imagem), (x_imagem + lado_imagem, y_imagem + lado_imagem)],
        radius=24, outline=CORES["line"], width=2,
    )

    if oferta.percentual_desconto:
        selo = f"-{oferta.percentual_desconto}%"
        largura_selo = draw.textlength(selo, font=fonte_desconto) + 28
        draw.rounded_rectangle(
            [(x_imagem + 20, y_imagem + 20), (x_imagem + 20 + largura_selo, y_imagem + 20 + 46)],
            radius=14, fill=CORES["highlight"],
        )
        draw.text((x_imagem + 34, y_imagem + 30), selo, font=fonte_desconto, fill=CORES["ink"])

    indicador = f"{indice}/{total}"
    draw.text(
        (tamanho[0] - margem - draw.textlength(indicador, font=fonte_indice), margem - 40),
        indicador, font=fonte_indice, fill=CORES["muted"],
    )

    y_texto = y_imagem + lado_imagem + 44
    linhas_nome = _quebrar_texto(draw, oferta.nome_curto or oferta.nome, fonte_nome, tamanho[0] - margem * 2)[:2]
    for linha in linhas_nome:
        draw.text((margem, y_texto), linha, font=fonte_nome, fill=CORES["ink"])
        y_texto += int(fonte_nome.size * 1.3)

    preco = f"R$ {oferta.preco_min:.2f}".replace(".", ",")
    draw.text((margem, y_texto + 10), preco, font=fonte_preco, fill=CORES["brand"])

    _badge_marca(draw, tamanho, CORES["brand"], margem)
    return img


def gerar_imagem_oferta_story(oferta, tamanho=(1080, 1920)) -> Image.Image:
    """Layout "hero" pra 1 oferta só ocupando o story inteiro - é sempre 1 oferta por
    story (ver publicar_story_oferta_do_momento/NUMERO_STORIES_OFERTAS_POR_DIA), então
    não faz sentido empilhar cartões pequenos encostados no topo. Estilo do cartão de
    oferta do site (ver ofertas/templates/ofertas/lista.html, .oferta-cartao): imagem
    grande, selo de desconto sobre a imagem, nome e preço em destaque.

    topo_seguro/rodape_seguro reservam espaço pra UI do próprio Instagram (ícone/nome
    da conta no topo, barra de resposta embaixo) não sobrepor a arte - o bloco inteiro
    (selo + imagem + texto) é centralizado dentro dessa área segura, em vez de fixo
    encostado nas bordas."""
    bg = CORES["paper"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 72
    topo_seguro, rodape_seguro = 260, 260

    fonte_eyebrow = _fonte(30, mono=True, negrito=True)
    fonte_nome = _fonte(46, negrito=True)
    fonte_preco = _fonte(58, mono=True, negrito=True)
    fonte_desconto = _fonte(30, negrito=True)
    fonte_marca = _fonte(42, negrito=True)
    fonte_link_bio = _fonte(32, negrito=True)

    largura_util = tamanho[0] - margem * 2
    nome = oferta.nome_curto or oferta.nome
    linhas_nome = _quebrar_texto(draw, nome, fonte_nome, largura_util)[:2]

    altura_eyebrow = int(fonte_eyebrow.size * 1.6)
    altura_marca = int(fonte_marca.size * 1.6)
    altura_cabecalho = max(altura_eyebrow, altura_marca)
    altura_nome = len(linhas_nome) * int(fonte_nome.size * 1.25)
    altura_preco = int(fonte_preco.size * 1.3)
    espacos = 28 * 3
    area_util = tamanho[1] - topo_seguro - rodape_seguro
    lado_imagem = min(largura_util, area_util - altura_cabecalho - altura_nome - altura_preco - espacos)

    # "link na bio" fica fora desse bloco (desenhado depois, centralizado e perto do
    # rodapé seguro) - só cabeçalho/imagem/nome/preço centralizam juntos aqui.
    altura_bloco = altura_cabecalho + 28 + lado_imagem + 28 + altura_nome + 20 + altura_preco
    y = topo_seguro + max(0, (area_util - altura_bloco) // 2)

    # anchor "m" (middle) nos dois - não "a" (ascender) - pra alinhar pelo centro
    # visual da linha, já que "OFERTA DO MOMENTO" e "cash-b" usam tamanhos de fonte
    # diferentes (se alinhasse pelo topo, o maior pareceria "descer" mais que o outro).
    y_centro_cabecalho = y + altura_cabecalho / 2
    draw.text((margem, y_centro_cabecalho), "OFERTA DO MOMENTO", font=fonte_eyebrow, fill=CORES["brand"], anchor="lm")
    draw.text((tamanho[0] - margem, y_centro_cabecalho), "cash-b", font=fonte_marca, fill=CORES["brand"], anchor="rm")
    y += altura_cabecalho + 28

    x_imagem = (tamanho[0] - lado_imagem) // 2
    y_imagem = y
    imagem_produto = _baixar_imagem(oferta.imagem_url) if oferta.imagem_url else None
    if imagem_produto:
        imagem_produto = imagem_produto.resize((lado_imagem, lado_imagem))
        mask = _rounded_mask((lado_imagem, lado_imagem), 32)
        img.paste(imagem_produto, (x_imagem, y_imagem), mask)
    else:
        draw.rounded_rectangle(
            [(x_imagem, y_imagem), (x_imagem + lado_imagem, y_imagem + lado_imagem)],
            radius=32, fill=CORES["paper-2"],
        )
    draw.rounded_rectangle(
        [(x_imagem, y_imagem), (x_imagem + lado_imagem, y_imagem + lado_imagem)],
        radius=32, outline=CORES["line"], width=2,
    )

    # Mesmas cores/posições do selo de desconto (esquerda) e cashback (direita) do
    # cartão de oferta do site - ver ofertas/templates/ofertas/lista.html, .desconto/.cashback.
    # anchor="mm" (não "la") pra centralizar o texto de verdade dentro da caixa nos
    # dois eixos - "la" ancora pelo ascender da fonte, que sobra espaço embaixo em
    # texto sem descendente (números/maiúsculas), ficando visualmente subido/torto.
    y0_selo, y1_selo = y_imagem + 24, y_imagem + 24 + 52
    y_centro_selo = (y0_selo + y1_selo) / 2

    if oferta.percentual_desconto:
        selo = f"-{oferta.percentual_desconto}%"
        largura_selo = draw.textlength(selo, font=fonte_desconto) + 32
        draw.rounded_rectangle(
            [(x_imagem + 24, y0_selo), (x_imagem + 24 + largura_selo, y1_selo)],
            radius=16, fill=CORES["danger"],
        )
        draw.text(
            (x_imagem + 24 + largura_selo / 2, y_centro_selo), selo, font=fonte_desconto, fill="#ffffff", anchor="mm",
        )

    if oferta.percentual_cashback:
        selo_cashback = f"{oferta.percentual_cashback}% cashback"
        largura_selo_cashback = draw.textlength(selo_cashback, font=fonte_desconto) + 32
        x_selo_cashback = x_imagem + lado_imagem - 24 - largura_selo_cashback
        draw.rounded_rectangle(
            [(x_selo_cashback, y0_selo), (x_selo_cashback + largura_selo_cashback, y1_selo)],
            radius=16, fill=CORES["highlight"],
        )
        draw.text(
            (x_selo_cashback + largura_selo_cashback / 2, y_centro_selo),
            selo_cashback, font=fonte_desconto, fill=CORES["ink"], anchor="mm",
        )

    y = y_imagem + lado_imagem + 28
    for linha in linhas_nome:
        draw.text((margem, y), linha, font=fonte_nome, fill=CORES["ink"])
        y += int(fonte_nome.size * 1.25)

    y += 20
    preco = f"R$ {oferta.preco_min:.2f}".replace(".", ",")
    draw.text((margem, y), preco, font=fonte_preco, fill=CORES["brand"])

    # Centralizado na largura toda (não alinhado com o resto do bloco, que é à
    # esquerda) e perto do limite inferior da área segura, não colado no preço.
    draw.text(
        (tamanho[0] / 2, tamanho[1] - rodape_seguro - 10),
        "link na bio", font=fonte_link_bio, fill=CORES["ink-soft"], anchor="ms",
    )

    return img
