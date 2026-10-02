"""Banner de e-mail para campanha de cashback aumentado em data dupla (hoje: 10.10, 50% a mais).

Estrutura inspirada no e-mail de afiliados da Shopee que o dono do produto trouxe como
referência: bloco de cor no topo com a data em corpo enorme, uma curva branca fechando
esse bloco, e uma fileira de pastilhas com os benefícios. O que muda é tudo o resto -
cor, tipografia e conteúdo são da cash-b.

Nada da Shopee entra na arte além do nome dela escrito: a cash-b é afiliada
independente (é o que o rodapé do site declara), e banner com a marca da Shopee sugere
um vínculo que não existe - ainda mais num e-mail que sai em nome da cash-b.

Dois fundos possíveis, escolhidos por `FUNDO_ILUSTRADO`:

- Ilustração em `arte/fundo-campanha.webp`, se o arquivo existir. É arte plana em
  vetor, nas cores da marca, com o centro vazio - gerada por modelo de imagem e
  aprovada pelo dono do produto. Casa com a regra do BRAND.md (forma chapada, sem
  fotografia e sem render 3D) apesar da origem.
- Senão, moedas e manchas desenhadas aqui mesmo em SVG. É o retrato de reserva: sai
  sempre, não depende de arquivo externo e é o que a marca já usa nos painéis de login.

O banner tem a mesma proporção 16:9 da arte, de propósito. Num quadro mais quadrado o
"cover" ampliava a ilustração para preencher a altura, e aí as caixas de presente dos
cantos inferiores cresciam para cima do texto. Na proporção nativa ela entra inteira, e
cada elemento fica no canto onde foi desenhado.

**O número do multiplicador é parâmetro.** Quem decide é a campanha cadastrada no admin
(pedidos.CampanhaCashback), não a arte - por isso a manchete é uma constante aqui, e por isso sai
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

LARGURA, ALTURA = 560, 315
ESCALA = 2

# Fundo da peça. Aponta para um dos fundos da família da marca
# (marketing/gerar_fundos_marca.py); trocar o nome aqui troca a cara do banner sem
# mexer em mais nada. A arte gerada por IA continua em banner-email/arte/, se um dia
# a campanha pedir algo mais ilustrado.
ARTE = Path(__file__).resolve().parent / "fundos-marca" / "fundo-03-canto-roxo-16x9.png"

DATA = "10.10"
DIA = DATA.split(".")[0]   # "10": só vale no dia
ARQ = DATA.replace(".", "-")   # nome dos arquivos: banner-10-10-...

# O que a campanha paga, em palavras. Sai da linha cadastrada em pedidos.CampanhaCashback
# (CampanhaCashback.percentual_extra: multiplicador 1,5 = 50). Conferir no admin antes de
# mandar o e-mail: arte prometendo um número diferente do que o sistema paga é o pior erro
# possível aqui.
#
# "50% a mais de cashback" e não "+50%": "+50%" lê como "cashback de 50%", o mal-entendido que
# vira reclamação depois. Se a campanha for de multiplicador 2, trocar por "Cashback em dobro".
PERCENTUAL_EXTRA = 50
MANCHETE_COM_NUMERO = f"{PERCENTUAL_EXTRA}% a mais de cashback"
MANCHETE_SEM_NUMERO = "Cashback aumentado"

# O parágrafo explica o que a manchete promete: quando vale, em quais pedidos e o que a
# pessoa ganha. Na versão sem número a frase não cita o percentual (é a que se usa quando o
# multiplicador ainda não está decidido).
DIA_MES = DATA.replace(".", "/")


def _texto(com_numero: bool) -> str:
    quanto = f"{PERCENTUAL_EXTRA}% a mais de cashback" if com_numero else "mais cashback"
    return (f"Durante todo o {DIA_MES}, todos os pedidos realizados terão {quanto}. "
            "Essa é a sua chance de poupar e ainda receber mais dinheiro de volta!")

BENEFICIOS = [
    "Vale em toda compra",
    "Entra automático",
    f"Só no dia {DIA}",
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


def _pagina(com_numero: bool, ilustrado: bool) -> str:
    manchete = MANCHETE_COM_NUMERO if com_numero else MANCHETE_SEM_NUMERO
    classe_topo = "ilustrado" if ilustrado else ""
    if ilustrado:
        arte64 = base64.b64encode(ARTE.read_bytes()).decode()
        fundo_css = (f"background-image:url(data:image/png;base64,{arte64});"
                     "background-size:cover; background-position:center;")
        decoracao = ""
        # O fundo abstrato deixa o miolo livre, então as pastilhas voltam: era a
        # ilustração cheia (caixas de presente no pé) que disputava esse espaço.
        pastilhas = ('<div class="beneficios">'
                     + "".join(f'<div class="beneficio">{b}</div>' for b in BENEFICIOS)
                     + "</div>")
    else:
        fundo_css = ""
        decoracao = _decoracao()
        pastilhas = ('<div class="beneficios">'
                     + "".join(f'<div class="beneficio">{b}</div>' for b in BENEFICIOS)
                     + "</div>")
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
        {fundo_css}
    }}
    /* Véu escuro sobre a ilustração. Sem ele o texto branco disputa com as moedas
       âmbar nas bordas; com ele o miolo escurece de leve e o texto ganha a frente,
       sem apagar a arte. */
    .veu {{ position:absolute; inset:0; background:rgba(46,16,101,0.22); }}
    .decoracao {{ position:absolute; inset:0; width:100%; height:100%; }}
    /* O bloco inteiro é centralizado na vertical (e não ancorado no alto): sobra a mesma
       folga em cima do selo e embaixo das pastilhas. A margem é medida no navegador a cada
       render (ver _medir_margens) e o gerador falha se cima e baixo diferirem. */
    .topo {{ display:flex; flex-direction:column; justify-content:center; }}
    .conteudo {{ position:relative; padding:0 40px; text-align:center; }}
    .topo .data {{ margin-top:8px; font-size:84px; }}
    .topo .manchete {{ font-size:22px; margin-top:2px; }}
    .texto {{
        margin:9px auto 0; max-width:430px; font-size:12.5px; font-weight:500; line-height:1.42;
        color:rgba(255,255,255,0.9); text-wrap:balance;
    }}
    .selo {{
        display:inline-block; padding:7px 18px; border-radius:999px;
        background:{CORES['highlight']}; color:{CORES['ink']};
        font-size:13px; font-weight:700; letter-spacing:2px; text-transform:uppercase;
    }}
    .data {{
        margin-top:10px; font-size:100px; font-weight:700; line-height:0.94;
        letter-spacing:-0.05em; color:#fff;
    }}
    .manchete {{
        margin-top:0; font-size:26px; font-weight:700; letter-spacing:0.02em;
        text-transform:uppercase; color:{CORES['highlight']};
    }}
    /* Pastilhas claras sobre o roxo, dentro do próprio bloco: a faixa branca da
       referência não cabe aqui, porque o template arredonda a imagem inteira e uma
       faixa branca no pé apareceria com o canto cortado. */
    .beneficios {{
        position:relative; margin-top:13px; display:flex; gap:8px;
        padding:0 30px; justify-content:center;
    }}
    .beneficio {{
        padding:7px 13px; border-radius:999px;
        background:rgba(255,255,255,0.14); border:1px solid rgba(255,255,255,0.28);
        font-size:12px; font-weight:700; color:#fff; white-space:nowrap;
    }}
    </style></head><body>
        <div class="topo {classe_topo}">
            {decoracao}
            <div class="conteudo">
                <span class="selo">campanha</span>
                <div class="data">{DATA}</div>
                <div class="manchete">{manchete}</div>
                <p class="texto">{_texto(com_numero)}</p>
                {pastilhas}
            </div>
        </div>
    </body></html>"""


