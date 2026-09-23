"""Capa de reel tipográfica: só texto, ocupando o quadro. Quatro formatos.

Alternativa à capa com foto (`gerar_capa_reel.py`), para reel em que ninguém aparece ou
cujo quadro não rende uma boa capa.

A peça é o título. Nasceu com um painel roxo e a moeda da marca no pé, e o dono do
produto pediu para tirar os dois - sem eles, texto em corpo médio boiava num quadro
vazio, então o título passou a ser dimensionado para preencher.

Os quatro formatos mudam só como a marca entra, que foi o ponto seguinte levantado: ela
estava discreta demais. São alternativas para escolher, não evolução uma da outra.

| Formato | A marca |
|---|---|
| `a-topo` | Wordmark grande no alto, à esquerda |
| `b-pastilha` | Wordmark claro dentro de uma pastilha roxa |
| `c-assinatura` | Título no alto e wordmark grande fechando o pé |
| `d-faixa` | Faixa roxa sangrando no topo, wordmark claro dentro |

**O corpo do título não é escrito na mão.** `_maior_corpo_que_cabe()` procura, por busca
binária no navegador, o maior tamanho em que o texto ainda cabe na largura sem estourar
e não passa da altura reservada - que muda de um formato para o outro, conforme o espaço
que a marca ocupa. Trocar TITULO e rodar de novo basta.

**Área segura.** A capa aparece em três recortes, e o mais apertado que NÃO dá para
escolher é o do feed, em 4:5: o Instagram tira 285px de cima e 285 de baixo do quadro
9:16. (O da grade do perfil tem aba própria no editor.) Nada que precise ser lido pode
sair da faixa y 285-1635 - as margens de 320 dão folga sobre ela. A faixa roxa do
formato `d` sangra de propósito: o que precisa estar dentro é o wordmark, não a caixa.

O nome "Shopee" aparece como texto, e o logotipo dela não aparece: a cash-b é afiliada
independente (é o que o rodapé do site declara), e arte carregando a marca da Shopee
sugere um vínculo que não existe.

Como usar:
    python3 gerar_capa_tipografica.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import (
    BRAND_DARK,
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
CORTE_FEED = 285          # o que o recorte 4:5 do feed tira de cada ponta
TOPO, BASE = 320, 320     # margens com folga sobre esse corte

# "na Shopee?" vai travado: solto, o ajuste automático cresce até a preposição cair
# sozinha numa linha, e "na" órfão no meio de um cartaz lê como erro de diagramação.
# Travado, ele vira a unidade mais larga do título e passa a governar o corpo escolhido.
TITULO = (
    'Como ganhar <span class="grifo">cashback</span> '
    '<span class="junto">na Shopee?</span>'
)
CHAMADA = "é mais fácil do que você imagina"

ALTURA_FAIXA = 500

# Cada formato: como a marca entra, quanto de altura sobra para o título e o que fica
# centralizado. "marca" centraliza só o logo e mantém o título à esquerda; "tudo"
# centraliza a peça inteira.
VARIANTES = {
    "a-topo":        {"marca": "texto",      "titulo": 820, "centro": ""},
    "b-pastilha":    {"marca": "pastilha",   "titulo": 820, "centro": ""},
    "c-assinatura":  {"marca": "assinatura", "titulo": 760, "centro": ""},
    "d-faixa":       {"marca": "faixa",      "titulo": 700, "centro": ""},
    "e-topo-centro": {"marca": "texto",      "titulo": 820, "centro": "marca"},
    "f-tudo-centro": {"marca": "texto",      "titulo": 820, "centro": "tudo"},
    "g-faixa-centro":{"marca": "faixa",      "titulo": 700, "centro": "marca"},
    "h-faixa-tudo":  {"marca": "faixa",      "titulo": 700, "centro": "tudo"},
}

# A faixa é posicionada por fora do fluxo, então não empurra nada: o título subiria por
# baixo dela e colidiria com o wordmark. Todo formato com faixa começa abaixo dela.
TOPO_POR_VARIANTE = {
    nome: ALTURA_FAIXA + 60 for nome, cfg in VARIANTES.items() if cfg["marca"] == "faixa"
}


def _marca(cfg: dict) -> str:
    if cfg["marca"] == "pastilha":
        return f'<div class="pastilha">{MARCA}</div>'
    if cfg["marca"] == "faixa":
        return f'<div class="faixa"><span>{MARCA}</span></div>'
    return f'<div class="marca">{MARCA}</div>'


def _rodape(cfg: dict) -> str:
    apoio = f'<div class="chamada">{CHAMADA}</div><div class="regua"></div>'
    if cfg["marca"] == "assinatura":
        # Aqui a marca fecha a composição: é ela a assinatura, no lugar de só uma régua.
        return f'<div class="rodape">{apoio}<div class="assinatura">{MARCA}</div></div>'
    return f'<div class="rodape">{apoio}</div>'


def _pagina(variante: str, corpo_titulo: int) -> str:
    cfg = VARIANTES[variante]
    # No formato de assinatura a marca sai do topo e vai para o pé.
    topo = "" if cfg["marca"] == "assinatura" else _marca(cfg)
    classe_corpo = f'centro-{cfg["centro"]}' if cfg["centro"] else ""
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{LIGHT_BG};
        font-family:"Familjen", Arial, sans-serif; overflow:hidden;
    }}
    body {{
        position:relative; display:flex; flex-direction:column;
        justify-content:space-between;
        padding:{TOPO_POR_VARIANTE.get(variante, TOPO)}px {MARGEM}px {BASE}px;
    }}
    /* Centralizar só a marca: ela vira cabeçalho da peça, e o título segue alinhado à
       esquerda como bloco de leitura. Centralizar tudo: a peça vira cartaz simétrico -
       aí a régua também precisa de margem automática, senão fica presa à esquerda. */
    .centro-marca > .marca, .centro-marca > .pastilha {{ align-self:center; }}
    .centro-marca .faixa, .centro-tudo .faixa {{ justify-content:center; padding-left:0; padding-right:0; }}
    .centro-tudo {{ text-align:center; align-items:center; }}
    .centro-tudo .regua {{ margin-left:auto; margin-right:auto; }}
    /* Degradê radial, não um círculo: forma de borda definida lia como elemento gráfico
       cortado ao meio, e o pedido foi tirar os elementos gráficos. Sem borda, vira
       temperatura de fundo - segura a metade de baixo sem colocar nada ali. */
    .mancha {{
        position:absolute; inset:0;
        background:radial-gradient(900px 760px at 12% 104%,
            rgba(167,139,250,0.40) 0%, rgba(167,139,250,0.14) 45%, rgba(167,139,250,0) 72%);
    }}
    .marca {{
        position:relative; font-size:124px; font-weight:700;
        letter-spacing:-0.045em; color:{BRAND_PRIMARY}; line-height:1;
    }}
    .pastilha {{
        position:relative; align-self:flex-start;
        padding:26px 52px; border-radius:999px; background:{BRAND_PRIMARY};
        font-size:82px; font-weight:700; letter-spacing:-0.04em; color:{LIGHT_BG}; line-height:1.1;
    }}
    /* Sangra nas três bordas de propósito: faixa com margem lateral vira um retângulo
       pousado na página, e o que se quer é que ela seja o topo da página. O corte de
       285px do feed come parte dela sem prejuízo - o wordmark está bem abaixo disso. */
    .faixa {{
        position:absolute; top:0; left:0; right:0; height:{ALTURA_FAIXA}px;
        background:linear-gradient(160deg, {BRAND_DARK} 0%, {BRAND_PRIMARY} 100%);
        display:flex; align-items:flex-end; padding:0 {MARGEM}px 54px;
    }}
    .faixa span {{
        font-size:104px; font-weight:700; letter-spacing:-0.045em; color:{LIGHT_BG}; line-height:1;
    }}
    /* Entrelinha abaixo de 1: a caixa de linha da Familjen reserva bastante espaço acima
       e abaixo da tinta, e em corpo de cartaz isso abre um vão entre as linhas maior que
       a altura das letras. */
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
    .assinatura {{
        margin-top:56px; font-size:132px; font-weight:700;
        letter-spacing:-0.045em; color:{BRAND_PRIMARY}; line-height:1;
    }}
    </style></head><body class="{classe_corpo}">
        <div class="mancha"></div>
        {topo}
        <div id="titulo">{TITULO}</div>
        {_rodape(cfg)}
    </body></html>"""


