"""Cards de produto para vídeo — dois por produto: só o preço, e com o cashback.

Feito para gravação: os dois cards de um mesmo produto são IDÊNTICOS em dimensão e
posição - ao "apertar o botão" na cena, nada muda de tamanho nem se desloca, só surgem
as informações de cashback. Conseguido com duas escolhas: o selo da % é absoluto sobre
a foto (não ocupa espaço) e o valor em R$ entra numa linha de altura travada, ao lado
do preço. Conferido comparando os dois arquivos: mesma caixa e diferença só nas duas
regiões novas.

O tratamento da % e do preço segue o card de oferta dos stories
(instagram_bot/templates_imagem.py, gerar_imagem_oferta_story): selo âmbar no canto da
foto e preço em roxo, na mono.

Fundo transparente, para o cartão poder ser posto sobre qualquer imagem do vídeo.

Validação em duas camadas: foto ausente ou preço zerado derrubam a geração (não tem
card para gerar), enquanto o piso de cashback e a repetição de categoria só avisam.
Esses dois eram critério para ESCOLHER o produto - depois que a escolha é feita à mão,
bloquear só impede de gerar o que foi pedido. "preco" continua sendo um campo único, o
que já impede produto com faixa de preço virar card.

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
    "highlight": "#f59e0b",
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
    # Separados à mão na vitrine (cash-b.com/ofertas) em 14/09/2026. Onde a vitrine
    # mostrava faixa de preço, entrou o PRIMEIRO valor - é o que as informações de
    # cashback da vitrine já consideram.
    {"nome": "Percarbonato de Sódio 100% Puro Tira Manchas", "categoria": "Casa e Decoração",
     "preco": "16.50", "percentual": "3.0", "foto": "01-percarbonato.jpg"},
    {"nome": "Cinta Modeladora Feminina", "categoria": "Roupas Femininas",
     "preco": "27.99", "percentual": "6.2", "foto": "02-cinta.jpg"},
    {"nome": "Creatina Monohidratada Pura Dark Lab", "categoria": "Saúde",
     "preco": "32.90", "percentual": "5.6", "foto": "03-creatina.jpg"},
    {"nome": "Ração Úmida Friskies para Gatos 15x85g", "categoria": "Animais Domésticos",
     "preco": "39.90", "percentual": "4.6", "foto": "04-friskies.jpg"},
    {"nome": "Torneira de Cozinha Gourmet 360°", "categoria": "Casa e Decoração",
     "preco": "25.88", "percentual": "5.6", "foto": "05-torneira.jpg"},
    {"nome": "Chaleira Elétrica Inox 110v", "categoria": "Eletrodomésticos",
     "preco": "44.90", "percentual": "3.0", "foto": "06-chaleira.jpg"},
    {"nome": "Gel de Limpeza Suave Principia GL-02 200g", "categoria": "Beleza",
     "preco": "39.00", "percentual": "3.6", "foto": "07-principia.jpg"},
    {"nome": "Kit Renovadores Faciais Kokeshi", "categoria": "Beleza",
     "preco": "39.90", "percentual": "6.2", "foto": "08-kokeshi.jpg"},
]


# ---------------------------------------------------------------- validação


def _validar(produtos):
    """Erro derruba a geração; aviso só alerta.

    A divisão é entre o que quebra a peça e o que é preferência editorial. Foto ausente
    ou preço zerado produzem um card errado - não tem card para gerar, então é erro. Já
    o piso de cashback e a variedade de categorias eram critério para ESCOLHER produto;
    depois que a escolha foi feita à mão, virar bloqueio só impede de gerar o que foi
    pedido. Viram aviso, e quem decide é quem escolheu.
    """
    if not produtos:
        raise SystemExit(
            "PRODUTOS está vazio. Preencha os produtos e salve as fotos em "
            f"{FOTOS_DIR.relative_to(REPO_ROOT)}/ - ver o comentário no topo do arquivo."
        )

    avisos = []
    categorias = []
    for p in produtos:
        preco = Decimal(str(p["preco"]))
        percentual = Decimal(str(p["percentual"]))

        if preco <= 0:
            raise SystemExit(f'"{p["nome"]}" está sem preço.')

        caminho = FOTOS_DIR / p["foto"]
        if not caminho.exists():
            raise SystemExit(f"Foto não encontrada: {caminho.relative_to(REPO_ROOT)}")

        if percentual < CASHBACK_MINIMO:
            avisos.append(f'{p["nome"]} tem {_percentual(percentual)}, abaixo de {CASHBACK_MINIMO}%')

        categorias.append(p["categoria"])

    repetidas = sorted({c for c in categorias if categorias.count(c) > 1})
    if repetidas:
        avisos.append("categorias repetidas: " + ", ".join(repetidas))

    for aviso in avisos:
        print(f"  AVISO: {aviso}")


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
    """As duas versões têm exatamente as mesmas dimensões.

    É o que o roteiro do reel exige: ao "apertar o botão", o card não pode mudar de
    tamanho nem mexer em nada que já estava na tela - só ganhar as informações de
    cashback. Por isso o selo da % é absoluto (flutua sobre a foto, não empurra nada) e
    o valor em R$ entra numa linha de altura fixa, ao lado do preço.
    """
    preco = Decimal(str(produto["preco"]))
    percentual = Decimal(str(produto["percentual"]))
    valor, _ = _valor_cashback(preco, percentual)

    selo = (
        f'<div class="selo-cashback">{_percentual(percentual)} cashback</div>'
        if com_cashback else ""
    )
    valor_cashback = (
        f'<span class="valor-cashback">+ {_reais(valor)}</span>' if com_cashback else ""
    )

    return f"""
    <div class="cartao">
        <div class="foto-area">
            <img class="foto" src="{_foto_embutida(FOTOS_DIR / produto['foto'])}" alt="">
            {selo}
        </div>
        <div class="nome">{produto['nome']}</div>
        <div class="linha-preco">
            <span class="preco">{_reais(preco)}</span>
            {valor_cashback}
        </div>
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
    .foto-area {{ position:relative; line-height:0; }}
    .foto {{ width:648px; height:648px; object-fit:cover; border-radius:28px; display:block; }}
    /* Absoluto de propósito: flutua sobre a foto sem ocupar espaço, então ligar o
       cashback não empurra nada para baixo nem muda a altura do cartão. Mesmas cores e
       cantos do selo do story de oferta (instagram_bot/templates_imagem.py). */
    .selo-cashback {{
        position:absolute; top:20px; right:20px;
        padding:10px 18px; border-radius:14px;
        background:{CORES['highlight']}; color:{CORES['ink']};
        font-size:24px; font-weight:700; line-height:1.15;
    }}
    /* Duas linhas sempre, mesmo com nome curto: é o que garante que todos os cards
       tenham a MESMA altura. Sem isso, um produto de nome curto sairia mais baixo e a
       tira ficaria com os cards desalinhados entre si. */
    .nome {{
        font-size:34px; font-weight:600; line-height:1.25; color:{CORES['ink']};
        margin-top:26px; letter-spacing:-0.01em; min-height:{ALTURA_NOME}px;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    /* Altura travada: o valor em R$ entra ao lado do preço, e sem altura fixa uma
       diferença de métrica entre as duas fontes mudaria a altura do cartão - que é
       justamente o que não pode acontecer na troca durante a cena. */
    .linha-preco {{ display:flex; align-items:baseline; gap:18px; height:76px; margin-top:14px; }}
    .preco {{ font-family:"JB Mono"; font-size:58px; font-weight:700; color:{CORES['brand']}; }}
    .valor-cashback {{ font-family:"JB Mono"; font-size:36px; font-weight:700; color:{CORES['success']}; }}
    .cartao-marca {{
        display:flex; align-items:center; justify-content:center;
        background:linear-gradient(165deg, {CORES['brand-strong']} 0%, {CORES['brand']} 100%);
    }}
    .cartao-marca span {{ font-size:110px; font-weight:700; letter-spacing:-0.03em; color:{CORES['paper']}; }}
    /* Centro óptico do wordmark. O flex centraliza a CAIXA da linha de texto, não a
       TINTA: a caixa reserva espaço de descendente embaixo (que "cash-b" não usa) e o
       letter-spacing negativo a encolhe depois do último "b". Medido nos arquivos
       gerados, a tinta saía baixa e à direita - proporcional ao corpo da fonte (17px e
       3px a 110px; 26px e 5px a 170px), por isso a correção vai em em e não em px: vale
       para os dois tamanhos e continua valendo se o corpo mudar. Mesma correção que
       gerar_artes_marca.py faz no glifo "cb", pelo mesmo motivo. */
    .cartao-marca span, .marca-solta span {{ transform:translate(-0.0147em, -0.0765em); }}
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
