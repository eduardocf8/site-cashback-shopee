"""Capa de reel sem foto: tipografia grande + a ilustração da marca.

Alternativa à capa com foto (`gerar_capa_reel.py`), para reel em que ninguém aparece
ou em que o quadro do vídeo não rende uma boa capa.

Segue a regra de ilustração do BRAND.md: forma geométrica plana nas cores da marca,
nunca fotografia de banco de imagens nem render 3D. A moeda é a mesma ilustração dos
painéis de login (`accounts/templates/accounts/_ilustracao_auth.html`) - anel âmbar
incompleto, moeda clara e o "R$" no roxo escuro -, só que em corpo grande.

O nome "Shopee" aparece como texto, e o logotipo dela não aparece em lugar nenhum: a
cash-b é afiliada independente (é o que o rodapé do site declara), e arte que carrega a
marca da Shopee sugere um vínculo que não existe.

Composição em duas faixas, e não elementos soltos sobre um fundo: em cima o bloco de
texto sobre o claro, embaixo o painel roxo com a ilustração. A divisão dá à capa uma
silhueta reconhecível mesmo no tamanho de miniatura da grade do perfil.

Como usar:
    python3 gerar_capa_ilustrada.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import (
    BRAND_DARK,
    BRAND_LIGHT,
    BRAND_PRIMARY,
    DARK_BG,
    FAMILJEN_B64,
    HIGHLIGHT,
    LIGHT_BG,
    MARCA,
    MUTED,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "capa-reel"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

TITULO = f'Como ganhar <span class="grifo">cashback</span> na Shopee?'
CHAMADA = "é mais fácil do que você imagina"


def _ilustracao() -> str:
    """A moeda dos painéis de autenticação, em corpo de capa.

    Mesmos elementos e proporções do original, com uma diferença: a mancha de fundo é
    branca a 10%, não âmbar a 16%. No painel de login ela fica sobre o claro e lê como
    âmbar; aqui, sobre o roxo, o âmbar translúcido vira um cinza-barro sem cor definida.
    Branco a baixa opacidade dá o mesmo volume e some como fundo, que é a função dela.
    """
    return f"""
    <svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg">
        <path d="M42,124 C14,78 66,18 138,24 C206,30 262,14 292,72 C322,130 302,202 248,244
                 C196,284 116,302 66,258 C18,216 68,172 42,124 Z"
              fill="#ffffff" opacity="0.10"/>
        <circle cx="160" cy="160" r="88" fill="none" stroke="{HIGHLIGHT}" stroke-width="10"
                stroke-linecap="round" stroke-dasharray="430 90"
                transform="rotate(-40 160 160)"/>
        <circle cx="160" cy="160" r="66" fill="{LIGHT_BG}"/>
        <text x="160" y="177" text-anchor="middle" font-size="46" letter-spacing="-2"
              font-family="Familjen" font-weight="700" fill="{BRAND_DARK}">R$</text>
    </svg>
    """


def _pagina() -> str:
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{
        width:{LARGURA}px; height:{ALTURA}px; background:{LIGHT_BG};
        font-family:"Familjen", Arial, sans-serif; overflow:hidden;
    }}
    body {{ position:relative; }}
    /* Manchas de fundo. Ficam atrás de tudo e sangram para fora do quadro de
       propósito: forma cortada pela borda lê como recorte de um sistema maior,
       enquanto a mesma forma inteira e centralizada lê como adesivo. */
    .mancha-a {{
        position:absolute; left:-190px; top:980px; width:560px; height:560px;
        border-radius:50%; background:{BRAND_LIGHT}; opacity:0.30;
    }}
    .mancha-b {{
        position:absolute; right:-150px; top:-120px; width:420px; height:420px;
        border-radius:50%; border:8px solid {BRAND_PRIMARY}; opacity:0.30;
    }}
    .topo {{ position:absolute; top:150px; left:90px; right:90px; }}
    .marca {{ font-size:78px; font-weight:700; letter-spacing:-0.04em; color:{BRAND_PRIMARY}; }}
    .titulo {{
        margin-top:110px; font-size:104px; font-weight:700; line-height:1.04;
        letter-spacing:-0.04em; color:{DARK_BG};
    }}
    .grifo {{ color:{BRAND_PRIMARY}; white-space:nowrap; }}
    .chamada {{
        margin-top:44px; font-size:30px; font-weight:600; letter-spacing:0.18em;
        text-transform:uppercase; color:{MUTED}; line-height:1.5;
    }}
    .regua {{ margin-top:40px; width:132px; height:9px; border-radius:99px; background:{BRAND_PRIMARY}; }}
    /* Painel de baixo: a faixa que dá silhueta à capa na miniatura da grade. */
    .painel {{
        position:absolute; left:0; right:0; bottom:0; height:760px;
        border-top-left-radius:120px;
        background:linear-gradient(165deg, {BRAND_DARK} 0%, {BRAND_PRIMARY} 100%);
        display:flex; align-items:center; justify-content:center;
    }}
    .painel svg {{ width:600px; height:600px; margin-top:-40px; }}
    </style></head><body>
        <div class="mancha-a"></div>
        <div class="mancha-b"></div>
        <div class="topo">
            <div class="marca">{MARCA}</div>
            <div class="titulo">{TITULO}</div>
            <div class="chamada">{CHAMADA}</div>
            <div class="regua"></div>
        </div>
        <div class="painel">{_ilustracao()}</div>
    </body></html>"""


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = OUT_DIR / "capa-ilustrada.png"
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina())
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=str(destino))
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


if __name__ == "__main__":
    gerar()
