"""Banner de e-mail para campanha de cashback aumentado em data dupla.

Estrutura inspirada no e-mail de afiliados da Shopee que o dono do produto trouxe como
referência: bloco de cor no topo com a data em corpo enorme, uma curva branca fechando
esse bloco, e uma fileira de pastilhas com os benefícios. O que muda é tudo o resto -
cor, tipografia e conteúdo são da cash-b.

Nada da Shopee entra na arte além do nome dela escrito: a cash-b é afiliada
independente (é o que o rodapé do site declara), e banner com a marca da Shopee sugere
um vínculo que não existe - ainda mais num e-mail que sai em nome da cash-b.

Ilustração em forma geométrica plana (BRAND.md): moedas e manchas desenhadas em SVG,
nas cores da marca. Sem fotografia e sem render 3D.

**O número do multiplicador é parâmetro.** Quem decide é a campanha cadastrada no admin
(pedidos.CampanhaCashback), não a arte - por isso MULTIPLICADOR aqui, e por isso sai
também uma versão sem número nenhum, para quando a campanha ainda não estiver fechada.

Feito para o campo de banner da comunicação em massa do admin
(`accounts.ComunicacaoEmail.banner`, Fase 50). O template
`templates/emails/comunicacao_vitrine.html` já imprime o wordmark da cash-b ACIMA do
banner e já traz o corpo do texto e os links abaixo dele - por isso a peça aqui não
repete nada disso: sem wordmark (seriam dois empilhados), sem corpo de texto e sem
botão (botão desenhado dentro de imagem não é clicável).

O container do e-mail tem 560px e a célula do banner tem 16px de recuo de cada lado,
então a imagem é exibida com cerca de 528px de largura. O arquivo sai em 2x para não
borrar em tela densa; o template já cuida da escala com width=100%.

O template também aplica `border-radius:12px` na imagem, então a arte é um bloco de cor
inteiro - não tem faixa branca no pé que ficaria com canto arredondado por fora.

Como usar:
    python3 marketing/gerar_banner_email.py
"""
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = REPO_ROOT / "static" / "fonts"
OUT_DIR = Path(__file__).resolve().parent / "banner-email"

FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()

CORES = {
    "ink": "#111827",
    "muted": "#6b7280",
    "brand": "#6d28d9",
    "brand-dark": "#4c1d95",
    "brand-light": "#a78bfa",
    "highlight": "#f59e0b",
    "paper": "#f8fafc",
    "line": "#e0dcef",
}

LARGURA, ALTURA = 560, 360
ESCALA = 2

DATA = "11.11"
# O que a campanha paga. Sai da linha cadastrada em pedidos.CampanhaCashback - o padrão
# do modelo é 2 (cashback em dobro). Conferir no admin antes de mandar o e-mail: arte
# prometendo um número diferente do que o sistema paga é o pior erro possível aqui.
MULTIPLICADOR = "em dobro"

BENEFICIOS = [
    "Vale em toda compra",
    "Entra automático",
    "Sem cupom nenhum",
]


def _moeda(x: int, y: int, tamanho: int, giro: int = 0, opacidade: float = 1.0) -> str:
    """Moeda chapada, no mesmo desenho da ilustração dos painéis de login."""
    r = tamanho / 2
    return f"""
    <g transform="translate({x},{y}) rotate({giro})" opacity="{opacidade}">
        <circle cx="0" cy="0" r="{r}" fill="{CORES['highlight']}"/>
        <circle cx="0" cy="0" r="{r * 0.76}" fill="none"
                stroke="rgba(120,53,15,0.28)" stroke-width="{max(2, tamanho * 0.05)}"/>
        <text x="0" y="{r * 0.34}" text-anchor="middle" font-family="Familjen"
              font-weight="700" font-size="{r * 0.92}" fill="rgba(120,53,15,0.55)"
              letter-spacing="-1">R$</text>
    </g>
    """


def _decoracao() -> str:
    """Moedas e manchas nas bordas, com o centro livre para o texto."""
    return f"""
    <svg class="decoracao" viewBox="0 0 560 360" xmlns="http://www.w3.org/2000/svg">
        <circle cx="516" cy="34" r="128" fill="{CORES['brand-light']}" opacity="0.20"/>
        <circle cx="34" cy="322" r="104" fill="{CORES['brand-light']}" opacity="0.16"/>
        {_moeda(58, 70, 50, -14)}
        {_moeda(118, 142, 30, 18, 0.9)}
        {_moeda(40, 200, 24, 8, 0.75)}
        {_moeda(512, 96, 52, 12)}
        {_moeda(458, 178, 28, -16, 0.9)}
        {_moeda(528, 236, 22, 6, 0.75)}
    </svg>
    """


def _pagina(com_numero: bool) -> str:
    manchete = f"Cashback {MULTIPLICADOR}" if com_numero else "Cashback aumentado"
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:#fff;
        font-family:"Familjen", Arial, sans-serif;
    }}
    .topo {{
        position:relative; height:{ALTURA}px; overflow:hidden;
        background:linear-gradient(160deg, {CORES['brand-dark']} 0%, {CORES['brand']} 62%, #5b21b6 100%);
    }}
    .decoracao {{ position:absolute; inset:0; width:100%; height:100%; }}
    .conteudo {{ position:relative; padding:34px 44px 0; text-align:center; }}
    .selo {{
        display:inline-block; padding:7px 18px; border-radius:999px;
        background:{CORES['highlight']}; color:{CORES['ink']};
        font-size:13px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
    }}
    .data {{
        margin-top:16px; font-size:116px; font-weight:700; line-height:0.94;
        letter-spacing:-0.05em; color:#fff;
    }}
    .manchete {{
        margin-top:2px; font-size:29px; font-weight:700; letter-spacing:0.02em;
        text-transform:uppercase; color:{CORES['highlight']};
    }}
    /* Pastilhas claras sobre o roxo, dentro do próprio bloco: a faixa branca da
       referência não cabe aqui, porque o template arredonda a imagem inteira e uma
       faixa branca no pé apareceria com o canto cortado. */
    .beneficios {{
        position:relative; margin-top:22px; display:flex; gap:8px;
        padding:0 30px; justify-content:center;
    }}
    .beneficio {{
        padding:8px 14px; border-radius:999px;
        background:rgba(255,255,255,0.14); border:1px solid rgba(255,255,255,0.28);
        font-size:13px; font-weight:700; color:#fff; white-space:nowrap;
    }}
    </style></head><body>
        <div class="topo">
            {_decoracao()}
            <div class="conteudo">
                <span class="selo">campanha</span>
                <div class="data">{DATA}</div>
                <div class="manchete">{manchete}</div>
                <div class="beneficios">
                    {"".join(f'<div class="beneficio">{b}</div>' for b in BENEFICIOS)}
                </div>
            </div>
        </div>
    </body></html>"""


def _render(com_numero: bool, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(com_numero))
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar():
    _render(True, OUT_DIR / "banner-11-11-em-dobro.png")
    _render(False, OUT_DIR / "banner-11-11-sem-numero.png")
    print("\nSubir no campo de banner da comunicação em massa do admin.")


if __name__ == "__main__":
    gerar()
