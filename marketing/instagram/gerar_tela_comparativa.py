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

# Pisos reais do site - settings.py. Escritos aqui porque o script roda sem Django.
MINIMO_DIRETA = "1,6%"
MINIMO_INDIRETA = "1%"

# O rótulo do botão é copiado do site (links/templates/links/home.html): na tela ele
# precisa ser igual ao que a pessoa vai procurar, letra por letra.
BOTAO_SHOPEE = "Botão &ldquo;Ir pra Shopee&rdquo;"


def _bloco(tag, cor, caminho, numero):
    """Um lado da comparação."""
    return f"""
    <div class="bloco" style="border-left-color:{cor}; background:{cor}1a;">
        <div class="bloco-tag" style="color:{cor};">{tag}</div>
        <div class="bloco-caminho">{caminho}</div>
        <div class="bloco-numero">
            <span class="numero" style="color:{cor};">{numero}</span>
            <span class="numero-rotulo">no mínimo</span>
        </div>
    </div>
    """


def _pagina(etapa: int, com_fundo: bool) -> str:
    fundo = LIGHT_BG if com_fundo else "transparent"
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{fundo};
        font-family:"Familjen", Arial, sans-serif;
    }}
    /* Ancorado pelo topo, não centralizado: assim a etapa 1 é um cartão mais curto e a
       etapa 2 cresce para baixo, com tudo que já estava na tela parado no mesmo pixel.
       Centralizado, a etapa 1 teria que reservar o espaço do bloco que ainda não
       apareceu - um vazio branco no meio da peça durante os segundos em que ela fica
       sozinha. O topo em {TOPO}px deixa as duas etapas dentro da faixa segura do reel,
       longe da interface do Instagram em cima e embaixo. */
    body {{ display:flex; align-items:flex-start; justify-content:center; padding-top:{TOPO}px; }}
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
    .bloco-tag {{ font-size:26px; font-weight:700; letter-spacing:3px; text-transform:uppercase; }}
    .bloco-caminho {{ font-size:38px; font-weight:600; color:{DARK_BG}; margin-top:14px; line-height:1.25; }}
    /* baseline: o "no mínimo" senta na linha de base do número, não no meio dele. */
    .bloco-numero {{ display:flex; align-items:baseline; gap:20px; margin-top:22px; }}
    /* A mono é a fonte dos números da marca (é a do preço nos cards de produto), mas
       nela a vírgula ocupa a mesma largura de um dígito - a 112px isso abria um buraco
       no meio de "1,6%", que lia como dois números. O letter-spacing negativo fecha o
       vão sem trocar de fonte. */
    .numero {{ font-family:"JB Mono", monospace; font-size:112px; font-weight:700; letter-spacing:-0.06em; }}
    .numero-rotulo {{ font-size:32px; color:{MUTED}; }}
    </style></head><body>
    <div class="cartao">
        <div class="tag">na prática</div>
        <div class="titulo">Direta ou indireta</div>
        <div class="subtitulo">As duas geram cashback. Uma rende mais.</div>
        {_bloco("Compra direta", SUCCESS, "Link convertido ou vitrine", MINIMO_DIRETA)}
        {_bloco("Compra indireta", MUTED, BOTAO_SHOPEE, MINIMO_INDIRETA) if etapa >= 2 else ""}
    </div>
    </body></html>"""


def _render(etapa: int, com_fundo: bool, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(etapa, com_fundo))
        pagina.wait_for_timeout(250)
        pagina.screenshot(path=str(destino), omit_background=not com_fundo)
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar():
    for etapa, nome in [(1, "01-direta"), (2, "02-completo")]:
        _render(etapa, False, OUT_DIR / f"comparativo-{nome}.png")
        _render(etapa, True, OUT_DIR / f"comparativo-{nome}-fundo.png")


if __name__ == "__main__":
    gerar()
