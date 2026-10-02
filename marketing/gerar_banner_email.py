"""Banner de e-mail com o conteúdo INTEIRO de uma campanha de cashback (hoje: 10.10, 50% a mais).

O e-mail da campanha é essa imagem. É o jeito dos e-mails de afiliados da Shopee, que serviram
de referência de estrutura: bloco de cor no topo com a data em corpo enorme, e embaixo tudo o
que a pessoa precisa para decidir - como funciona, quanto recebe, as condições. Cor,
tipografia e conteúdo são da cash-b. Nada da Shopee entra na arte além do nome dela escrito: a
cash-b é afiliada independente, e arte com a marca da Shopee sugeriria um vínculo que não existe.

Estrutura, de cima para baixo:

1. Topo (roxo, com o fundo abstrato da marca): selo, data, manchete e um parágrafo.
2. Como funciona: três passos.
3. Quanto você recebe: o cashback mínimo antes e depois da campanha, em % e em reais.
4. Bom saber: as condições, na barra lateral âmbar. É a parte que evita reclamação depois.

A faixa roxa do rodapé ("Sem mensalidade. Sem taxa." com o site e o Instagram) NÃO é parte da
imagem: é HTML no template do e-mail (`templates/emails/comunicacao_vitrine.html`), colada no
pé do banner. Dentro de uma imagem "cash-b.com" e "@usecashb" seriam só pixels, e o único link
possível é o da imagem inteira; como HTML, cada um é um link de verdade e leva ao seu destino.
A imagem termina no "Bom saber".

**Por que a tela tem 400 unidades de largura, e não 560.** O e-mail é exibido com ~528px em
desktop e ~343px em celular. Uma fonte de 12,5px desenhada sobre 560 vira 7,6px no celular,
que não se lê. Sobre 400, a mesma fonte vira 10,7px e a de 14px vira 12px. Tudo aqui é
dimensionado para o celular, que é onde a maioria abre o e-mail.

**O que NÃO cabe dentro da imagem, e por isso vive fora dela** (ver
`templates/emails/comunicacao_vitrine.html`):

- Links. Uma imagem só tem um link; o site e o Instagram escritos aqui dentro não são
  clicáveis. O template põe botões de verdade logo abaixo e torna o banner inteiro clicável.
- O descadastro e o texto alternativo (o assunto do e-mail), para quem tem imagem bloqueada.
- A vitrine de produtos, que tem um link por produto.

**Os números não são livres.** `PERCENTUAL_EXTRA` vem da campanha cadastrada no admin
(`pedidos.CampanhaCashback.percentual_extra`; multiplicador 1,5 = 50). Os pisos
(`MINIMO_DIRETA`, `MINIMO_INDIRETA`) são `CASHBACK_MINIMO_VENDA_DIRETA` e
`CASHBACK_MINIMO_VENDA_INDIRETA` de `cashback_shopee/settings.py`, e o saque mínimo é
`SAQUE_VALOR_MINIMO`. Arte prometendo número diferente do que o sistema paga é o pior erro
possível aqui: conferir os quatro antes de mandar.

**Margens.** A margem de cima (selo) é a de baixo do rodapé HTML. Como o rodapé é HTML em px
fixos e a imagem escala com a largura do e-mail, elas só são iguais numa largura: a do celular
(~375px de tela, imagem a ~343px), que é onde o e-mail é mais aberto. Ver o comentário do
rodapé no template.

O template arredonda só o topo da imagem; o pé arredondado é o do rodapé HTML.

Como usar:
    python3 marketing/gerar_banner_email.py
"""
import base64
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = REPO_ROOT / "static" / "fonts"
OUT_DIR = Path(__file__).resolve().parent / "banner-email"
ARTE = Path(__file__).resolve().parent / "fundos-marca" / "fundo-03-canto-roxo-16x9.png"

FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()

CORES = {
    "ink": "#111827",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "brand-dark": "#4c1d95",
    "highlight": "#f59e0b",
    "success": "#059669",
    "paper": "#f8fafc",
    "line": "#e0dcef",
}

LARGURA = 400   # unidades; o arquivo sai em ESCALA x isso
ESCALA = 3      # 1200px de largura: nítido em tela densa sem passar do razoável de peso
PADDING_VERTICAL = 30   # margem de cima (unidades); a do rodapé HTML é ajustada a ela no template

