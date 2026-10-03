"""Cards "antes -> agora" da campanha 10.10: o MESMO produto da vitrine, com o cashback de um
dia normal e com o cashback da campanha.

Por que um produto de verdade e não um exemplo genérico: "50% a mais" é abstrato; "R$ 4,05
-> R$ 6,08 neste produto" é o que a pessoa consegue imaginar no próprio pedido. Os números
são os que a vitrine mostra: o site calcula o % do card como `% do produto x multiplicador`
(arredondado em 0,1) e o valor como `preço base x % x multiplicador`
(`ofertas/models.py`, `cashback_exibido`/`percentual_cashback_exibido`). 5,8% x 1,5 = 8,7% e
R$ 69,90 x 5,8% x 1,5 = R$ 6,08. Se o produto ou a campanha mudarem, mude `PRODUTO` em
`gerar_cards_vitrine.py` e o `PERCENTUAL_EXTRA` em `gerar_banner_email.py`: tudo daqui sai
deles, nada é digitado de novo.

Sai em três peças:

- `card-antes.png` e `card-agora.png`: o card do site, transparente, do mesmo tamanho e com
  tudo no mesmo pixel (para trocar um pelo outro num editor/reel sem o card pular). O card
  é o de `gerar_cards_vitrine.py`; aqui só muda o %.
- `story-antes-agora.png`: story 1080x1920 com o card "agora" grande e, embaixo, a conta
  lado a lado (dia normal riscado -> 10.10 em verde). O card sozinho num story fica com o
  texto pequeno demais (um card de telefone de 390px esticado a ~600px vira ~7pt na tela),
  então quem carrega a mensagem é a faixa de números, em corpo grande; o card prova que o
  valor é o do site.

O card é o da vitrine, que mostra o cashback sobre o PRIMEIRO preço da faixa (R$ 69,90),
igual ao site. A nota da arte diz isso.

Margens do story: 250px em cima e 300px embaixo ficam livres (interface do Instagram).

Como usar:
    python3 gerar_cards_antes_agora.py
"""
import base64
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import FAMILJEN_B64, HIGHLIGHT

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "marketing"))

import gerar_cards_vitrine as vitrine  # noqa: E402
from gerar_banner_email import DATA, MULTIPLICADOR, PERCENTUAL_EXTRA  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "cards-antes-agora"
LARGURA, ALTURA = 1080, 1920
ESCALA_STORY = 2

VERDE_SOBRE_ROXO = "#4ade80"
ROXO_CLARO = "#e9e1fb"

PCT_ANTES = Decimal(vitrine.PRODUTO["percentual_direta"])
# Igual ao site: % x multiplicador, arredondado em 0,1 (percentual_cashback_exibido).
PCT_AGORA = (PCT_ANTES * MULTIPLICADOR).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _valor(pct: Decimal, multiplicador: Decimal = Decimal("1")) -> Decimal:
    # O site multiplica o valor bruto (preço x fração x multiplicador) e só então arredonda:
    # R$ 69,90 x 5,8% x 1,5 = 6,0813 -> 6,08. Arredondar o 4,05 antes e multiplicar
    # (4,05 x 1,5 = 6,075 -> 6,08) por acaso dá igual aqui, mas não em todo produto.
    base = Decimal(str(vitrine.PRODUTO["preco_base"]))
    return (base * pct / 100 * multiplicador).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


VALOR_ANTES = _valor(PCT_ANTES)
VALOR_AGORA = _valor(PCT_ANTES, MULTIPLICADOR)


def _renderizar_card(navegador, pct: Decimal, destino: Path, foto: Path):
    # Usa a página do card da vitrine como está (mesmo HTML, mesmos pixels). O valor em
    # reais que ela calcula é `_valor(pct)` dela, sem multiplicador: por isso o card
    # "agora" recebe o % JÁ multiplicado e o valor sai de 69,90 x 8,7% = 6,08, o mesmo
    # que VALOR_AGORA (a asserção abaixo trava se algum dia divergirem).
    assert vitrine._valor(pct) in (VALOR_ANTES, VALOR_AGORA), "valor do card não bate com a conta"
    pagina = navegador.new_page(
        viewport={"width": vitrine.LARGURA_CSS, "height": 800}, device_scale_factor=vitrine.ESCALA
    )
    pagina.set_content(vitrine._pagina("direta", foto, percentual_direta=pct))
    pagina.wait_for_timeout(250)
    caixa = pagina.locator(".oferta-cartao").bounding_box()
    folga = 10
    pagina.screenshot(path=str(destino), omit_background=True, clip={
        "x": caixa["x"] - folga, "y": caixa["y"] - folga,
        "width": caixa["width"] + folga * 2, "height": caixa["height"] + folga * 2,
    })
    pagina.close()
    print("gerado:", destino.relative_to(REPO_ROOT))


