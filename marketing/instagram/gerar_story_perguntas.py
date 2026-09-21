"""Fundo de story para a caixa de perguntas do Instagram.

A arte é moldura, não conteúdo: a figurinha de perguntas do Instagram é colada por cima
dela na hora de postar. Por isso o meio do quadro fica vazio de propósito - é o lugar
onde a figurinha vai entrar. Texto no meio sairia coberto, e é o erro mais comum nesse
tipo de arte.

Os exemplos embaixo não são enfeite. Caixa de pergunta sem sugestão recebe pouca
resposta: quem está passando o dedo não para para inventar uma dúvida, mas reconhece a
própria dúvida numa lista.

A arte não traz convite escrito ("pergunte o que quiser" e afins): a própria figurinha
do Instagram já tem um campo de texto onde o convite é escrito na hora de postar, e
repetir a mesma frase acima dela seria dizer duas vezes a mesma coisa.

Sem promessa de anonimato na arte: quem manda a pergunta fica visível para o dono da
conta, e só é anônimo para quem vê a resposta publicada. Escrever "pergunta anônima"
seria informação errada.

Sai em duas peças. A de PERGUNTAS traz os exemplos embaixo e é a que abre a caixa. A de
RESPOSTAS é a mesma arte sem eles, para usar de fundo em cada resposta: ali o cartão da
pergunta e o texto da resposta é que ocupam o quadro, e a lista de exemplos só brigaria
por espaço com eles. Usar o mesmo fundo nas duas faz a sequência inteira ler como uma
coisa só, em vez de stories soltos.

Cada peça em duas cores, porque o fundo depende do que mais vai ao ar no dia: a roxa é a
padrão, a clara serve quando a sequência de stories já está escura.

Como usar:
    python3 gerar_story_perguntas.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    FAMILJEN_B64,
    LIGHT_BG,
    MARCA,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "story-perguntas"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

# Faixa livre para a figurinha de perguntas. A figurinha do Instagram tem cerca de 900px
# de largura e 380 de altura no story; a folga aqui é maior de propósito, para o texto
# não encostar nela mesmo se você arrastar a figurinha um pouco para cima ou para baixo.
ALTURA_VAO = 520

EXEMPLOS = [
    "como o cashback funciona",
    "quando o dinheiro cai",
    "saque via Pix",
    "o site é confiável?",
    "quanto cashback posso ganhar?",
    f"a {MARCA} tem aplicativo?",
]


def _pagina(claro: bool, com_exemplos: bool = True) -> str:
    fundo = LIGHT_BG if claro else BRAND_GRADIENT
    tinta = DARK_BG if claro else "#fff"
    tinta_tag = BRAND_PRIMARY if claro else "rgba(255,255,255,0.65)"
    chip_fundo = "rgba(109,40,217,0.08)" if claro else "rgba(255,255,255,0.14)"
    chip_borda = "rgba(109,40,217,0.18)" if claro else "rgba(255,255,255,0.22)"

    if com_exemplos:
        chips = "".join(f'<span class="chip">{texto}</span>' for texto in EXEMPLOS)
        rodape = (
            '<div class="rodape-titulo">não sabe o que perguntar?</div>'
            f'<div class="chips">{chips}</div>'
        )
    else:
        rodape = ""

    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{fundo};
        font-family:"Familjen", Arial, sans-serif; color:{tinta};
    }}
    /* As margens de cima e de baixo são as faixas que a interface do Instagram ocupa:
       em cima a foto de perfil e o nome da conta, embaixo a barra de resposta. Texto
       ali fica escondido atrás da interface no aparelho de quem assiste. */
    body {{ display:flex; flex-direction:column; padding:250px 90px 300px; }}
    .marca {{ font-size:46px; font-weight:700; letter-spacing:-0.03em; }}
    .tag {{
        font-size:24px; font-weight:700; letter-spacing:4px; text-transform:uppercase;
        color:{tinta_tag}; margin-top:56px;
    }}
    /* O vão. É o motivo de a arte existir: a figurinha de perguntas entra aqui.
       flex:1 em vez de altura fixa para ele comer toda a sobra - assim o texto de cima
       encosta no topo da área segura e os exemplos encostam na base dela, sem espaço
       morto numa das pontas. O min-height é o piso: o vão nunca fica menor que a
       figurinha, mesmo que a lista de exemplos cresça. */
    .vao {{ flex:1; min-height:{ALTURA_VAO}px; }}
    .rodape-titulo {{ font-size:28px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:{tinta_tag}; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:26px; }}
    /* nowrap: rótulo de uma linha só. Além de ser o que uma pastilha deve ser, protege
       o nome da marca - o navegador quebra linha depois de hífen, e "cash-b" partido
       vira "cash-" numa linha e "b" na outra, que lê como erro de digitação. */
    .chip {{
        font-size:32px; padding:18px 28px; border-radius:999px; white-space:nowrap;
        background:{chip_fundo}; border:2px solid {chip_borda}; color:{tinta};
    }}
    </style></head><body>
        <div class="marca">cash-b</div>
        <div class="tag">caixa de perguntas</div>
        <div class="vao"></div>
        {rodape}
    </body></html>"""


def _render(claro: bool, com_exemplos: bool, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(claro, com_exemplos))
        pagina.wait_for_timeout(250)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar():
    for claro, cor in [(False, "roxo"), (True, "claro")]:
        _render(claro, True, OUT_DIR / f"story-perguntas-{cor}.png")
        _render(claro, False, OUT_DIR / f"story-respostas-{cor}.png")


if __name__ == "__main__":
    gerar()
