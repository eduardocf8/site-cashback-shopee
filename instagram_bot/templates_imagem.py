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


# ---------------------------------------------------------------------------
# Formatos com dado real (número do catálogo e "a conta")
#
# Existem porque todo o conteúdo diário do bot passava por gerar_imagem_texto_simples:
# uma frase centralizada sobre cor chapada. Com um layout só, o post do dia 1 e o do
# dia 30 têm a mesma cara, e o conteúdo acaba sendo a marca falando bem de si mesma
# ("cashback de verdade, sem pegadinha") em vez de informação que a pessoa ganha algo
# em ler. Estes dois preenchem com número real - do catálogo ou de uma conta feita na
# hora -, então mudam sozinhos todo dia e dão o que olhar.
# ---------------------------------------------------------------------------


def _cabecalho_rodape(draw, tamanho, margem, cor_texto, cor_acento, rotulo, y_rotulo, centralizado=False):
    """Rótulo pequeno no topo do bloco + risco e selo da marca no rodapé - a moldura
    comum dos formatos abaixo. Centralizado quando o conteúdo do bloco também é (caso
    do layout com foto do produto), pra não ficar um rótulo à esquerda sobre uma
    composição centralizada."""
    escala = tamanho[1] / 1080
    fonte_rotulo = _fonte(int(30 * min(escala, 1.4)), mono=True, negrito=True)
    x, ancora = (tamanho[0] / 2, "mm") if centralizado else (margem, "lm")
    draw.text((x, y_rotulo), rotulo.upper(), font=fonte_rotulo, fill=cor_acento, anchor=ancora)
    linha_y = tamanho[1] - int(margem * 1.6)
    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=cor_acento, width=max(2, int(2 * escala)))
    _badge_marca(draw, tamanho, cor_texto, margem)


