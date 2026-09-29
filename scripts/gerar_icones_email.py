"""Gera os 2 ícones usados no e-mail semanal de venda indireta (ver
accounts/comunicacoes.py::enviar_lembrete_venda_indireta_semanal e
templates/emails/lembrete_venda_indireta.html): um ícone simples na cor da marca pro
link de Regras do cashback, e o glifo do Instagram (com o gradiente oficial) pro link
do Reel. Desenhados em 4x e reduzidos com LANCZOS pra ficar com anti-aliasing (PIL não
desenha suavizado nativamente) - mesma pasta (static/images/) do og-cash-b.png.

Rodar de novo só se precisar mudar o desenho - o resultado já fica versionado.
"""
from PIL import Image, ImageDraw

ESCALA = 4
TAMANHO_FINAL = 128
TAMANHO = TAMANHO_FINAL * ESCALA

BRAND_PURPLE = (109, 40, 217, 255)  # #6d28d9, mesma cor de mobile-app/gen_icons.py
BRANCO = (255, 255, 255, 255)

# Gradiente oficial do Instagram (5 paradas, canto inferior-esquerdo -> superior-direito)
INSTAGRAM_STOPS = [
    (0.00, (254, 218, 117)),  # amarelo
    (0.25, (250, 126, 30)),   # laranja
    (0.50, (214, 41, 118)),   # rosa/vermelho
    (0.75, (150, 47, 191)),   # roxo
    (1.00, (79, 91, 213)),    # azul
]


def _cor_gradiente(t: float) -> tuple:
    for (t0, c0), (t1, c1) in zip(INSTAGRAM_STOPS, INSTAGRAM_STOPS[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
    return INSTAGRAM_STOPS[-1][1]


def gerar_icone_regras(caminho: str) -> None:
    img = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Mesmo formato do ícone do Instagram (rounded square, raio ~22% do lado) e mesmas
    # dimensões - os 2 ícones do e-mail seguem o mesmo "porte" visual lado a lado.
    draw.rounded_rectangle([0, 0, TAMANHO - 1, TAMANHO - 1], radius=int(TAMANHO * 0.22), fill=BRAND_PURPLE)

    # 3 linhas brancas (glifo de lista/regras), com uma bolinha antes de cada uma
    largura_linha = TAMANHO * 0.42
    x_bolinha = TAMANHO * 0.28
    x_linha_inicio = TAMANHO * 0.36
    raio_bolinha = TAMANHO * 0.028
    espessura = int(TAMANHO * 0.045)
    for i, y_frac in enumerate((0.36, 0.5, 0.64)):
        y = TAMANHO * y_frac
        draw.ellipse(
            [x_bolinha - raio_bolinha, y - raio_bolinha, x_bolinha + raio_bolinha, y + raio_bolinha],
            fill=BRANCO,
        )
        draw.line(
            [(x_linha_inicio, y), (x_linha_inicio + largura_linha, y)],
            fill=BRANCO, width=espessura,
        )

    img = img.resize((TAMANHO_FINAL, TAMANHO_FINAL), Image.LANCZOS)
    img.save(caminho)
    print(f"gerado {caminho}")


def gerar_icone_instagram(caminho: str) -> None:
    img = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    fundo = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
    pixels = fundo.load()
    for y in range(TAMANHO):
        for x in range(TAMANHO):
            t = (x + (TAMANHO - y)) / (2 * TAMANHO)  # diagonal inferior-esq -> superior-dir
            r, g, b = _cor_gradiente(t)
            pixels[x, y] = (r, g, b, 255)

    # máscara de "rounded square" (raio ~22% do lado, igual ao glifo oficial)
    mascara = Image.new("L", (TAMANHO, TAMANHO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, TAMANHO - 1, TAMANHO - 1], radius=int(TAMANHO * 0.22), fill=255
    )
    img.paste(fundo, (0, 0), mascara)

    draw = ImageDraw.Draw(img)
    centro = TAMANHO / 2
    raio_lente = TAMANHO * 0.20
    espessura = int(TAMANHO * 0.045)
    draw.ellipse(
        [centro - raio_lente, centro - raio_lente, centro + raio_lente, centro + raio_lente],
        outline=BRANCO, width=espessura,
    )
    # ponto do "flash", canto superior direito
    raio_ponto = TAMANHO * 0.028
    cx, cy = TAMANHO * 0.74, TAMANHO * 0.26
    draw.ellipse([cx - raio_ponto, cy - raio_ponto, cx + raio_ponto, cy + raio_ponto], fill=BRANCO)

    img = img.resize((TAMANHO_FINAL, TAMANHO_FINAL), Image.LANCZOS)
    img.save(caminho)
    print(f"gerado {caminho}")


if __name__ == "__main__":
    gerar_icone_regras("static/images/email-icone-regras.png")
    gerar_icone_instagram("static/images/email-icone-instagram.png")
