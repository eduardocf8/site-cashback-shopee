"""Os 5 Pins do teste manual (passo 0 do plano do Pinterest) que levam para a cash-b.

Arte só tipográfica, sem foto de produto, de propósito: o teste compara o destino
(tag nativa da Shopee x página da categoria na cash-b), e uma arte que não depende de
foto pode ser feita sem acesso à Shopee e não fica velha quando o produto sai do ar.
Sem preço, pelo mesmo motivo de pinterest/imagem.py: Pin vive meses.

Fundo: composição 03-canto (a padrão da família, ver BRAND.md > Fundos da marca),
redesenhada em 2:3 em vez de recortada. Fontes e paleta: carrossel_base.py.

Saída em marketing/pinterest/pins-teste/, com legendas.txt ao lado (título, descrição,
link e board de cada Pin, prontos para copiar).

Como usar:
    python3 marketing/pinterest/gerar_pins_teste.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / "instagram"))

from carrossel_base import (  # noqa: E402
    BRAND_DARK, BRAND_LIGHT, BRAND_PRIMARY, DARK_BG, FONT_FACES, HIGHLIGHT, MARCA, MUTED, SUCCESS,
)
from gerar_fundos_marca import _canto, _svg  # noqa: E402

OUT_DIR = AQUI / "pins-teste"
LARGURA, ALTURA = 1000, 1500
SITE = "https://cash-b.com"

# id = categoria nível 1 da Shopee (ofertas/data/shopee_categorias_nivel1.json); o link
# do Pin cai em /ofertas/?categoria=id, que sobrevive à sincronização diária.
# "titulo_arte" é o nome curto que cabe grande na arte; "nome" é o nome da Shopee.
PINS = [
    {"id": 100636, "nome": "Casa e Decoração", "titulo_arte": "Casa e decoração",
     "gancho": "Para deixar a casa do seu jeito", "slug": "casa-e-decoracao"},
    {"id": 100630, "nome": "Beleza", "titulo_arte": "Beleza",
     "gancho": "Do skincare à maquiagem", "slug": "beleza"},
    {"id": 100013, "nome": "Celulares e Dispositivos", "titulo_arte": "Celular e acessórios",
     "gancho": "Capinhas, carregadores e fones", "slug": "celulares-e-dispositivos"},
    {"id": 100017, "nome": "Roupas Femininas", "titulo_arte": "Moda feminina",
     "gancho": "Os looks que mais vendem", "slug": "roupas-femininas"},
    {"id": 100637, "nome": "Esportes e Atividades ao Ar Livre", "titulo_arte": "Esporte e ar livre",
     "gancho": "Para treinar e se aventurar", "slug": "esportes-e-atividades-ao-ar-livre"},
]

PASSOS = [
    ("Escolha a oferta", "na cash-b, entre os mais vendidos da Shopee"),
    ("Compre normalmente", "no app da Shopee, do jeito de sempre"),
    ("Receba de volta", "parte do valor cai para você via Pix"),
]


def _passo(numero, titulo, texto):
    return f"""
    <div style="display:flex; gap:28px; align-items:flex-start; padding:26px 0;
                border-bottom:2px solid #ede9f7;">
        <div style="font-family:'JB Mono'; font-weight:700; font-size:44px; color:{BRAND_PRIMARY};
                    letter-spacing:-0.06em; line-height:1; width:44px; flex-shrink:0;">{numero}</div>
        <div>
            <div style="font-family:Familjen; font-weight:700; font-size:38px; color:{DARK_BG};
                        letter-spacing:-0.02em; line-height:1.1;">{titulo}</div>
            <div style="font-family:Familjen; font-size:28px; color:{MUTED}; margin-top:8px;
                        line-height:1.3;">{texto}</div>
        </div>
    </div>"""


def _html(pin):
    passos = "".join(_passo(i, t, x) for i, (t, x) in enumerate(PASSOS, start=1))
    # Grifo âmbar uma vez só na peça (BRAND.md > O grifo), como background da própria
    # palavra - não pseudo-elemento, que some atrás do fundo.
    grifo = f"background:linear-gradient(to top, {HIGHLIGHT} 0 14px, transparent 14px); padding:0 4px;"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    {FONT_FACES}
    body {{ margin:0; width:{LARGURA}px; height:{ALTURA}px; overflow:hidden; position:relative; }}
    .fundo {{ position:absolute; inset:0; }}
    .conteudo {{ position:absolute; inset:0; padding:96px 84px 84px; box-sizing:border-box;
                 display:flex; flex-direction:column; }}
    </style></head><body>
    <div class="fundo">{_svg(_canto, LARGURA, ALTURA, claro=False)}</div>
    <div class="conteudo">
        <div style="flex:0.6;"></div>
        <div style="font-family:'JB Mono'; font-weight:700; font-size:28px; letter-spacing:0.08em;
                    color:{BRAND_LIGHT};">OFERTAS NA SHOPEE</div>
        <div style="font-family:Familjen; font-weight:700; font-size:104px; line-height:1.0;
                    letter-spacing:-0.035em; color:#fff; margin-top:28px;">{pin['titulo_arte']}</div>
        <div style="font-family:Familjen; font-weight:700; font-size:46px; line-height:1.2;
                    letter-spacing:-0.025em; color:#fff; margin-top:28px;">
            {pin['gancho']}, com <span style="{grifo} color:{DARK_BG};">cashback</span>
        </div>
        <div style="flex:0.4; min-height:72px;"></div>
        <div style="background:#fff; border-radius:56px; padding:40px 64px 30px;
                    box-shadow:0 30px 60px rgba(17,24,39,0.18);">
            <div style="font-family:Familjen; font-weight:700; font-size:26px; color:{SUCCESS};
                        letter-spacing:0.02em; padding-bottom:6px;">Toda compra gera cashback</div>
            {passos.rsplit('border-bottom:2px solid #ede9f7;', 1)[0]}{passos.rsplit('border-bottom:2px solid #ede9f7;', 1)[1]}
        </div>
        <div style="flex:0.6;"></div>
        <div style="display:flex; justify-content:space-between; align-items:baseline;">
            <div style="font-family:Familjen; font-weight:700; font-size:64px; letter-spacing:-0.03em;
                        color:#fff;">{MARCA}</div>
            <div style="font-family:Familjen; font-size:30px; color:{BRAND_LIGHT};">Toque para ver as ofertas</div>
        </div>
    </div>
    </body></html>"""