def gerar_imagem_numero_destaque(
    numero: str,
    rotulo: str,
    apoio: str,
    bg: str | None = None,
    cor_texto: str | None = None,
    cor_numero: str | None = None,
    tamanho=(1080, 1080),
) -> Image.Image:
    """Um número enorme como protagonista, com uma linha de apoio explicando de onde
    ele vem. O número é o gancho: quem passa o dedo pelo story para num "8,4%" muito
    antes de parar numa frase.

    O corpo do número se ajusta ao comprimento porque "8,4%" e "R$ 1.509" ocupam
    larguras bem diferentes - com tamanho fixo, um sobrava e o outro estourava."""
    bg = bg or CORES["brand"]
    cor_texto = cor_texto or CORES["paper"]
    cor_numero = cor_numero or CORES["highlight"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)

    escala = tamanho[1] / 1080
    margem = 88
    story = tamanho[1] > tamanho[0] * 1.2
    topo_seguro = 260 if story else margem
    rodape_seguro = 260 if story else int(margem * 2.2)
    largura_max = tamanho[0] - margem * 2

    _textura_de_fundo(draw, tamanho, bg, cor_texto)

    # o número usa a mono da marca (mesma dos valores no site) e encolhe até caber
    for corpo in range(int(200 * min(escala, 1.6)), 60, -6):
        fonte_numero = _fonte(corpo, mono=True, negrito=True)
        if draw.textlength(numero, font=fonte_numero) <= largura_max:
            break

    fonte_apoio = _fonte(int(38 * min(escala, 1.5)), negrito=False)
    linhas_apoio = _quebrar_texto(draw, apoio, fonte_apoio, largura_max)

    altura_numero = int(fonte_numero.size * 1.05)
    altura_apoio = len(linhas_apoio) * int(fonte_apoio.size * 1.35)
    altura_bloco = altura_numero + 36 + altura_apoio

    area_util = tamanho[1] - topo_seguro - rodape_seguro
    y = topo_seguro + max(0, (area_util - altura_bloco) // 2)

    _cabecalho_rodape(draw, tamanho, margem, cor_texto, cor_numero, rotulo, y - 46)
    draw.text((margem, y + altura_numero / 2), numero, font=fonte_numero, fill=cor_numero, anchor="lm")
    _desenhar_bloco_texto(draw, linhas_apoio, fonte_apoio, margem, y + altura_numero + 36, cor_texto, espacamento=1.35)
    return img


def gerar_imagem_conta(
    titulo: str,
    linhas: list[tuple[str, str]],
    destaque: tuple[str, str],
    rodape: str = "",
    bg: str | None = None,
    cor_texto: str | None = None,
    tamanho=(1080, 1080),
) -> Image.Image:
    """Formato "a conta": rótulo à esquerda, valor à direita, uma linha por vez, com a
    última destacada. Serve pra qualquer comparação em que o ponto é o resultado -
    quanto você paga contra quanto volta, com cashback contra sem.

    Mostrar a conta armada convence mais que afirmar o resultado pronto: a pessoa
    acompanha o raciocínio em vez de ter que acreditar."""
    bg = bg or CORES["paper"]
    cor_texto = cor_texto or CORES["ink"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)

    escala = tamanho[1] / 1080
    margem = 88
    story = tamanho[1] > tamanho[0] * 1.2
    topo_seguro = 260 if story else margem
    rodape_seguro = 260 if story else int(margem * 2.2)
    largura_max = tamanho[0] - margem * 2

    fonte_titulo = _fonte(int(52 * min(escala, 1.4)), negrito=True)
    fonte_rotulo = _fonte(int(34 * min(escala, 1.4)))
    fonte_valor = _fonte(int(38 * min(escala, 1.4)), mono=True, negrito=True)
    fonte_destaque_rotulo = _fonte(int(36 * min(escala, 1.4)), negrito=True)
    fonte_destaque_valor = _fonte(int(56 * min(escala, 1.5)), mono=True, negrito=True)
    fonte_rodape = _fonte(int(28 * min(escala, 1.4)))

    linhas_titulo = _quebrar_texto(draw, titulo, fonte_titulo, largura_max)
    altura_titulo = len(linhas_titulo) * int(fonte_titulo.size * 1.2)
    altura_linha = int(fonte_valor.size * 2.2)
    altura_destaque = int(fonte_destaque_valor.size * 1.9)
    linhas_rodape = _quebrar_texto(draw, rodape, fonte_rodape, largura_max) if rodape else []
    altura_rodape = len(linhas_rodape) * int(fonte_rodape.size * 1.4)

    altura_bloco = altura_titulo + 40 + len(linhas) * altura_linha + altura_destaque
    if linhas_rodape:
        altura_bloco += 28 + altura_rodape

    area_util = tamanho[1] - topo_seguro - rodape_seguro
    y = topo_seguro + max(0, (area_util - altura_bloco) // 2)

    _desenhar_bloco_texto(draw, linhas_titulo, fonte_titulo, margem, y, cor_texto, espacamento=1.2)
    y += altura_titulo + 40

    for rotulo, valor in linhas:
        centro = y + altura_linha / 2
        draw.text((margem, centro), rotulo, font=fonte_rotulo, fill=CORES["muted"], anchor="lm")
        draw.text((tamanho[0] - margem, centro), valor, font=fonte_valor, fill=cor_texto, anchor="rm")
        draw.line(
            [(margem, y + altura_linha), (tamanho[0] - margem, y + altura_linha)],
            fill=CORES["line"], width=max(1, int(escala)),
        )
        y += altura_linha

    # a última linha é o ponto do post, então ganha corpo maior e a cor de destaque
    centro = y + altura_destaque / 2
    draw.text((margem, centro), destaque[0], font=fonte_destaque_rotulo, fill=cor_texto, anchor="lm")
    draw.text(
        (tamanho[0] - margem, centro), destaque[1],
        font=fonte_destaque_valor, fill=CORES["brand"], anchor="rm",
    )
    y += altura_destaque

    if linhas_rodape:
        _desenhar_bloco_texto(draw, linhas_rodape, fonte_rodape, margem, y + 28, CORES["muted"], espacamento=1.4)

    linha_y = tamanho[1] - int(margem * 1.6)
    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=CORES["brand"], width=max(2, int(2 * escala)))
    _badge_marca(draw, tamanho, cor_texto, margem)
    return img


def _cartao_produto(img, draw, imagem_url: str, centro_x: int, topo: int, lado: int) -> bool:
    """Foto do produto num cartão arredondado. Devolve False quando a imagem não veio -
    aí quem chama segue sem ela, em vez de deixar um buraco cinza no story."""
    foto = _baixar_imagem(imagem_url) if imagem_url else None
    if foto is None:
        return False
    foto = foto.resize((lado, lado), Image.LANCZOS)
    x = centro_x - lado // 2
    img.paste(foto, (x, topo), _rounded_mask((lado, lado), int(lado * 0.06)))
    return True


def gerar_imagem_numero_com_produto(
    numero: str,
    rotulo: str,
    apoio: str,
    imagem_url: str,
    legenda_produto: str = "",
    bg: str | None = None,
    cor_texto: str | None = None,
    cor_numero: str | None = None,
    tamanho=(1080, 1920),
) -> Image.Image:
    """A foto do produto junto com o número que ele devolve.

    Só o primeiro story do combo leva foto: repetir a mesma imagem em todos deixa a
    sequência monótona, e o papel dela é abrir - dar cara ao número que vem depois.
    Sem a foto o número fica abstrato ("8,4% de quê?"), com ela em todos vira catálogo.

    Se a foto não baixar, cai no layout sem imagem em vez de falhar."""
    bg = bg or CORES["brand"]
    cor_texto = cor_texto or CORES["paper"]
    cor_numero = cor_numero or CORES["highlight"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)

    escala = tamanho[1] / 1080
    margem = 88
    topo_seguro, rodape_seguro = 260, 260
    largura_max = tamanho[0] - margem * 2

    _textura_de_fundo(draw, tamanho, bg, cor_texto)

    lado_foto = min(largura_max, 620)
    fonte_numero = _fonte(int(150 * min(escala, 1.4)), mono=True, negrito=True)
    while draw.textlength(numero, font=fonte_numero) > largura_max and fonte_numero.size > 70:
        fonte_numero = _fonte(fonte_numero.size - 6, mono=True, negrito=True)
    fonte_apoio = _fonte(int(36 * min(escala, 1.4)))
    fonte_legenda = _fonte(int(30 * min(escala, 1.4)))
    linhas_apoio = _quebrar_texto(draw, apoio, fonte_apoio, largura_max)
    # O nome do produto aparece só aqui, como legenda da foto - é o lugar onde ele
    # explica a imagem sem disputar espaço com o número, que é o que segura o dedo.
    linhas_legenda = _quebrar_texto(draw, legenda_produto, fonte_legenda, lado_foto)[:2] if legenda_produto else []

    altura_numero = int(fonte_numero.size * 1.05)
    altura_apoio = len(linhas_apoio) * int(fonte_apoio.size * 1.35)
    altura_legenda = len(linhas_legenda) * int(fonte_legenda.size * 1.3)
    area_util = tamanho[1] - topo_seguro - rodape_seguro

    # Espaço reservado ao rótulo acima da foto. O rótulo fica centralizado nessa faixa,
    # então o valor precisa ser bem maior que a altura dele - senão sobra pouco entre a
    # base do texto e o topo do cartão, e o rótulo parece colado na imagem.
    respiro_rotulo = 130
    altura_bloco = respiro_rotulo + lado_foto + altura_legenda + 40 + altura_numero + 28 + altura_apoio
    if linhas_legenda:
        altura_bloco += 20
    y = topo_seguro + max(0, (area_util - altura_bloco) // 2)

    _cabecalho_rodape(
        draw, tamanho, margem, cor_texto, cor_numero, rotulo,
        y + respiro_rotulo / 2, centralizado=True,
    )
    y += respiro_rotulo

    if _cartao_produto(img, draw, imagem_url, tamanho[0] // 2, y, lado_foto):
        y += lado_foto
    else:
        y += lado_foto // 2

    if linhas_legenda:
        y += 20
        altura_linha_legenda = int(fonte_legenda.size * 1.3)
        for i, linha in enumerate(linhas_legenda):
            draw.text(
                (tamanho[0] // 2, y + i * altura_linha_legenda + altura_linha_legenda / 2),
                linha, font=fonte_legenda, fill=cor_texto, anchor="mm",
            )
        y += altura_legenda

    y += 40
    draw.text((tamanho[0] // 2, y + altura_numero / 2), numero, font=fonte_numero, fill=cor_numero, anchor="mm")
    y += altura_numero + 28
    altura_linha = int(fonte_apoio.size * 1.35)
    for i, linha in enumerate(linhas_apoio):
        draw.text(
            (tamanho[0] // 2, y + i * altura_linha + altura_linha / 2),
            linha, font=fonte_apoio, fill=cor_texto, anchor="mm",
        )
    return img


def gerar_imagem_passos(
    titulo: str,
    passos: list[str],
    rodape: str = "",
    bg: str | None = None,
    cor_texto: str | None = None,
    tamanho=(1080, 1920),
) -> Image.Image:
    """Passo a passo numerado - fecha o combo mostrando como chegar no produto.

    Existe porque a API de stories não aceita link clicável: o bot consegue publicar a
    imagem, mas não o sticker de link. Sem esse último story, a pessoa vê um produto que
    devolve 8% e não tem como chegar nele - o combo inteiro vira beco sem saída."""
    bg = bg or CORES["paper"]
    cor_texto = cor_texto or CORES["ink"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)

    escala = tamanho[1] / 1080
    margem = 88
    story = tamanho[1] > tamanho[0] * 1.2
    topo_seguro = 260 if story else margem
    rodape_seguro = 260 if story else int(margem * 2.2)
    largura_max = tamanho[0] - margem * 2

    fonte_titulo = _fonte(int(54 * min(escala, 1.4)), negrito=True)
    fonte_passo = _fonte(int(38 * min(escala, 1.4)), negrito=True)
    fonte_numero = _fonte(int(34 * min(escala, 1.4)), mono=True, negrito=True)
    fonte_rodape = _fonte(int(28 * min(escala, 1.4)))

    diametro = int(72 * min(escala, 1.4))
    recuo = diametro + 32

    linhas_titulo = _quebrar_texto(draw, titulo, fonte_titulo, largura_max)
    altura_titulo = len(linhas_titulo) * int(fonte_titulo.size * 1.2)

    blocos = [_quebrar_texto(draw, p, fonte_passo, largura_max - recuo) for p in passos]
    alturas = [max(diametro, len(b) * int(fonte_passo.size * 1.3)) + 40 for b in blocos]
    linhas_rodape = _quebrar_texto(draw, rodape, fonte_rodape, largura_max) if rodape else []
    altura_rodape = len(linhas_rodape) * int(fonte_rodape.size * 1.4)

    altura_bloco = altura_titulo + 48 + sum(alturas)
    if linhas_rodape:
        altura_bloco += 32 + altura_rodape

    area_util = tamanho[1] - topo_seguro - rodape_seguro
    y = topo_seguro + max(0, (area_util - altura_bloco) // 2)

    _desenhar_bloco_texto(draw, linhas_titulo, fonte_titulo, margem, y, cor_texto, espacamento=1.2)
    y += altura_titulo + 48

    # O círculo e o texto do passo têm alturas diferentes (o círculo é maior que uma
    # linha de texto), então cada um é centralizado dentro da altura do passo em vez de
    # os dois começarem no mesmo topo - encostados no topo, o texto fica visivelmente
    # mais alto que o número. Centralizar os dois também mantém o alinhamento quando o
    # passo quebra em duas linhas e fica mais alto que o círculo.
    altura_linha_passo = int(fonte_passo.size * 1.3)
    for i, (bloco, altura) in enumerate(zip(blocos, alturas), start=1):
        altura_texto = len(bloco) * altura_linha_passo
        altura_conteudo = max(diametro, altura_texto)
        topo_circulo = y + (altura_conteudo - diametro) / 2
        topo_texto = y + (altura_conteudo - altura_texto) / 2

        draw.ellipse(
            [(margem, topo_circulo), (margem + diametro, topo_circulo + diametro)],
            fill=CORES["brand"],
        )
        draw.text(
            (margem + diametro / 2, topo_circulo + diametro / 2), str(i),
            font=fonte_numero, fill=CORES["paper"], anchor="mm",
        )
        _desenhar_bloco_texto(draw, bloco, fonte_passo, margem + recuo, topo_texto, cor_texto, espacamento=1.3)
        y += altura

    if linhas_rodape:
        _desenhar_bloco_texto(draw, linhas_rodape, fonte_rodape, margem, y + 32, CORES["muted"], espacamento=1.4)

    linha_y = tamanho[1] - int(margem * 1.6)
    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=CORES["brand"], width=max(2, int(2 * escala)))
    _badge_marca(draw, tamanho, cor_texto, margem)
    return img
