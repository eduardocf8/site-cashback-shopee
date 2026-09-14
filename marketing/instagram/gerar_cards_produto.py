"""Cards de produto para vídeo — dois por produto: só o preço, e com o cashback.

Feito para gravação: os dois cards de um mesmo produto saem na MESMA tela de
1080x1200, com o cartão preso no TOPO - não centralizado. Centralizado, o cartão com
cashback (mais alto) empurrava foto e preço para cima, e na troca durante o vídeo tudo
saltava de lugar. Preso no topo, foto, nome e preço ficam no mesmo pixel nos dois
arquivos e só o bloco de cashback aparece. Fundo transparente, para o cartão poder ser
posto sobre qualquer imagem do vídeo.

Os requisitos de escolha do produto (definidos pelo dono da marca) viram validação aqui
em cima em vez de ficarem num comentário: preço único (sem variação), cashback de 4%
para cima e três categorias diferentes. Dado que não cumpre isso derruba a geração, em
vez de virar um card publicado com produto errado.

A porcentagem de desconto não entra de propósito: o vídeo é sobre cashback, e desconto
na mesma arte divide a atenção entre dois números que não se somam.

Além dos cards soltos, gera a TIRA do carrossel: todos os cards lado a lado num PNG
só, terminando no card da marca. No editor, rolar o carrossel vira deslocar uma camada
no eixo X com curva de desaceleração - bem mais simples (e mais fiel ao movimento real
de um carrossel) do que animar oito camadas separadas.

O primeiro card da tira ocupa exatamente a mesma posição do card solto, então trocar um
pelo outro no momento da rolagem não move nada na tela.

Como usar:
    1. Preencha PRODUTOS abaixo com os dados que a vitrine mostra.
    2. Salve a foto de cada produto em cards-produto/fotos/.
    3. python3 gerar_cards_produto.py
"""
import base64
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "cards-produto"
FOTOS_DIR = OUT_DIR / "fotos"

CORES = {
    "ink": "#111827",
    "brand-strong": "#4c1d95",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "success": "#059669",
    "paper": "#f8fafc",
    "line": "#e0dcef",
}

# Regras de escolha do produto, aplicadas em _validar().
CASHBACK_MINIMO = Decimal("4")
TETO_POR_PRODUTO = Decimal("10")

LARGURA, ALTURA = 1080, 1200
LARGURA_CARTAO = 720
# Duas linhas de nome (34px x 1.25), reservadas mesmo quando o nome ocupa uma só.
ALTURA_NOME = 85
# Respiro entre um card e outro na tira do carrossel.
VAO = 60
# Margem nas pontas da tira - igual à sobra do card centralizado na tela de 1080,
# para o primeiro card da tira cair no mesmo pixel do card solto.
MARGEM_LATERAL = (LARGURA - LARGURA_CARTAO) // 2
# Folga embaixo para a sombra do cartão não ser cortada no arquivo mais alto.
MARGEM_TOPO = 40


# ---------------------------------------------------------------- produtos

# Preencha com o que a vitrine mostra. "preco" é um valor só de propósito: produto com
# faixa de preço (R$ 39 - R$ 88) não entra, porque o card mostraria um número que não é
# o que a pessoa vai pagar.
PRODUTOS = [
    # {
    #     "nome": "Nome curto do produto",
    #     "categoria": "Eletrônicos",
    #     "preco": "129.90",
    #     "percentual": "5.2",
    #     "foto": "fone.jpg",   # arquivo dentro de cards-produto/fotos/
    # },
]


# ---------------------------------------------------------------- validação


def _validar(produtos):
    if not produtos:
        raise SystemExit(
            "PRODUTOS está vazio. Preencha os três produtos e salve as fotos em "
            f"{FOTOS_DIR.relative_to(REPO_ROOT)}/ - ver o comentário no topo do arquivo."
        )

    categorias = []
    for p in produtos:
        preco = Decimal(str(p["preco"]))
        percentual = Decimal(str(p["percentual"]))

        if percentual < CASHBACK_MINIMO:
            raise SystemExit(
                f'"{p["nome"]}" tem {percentual}% de cashback, abaixo do mínimo de '
                f"{CASHBACK_MINIMO}% combinado para estes cards."
            )
        if preco <= 0:
            raise SystemExit(f'"{p["nome"]}" está sem preço.')

        caminho = FOTOS_DIR / p["foto"]
        if not caminho.exists():
            raise SystemExit(f"Foto não encontrada: {caminho.relative_to(REPO_ROOT)}")

        categorias.append(p["categoria"])

    repetidas = {c for c in categorias if categorias.count(c) > 1}
    if repetidas:
        raise SystemExit(
            "Categorias repetidas: " + ", ".join(sorted(repetidas)) +
            ". A ideia é mostrar que o cashback vale em setores diferentes da loja."
        )


