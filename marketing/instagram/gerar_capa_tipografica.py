"""Capa de reel tipográfica: só texto sobre o claro, sem foto e sem ilustração.

Alternativa à capa com foto (`gerar_capa_reel.py`), para reel em que ninguém aparece ou
cujo quadro não rende uma boa capa.

Nasceu com um painel roxo e a moeda da marca no pé, e o dono do produto pediu para tirar
os dois - a peça ficou só com o bloco de texto. A construção que sobrou é o que ele
aprovou: wordmark no topo, título grande com a palavra-chave em roxo, linha de apoio em
caixa alta espaçada e a régua curta fechando o bloco.

Sem elemento gráfico no pé, o vazio de baixo passa a ser parte da composição e não uma
sobra. Duas decisões seguram isso:

- O bloco de texto desce um pouco em relação ao topo, para o peso ficar no meio do
  quadro em vez de empilhado em cima.
- Uma mancha lilás difusa sobe do canto inferior esquerdo. É degradê radial, sem borda
  definida: um círculo, por mais claro que fosse, lia como elemento gráfico cortado ao
  meio, e o pedido foi tirar os elementos gráficos, não trocá-los de lugar. Sem borda,
  vira temperatura de fundo - impede a metade de baixo de ler como área não terminada
  sem colocar nada ali.

O nome "Shopee" aparece como texto, e o logotipo dela não aparece: a cash-b é afiliada
independente (é o que o rodapé do site declara), e arte carregando a marca da Shopee
sugere um vínculo que não existe.

Como usar:
    python3 gerar_capa_tipografica.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import (
    BRAND_PRIMARY,
    DARK_BG,
    FAMILJEN_B64,
    LIGHT_BG,
    MARCA,
    MUTED,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "capa-reel"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

TITULO = 'Como ganhar <span class="grifo">cashback</span> na Shopee?'
CHAMADA = "é mais fácil do que você imagina"


def _pagina() -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{LIGHT_BG};
        font-family:"Familjen", Arial, sans-serif; overflow:hidden;
    }}
    body {{ position:relative; }}
    /* Degradê radial, e não um círculo de borda definida: o círculo, por mais claro que
       fosse, lia como um elemento gráfico cortado ao meio - e o pedido foi tirar os
       elementos gráficos, não trocá-los de lugar. Sem borda, isso vira temperatura de
       fundo: segura a metade de baixo sem colocar nada ali. */
    .mancha {{
        position:absolute; inset:0;
        background:radial-gradient(900px 760px at 12% 104%,
            rgba(167,139,250,0.40) 0%, rgba(167,139,250,0.14) 45%, rgba(167,139,250,0) 72%);
    }}
    .marca {{
        position:absolute; top:150px; left:90px;
        font-size:78px; font-weight:700; letter-spacing:-0.04em; color:{BRAND_PRIMARY};
    }}
    /* Bloco de texto abaixo do topo, não colado nele: sem nada no pé do quadro, o peso
       precisa cair mais para o meio, senão a capa fica empilhada em cima e oca embaixo. */
    .texto {{ position:absolute; top:500px; left:90px; right:90px; }}
    .titulo {{ font-size:104px; font-weight:700; line-height:1.04; letter-spacing:-0.04em; color:{DARK_BG}; }}
    .grifo {{ color:{BRAND_PRIMARY}; white-space:nowrap; }}
    .chamada {{
        margin-top:44px; font-size:30px; font-weight:600; letter-spacing:0.18em;
        text-transform:uppercase; color:{MUTED}; line-height:1.5;
    }}
    .regua {{ margin-top:40px; width:132px; height:9px; border-radius:99px; background:{BRAND_PRIMARY}; }}
    </style></head><body>
        <div class="mancha"></div>
        <div class="marca">{MARCA}</div>
        <div class="texto">
            <div class="titulo">{TITULO}</div>
            <div class="chamada">{CHAMADA}</div>
            <div class="regua"></div>
        </div>
    </body></html>"""


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = OUT_DIR / "capa-tipografica.png"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina())
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


if __name__ == "__main__":
    gerar()
