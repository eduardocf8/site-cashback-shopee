"""Botões ligado/desligado para vídeo — o objeto que a mão "aperta" na cena.

Mesma regra dos cards de produto (gerar_cards_produto.py): os dois estados de um
mesmo botão saem com EXATAMENTE as mesmas dimensões e na mesma posição dentro do
arquivo. Na edição, ligar o botão é trocar uma imagem pela outra na mesma camada -
nada muda de tamanho nem se desloca, só o estado. O que muda de um arquivo para o
outro é só a tinta: a caneleta, a posição da bolinha e o brilho.

Por isso nada aqui é recortado na tinta (ao contrário do kit de logos): o desligado
tem a bolinha à esquerda e o ligado à direita, então recortar justo daria dois
arquivos de tamanhos diferentes e o botão pularia na troca.

Duas famílias, porque a cena pede coisas diferentes:

- interruptor: lê como ligar/desligar sem precisar de legenda, e tem a bolinha que
  se move - se quiser, dá para animar o deslocamento dela entre os dois quadros.
- botão de apertar: redondo, com o símbolo de liga/desliga. É o que combina com o
  gesto de apertar com o dedo, de frente para a câmera.

Cada um também sai com a palavra "cashback" ao lado, em duas cores de texto: a
escura para fundo claro e a clara para fundo escuro. A caneleta e o corpo do botão
funcionam sobre qualquer fundo (são opacos e têm sombra), mas texto solto não - e
só dá para saber qual serve depois de ver o fundo que a câmera capturou.

Sombra em todos os estados, inclusive no desligado: é ela que separa o botão do
fundo do vídeo. Sem ela, o desligado (cinza claro) some numa parede branca.

Como usar:
    python3 gerar_botoes_reel.py
"""
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = REPO_ROOT / "static" / "fonts"
FAMILJEN_B64 = base64.b64encode((FONT_DIR / "familjen-grotesk.woff2").read_bytes()).decode()

OUT_DIR = Path(__file__).resolve().parent / "botoes-reel"

CORES = {
    "ink": "#111827",
    "brand": "#6d28d9",
    "brand-strong": "#4c1d95",
    "paper": "#f8fafc",
    "cinza": "#9ca3af",
    "trilho": "#e5e7eb",
}

# Escala 2 pelo mesmo motivo dos cards: no reel o botão aparece grande na tela, e um
# PNG de 1x ampliado na edição deixa a borda mole.
ESCALA = 2

# Folga em volta do desenho. Precisa caber o brilho do estado ligado, que é o
# elemento que mais se espalha - sem folga suficiente ele sai cortado no arquivo.
# Com 90 o brilho do botão redondo ainda chegava na borda do PNG (alfa 1 nos cantos);
# 120 fecha o degradê dentro do arquivo, com a borda em alfa 0 nos dois estados.
FOLGA = 120


def _svg_energia(cor: str) -> str:
    """Símbolo de liga/desliga (IEC 5010) - o arco aberto com o traço em cima."""
    return f"""
    <svg viewBox="0 0 24 24" fill="none" stroke="{cor}" stroke-width="2.1"
         stroke-linecap="round" class="glifo">
        <path d="M18.36 6.64a9 9 0 1 1-12.72 0"/>
        <path d="M12 2v10"/>
    </svg>
    """


def _interruptor(ligado: bool) -> str:
    estado = "ligado" if ligado else "desligado"
    return f'<div class="trilho {estado}"><div class="bolinha"></div></div>'


def _botao(ligado: bool) -> str:
    estado = "ligado" if ligado else "desligado"
    cor_glifo = CORES["paper"] if ligado else CORES["cinza"]
    return f'<div class="redondo {estado}">{_svg_energia(cor_glifo)}</div>'


def _com_legenda(desenho: str, claro: bool) -> str:
    cor = CORES["paper"] if claro else CORES["ink"]
    return (
        f'<div class="conjunto">{desenho}'
        f'<span class="legenda" style="color:{cor};">cashback</span></div>'
    )