def _valor_cashback(preco: Decimal, percentual: Decimal) -> tuple[Decimal, bool]:
    """Devolve (valor, bateu_no_teto). O percentual que a vitrine mostra já vem ajustado
    pelo teto de R$ 10 por produto, então bater no teto aqui é sinal de que o número
    copiado veio de outro lugar - por isso a flag, para avisar em vez de publicar um
    valor que o site não pagaria."""
    bruto = (preco * percentual / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (TETO_POR_PRODUTO, True) if bruto > TETO_POR_PRODUTO else (bruto, False)


def _reais(valor: Decimal) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def _percentual(valor: Decimal) -> str:
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",") + "%"


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40]


# ------------------------------------------------------------------ arte


def _foto_embutida(caminho: Path) -> str:
    tipo = "jpeg" if caminho.suffix.lower() in {".jpg", ".jpeg"} else caminho.suffix.lstrip(".")
    return f"data:image/{tipo};base64,{base64.b64encode(caminho.read_bytes()).decode()}"


def _cartao(produto, com_cashback: bool) -> str:
    preco = Decimal(str(produto["preco"]))
    percentual = Decimal(str(produto["percentual"]))
    valor, _ = _valor_cashback(preco, percentual)

    bloco_cashback = f"""
    <div style="margin-top:26px; padding-top:24px; border-top:2px dashed {CORES['line']};
                display:flex; align-items:center; justify-content:space-between;">
        <div>
            <div style="font-size:20px; font-weight:600; letter-spacing:0.08em;
                        text-transform:uppercase; color:{CORES['muted']};">cashback</div>
            <div style="font-family:'JB Mono'; font-size:44px; font-weight:700;
                        color:{CORES['success']}; margin-top:6px;">{_reais(valor)}</div>
        </div>
        <div style="padding:12px 22px; border-radius:999px; background:{CORES['brand']};
                    font-family:'JB Mono'; font-size:34px; font-weight:700; color:#fff;">
            {_percentual(percentual)}
        </div>
    </div>
    """ if com_cashback else ""

    return f"""
    <div class="cartao">
        <img class="foto" src="{_foto_embutida(FOTOS_DIR / produto['foto'])}" alt="">
        <div class="nome">{produto['nome']}</div>
        <div class="preco">{_reais(preco)}</div>
        {bloco_cashback}
    </div>
    """


def _pagina(corpo: str, largura: int, altura: int) -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{ width:{largura}px; height:{altura}px; background:transparent; font-family:"Familjen", Arial, sans-serif; }}
    body {{ display:flex; align-items:flex-start; padding-top:{MARGEM_TOPO}px; gap:{VAO}px; }}
    .cartao {{
        width:{LARGURA_CARTAO}px; padding:36px; border-radius:40px; background:#fff;
        flex-shrink:0; box-shadow:0 30px 60px rgba(17,24,39,0.18);
    }}
    .foto {{ width:648px; height:648px; object-fit:cover; border-radius:28px; display:block; }}
    /* Duas linhas sempre, mesmo com nome curto: é o que garante que todos os cards
       tenham a MESMA altura. Sem isso, um produto de nome curto sairia mais baixo e a
       tira ficaria com os cards desalinhados entre si. */
    .nome {{
        font-size:34px; font-weight:600; line-height:1.25; color:{CORES['ink']};
        margin-top:26px; letter-spacing:-0.01em; min-height:{ALTURA_NOME}px;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    .preco {{ font-family:"JB Mono"; font-size:58px; font-weight:700; color:{CORES['ink']}; margin-top:14px; }}
    .cartao-marca {{
        display:flex; align-items:center; justify-content:center;
        background:linear-gradient(165deg, {CORES['brand-strong']} 0%, {CORES['brand']} 100%);
    }}
    .cartao-marca span {{ font-size:110px; font-weight:700; letter-spacing:-0.03em; color:{CORES['paper']}; }}
    /* Mesma largura e altura de um card, mas sem caixa: mantém o compasso da fila
       durante a rolagem e ainda assim lê como assinatura, não como mais um produto. */
    .marca-solta {{
        width:{LARGURA_CARTAO}px; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
    }}
    .marca-solta span {{ font-size:170px; font-weight:700; letter-spacing:-0.03em; color:{CORES['brand']}; }}
    </style></head><body>{corpo}</body></html>"""


def _render(corpo: str, destino: Path, largura: int = LARGURA, altura: int = ALTURA, escala: int = 2):
    """escala=2 de propósito: no reel o card aparece grande na tela, e subir um PNG de
    1x na edição deixa texto e foto moles."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": largura, "height": altura}, device_scale_factor=escala
        )
        pagina.set_content(_pagina(corpo, largura, altura))
        pagina.wait_for_timeout(250)
        # Sem recorte na tinta, ao contrário do kit de logos: os arquivos do mesmo
        # produto precisam sair do mesmo tamanho para não pular na troca durante o vídeo.
        pagina.screenshot(path=str(destino), omit_background=True)
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({largura*escala}x{altura*escala})")


def _centralizado(cartao: str) -> str:
    """O card solto vive numa tela de 1080 e fica centralizado nela; na tira ele é só
    mais um item da fila. A margem lateral aqui é a mesma que a tira usa nas pontas,
    para o primeiro card cair no mesmo pixel nos dois arquivos."""
    return f'<div style="padding-left:{MARGEM_LATERAL}px;">{cartao}</div>'