# --- o que a campanha paga -------------------------------------------------------------
DATA = "10.10"
DIA_MES = DATA.replace(".", "/")
PERCENTUAL_EXTRA = 50
MULTIPLICADOR = 1 + Decimal(PERCENTUAL_EXTRA) / 100
MINIMO_DIRETA = Decimal("1.6")      # CASHBACK_MINIMO_VENDA_DIRETA
MINIMO_INDIRETA = Decimal("1")      # CASHBACK_MINIMO_VENDA_INDIRETA
SAQUE_MINIMO = 20                   # SAQUE_VALOR_MINIMO
COMPRA_EXEMPLO = Decimal("100")

MANCHETE = f"{PERCENTUAL_EXTRA}% a mais de cashback"
PARAGRAFO = (f"Durante todo o {DIA_MES}, todos os pedidos realizados terão {PERCENTUAL_EXTRA}% a mais de "
             "cashback. Essa é a sua chance de poupar e ainda receber mais dinheiro de volta!")

# Cada informação aparece UMA vez. Na primeira versão a pendência ("até a Shopee validar") estava
# no passo 3 e de novo no "Bom saber", e o dia 10/10 no passo 2 e na primeira condição: repetir
# faz o banner parecer mais longo do que é e esconde o que é novo em cada bloco.
PASSOS = [
    ("Entre na cash-b e escolha o produto",
     "Cole o link, use a vitrine ou o botão “Ir pra Shopee”."),
    (f"Compre na Shopee no dia {DIA_MES}",
     "Vale para qualquer pedido do dia."),
    (f"Receba {PERCENTUAL_EXTRA}% a mais de cashback",
     "Ele entra na sua conta da cash-b."),
]

CONDICOES = [
    "O dia vale no horário de Brasília, das 0h às 23h59.",
    "O cashback fica pendente até a Shopee validar a compra.",
    f"Saque via Pix a partir de R$ {SAQUE_MINIMO}, com o e-mail verificado.",
]


def _pct(valor: Decimal) -> str:
    return f"{valor.normalize():f}".replace(".", ",") + "%"


def _reais(valor: Decimal) -> str:
    return "R$ " + f"{valor:.2f}".replace(".", ",")


def _sobre(cor: str, base: str, opacidade: float) -> str:
    """Cor translúcida já misturada com o fundo (opaca). Sobre imagem, translúcido deixa o fundo
    aparecer através do texto; misturado, o contraste é o calculado."""
    c = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * opacidade + y * (1 - opacidade)):02x}" for x, y in zip(c, b))