def _pagina(corpo: str, largura: int, altura: int) -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{largura}px; height:{altura}px; background:transparent;
        font-family:"Familjen", Arial, sans-serif;
    }}
    body {{ display:flex; align-items:center; justify-content:center; }}
    .conjunto {{ display:flex; align-items:center; gap:44px; }}
    .legenda {{ font-size:72px; font-weight:700; letter-spacing:-0.02em; line-height:1; }}

    /* ------------------------------------------------- interruptor */
    .trilho {{
        position:relative; width:420px; height:200px; border-radius:100px;
        flex-shrink:0; transition:none;
        box-shadow:0 18px 38px rgba(17,24,39,0.22);
    }}
    /* A borda entra por dentro (inset) e não como border: border mudaria a caixa e
       a conta da posição da bolinha; o inset é só tinta. */
    .trilho.desligado {{
        background:{CORES['trilho']};
        box-shadow:0 18px 38px rgba(17,24,39,0.22), inset 0 0 0 3px rgba(17,24,39,0.10);
    }}
    .trilho.ligado {{
        background:linear-gradient(160deg, {CORES['brand']} 0%, {CORES['brand-strong']} 100%);
        box-shadow:0 18px 38px rgba(17,24,39,0.22), 0 0 70px rgba(109,40,217,0.55);
    }}
    .bolinha {{
        position:absolute; top:20px; width:160px; height:160px; border-radius:50%;
        background:#fff; box-shadow:0 8px 18px rgba(17,24,39,0.28);
    }}
    .trilho.desligado .bolinha {{ left:20px; }}
    .trilho.ligado .bolinha {{ left:240px; }}

    /* --------------------------------------------- botão de apertar */
    .redondo {{
        width:380px; height:380px; border-radius:50%; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
        box-shadow:0 22px 44px rgba(17,24,39,0.26);
    }}
    .redondo.desligado {{
        background:linear-gradient(170deg, #ffffff 0%, {CORES['trilho']} 100%);
        box-shadow:0 22px 44px rgba(17,24,39,0.26), inset 0 0 0 5px rgba(17,24,39,0.12);
    }}
    .redondo.ligado {{
        background:linear-gradient(170deg, {CORES['brand']} 0%, {CORES['brand-strong']} 100%);
        box-shadow:0 22px 44px rgba(17,24,39,0.26), 0 0 80px rgba(109,40,217,0.60),
                   inset 0 0 0 5px rgba(255,255,255,0.30);
    }}
    .glifo {{ width:190px; height:190px; }}
    </style></head><body>{corpo}</body></html>"""


def _render(corpo: str, destino: Path, largura: int, altura: int):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": largura, "height": altura}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(corpo, largura, altura))
        pagina.wait_for_timeout(200)
        pagina.screenshot(path=str(destino), omit_background=True)
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({largura*ESCALA}x{altura*ESCALA})")


def gerar():
    # As medidas de cada família são calculadas uma vez e usadas nos dois estados: é o
    # que garante o mesmo arquivo do mesmo tamanho ligado e desligado.
    largura_trilho, altura_trilho = 420, 200
    lado_redondo = 380
    largura_legenda = 44 + 330  # respiro + a palavra "cashback" a 72px

    medidas = {
        "interruptor": (largura_trilho + FOLGA * 2, altura_trilho + FOLGA * 2),
        "interruptor-cashback": (largura_trilho + largura_legenda + FOLGA * 2, altura_trilho + FOLGA * 2),
        "botao": (lado_redondo + FOLGA * 2, lado_redondo + FOLGA * 2),
        "botao-cashback": (lado_redondo + largura_legenda + FOLGA * 2, lado_redondo + FOLGA * 2),
    }

    for ligado in (False, True):
        estado = "on" if ligado else "off"

        largura, altura = medidas["interruptor"]
        _render(_interruptor(ligado), OUT_DIR / f"interruptor-{estado}.png", largura, altura)

        largura, altura = medidas["botao"]
        _render(_botao(ligado), OUT_DIR / f"botao-{estado}.png", largura, altura)

        for claro in (False, True):
            sufixo = "-claro" if claro else ""
            largura, altura = medidas["interruptor-cashback"]
            _render(
                _com_legenda(_interruptor(ligado), claro),
                OUT_DIR / f"interruptor-cashback-{estado}{sufixo}.png", largura, altura,
            )
            largura, altura = medidas["botao-cashback"]
            _render(
                _com_legenda(_botao(ligado), claro),
                OUT_DIR / f"botao-cashback-{estado}{sufixo}.png", largura, altura,
            )


if __name__ == "__main__":
    gerar()
