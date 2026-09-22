"""Moldura de celular para encaixar gravação de tela no vídeo, e fundo roxo chapado.

A moldura tem a área da tela VAZADA de verdade (alfa 0), não pintada de preto: a
gravação entra numa camada atrás da moldura e aparece pelo buraco. Mockup com tela
opaca obrigaria a recortar o vídeo na mão, e o canto arredondado nunca sairia limpo.

Por isso o desenho é feito em SVG com máscara, e não com caixas de CSS: a máscara
recorta o buraco com antisserrilhado, e a sombra é desenhada DENTRO do grupo mascarado -
sem isso ela vazaria para dentro da tela e mancharia o topo da gravação.

Sem notch nem ilha dinâmica de propósito. A gravação de tela já traz a barra de status
do aparelho; um recorte desenhado por cima apareceria como uma segunda barra, sobre a
que já existe na imagem.

A abertura é 1080x2268 reduzido - a proporção da tela do aparelho que gravou (a mesma
das capturas mandadas no chat). Assim a gravação entra sem corte nenhum.

A moldura já sai posicionada num quadro de 1080x1920: é só arrastar para a linha do
tempo, sem escala nem posição para acertar.

Como usar:
    python3 gerar_moldura_celular.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import BRAND_PRIMARY, DARK_BG

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "moldura-celular"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

# Abertura da tela. 740/1554 = 0,476190, a mesma proporção de 1080x2268 - a tela do
# aparelho que gravou. Gravação em outra proporção entra igual, só com um corte mínimo
# nas pontas ao ser ajustada para preencher.
TELA_L, TELA_A = 740, 1554
MOLDURA = 26  # espessura da borda em volta da tela
RAIO_CORPO, RAIO_TELA = 92, 68

CORPO_L, CORPO_A = TELA_L + MOLDURA * 2, TELA_A + MOLDURA * 2
CORPO_X, CORPO_Y = (LARGURA - CORPO_L) // 2, (ALTURA - CORPO_A) // 2
TELA_X, TELA_Y = CORPO_X + MOLDURA, CORPO_Y + MOLDURA

TRILHO = "#4b5563"  # o brilho da lateral metálica


def _botao(x, y, altura, largura=7):
    """Botão lateral. Fica colado na borda do corpo, para ler como volume/power."""
    return (f'<rect x="{x}" y="{y}" width="{largura}" height="{altura}" rx="{largura // 2}" '
            f'fill="{TRILHO}"/>')


def _svg() -> str:
    botoes = (
        # volume, na esquerda; power, na direita
        _botao(CORPO_X - 7, CORPO_Y + 300, 110)
        + _botao(CORPO_X - 7, CORPO_Y + 440, 110)
        + _botao(CORPO_X + CORPO_L, CORPO_Y + 380, 170)
    )
    return f"""
    <svg width="{LARGURA}" height="{ALTURA}" viewBox="0 0 {LARGURA} {ALTURA}"
         xmlns="http://www.w3.org/2000/svg">
      <defs>
        <!-- Branco onde a arte fica, preto onde o buraco da tela é aberto. -->
        <mask id="buraco">
          <rect width="{LARGURA}" height="{ALTURA}" fill="#fff"/>
          <rect x="{TELA_X}" y="{TELA_Y}" width="{TELA_L}" height="{TELA_A}"
                rx="{RAIO_TELA}" fill="#000"/>
        </mask>
        <filter id="sombra" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="26"/>
        </filter>
      </defs>
      <!-- Tudo dentro do grupo mascarado, inclusive a sombra: fora dele, a sombra
           entraria por baixo do buraco e escureceria o topo da gravação. -->
      <g mask="url(#buraco)">
        <rect x="{CORPO_X}" y="{CORPO_Y + 22}" width="{CORPO_L}" height="{CORPO_A}"
              rx="{RAIO_CORPO}" fill="#000" opacity="0.45" filter="url(#sombra)"/>
        {botoes}
        <rect x="{CORPO_X}" y="{CORPO_Y}" width="{CORPO_L}" height="{CORPO_A}"
              rx="{RAIO_CORPO}" fill="{DARK_BG}"/>
        <rect x="{CORPO_X + 2}" y="{CORPO_Y + 2}" width="{CORPO_L - 4}" height="{CORPO_A - 4}"
              rx="{RAIO_CORPO - 2}" fill="none" stroke="{TRILHO}" stroke-width="4"/>
      </g>
    </svg>
    """


def _render(corpo: str, destino: Path, fundo: str = "transparent"):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(
            f"<html><body style='margin:0;width:{LARGURA}px;height:{ALTURA}px;"
            f"background:{fundo};'>{corpo}</body></html>"
        )
        pagina.wait_for_timeout(200)
        pagina.screenshot(path=str(destino), omit_background=fundo == "transparent")
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar():
    _render(_svg(), OUT_DIR / "moldura-celular.png")
    _render("", OUT_DIR / "fundo-roxo.png", BRAND_PRIMARY)

    print(
        f"\nAbertura da tela, em pixels do quadro de {LARGURA}x{ALTURA}:\n"
        f"  {TELA_L} x {TELA_A}, com o canto superior esquerdo em ({TELA_X}, {TELA_Y}).\n"
        f"  Centralizada na horizontal; na vertical, {TELA_Y}px do topo.\n"
        f"  Gravação de 1080 de largura entra a {TELA_L / 1080:.1%}."
    )


if __name__ == "__main__":
    gerar()
