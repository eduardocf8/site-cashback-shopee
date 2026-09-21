"""Fundo de story para a caixa de perguntas do Instagram.

A arte é moldura, não conteúdo: a figurinha de perguntas do Instagram é colada por cima
dela na hora de postar. Por isso o meio do quadro fica vazio de propósito - é o lugar
onde a figurinha vai entrar. Texto no meio sairia coberto, e é o erro mais comum nesse
tipo de arte.

Os exemplos embaixo não são enfeite. Caixa de pergunta sem sugestão recebe pouca
resposta: quem está passando o dedo não para para inventar uma dúvida, mas reconhece a
própria dúvida numa lista. Os quatro são os assuntos que o site mais explica
(regras_cashback.html, e_confiavel.html, faq.html) - ou seja, o que já se sabe que as
pessoas perguntam.

Sem promessa de anonimato na arte: quem manda a pergunta fica visível para o dono da
conta, e só é anônimo para quem vê a resposta publicada. Escrever "pergunta anônima"
seria informação errada.

Duas versões, porque o fundo do story depende do que mais vai ao ar no dia: a roxa é a
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
    JBMONO_B64,
    LIGHT_BG,
    MARCA,
    MUTED,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "story-perguntas"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

# Faixa livre para a figurinha de perguntas. A figurinha do Instagram tem cerca de 900px
# de largura e 380 de altura no story; a folga aqui é maior de propósito, para o texto
# não encostar nela mesmo se você arrastar a figurinha um pouco para cima ou para baixo.
ALTURA_VAO = 520

TITULO = f"Pergunte o que quiser sobre a {MARCA}"
CHAMADA = "Respondo tudo aqui nos stories."
EXEMPLOS = [
    "como o cashback funciona",
    "quando o dinheiro cai",
    "saque via Pix",
    "o site é confiável?",
]


def _pagina(claro: bool) -> str:
    fundo = LIGHT_BG if claro else BRAND_GRADIENT
    tinta = DARK_BG if claro else "#fff"
    tinta_suave = MUTED if claro else "rgba(255,255,255,0.78)"
    tinta_tag = BRAND_PRIMARY if claro else "rgba(255,255,255,0.65)"
    chip_fundo = "rgba(109,40,217,0.08)" if claro else "rgba(255,255,255,0.14)"
    chip_borda = "rgba(109,40,217,0.18)" if claro else "rgba(255,255,255,0.22)"

    chips = "".join(f'<span class="chip">{texto}</span>' for texto in EXEMPLOS)

    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    @font-face {{ font-family:"JB Mono"; src:url(data:font/woff2;base64,{JBMONO_B64}) format("woff2"); font-weight:400 700; }}
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
    .titulo {{ font-size:82px; font-weight:700; letter-spacing:-0.035em; line-height:1.08; margin-top:22px; }}
    .chamada {{ font-size:34px; color:{tinta_suave}; margin-top:24px; line-height:1.35; }}
    /* O vão. É o motivo de a arte existir: a figurinha de perguntas entra aqui.
       flex:1 em vez de altura fixa para ele comer toda a sobra - assim o texto de cima
       encosta no topo da área segura e os exemplos encostam na base dela, sem espaço
       morto numa das pontas. O min-height é o piso: o vão nunca fica menor que a
       figurinha, mesmo que o título cresça. */
    .vao {{ flex:1; min-height:{ALTURA_VAO}px; }}
    .rodape-titulo {{ font-size:28px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:{tinta_tag}; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:26px; }}
    .chip {{
        font-size:32px; padding:18px 28px; border-radius:999px;
        background:{chip_fundo}; border:2px solid {chip_borda}; color:{tinta};
    }}
    </style></head><body>
        <div class="marca">cash-b</div>
        <div class="tag">caixa de perguntas</div>
        <div class="titulo">{TITULO}</div>
        <div class="chamada">{CHAMADA}</div>
        <div class="vao"></div>
        <div class="rodape-titulo">não sabe o que perguntar?</div>
        <div class="chips">{chips}</div>
    </body></html>"""


def _render(claro: bool, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(claro))
        pagina.wait_for_timeout(250)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar():
    _render(False, OUT_DIR / "story-perguntas-roxo.png")
    _render(True, OUT_DIR / "story-perguntas-claro.png")


if __name__ == "__main__":
    gerar()
