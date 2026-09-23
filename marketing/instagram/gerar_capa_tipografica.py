"""Capa de reel tipográfica: só texto, ocupando o quadro.

Alternativa à capa com foto (`gerar_capa_reel.py`), para reel em que ninguém aparece ou
cujo quadro não rende uma boa capa.

A peça é o título. Nasceu com um painel roxo e a moeda da marca no pé, e o dono do
produto pediu para tirar os dois - sem eles, texto em corpo médio boiava num quadro
vazio. Agora o título é dimensionado para preencher: wordmark no topo, título grande
ocupando o miolo, linha de apoio e régua fechando embaixo.

**O corpo do título não é escrito na mão.** `_maior_corpo_que_cabe()` procura, por busca
binária no navegador, o maior tamanho em que o texto ainda cabe na largura sem estourar
e não passa da altura reservada. Número fixo obrigaria a reajustar à mão a cada troca de
texto - e "Como ganhar cashback na Shopee?" e "3 formas de ganhar cashback" não cabem no
mesmo corpo. Trocar TITULO e rodar de novo basta.

A mancha lilás do pé é degradê radial, sem borda definida: um círculo, por mais claro
que fosse, lia como elemento gráfico cortado ao meio - e o pedido foi tirar os elementos
gráficos, não trocá-los de lugar. Sem borda, vira temperatura de fundo.

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

MARGEM = 72

# A capa aparece em três recortes diferentes, e o mais apertado que NÃO dá para escolher
# é o do feed, em 4:5 - o Instagram tira 285px de cima e 285 de baixo do quadro 9:16.
# (O da grade do perfil tem aba própria no editor, então esse é escolhido na mão.)
# Nada que precise ser lido pode ficar fora da faixa que sobra: y 285 a 1635.
#
# As margens abaixo são maiores que essa faixa de propósito, com folga: 320 em cima
# mantém o wordmark dentro do recorte do feed, e 320 embaixo deixa o rodapé acima tanto
# do corte do feed quanto da barra de nome e legenda que o player escreve sobre o vídeo.
CORTE_FEED = 285
TOPO, BASE = 320, 320
# Altura reservada ao título, dentro do que sobra entre as duas margens.
ALTURA_TITULO = 900

# "na Shopee?" vai travado: solto, o ajuste automático cresce até a preposição cair
# sozinha numa linha, e "na" órfão no meio de um cartaz lê como erro de diagramação.
# Travado, ele vira a unidade mais larga do título e passa a governar o corpo escolhido.
TITULO = (
    'Como ganhar <span class="grifo">cashback</span> '
    '<span class="junto">na Shopee?</span>'
)
CHAMADA = "é mais fácil do que você imagina"


def _pagina(corpo_titulo: int) -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{LIGHT_BG};
        font-family:"Familjen", Arial, sans-serif; overflow:hidden;
    }}
    body {{
        position:relative; display:flex; flex-direction:column;
        justify-content:space-between; padding:{TOPO}px {MARGEM}px {BASE}px;
    }}
    .mancha {{
        position:absolute; inset:0;
        background:radial-gradient(900px 760px at 12% 104%,
            rgba(167,139,250,0.40) 0%, rgba(167,139,250,0.14) 45%, rgba(167,139,250,0) 72%);
    }}
    .marca {{
        position:relative; font-size:78px; font-weight:700;
        letter-spacing:-0.04em; color:{BRAND_PRIMARY};
    }}
    /* Entrelinha abaixo de 1: a caixa de linha da Familjen reserva bastante espaço
       acima e abaixo da tinta, e em corpo de cartaz isso abre um vão entre as linhas
       maior que a altura das letras. Apertar para 0.94 junta o bloco sem encostar
       ascendente em descendente. */
    #titulo {{
        position:relative; font-size:{corpo_titulo}px; font-weight:700;
        line-height:0.94; letter-spacing:-0.045em; color:{DARK_BG};
    }}
    .grifo {{ color:{BRAND_PRIMARY}; white-space:nowrap; }}
    .junto {{ white-space:nowrap; }}
    .rodape {{ position:relative; }}
    .chamada {{
        font-size:34px; font-weight:600; letter-spacing:0.18em;
        text-transform:uppercase; color:{MUTED}; line-height:1.5;
    }}
    .regua {{ margin-top:34px; width:150px; height:10px; border-radius:99px; background:{BRAND_PRIMARY}; }}
    </style></head><body>
        <div class="mancha"></div>
        <div class="marca">{MARCA}</div>
        <div id="titulo">{TITULO}</div>
        <div class="rodape">
            <div class="chamada">{CHAMADA}</div>
            <div class="regua"></div>
        </div>
    </body></html>"""


def _maior_corpo_que_cabe(pagina, minimo=80, maximo=300) -> int:
    """Busca binária pelo maior corpo de fonte que ainda cabe.

    Duas restrições. A largura é a que quebra a peça: uma palavra mais larga que a
    coluna vaza para fora do quadro e sai cortada no arquivo. A altura é o limite do
    espaço reservado ao título, para não invadir o rodapé.

    Medir no navegador em vez de estimar por contagem de caracteres: a largura real
    depende do desenho de cada letra e do letter-spacing negativo, e "Shopee?" e
    "cashback" têm o mesmo número de letras com larguras bem diferentes.
    """
    largura_coluna = LARGURA - MARGEM * 2

    def cabe(corpo: int) -> bool:
        pagina.set_content(_pagina(corpo))
        return pagina.evaluate(
            """([largura, altura]) => {
                const el = document.getElementById("titulo");
                const r = document.createRange();
                let maior = 0;
                for (const no of el.childNodes) {
                    r.selectNodeContents(no);
                    for (const caixa of r.getClientRects()) maior = Math.max(maior, caixa.width);
                }
                return maior <= largura && el.offsetHeight <= altura;
            }""",
            [largura_coluna, ALTURA_TITULO],
        )

    while minimo < maximo:
        meio = (minimo + maximo + 1) // 2
        if cabe(meio):
            minimo = meio
        else:
            maximo = meio - 1
    return minimo


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = OUT_DIR / "capa-tipografica.png"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        corpo = _maior_corpo_que_cabe(pagina)
        pagina.set_content(_pagina(corpo))
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")
    print(f"corpo do título escolhido: {corpo}px")


if __name__ == "__main__":
    gerar()
