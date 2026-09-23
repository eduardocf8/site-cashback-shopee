"""Capa do reel: a foto de quem aparece no vídeo + a camada da marca por cima.

A capa é escolhida no Instagram em "Editar capa", e o botão "Adicionar do Rolo da
Câmera" aceita uma imagem pronta - que é o que este script gera. Por isso a arte sai
achatada com a foto, e não como adesivo para colar depois: o editor do Instagram não
monta camada, só aceita a imagem final.

Duas faixas do quadro ficam livres de texto de propósito:

- Os ~300px de baixo, onde o player do reel escreve o nome do perfil e a legenda por
  cima da capa. Texto ali some atrás da interface.
- O rosto. O escurecimento sobe do pé do quadro e para antes da altura da cabeça, para
  a pessoa continuar reconhecível - é ela que faz alguém parar de rolar, não a frase.

O texto fica na faixa de baixo do meio (por volta de 1180 a 1560), que sobrevive ao
recorte quadrado da grade do perfil e ainda assim está acima da interface do player.

A foto entra cobrindo o quadro (cover, não contain): sobra é cortada, mas nunca aparece
borda vazia. O enquadramento horizontal é ajustável em FOCO_X, porque em foto de pessoa
o centro geométrico quase nunca é o centro do assunto.

Como usar:
    python3 gerar_capa_reel.py caminho/da/foto.jpg
    python3 gerar_capa_reel.py            # só a camada da marca, fundo transparente
"""
import base64
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from carrossel_base import BRAND_DARK, FAMILJEN_B64, HIGHLIGHT, MARCA

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "capa-reel"

LARGURA, ALTURA = 1080, 1920
ESCALA = 2

# Posição horizontal do assunto dentro da foto, para o corte "cover". 50% é o centro.
FOCO_X = "50%"

TITULO = f'3 formas de ganhar <span class="grifo">cashback</span> na Shopee'


def _foto_embutida(caminho: Path) -> str:
    tipo = "jpeg" if caminho.suffix.lower() in {".jpg", ".jpeg"} else caminho.suffix.lstrip(".")
    return f"data:image/{tipo};base64,{base64.b64encode(caminho.read_bytes()).decode()}"


def _pagina(foto: Path | None) -> str:
    fundo_foto = (
        f'background-image:url({_foto_embutida(foto)}); background-size:cover; '
        f"background-position:{FOCO_X} center;"
        if foto else "background:transparent;"
    )
    return f"""<html><head><style>
    @font-face {{ font-family:"Familjen"; src:url(data:font/woff2;base64,{FAMILJEN_B64}) format("woff2"); font-weight:400 700; }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    html, body {{ width:{LARGURA}px; height:{ALTURA}px; font-family:"Familjen", Arial, sans-serif; }}
    body {{ {fundo_foto} position:relative; }}
    /* O escurecimento começa transparente na altura do rosto e fecha no pé do quadro.
       Sem ele o texto branco disputa com o que estiver na foto; com ele chapado por
       cima de tudo, a pessoa desaparece. */
    .veu {{
        position:absolute; inset:0;
        background:linear-gradient(to bottom,
            rgba(46,16,101,0) 42%,
            rgba(46,16,101,0.55) 58%,
            {BRAND_DARK} 78%,
            #2e1065 100%);
    }}
    .marca {{
        position:absolute; top:150px; left:90px;
        font-size:48px; font-weight:700; letter-spacing:-0.03em; color:#fff;
        text-shadow:0 4px 24px rgba(0,0,0,0.45);
    }}
    /* bottom em 360px: acima dos ~300px que o player do reel cobre com nome e legenda. */
    .titulo {{
        position:absolute; left:90px; right:90px; bottom:360px;
        font-size:92px; font-weight:700; line-height:1.06; letter-spacing:-0.035em; color:#fff;
    }}
    /* Grifo âmbar na palavra que importa - mesmo recurso dos carrosséis. Feito como
       fundo da própria palavra, e não como pseudo-elemento atrás dela: com z-index
       negativo o grifo caía atrás do véu (que é irmão mais antigo no DOM) e sumia. Como
       background, ele fica na caixa do texto e a letra continua por cima. */
    .grifo {{
        white-space:nowrap; padding:0 8px;
        background:linear-gradient(to top, {HIGHLIGHT} 0 24px, transparent 24px);
    }}
    </style></head><body>
        <div class="veu"></div>
        <div class="marca">cash-b</div>
        <div class="titulo">{TITULO}</div>
    </body></html>"""


def _render(foto: Path | None, destino: Path):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(
            viewport={"width": LARGURA, "height": ALTURA}, device_scale_factor=ESCALA
        )
        pagina.set_content(_pagina(foto))
        pagina.wait_for_timeout(300)
        pagina.screenshot(path=str(destino), omit_background=foto is None)
        navegador.close()
    print("gerado:", destino.relative_to(REPO_ROOT), f"({LARGURA*ESCALA}x{ALTURA*ESCALA})")


def gerar(foto: Path | None = None):
    # A camada sozinha sai sempre: serve para montar a capa em outro editor, se um dia
    # a foto vier de um lugar que este script não alcança.
    _render(None, OUT_DIR / "capa-camada.png")
    if foto:
        _render(foto, OUT_DIR / "capa-reel.png")


if __name__ == "__main__":
    gerar(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
