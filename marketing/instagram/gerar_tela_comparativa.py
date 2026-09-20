"""Tela comparativa "venda direta x venda indireta" para o reel.

Entra no resumo do roteiro (por volta de 0:50), enquanto a narração fecha a explicação
das três formas de comprar. É arte de apoio: quem está ouvindo já recebeu a informação,
a tela serve para fixar e para quem assiste sem som.

Por isso o texto é curto e os números são o elemento maior da peça. Em seis segundos de
tela ninguém lê parágrafo - lê dois números lado a lado e entende a diferença.

Os percentuais são os pisos reais do site (CASHBACK_MINIMO_VENDA_DIRETA e
CASHBACK_MINIMO_VENDA_INDIRETA em settings.py), e vêm rotulados como mínimo de
propósito: o cashback costuma ser maior que isso, e um número solto na tela viraria
promessa de teto.

Duas decisões de cor que fogem do "verde x amarelo" do semáforo:

- O âmbar da marca (HIGHLIGHT) é o selo de cashback dos cards de produto, que aparecem
  antes nesse mesmo reel. Usar âmbar aqui como "rende menos" faria a mesma cor dizer
  duas coisas opostas em um minuto de vídeo.
- Amarelo de semáforo lê como alerta, e a venda indireta não é erro - ela paga, só paga
  menos. É a linha editorial do carrossel 07, decidida pelo dono do produto: "Todas
  geram cashback, porém uma delas é menor". Cinza neutro diz "menos" sem dizer "cuidado".

Sai em duas etapas com as mesmas dimensões, para o bloco da indireta poder surgir
depois do da direta acompanhando a narração, sem nada se mexer na tela.

Gera também cada caixa sozinha, num arquivo próprio (caixa-direta.png e
caixa-indireta.png), para entrar por cima de um vídeo explicativo sem o cartão em
volta. Nessa versão a tinta de fundo é achatada contra branco: dentro do cartão ela é
translúcida e o branco aparece por trás, mas solta sobre filmagem a translucidez
deixaria a imagem passar e o texto perderia contraste. As duas saem do mesmo tamanho e
com a caixa no mesmo lugar do arquivo, então trocar uma pela outra não move nada.

Como usar:
    python3 gerar_tela_comparativa.py
"""
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import (
    BRAND_PRIMARY,
    DARK_BG,
    FAMILJEN_B64,
    JBMONO_B64,
    LIGHT_BG,
    MUTED,
    SUCCESS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "cards-produto"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2
# Topo do cartão. Abaixo da faixa que a interface do Instagram ocupa em cima, e alto o
# bastante para a etapa 2 inteira caber acima da faixa de baixo.
TOPO = 380

# Caixas soltas (uma por arquivo, para usar por cima de vídeo). A largura é a mesma que
# a caixa tem dentro do cartão - assim a peça solta e a tela comparativa são a mesma
# coisa, no mesmo corpo de texto, e podem aparecer no mesmo vídeo sem parecerem duas
# artes diferentes. A folga em volta existe para a sombra não sair cortada.
LARGURA_CAIXA = 792
FOLGA_CAIXA = 90
ALTURA_CAIXA = 500

# Pisos reais do site - settings.py. Escritos aqui porque o script roda sem Django.
MINIMO_DIRETA = "1,6%"
MINIMO_INDIRETA = "1%"

# O rótulo do botão é copiado do site (links/templates/links/home.html): na tela ele
# precisa ser igual ao que a pessoa vai procurar, letra por letra.
BOTAO_SHOPEE = "Botão &ldquo;Ir pra Shopee&rdquo;"


BLOCOS = {
    "direta": ("Compra direta", SUCCESS, "Link convertido ou vitrine", MINIMO_DIRETA),
    "indireta": ("Compra indireta", MUTED, BOTAO_SHOPEE, MINIMO_INDIRETA),
}


def _sobre_branco(cor: str, opacidade: float = 0.10) -> str:
    """A tinta de fundo do bloco, achatada contra branco.

    Dentro do cartão a tinta é translúcida e o branco do cartão aparece por trás. Solta
    sobre um vídeo não existe esse branco: a translucidez deixaria a filmagem passar e o
    texto perderia contraste. Calcular a mistura aqui dá a mesma cor de sempre, só que
    opaca - a caixa solta fica idêntica à que está dentro do cartão.
    """
    canais = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c * opacidade + 255 * (1 - opacidade)):02x}" for c in canais)


def _bloco(tag, cor, caminho, numero, solto=False):
    """Um lado da comparação. solto=True é a versão para usar fora do cartão."""
    fundo = _sobre_branco(cor) if solto else f"{cor}1a"
    classe = "bloco bloco-solto" if solto else "bloco"
    return f"""
    <div class="{classe}" style="border-left-color:{cor}; background:{fundo};">
        <div class="bloco-tag" style="color:{cor};">{tag}</div>
        <div class="bloco-caminho">{caminho}</div>
        <div class="bloco-numero">
            <span class="numero" style="color:{cor};">{numero}</span>
            <span class="numero-rotulo">no mínimo</span>
        </div>
    </div>
    """


