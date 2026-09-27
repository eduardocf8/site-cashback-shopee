"""Cards da vitrine em três estados, para o reel de venda direta x indireta.

Reproduz o card de oferta do site (`.oferta-cartao` em static/css/brand.css, markup em
ofertas/templates/ofertas/_card.html) em três versões do MESMO produto:

    1. sem-cashback   nenhuma informação de cashback
    2. indireta       o piso da venda indireta, em cinza
    3. direta         o cashback real da vitrine, em verde

A sequência é a do reel: o produto aparece primeiro cru, depois com o que a venda
indireta paga, depois com o que a direta paga. O cinza na indireta segue a decisão já
registrada no BRAND.md - cinza diz "menos" sem dizer "cuidado", e âmbar ou vermelho
transformariam uma opção que paga numa opção que assusta.

**Os três saem do mesmo tamanho e com tudo no mesmo pixel.** Nos estados sem cashback a
linha de valor continua ocupando o lugar dela, invisível: sem isso o card encolheria e
pularia na troca durante o vídeo - mesma regra dos cards de produto e dos botões.

Por que refazer em vez de editar uma captura de tela: o selo de cashback fica colado na
borda de cima da foto, com o lustre da foto logo ao lado, e apagá-lo de um print não sai
limpo. Refeito daqui, o estado sem cashback simplesmente não desenha o selo.

Preencha PRODUTO com o que a vitrine mostra e salve a foto em cards-vitrine/fotos/.

    python3 gerar_cards_vitrine.py
"""
import base64
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()
JBMONO_B64 = base64.b64encode((FONT_DIR / "jetbrains-mono.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "cards-vitrine"
FOTOS_DIR = OUT_DIR / "fotos"

CORES = {
    "ink": "#111827", "muted": "#6b7280", "brand": "#6d28d9",
    "success": "#059669", "danger": "#dc2626",
    "paper": "#f8fafc", "paper-2": "#f1eefb", "line": "#e0dcef",
}

# O card do site é desenhado para telefone. Renderizar na largura de um telefone e
# multiplicar pelo fator dá exatamente o mesmo desenho, só que em tamanho de vídeo.
LARGURA_CSS = 390
ESCALA = 1080 / LARGURA_CSS

# Piso da venda indireta - CASHBACK_MINIMO_VENDA_INDIRETA em settings.py.
MINIMO_INDIRETA = Decimal("1")

PRODUTO = {
    "categoria": "Casa e Decoração",
    "nome": "Kit Peseira para Cama com Capas de Almofada",
    # Faixa de preço, como a vitrine mostra. O cashback é calculado sobre o PRIMEIRO
    # valor - é o que o site faz, e o que fecha com os R$ 4,05 que ele exibe.
    "preco": "R$ 69,90 – R$ 89,99",
    "preco_base": "69.90",
    "desconto": "-59%",
    "percentual_direta": "5.8",
    "foto": "kit-peseira.jpg",
}


def _reais(valor: Decimal) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def _percentual(valor: Decimal) -> str:
    return f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def _valor(percentual: Decimal) -> Decimal:
    base = Decimal(str(PRODUTO["preco_base"]))
    return (base * percentual / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _foto_embutida(caminho: Path) -> str:
    tipo = "jpeg" if caminho.suffix.lower() in {".jpg", ".jpeg"} else caminho.suffix.lstrip(".")
    return f"data:image/{tipo};base64,{base64.b64encode(caminho.read_bytes()).decode()}"


def _pagina(estado: str, foto: Path) -> str:
    if estado == "direta":
        pct, cor = Decimal(PRODUTO["percentual_direta"]), CORES["success"]
    elif estado == "indireta":
        pct, cor = MINIMO_INDIRETA, CORES["muted"]
    else:
        pct, cor = None, None

    selo = (f'<span class="cashback" style="background:{cor};">{_percentual(pct)}</span>'
            if pct is not None else "")
    # visibility e não display: o espaço da linha continua reservado, então o card tem
    # a mesma altura nos três estados e nada se move na troca durante o vídeo.
    oculto = "" if pct is not None else "visibility:hidden;"
    valor = _reais(_valor(pct)) if pct is not None else "R$ 0,00"

    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{ width:{LARGURA_CSS}px; background:transparent; font-family:"Familjen", Arial, sans-serif; }}
    body {{ padding:10px; }}
    .oferta-cartao {{
        background:{CORES['paper']}; border:1px solid {CORES['line']}; border-radius:12px;
        overflow:hidden; display:flex; flex-direction:column;
    }}
    .imagem {{ position:relative; aspect-ratio:1/1; background:{CORES['paper-2']}; }}
    .imagem img {{ width:100%; height:100%; object-fit:cover; display:block; }}
    .desconto, .cashback {{
        position:absolute; top:8px; color:#fff;
        font-size:12px; font-weight:700; padding:3px 8px; border-radius:10px;
    }}
    .desconto {{ left:8px; background:{CORES['danger']}; }}
    .cashback {{ right:8px; }}
    .corpo {{ padding:14px; display:flex; flex-direction:column; gap:6px; flex:1; }}
    .categoria {{ font-size:12px; color:{CORES['muted']}; }}
    .nome {{ font-size:14px; line-height:1.4; max-height:2.8em; overflow:hidden; color:{CORES['ink']}; }}
    .preco {{ font-family:"JB Mono", monospace; font-size:17px; font-weight:500; margin-top:auto; color:{CORES['ink']}; }}
    .cashback-valor {{ font-size:12.5px; font-weight:700; {oculto} }}
    .botao-cta {{
        text-align:center; margin:4px 14px 14px; padding:12px 24px; border-radius:8px;
        background:{CORES['brand']}; color:#fff; font-weight:600; font-size:14px;
    }}
    </style></head><body>
        <div class="oferta-cartao">
            <div class="imagem">
                <img src="{_foto_embutida(foto)}" alt="">
                <span class="desconto">{PRODUTO['desconto']}</span>
                {selo}
            </div>
            <div class="corpo">
                <div class="categoria">{PRODUTO['categoria']}</div>
                <div class="nome">{PRODUTO['nome']}</div>
                <div class="preco">{PRODUTO['preco']}</div>
                <div class="cashback-valor" style="color:{cor or CORES['success']};">Receba {valor} de cashback</div>
            </div>
            <div class="botao-cta">Ir pra oferta</div>
        </div>
    </body></html>"""


def gerar(foto: Path | None = None):
    foto = foto or (FOTOS_DIR / PRODUTO["foto"])
    if not foto.exists():
        raise SystemExit(f"Foto não encontrada: {foto}. Salve a imagem do produto ali.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for estado in ("sem-cashback", "indireta", "direta"):
            pagina = nav.new_page(viewport={"width": LARGURA_CSS, "height": 800},
                                  device_scale_factor=ESCALA)
            pagina.set_content(_pagina(estado, foto))
            pagina.wait_for_timeout(250)
            # Recorta no próprio cartão, com uma folga igual em volta. Sem isso o
            # arquivo sai com a sobra do viewport embaixo - não quebra nada, mas
            # atrapalha na hora de posicionar no editor. A folga vem da caixa do
            # elemento, então é a mesma nos três estados.
            caixa = pagina.locator(".oferta-cartao").bounding_box()
            folga = 10
            alvo = OUT_DIR / f"card-{estado}.png"
            pagina.screenshot(path=str(alvo), omit_background=True, clip={
                "x": caixa["x"] - folga, "y": caixa["y"] - folga,
                "width": caixa["width"] + folga * 2, "height": caixa["height"] + folga * 2,
            })
            pagina.close()
            print("gerado:", alvo.relative_to(REPO_ROOT))
        nav.close()
    print(f"\nindireta: {_percentual(MINIMO_INDIRETA)} = {_reais(_valor(MINIMO_INDIRETA))}"
          f"   |   direta: {_percentual(Decimal(PRODUTO['percentual_direta']))} = "
          f"{_reais(_valor(Decimal(PRODUTO['percentual_direta'])))}")


if __name__ == "__main__":
    import sys
    gerar(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