TOLERANCIA_MARGEM = 1.0   # px (na escala do banner, 560x315)


def _medir_margens(pagina) -> dict:
    """Margens reais do conteúdo, medidas no navegador: do topo do selo ao topo do banner e do
    pé das pastilhas ao pé do banner, e as laterais do bloco inteiro."""
    return pagina.evaluate("""() => {
        const caixa = (el) => el.getBoundingClientRect();
        const selo = caixa(document.querySelector('.selo'));
        const pastilhas = [...document.querySelectorAll('.beneficio')].map(caixa);
        const todos = [selo, caixa(document.querySelector('.data')),
                       caixa(document.querySelector('.manchete')), caixa(document.querySelector('.texto')),
                       ...pastilhas];
        const l = Math.min(...todos.map(b => b.left)), r = Math.max(...todos.map(b => b.right));
        const fundo = Math.max(...pastilhas.map(b => b.bottom));
        return {cima: selo.top, baixo: innerHeight - fundo, esq: l, dir: innerWidth - r};
    }""")


def _render(com_numero: bool, ilustrado: bool, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(com_numero, ilustrado))
        pagina.wait_for_timeout(300)
        m = _medir_margens(pagina)
        if abs(m["cima"] - m["baixo"]) > TOLERANCIA_MARGEM:
            raise SystemExit(f"Margens desiguais em {destino.name}: cima {m['cima']:.1f}px, "
                             f"baixo {m['baixo']:.1f}px - ajustar o layout antes de usar o banner.")
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})",
          f"| margens cima {m['cima']:.1f} / baixo {m['baixo']:.1f}px, laterais {m['esq']:.0f} / {m['dir']:.0f}px")


def gerar():
    for ilustrado in ([True, False] if ARTE.exists() else [False]):
        sufixo = "" if ilustrado else "-vetor"
        _render(True, ilustrado, OUT_DIR / f"banner-{ARQ}-mais-50{sufixo}.png")
        _render(False, ilustrado, OUT_DIR / f"banner-{ARQ}-sem-numero{sufixo}.png")
    print("\nSubir no campo de banner da comunicação em massa do admin.")


if __name__ == "__main__":
    gerar()
