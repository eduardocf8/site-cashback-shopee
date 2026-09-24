"""Fundos abstratos da marca: manchas e arcos.

Família de fundos para banner de e-mail, capa, story e qualquer peça que precise de um
plano de fundo com cara de cash-b e o miolo livre para texto.

O estilo veio de uma rodada de geração por IA que o dono do produto aprovou - abstrato,
minimalista, sem objeto nenhum. Desenhar aqui em vez de gerar resolve quatro coisas de
uma vez: a cor sai no hex exato da paleta (o gerador dava um roxo aproximado e um âmbar
dessaturado), a composição é ajustável, sai em qualquer tamanho sem recortar, e não
depende de cota de serviço externo nem de download.

A regra da família, para variações futuras manterem a mesma cara:

- Só dois elementos: mancha arredondada e arco fino.
- Tudo encostado nas bordas, sangrando para fora. Forma inteira e centralizada lê como
  adesivo; forma cortada pela borda lê como recorte de um sistema maior.
- O miolo fica vazio. É onde o texto cai, e é o que diferencia fundo de ilustração.
- Monocromático, só roxo. Os pontos âmbar que existiam aqui saíram por decisão do dono
  do produto: num fundo, o âmbar compete com o destaque do próprio texto que vai por
  cima - e é o texto que precisa da cor de atenção, não o plano de fundo.

Cada composição tem um papel. Sem isso o conjunto vira menu, e escolher no chute a cada
peça é o que faz uma marca parecer seis marcas:

| Composição | Quando usar |
|---|---|
| `01-manchas` | Peça curta e solta: um aviso, um story de recado |
| `02-ondas` | Peça com muito texto - é o mais silencioso, só linha |
| `03-canto` | **Padrão.** Usa este quando não houver motivo para outro |
| `04-moldura` | Texto centralizado, que pede simetria |
| `05-diagonal` | Campanha e data dupla: o de mais energia |
| `06-halo` | Fechamento e assinatura: os arcos emolduram a marca no centro |

Como usar:
    python3 marketing/gerar_fundos_marca.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / "fundos-marca"

BRAND = "#6d28d9"
BRAND_DARK = "#4c1d95"
BRAND_LIGHT = "#a78bfa"
PAPER = "#f8fafc"

# Formatos em que cada fundo é gerado - as proporções que as peças realmente usam.
# Cada um é REDESENHADO, não recortado: as posições são calculadas em porcentagem do
# quadro, então a mancha cai no mesmo canto seja qual for a proporção. Recortar um
# 16:9 para virar story faria a mancha ou os arcos saírem fora, dependendo de onde o
# corte caísse. Formato novo é uma linha aqui.
FORMATOS = {
    "16x9": (1536, 864),    # banner de e-mail
    "4x5": (1080, 1350),    # post e carrossel de feed
    "9x16": (1080, 1920),   # story e capa de reel
    "1x1": (1080, 1080),    # avatar, miniatura, capa de destaque
}
ESCALA = 1


def _mancha(cx, cy, r, cor=BRAND_LIGHT, opacidade=0.22):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{cor}" opacity="{opacidade}"/>'


def _arcos(cx, cy, raio_inicial, quantidade=5, passo=26, cor=BRAND_LIGHT, opacidade=0.30):
    """Arcos concêntricos. Desenhados como círculos sem preenchimento: fora do quadro
    eles somem sozinhos, e o que sobra na borda é o rastro que dá profundidade."""
    return "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{raio_inicial + i * passo}" fill="none" '
        f'stroke="{cor}" stroke-width="2.5" opacity="{opacidade}"/>'
        for i in range(quantidade)
    )



def _manchas(l, a):
    return (
        _mancha(l * 0.04, a * 0.06, min(l, a) * 0.30)
        + _mancha(l * 0.98, a * 0.92, min(l, a) * 0.34)
        + _arcos(l * 0.97, a * 0.10, min(l, a) * 0.17, 4)
    )


def _ondas(l, a):
    return (
        _arcos(-l * 0.10, a * 1.05, min(l, a) * 0.28, 7, min(l, a) * 0.045)
        + _arcos(l * 1.10, -a * 0.05, min(l, a) * 0.28, 7, min(l, a) * 0.045)
    )


def _canto(l, a):
    """Mancha grande num canto, com os arcos da composição 01 no canto oposto.

    Era a mais silenciosa da família, com peso só embaixo à esquerda - o que deixava a
    diagonal oposta completamente morta. Os arcos no alto à direita fecham a diagonal
    sem encher o quadro: são linha, não massa, então equilibram a composição e o miolo
    continua livre para o texto."""
    return (
        _mancha(l * 0.02, a * 1.02, min(l, a) * 0.52, BRAND_LIGHT, 0.20)
        + _mancha(l * 0.16, a * 0.92, min(l, a) * 0.26, BRAND_LIGHT, 0.16)
        + _arcos(l * 0.97, a * 0.10, min(l, a) * 0.17, 4)
    )


def _moldura(l, a):
    """Manchas nos quatro cantos, miolo totalmente limpo. O mais simétrico - bom quando
    o texto é centralizado."""
    r = min(l, a) * 0.26
    return (
        _mancha(0, 0, r) + _mancha(l, 0, r * 0.8)
        + _mancha(0, a, r * 0.85) + _mancha(l, a, r)
    )


def _diagonal(l, a):
    """Uma elipse larga atravessando o quadro na diagonal. É a de mais energia da
    família - a inclinação dá movimento que mancha redonda não dá -, e por isso a
    indicada para campanha. Continua sendo mancha: só esticada e girada."""
    d = max(l, a)
    return (
        f'<ellipse cx="{l * 0.5}" cy="{a * 0.5}" rx="{d * 0.85}" ry="{d * 0.16}" '
        f'fill="{BRAND_LIGHT}" opacity="0.16" '
        f'transform="rotate(-24 {l * 0.5} {a * 0.5})"/>'
        + f'<ellipse cx="{l * 0.62}" cy="{a * 0.66}" rx="{d * 0.70}" ry="{d * 0.10}" '
        f'fill="{BRAND_LIGHT}" opacity="0.12" '
        f'transform="rotate(-24 {l * 0.62} {a * 0.66})"/>'
        + _arcos(l * 0.02, a * 0.04, min(l, a) * 0.14, 4)
    )


def _halo(l, a):
    """Arcos concêntricos centrados no meio, formando um halo. Ao contrário do resto da
    família, aqui o centro NÃO fica vazio - é o único caso em que o fundo emoldura em
    vez de se afastar. Serve para peça de fechamento, onde o que fica no meio é a marca
    ou uma frase curta, não um bloco de texto."""
    return (
        _arcos(l * 0.5, a * 0.5, min(l, a) * 0.30, 6, min(l, a) * 0.055, opacidade=0.22)
        + _mancha(l * 0.5, a * 0.5, min(l, a) * 0.26, BRAND_LIGHT, 0.10)
    )


COMPOSICOES = {
    "01-manchas": _manchas,
    "02-ondas": _ondas,
    "03-canto": _canto,
    "04-moldura": _moldura,
    "05-diagonal": _diagonal,
    "06-halo": _halo,
}


def _svg(composicao, l, a, claro: bool) -> str:
    if claro:
        fundo = f'<rect width="{l}" height="{a}" fill="{PAPER}"/>'
        # No claro a mancha precisa de mais tinta para existir: a mesma opacidade que
        # funciona sobre o roxo escuro some sobre o quase branco.
        corpo = composicao(l, a).replace('opacity="0.22"', 'opacity="0.30"') \
                                .replace('opacity="0.20"', 'opacity="0.28"') \
                                .replace('opacity="0.16"', 'opacity="0.24"') \
                                .replace('opacity="0.30"', 'opacity="0.38"')
    else:
        fundo = (f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                 f'<stop offset="0" stop-color="{BRAND_DARK}"/>'
                 f'<stop offset="1" stop-color="{BRAND}"/></linearGradient></defs>'
                 f'<rect width="{l}" height="{a}" fill="url(#g)"/>')
        corpo = composicao(l, a)
    return (f'<svg width="{l}" height="{a}" viewBox="0 0 {l} {a}" '
            f'xmlns="http://www.w3.org/2000/svg">{fundo}{corpo}</svg>')


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for nome, composicao in COMPOSICOES.items():
            for formato, (l, a) in FORMATOS.items():
                for claro in (False, True):
                    tom = "claro" if claro else "roxo"
                    pagina = navegador.new_page(
                        viewport={"width": l, "height": a}, device_scale_factor=ESCALA
                    )
                    pagina.set_content(
                        f"<html><body style='margin:0'>{_svg(composicao, l, a, claro)}</body></html>"
                    )
                    pagina.wait_for_timeout(120)
                    destino = OUT_DIR / f"fundo-{nome}-{tom}-{formato}.png"
                    pagina.screenshot(path=str(destino))
                    pagina.close()
        navegador.close()
    print(f"gerados {len(COMPOSICOES) * len(FORMATOS) * 2} fundos em "
          f"{OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    gerar()
