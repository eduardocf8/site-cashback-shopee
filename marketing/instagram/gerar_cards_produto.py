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


def _render(html_cartao, destino: Path):
    html = f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{ width:{LARGURA}px; height:{ALTURA}px; background:transparent; font-family:"Familjen", Arial, sans-serif; }}
    body {{ display:flex; align-items:flex-start; justify-content:center; padding-top:{MARGEM_TOPO}px; }}
    .cartao {{
        width:720px; padding:36px; border-radius:40px; background:#fff;
        box-shadow:0 30px 60px rgba(17,24,39,0.18);
    }}
    .foto {{ width:648px; height:648px; object-fit:cover; border-radius:28px; display:block; }}
    .nome {{
        font-size:34px; font-weight:600; line-height:1.25; color:{CORES['ink']};
        margin-top:26px; letter-spacing:-0.01em;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    .preco {{ font-family:"JB Mono"; font-size:58px; font-weight:700; color:{CORES['ink']}; margin-top:14px; }}
    </style></head><body>{html_cartao}</body></html>"""

    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=1)
        pagina.set_content(html)
        pagina.wait_for_timeout(200)
        # Sem recorte na tinta, ao contrário do kit de logos: os dois cards do mesmo
        # produto precisam sair do mesmo tamanho para não pular na troca durante o vídeo.
        pagina.screenshot(path=str(destino), omit_background=True)
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT))


def gerar(produtos=None):
    produtos = produtos if produtos is not None else PRODUTOS
    _validar(produtos)

    for i, produto in enumerate(produtos, start=1):
        base = f"{i:02d}-{_slug(produto['nome'])}"
        _render(_cartao(produto, com_cashback=False), OUT_DIR / f"{base}-so-preco.png")
        _render(_cartao(produto, com_cashback=True), OUT_DIR / f"{base}-com-cashback.png")

        preco = Decimal(str(produto["preco"]))
        _, no_teto = _valor_cashback(preco, Decimal(str(produto["percentual"])))
        if no_teto:
            print(
                f"  AVISO: {produto['nome']} bateu no teto de R$ {TETO_POR_PRODUTO} por "
                "produto. Confira o valor que a vitrine mostra - o percentual dela já "
                "vem ajustado pelo teto."
            )


if __name__ == "__main__":
    gerar()