def _maior_corpo_que_cabe(pagina, variante: str, minimo=80, maximo=300) -> int:
    """Busca binária pelo maior corpo de fonte que ainda cabe.

    Duas restrições. A largura é a que quebra a peça: uma palavra mais larga que a coluna
    vaza para fora do quadro e sai cortada no arquivo. A altura é o limite do espaço
    reservado ao título no formato, para não invadir a marca nem o rodapé.

    Medido no navegador em vez de estimado por contagem de caracteres: a largura real
    depende do desenho de cada letra e do letter-spacing negativo - "Shopee?" e
    "cashback" têm o mesmo número de letras e larguras bem diferentes.
    """
    largura_coluna = LARGURA - MARGEM * 2
    altura_alvo = VARIANTES[variante]["titulo"]

    def cabe(corpo: int) -> bool:
        pagina.set_content(_pagina(variante, corpo))
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
            [largura_coluna, altura_alvo],
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
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        for variante in VARIANTES:
            corpo = _maior_corpo_que_cabe(pagina, variante)
            pagina.set_content(_pagina(variante, corpo))
            pagina.wait_for_timeout(300)
            destino = OUT_DIR / f"capa-{variante}.png"
            pagina.screenshot(path=str(destino))
            print(f"gerado: {destino.relative_to(REPO_ROOT)} (título a {corpo}px)")
        navegador.close()


if __name__ == "__main__":
    gerar()