def _link(pin):
    return (f"{SITE}/ofertas/?categoria={pin['id']}&utm_source=pinterest&utm_medium=pin"
            f"&utm_campaign={pin['slug']}")


def _legendas():
    blocos = []
    for i, pin in enumerate(PINS, start=1):
        blocos.append(
            f"PIN {i}: pin-{i:02d}-{pin['slug']}.png\n"
            f"Título: {pin['nome']}: os mais vendidos da Shopee com cashback\n"
            f"Descrição: Os produtos mais vendidos de {pin['nome']} na Shopee, reunidos na cash-b. "
            "Você compra normalmente na Shopee e parte do valor volta para você via Pix: "
            "toda compra gera cashback. Contém link de afiliado.\n"
            f"Link: {_link(pin)}\n"
            f"Board: Ofertas de {pin['nome']} na Shopee\n"
        )
    return "\n".join(blocos)


def gerar():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for i, pin in enumerate(PINS, start=1):
            pagina = navegador.new_page(viewport={"width": LARGURA, "height": ALTURA})
            pagina.set_content(_html(pin))
            pagina.wait_for_timeout(200)
            pagina.screenshot(path=str(OUT_DIR / f"pin-{i:02d}-{pin['slug']}.png"))
            pagina.close()
        navegador.close()
    (OUT_DIR / "legendas.txt").write_text(_legendas(), encoding="utf-8")
    print(f"gerados {len(PINS)} Pins em {OUT_DIR}")


if __name__ == "__main__":
    gerar()