def _cartao_marca(altura_cartao: int, com_fundo: bool = False, clara: bool = False) -> str:
    """Último elemento do carrossel.

    Por padrão a marca vai solta, sem cartão atrás: dentro de um cartão ela vira só mais
    um item da lista, e o que se quer no fim do reel é uma assinatura - o momento em que
    a fila acaba e sobra quem fez. Ela ocupa a mesma largura e altura de um card, então a
    fila continua no mesmo compasso durante a rolagem.

    clara=True troca o roxo pelo claro da marca: sobre fundo escuro o roxo some, e foi
    o que apareceu ao testar as duas versões sobre um fundo simulado.

    com_fundo=True devolve a versão em cartão roxo, que resolve o contraste de um jeito
    diferente - com caixa, à custa de parecer mais um item da lista.
    """
    if com_fundo:
        return (
            f'<div class="cartao cartao-marca" style="height:{altura_cartao}px; padding:0;">'
            f"<span>cash-b</span></div>"
        )
    cor = CORES["paper"] if clara else CORES["brand"]
    return (
        f'<div class="marca-solta" style="height:{altura_cartao}px;">'
        f'<span style="color:{cor};">cash-b</span></div>'
    )


def _altura_do_cartao(produto) -> int:
    """Mede o card renderizado em vez de somar as alturas na mão - qualquer ajuste de
    corpo de fonte mudaria a conta e o card da marca ficaria fora de esquadro."""
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(viewport={"width": LARGURA, "height": ALTURA})
        pagina.set_content(_pagina(_cartao(produto, com_cashback=True), LARGURA, ALTURA))
        pagina.wait_for_timeout(250)
        altura = pagina.evaluate("Math.round(document.querySelector('.cartao').getBoundingClientRect().height)")
        navegador.close()
    return int(altura)


def gerar_tira(produtos, escala: int = 2, marca_com_fundo: bool = False,
               marca_clara: bool = False, nome_arquivo: str = "carrossel-tira.png"):
    """A fila inteira num PNG só: cards de produto com cashback + o card da marca no fim.

    Devolve a lista de deslocamentos em X (já na escala do arquivo) em que cada card
    fica centralizado na tela - são os valores dos quadros-chave da rolagem no editor.
    """
    altura_cartao = _altura_do_cartao(produtos[0])
    passo = LARGURA_CARTAO + VAO
    itens = len(produtos) + 1  # +1 do card da marca
    largura_tira = MARGEM_LATERAL * 2 + itens * LARGURA_CARTAO + (itens - 1) * VAO
    altura_tira = MARGEM_TOPO + altura_cartao + 120  # folga para a sombra

    corpo = (
        f'<div style="padding-left:{MARGEM_LATERAL}px;"></div>'
        + "".join(_cartao(p, com_cashback=True) for p in produtos)
        + _cartao_marca(altura_cartao, marca_com_fundo, marca_clara)
    )
    # O primeiro padding-left entra como item flex, então some com o gap extra dele
    corpo = corpo.replace(f'<div style="padding-left:{MARGEM_LATERAL}px;"></div>', "")
    corpo = f'<div style="width:{MARGEM_LATERAL - VAO}px; flex-shrink:0;"></div>' + corpo

    _render(corpo, OUT_DIR / nome_arquivo, largura_tira, altura_tira, escala)

    return [(-i * passo * escala) for i in range(itens)]


def gerar(produtos=None):
    produtos = produtos if produtos is not None else PRODUTOS
    _validar(produtos)

    for i, produto in enumerate(produtos, start=1):
        base = f"{i:02d}-{_slug(produto['nome'])}"
        _render(_centralizado(_cartao(produto, com_cashback=False)), OUT_DIR / f"{base}-so-preco.png")
        _render(_centralizado(_cartao(produto, com_cashback=True)), OUT_DIR / f"{base}-com-cashback.png")

        preco = Decimal(str(produto["preco"]))
        _, no_teto = _valor_cashback(preco, Decimal(str(produto["percentual"])))
        if no_teto:
            print(
                f"  AVISO: {produto['nome']} bateu no teto de R$ {TETO_POR_PRODUTO} por "
                "produto. Confira o valor que a vitrine mostra - o percentual dela já "
                "vem ajustado pelo teto."
            )


    # As três terminações saem juntas: qual funciona depende do fundo que a câmera
    # captou, e isso só dá para julgar na linha do tempo. A rolagem é a mesma nas três.
    quadros = gerar_tira(produtos)
    gerar_tira(produtos, marca_clara=True, nome_arquivo="carrossel-tira-marca-clara.png")
    gerar_tira(produtos, marca_com_fundo=True, nome_arquivo="carrossel-tira-marca-em-card.png")
    print("\nQuadros-chave da rolagem (deslocamento em X da camada da tira):")
    nomes = [p["nome"] for p in produtos] + ["cash-b (fim)"]
    for x, nome in zip(quadros, nomes):
        print(f"  {x:>7} px  ->  {nome}")
    print("Comece rápido e desacelere até o último valor (ease-out).")


if __name__ == "__main__":
    gerar()