def _pagina(corpo: str, largura: int, altura: int, fundo: str, alinhamento: str) -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{largura}px; height:{altura}px; background:{fundo};
        font-family:"Familjen", Arial, sans-serif;
    }}
    /* Ancorado pelo topo, não centralizado: assim a etapa 1 é um cartão mais curto e a
       etapa 2 cresce para baixo, com tudo que já estava na tela parado no mesmo pixel.
       Centralizado, a etapa 1 teria que reservar o espaço do bloco que ainda não
       apareceu - um vazio branco no meio da peça durante os segundos em que ela fica
       sozinha. O topo em {TOPO}px deixa as duas etapas dentro da faixa segura do reel,
       longe da interface do Instagram em cima e embaixo. */
    body {{ display:flex; align-items:{alinhamento}; justify-content:center; padding-top:{TOPO if alinhamento == "flex-start" else 0}px; }}
    /* Cartão branco opaco, e não os blocos soltos sobre o vídeo: as tintas de fundo
       dos blocos são translúcidas, então sem uma base opaca a filmagem apareceria
       através delas e o texto perderia contraste. Mesma linguagem dos cards de produto
       (branco, canto 40, sombra funda). */
    .cartao {{
        width:920px; padding:64px; border-radius:56px; background:#fff;
        box-shadow:0 40px 80px rgba(17,24,39,0.22);
    }}
    .tag {{
        font-size:26px; font-weight:700; letter-spacing:4px; text-transform:uppercase;
        color:{BRAND_PRIMARY}; margin-bottom:20px;
    }}
    .titulo {{ font-size:62px; font-weight:700; letter-spacing:-0.03em; line-height:1.1; color:{DARK_BG}; }}
    .subtitulo {{ font-size:36px; color:{MUTED}; margin-top:12px; line-height:1.3; }}
    /* A barra na lateral é o que diferencia os dois blocos à distância, antes de
       qualquer texto ser lido - mesmo recurso do destaque() dos carrosséis. */
    .bloco {{
        border-left:12px solid; border-radius:28px; padding:36px 40px; margin-top:36px;
    }}
    /* Solta sobre o vídeo, a caixa precisa da sombra para se descolar da filmagem - e
       da largura travada, para as duas saírem do mesmo tamanho. A altura vem travada
       pelo .bloco-caminho, logo abaixo. */
    .bloco-solto {{
        width:{LARGURA_CAIXA}px; margin-top:0;
        box-shadow:0 20px 44px rgba(17,24,39,0.20);
    }}
    .bloco-tag {{ font-size:26px; font-weight:700; letter-spacing:3px; text-transform:uppercase; }}
    /* min-height de uma linha: as duas frases cabem numa linha só, e reservar a altura
       garante que continuem saindo do mesmo tamanho se um dia uma delas crescer e
       quebrar - as duas caixas precisam ser intercambiáveis na linha do tempo. */
    .bloco-caminho {{
        font-size:38px; font-weight:600; color:{DARK_BG}; margin-top:14px; line-height:1.25;
        min-height:48px;
    }}
    /* baseline: o "no mínimo" senta na linha de base do número, não no meio dele. */
    .bloco-numero {{ display:flex; align-items:baseline; gap:20px; margin-top:22px; }}
    /* A mono é a fonte dos números da marca (é a do preço nos cards de produto), mas
       nela a vírgula ocupa a mesma largura de um dígito - a 112px isso abria um buraco
       no meio de "1,6%", que lia como dois números. O letter-spacing negativo fecha o
       vão sem trocar de fonte. */
    .numero {{ font-family:"JB Mono", monospace; font-size:112px; font-weight:700; letter-spacing:-0.06em; }}
    .numero-rotulo {{ font-size:32px; color:{MUTED}; }}
    </style></head><body>{corpo}</body></html>"""


def _tela(etapa: int) -> str:
    return f"""
    <div class="cartao">
        <div class="tag">na prática</div>
        <div class="titulo">Direta ou indireta</div>
        <div class="subtitulo">As duas geram cashback. Uma rende mais.</div>
        {_bloco(*BLOCOS["direta"])}
        {_bloco(*BLOCOS["indireta"]) if etapa >= 2 else ""}
    </div>
    """


def _render(corpo: str, destino: Path, largura: int, altura: int, fundo: str = "transparent",
            alinhamento: str = "flex-start"):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": largura, "height": altura}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(corpo, largura, altura, fundo, alinhamento))
        pagina.wait_for_timeout(250)
        pagina.screenshot(path=str(destino), omit_background=fundo == "transparent")
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({largura*ESCALA}x{altura*ESCALA})")


def gerar():
    for etapa, nome in [(1, "01-direta"), (2, "02-completo")]:
        _render(_tela(etapa), OUT_DIR / f"comparativo-{nome}.png", LARGURA, ALTURA)
        _render(_tela(etapa), OUT_DIR / f"comparativo-{nome}-fundo.png", LARGURA, ALTURA, LIGHT_BG)

    # As caixas sozinhas, uma por arquivo, para entrar por cima de um vídeo explicativo
    # sem o cartão em volta. Mesma tela para as duas, e as duas centralizadas nela: assim
    # saem do mesmo tamanho e no mesmo lugar, e trocar uma pela outra na edição não move
    # nada - mesma regra dos cards de produto e dos botões.
    for nome, dados in BLOCOS.items():
        _render(_bloco(*dados, solto=True), OUT_DIR / f"caixa-{nome}.png",
                LARGURA_CAIXA + FOLGA_CAIXA * 2, ALTURA_CAIXA, alinhamento="center")


if __name__ == "__main__":
    gerar()
