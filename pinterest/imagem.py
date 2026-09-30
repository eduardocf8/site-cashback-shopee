"""Arte de Pin (2:3, 1000x1500) de uma CATEGORIA, não de uma oferta.

Duas decisões que separam isto das artes do Instagram (instagram_bot/templates_imagem.py):

- Sem preço na imagem. Um Pin leva de 3 a 6 meses pra ganhar tração e continua
  aparecendo por meses depois disso; um story vive 24h. Preço de Shopee muda em dias,
  e o Pinterest pede que a imagem continue coerente com o destino - preço velho na
  arte é justamente o que não pode acontecer.
- Uma categoria por Pin, com 4 fotos dos mais vendidos dela. O link do Pin vai pra
  /ofertas/?categoria=ID, que continua existindo depois que a sincronização diária
  apaga e recria as ofertas (o id de uma Oferta não sobrevive a um dia - ver
  ofertas/services.py::sincronizar_ofertas).

Cores e fontes vêm do mesmo lugar das artes do bot, pra não criar um quinto arquivo
com a paleta duplicada (ver "Fonte de verdade de cor" em BRAND.md).
"""
from PIL import Image, ImageDraw

from instagram_bot.templates_imagem import (
    CORES,
    _badge_marca,
    _baixar_imagem,
    _fonte,
    _quebrar_texto,
    _rounded_mask,
    _textura_de_fundo,
)

TAMANHO_PIN = (1000, 1500)

# Verde é dinheiro (regra de ouro do BRAND.md). Estas duas não existem no CORES do bot
# porque as artes do Instagram ainda usam âmbar no selo de cashback - divergência
# registrada no BRAND.md, que o Pin não herda: aqui segue o site.
VERDE_DINHEIRO = "#059669"
VERDE_DINHEIRO_FUNDO = "#ecfdf5"


def _foto_ou_placeholder(img, draw, oferta, x, y, lado):
    foto = _baixar_imagem(oferta.imagem_url) if oferta and oferta.imagem_url else None
    if foto:
        img.paste(foto.resize((lado, lado)), (x, y), _rounded_mask((lado, lado), 28))
    else:
        draw.rounded_rectangle([(x, y), (x + lado, y + lado)], radius=28, fill=CORES["paper-2"])
    draw.rounded_rectangle([(x, y), (x + lado, y + lado)], radius=28, outline=CORES["line"], width=2)


def gerar_imagem_pin_categoria(categoria_nome: str, ofertas, tamanho=TAMANHO_PIN) -> Image.Image:
    """`ofertas` são até 4 ofertas da categoria (só a foto é usada). Com menos de 4, o
    espaço que sobra fica com o placeholder lilás - melhor que esticar uma foto só."""
    bg = CORES["paper"]
    img = Image.new("RGB", tamanho, bg)
    draw = ImageDraw.Draw(img)
    margem = 72
    largura_util = tamanho[0] - margem * 2

    _textura_de_fundo(draw, tamanho, bg, CORES["brand"])

    fonte_rotulo = _fonte(30, mono=True, negrito=True)
    fonte_titulo = _fonte(84, negrito=True)
    fonte_selo = _fonte(34, negrito=True)

    linhas = _quebrar_texto(draw, categoria_nome, fonte_titulo, largura_util)[:2]
    altura_linha = int(fonte_titulo.size * 1.1)
    espaco = 24
    lado = (largura_util - espaco) // 2
    linha_y = tamanho[1] - int(margem * 1.6)

    # Centraliza o bloco todo (rótulo, título, grade, selo) no espaço acima do risco
    # do rodapé: nome de categoria de uma linha ("Beleza") e de duas ("Esportes e
    # Atividades ao Ar Livre") ficam com a mesma folga em cima e embaixo.
    altura_bloco = 48 + len(linhas) * altura_linha + 40 + lado * 2 + espaco + 48 + 64
    y = margem + max(0, (linha_y - margem - altura_bloco) // 2)
    draw.text((margem, y), "OFERTAS NA SHOPEE", font=fonte_rotulo, fill=CORES["brand"], anchor="lm")
    y += 48

    for linha in linhas:
        draw.text((margem, y + altura_linha / 2), linha, font=fonte_titulo, fill=CORES["ink"], anchor="lm")
        y += altura_linha
    y += 40

    ofertas = list(ofertas)[:4]
    for indice in range(4):
        linha, coluna = divmod(indice, 2)
        _foto_ou_placeholder(
            img, draw, ofertas[indice] if indice < len(ofertas) else None,
            margem + coluna * (lado + espaco), y + linha * (lado + espaco), lado,
        )
    y += lado * 2 + espaco + 48

    selo = "cashback em toda compra"
    largura_selo = draw.textlength(selo, font=fonte_selo) + 48
    draw.rounded_rectangle([(margem, y), (margem + largura_selo, y + 64)], radius=16, fill=VERDE_DINHEIRO_FUNDO)
    draw.text((margem + largura_selo / 2, y + 32), selo, font=fonte_selo, fill=VERDE_DINHEIRO, anchor="mm")

    draw.line([(margem, linha_y), (tamanho[0] - margem, linha_y)], fill=CORES["brand"], width=2)
    _badge_marca(draw, tamanho, CORES["brand"], margem)
    return img