def _pagina() -> str:
    arte64 = base64.b64encode(ARTE.read_bytes()).decode()
    direta_hoje, direta_nova = MINIMO_DIRETA, MINIMO_DIRETA * MULTIPLICADOR
    ind_hoje, ind_nova = MINIMO_INDIRETA, MINIMO_INDIRETA * MULTIPLICADOR
    exemplo_hoje = COMPRA_EXEMPLO * direta_hoje / 100
    exemplo_novo = COMPRA_EXEMPLO * direta_nova / 100
    fundo_barra = _sobre(CORES["highlight"], CORES["paper"], 0.14)

    passos = "".join(
        f'<div class="passo"><div class="num">{i}</div>'
        f'<div><div class="passo-t">{t}</div><div class="passo-d">{d}</div></div></div>'
        for i, (t, d) in enumerate(PASSOS, start=1)
    )
    condicoes = "".join(f"<li>{c}</li>" for c in CONDICOES)

    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{ width:{LARGURA}px; background:{CORES['paper']}; font-family:"Familjen", Arial, sans-serif; color:{CORES['ink']}; }}

    .topo {{
        position:relative; text-align:center; color:#fff;
        padding:{PADDING_VERTICAL}px 30px 34px;
        background:linear-gradient(160deg, {CORES['brand-dark']} 0%, {CORES['brand']} 62%, #5b21b6 100%);
        background-image:url(data:image/png;base64,{arte64}); background-size:cover; background-position:center;
    }}
    .selo {{
        display:inline-block; padding:6px 16px; border-radius:999px;
        background:{CORES['highlight']}; color:{CORES['ink']};
        font-size:12px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
    }}
    .data {{ margin-top:6px; font-size:78px; font-weight:700; line-height:1; letter-spacing:-0.05em; }}
    .manchete {{ margin-top:0; font-size:19px; font-weight:700; letter-spacing:0.02em; text-transform:uppercase; color:{CORES['highlight']}; }}
    .paragrafo {{ margin:12px auto 0; max-width:330px; font-size:14px; font-weight:500; line-height:1.42; color:rgba(255,255,255,0.92); text-wrap:balance; }}

    .miolo {{ padding:28px 24px 28px; }}
    .tag {{ font-size:12px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:{CORES['brand']}; margin-bottom:14px; }}
    .passo {{ display:flex; gap:14px; align-items:flex-start; margin-bottom:16px; }}
    .num {{
        flex:none; width:30px; height:30px; border-radius:50%; background:{CORES['brand']}; color:#fff;
        font-size:15px; font-weight:700; display:flex; align-items:center; justify-content:center;
    }}
    .passo-t {{ font-size:16px; font-weight:700; line-height:1.25; }}
    .passo-d {{ margin-top:3px; font-size:13.5px; line-height:1.4; color:{CORES['muted']}; }}

    .bloco2 {{ margin-top:26px; }}
    .cartao {{ background:#fff; border:1px solid {CORES['line']}; border-radius:16px; padding:6px 18px; }}
    .linha {{ display:flex; justify-content:space-between; align-items:center; padding:14px 0; }}
    .linha + .linha {{ border-top:1px solid {CORES['line']}; }}
    .linha-t {{ font-size:15px; font-weight:700; line-height:1.25; }}
    .linha-s {{ font-size:12.5px; color:{CORES['muted']}; margin-top:2px; }}
    .valores {{ display:flex; align-items:baseline; gap:8px; white-space:nowrap; }}
    .antes {{ font-size:15px; color:{CORES['muted']}; text-decoration:line-through; }}
    .seta {{ font-size:14px; color:{CORES['muted']}; }}
    .agora {{ font-size:26px; font-weight:700; color:{CORES['success']}; letter-spacing:-0.02em; }}
    .exemplo {{ margin-top:12px; font-size:13.5px; line-height:1.45; color:{CORES['ink']}; }}
    .exemplo b {{ color:{CORES['success']}; }}
    .mais {{ margin-top:4px; font-size:13px; line-height:1.4; color:{CORES['muted']}; }}

    .bom-saber {{
        margin-top:24px; padding:16px 18px; border-left:6px solid {CORES['highlight']};
        background:{fundo_barra}; border-radius:0 12px 12px 0;
    }}
    .bom-saber .tag {{ color:{CORES['ink']}; margin-bottom:8px; }}
    .bom-saber ul {{ list-style:none; }}
    .bom-saber li {{ font-size:13px; line-height:1.4; padding:3px 0 3px 16px; position:relative; }}
    .bom-saber li::before {{ content:""; position:absolute; left:0; top:10px; width:6px; height:6px; border-radius:50%; background:{CORES['highlight']}; }}

    </style></head><body>
        <section class="topo">
            <span class="selo">campanha</span>
            <div class="data">{DATA}</div>
            <div class="manchete">{MANCHETE}</div>
            <p class="paragrafo">{PARAGRAFO}</p>
        </section>

        <section class="miolo">
            <div class="tag">como funciona</div>
            {passos}

            <div class="bloco2">
                <div class="tag">quanto você recebe</div>
                <div class="cartao">
                    <div class="linha">
                        <div><div class="linha-t">Por link ou vitrine</div><div class="linha-s">cashback mínimo</div></div>
                        <div class="valores"><span class="antes">{_pct(direta_hoje)}</span><span class="seta">→</span><span class="agora">{_pct(direta_nova)}</span></div>
                    </div>
                    <div class="linha">
                        <div><div class="linha-t">Botão “Ir pra Shopee”</div><div class="linha-s">cashback mínimo</div></div>
                        <div class="valores"><span class="antes">{_pct(ind_hoje)}</span><span class="seta">→</span><span class="agora">{_pct(ind_nova)}</span></div>
                    </div>
                </div>
                <p class="exemplo">Em uma compra de {_reais(COMPRA_EXEMPLO)} pelo link, no mínimo:
                    <b>{_reais(exemplo_novo)}</b> de volta, em vez de {_reais(exemplo_hoje)}.</p>
                <p class="mais">Muitas vezes, bem mais: o valor de cada produto aparece no card da vitrine.</p>
            </div>

            <div class="bom-saber">
                <div class="tag">bom saber</div>
                <ul>{condicoes}</ul>
            </div>
        </section>

    </body></html>"""


def gerar() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = OUT_DIR / f"banner-{DATA.replace('.', '-')}-completo.png"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(viewport={"width": LARGURA, "height": 800}, device_scale_factor=ESCALA)
        pagina.set_content(_pagina())
        pagina.wait_for_timeout(300)
        altura = pagina.evaluate("document.documentElement.scrollHeight")
        png = pagina.screenshot(clip={"x": 0, "y": 0, "width": LARGURA, "height": altura}, full_page=True)
        navegador.close()
    destino.write_bytes(png)
    print(f"gerado: {destino.relative_to(REPO_ROOT)} ({LARGURA * ESCALA}x{altura * ESCALA}, {len(png) / 1024:.0f} KB)")
    return destino


if __name__ == "__main__":
    gerar()