def _png64(caminho: Path) -> str:
    return base64.b64encode(caminho.read_bytes()).decode()


def _story(card_agora: Path) -> str:
    fundo = base64.b64encode(
        (REPO_ROOT / "marketing" / "fundos-marca" / "fundo-03-canto-roxo-9x16.png").read_bytes()
    ).decode()
    pct = lambda v: vitrine._percentual(v)  # noqa: E731
    reais = vitrine._reais
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; color:#fff;
        background:#5b21b6 url(data:image/png;base64,{fundo}) center/cover no-repeat;
        font-family:"Familjen", Arial, sans-serif;
    }}
    body {{ display:flex; flex-direction:column; padding:250px 90px 300px; }}
    .marca {{ font-size:46px; font-weight:700; letter-spacing:-0.03em; }}
    .miolo {{ flex:1; padding:34px 0 30px; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
    .titulo {{ font-size:66px; font-weight:700; line-height:1.06; letter-spacing:-0.025em; text-align:center; }}
    .titulo span {{ color:{HIGHLIGHT}; }}
    .card {{ width:470px; margin-top:30px; filter:drop-shadow(0 22px 40px rgba(17,10,50,.45)); }}
    .conta {{
        width:100%; margin-top:30px; background:#fff; color:#111827; border-radius:40px;
        padding:26px 44px; display:flex; align-items:center; justify-content:space-between;
    }}
    .lado small {{ display:block; font-size:28px; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#6b7280; }}
    .lado.novo small {{ color:#b45309; }}
    .pct {{ font-size:84px; font-weight:700; letter-spacing:-0.03em; line-height:1.05; }}
    .antes .pct {{ color:#6b7280; text-decoration:line-through; text-decoration-thickness:6px; }}
    .antes .reais, .novo .reais {{ font-size:40px; font-weight:700; }}
    .antes .reais {{ color:#6b7280; text-decoration:line-through; text-decoration-thickness:4px; }}
    .novo .pct, .novo .reais {{ color:#059669; }}
    .seta {{ font-size:64px; color:#6d28d9; font-weight:700; }}
    .nota {{ margin-top:24px; font-size:29px; line-height:1.35; color:{ROXO_CLARO}; text-align:center; }}
    .rodape {{ font-size:36px; font-weight:700; letter-spacing:1px; color:{ROXO_CLARO}; }}
    </style></head><body>
        <div class="marca">cash-b</div>
        <div class="miolo">
            <div class="titulo">Mesmo produto,<br><span>{PERCENTUAL_EXTRA}% a mais</span> de cashback</div>
            <img class="card" src="data:image/png;base64,{_png64(card_agora)}">
            <div class="conta">
                <div class="lado antes"><small>dia normal</small><div class="pct">{pct(PCT_ANTES)}</div><div class="reais">{reais(VALOR_ANTES)}</div></div>
                <div class="seta">&rarr;</div>
                <div class="lado novo"><small>no {DATA}</small><div class="pct">{pct(PCT_AGORA)}</div><div class="reais">{reais(VALOR_AGORA)}</div></div>
            </div>
            <div class="nota">Exemplo: {vitrine.PRODUTO['nome'].split(' com ')[0]}, sobre R$ {str(vitrine.PRODUTO['preco_base']).replace('.', ',')}.<br>O valor de cada produto aparece no card da vitrine.</div>
        </div>
        <div class="rodape">cash-b.com</div>
    </body></html>"""


def gerar():
    foto = vitrine.FOTOS_DIR / vitrine.PRODUTO["foto"]
    if not foto.exists():
        raise SystemExit(f"Foto não encontrada: {foto}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card_antes = OUT_DIR / "card-antes.png"
    card_agora = OUT_DIR / "card-agora.png"
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        _renderizar_card(nav, PCT_ANTES, card_antes, foto)
        _renderizar_card(nav, PCT_AGORA, card_agora, foto)
        pagina = nav.new_page(viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA_STORY)
        pagina.set_content(_story(card_agora))
        pagina.wait_for_timeout(250)
        destino = OUT_DIR / "story-antes-agora.png"
        pagina.screenshot(path=str(destino))
        print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA * ESCALA_STORY}x{ALTURA * ESCALA_STORY})")
        nav.close()
    print(f"\nantes: {vitrine._percentual(PCT_ANTES)} = {vitrine._reais(VALOR_ANTES)}"
          f"   |   agora: {vitrine._percentual(PCT_AGORA)} = {vitrine._reais(VALOR_AGORA)}")


if __name__ == "__main__":
    gerar()
