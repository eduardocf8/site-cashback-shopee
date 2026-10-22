"""Artes dos produtos do Appfiliado para o checkout da Zouti (1000 x 1000 px, PNG).

Uso (na raiz do repositório, com o Playwright e o Chromium instalados):
    python3 marketing/appfiliado/gerar_artes_produtos.py

Sai em marketing/appfiliado/produtos/. As artes não têm preço de propósito: o mesmo
produto pode ter plano mensal e anual, e o preço muda sem precisar refazer a arte.
Cores e logotipo são os do painel (painel/static/painel/painel.css)."""

import html
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "produtos"

VERDE, VERDE_2, CREME, AMARELO, TINTA = "#1F3A2E", "#2D4B3D", "#F6F3EA", "#F2C230", "#1D2A23"
ICONES = {
    "whatsapp": "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z",
    "site": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "carrosseis": "M7 5h10v14H7zM3 7v10M21 7v10",
    "notas": "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
}
LOGO = ('<svg viewBox="3 8.25 36 36" width="54" height="54"><g fill="none" stroke="currentColor" stroke-width="5" '
        'stroke-linecap="round"><circle cx="21" cy="26" r="9.5"/><path d="M30.5 16.5V36"/></g>'
        '<circle cx="21" cy="26" r="3.6" fill="currentColor"/></svg>')

BOT = ("whatsapp", "Bot de WhatsApp", "Ofertas da Shopee no automático nos seus grupos, com o seu link.")
SITE = ("site", "Meu site", "Seu link na bio com vitrine de ofertas e conversor de links.")
CARR = ("carrosseis", "Gerador de carrosséis", "Carrosséis para o Instagram prontos a partir de um link da Shopee.")
NOTAS = ("notas", "Emissor NFS-e", "As notas dos vendedores direto do relatório da Shopee.")

AVULSOS = [
    ("bot-standard", BOT, "Standard", ["Até 10 grupos e canais", "60 ofertas por dia em cada grupo",
                                        "Seu link de afiliado em todas"]),
    ("bot-premium", BOT, "Premium", ["Até 50 grupos e canais", "300 ofertas por dia em cada grupo",
                                      "Copia ofertas de outros grupos e revisa o texto com IA"]),
    ("site-standard", SITE, "Standard", ["Até 3 botões", "Conversor de links da Shopee",
                                          "Vitrine com as ofertas do bot ou da busca"]),
    ("site-premium", SITE, "Premium", ["Até 10 botões", "Vitrine com os produtos que você escolher",
                                        "Sem a marca Appfiliado"]),
    ("carrosseis-standard", CARR, "Standard", ["3 carrosséis por dia", "Roteiro escrito por IA",
                                                "Seu link de afiliado na legenda"]),
    ("carrosseis-premium", CARR, "Premium", ["10 carrosséis por dia", "Mais modelos, cores livres e foto própria",
                                              "IA reescrevendo os slides"]),
]
FAIXAS = [("100", "100"), ("500", "500"), ("2000", "2.000"), ("5000", "5.000"), ("10000", "10.000"), ("ilimitado", None)]
BENEFICIOS_NOTAS = ["Uma nota por loja, sem digitar nada", "E-mail com a nota para cada vendedor",
                    "Emitidas no Emissor Nacional do governo"]

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700;9..40,800&display=swap');
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 1000px; height: 1000px; font-family: 'DM Sans', Arial, sans-serif; color: {CREME};
  background: radial-gradient(circle at 85% 12%, {VERDE_2} 0, {VERDE} 46%, #17301F 100%); overflow: hidden; position: relative; }}
.anel {{ position: absolute; right: -170px; bottom: -170px; width: 560px; height: 560px; border-radius: 50%;
  border: 70px solid rgba(242,194,48,.08); }}
.conteudo {{ position: absolute; inset: 0; padding: 78px 84px; display: flex; flex-direction: column; }}
.marca {{ display: flex; align-items: center; gap: 16px; font-size: 32px; font-weight: 800; letter-spacing: -.01em; }}
.marca .logo {{ width: 74px; height: 74px; border-radius: 18px; background: {AMARELO}; color: {TINTA}; display: grid; place-items: center; }}
.icones {{ display: flex; gap: 18px; margin-top: 92px; }}
.icone {{ width: 128px; height: 128px; border-radius: 30px; background: rgba(246,243,234,.1); display: grid; place-items: center;
  border: 2px solid rgba(246,243,234,.16); }}
.icone svg {{ width: 66px; height: 66px; fill: none; stroke: {AMARELO}; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }}
.icones.varios .icone {{ width: 104px; height: 104px; border-radius: 26px; }}
.icones.varios .icone svg {{ width: 54px; height: 54px; }}
h1 {{ font-size: 76px; font-weight: 800; letter-spacing: -.025em; line-height: 1.02; margin-top: 40px; }}
.selo {{ display: inline-flex; align-self: flex-start; align-items: center; gap: 10px; margin-top: 22px; padding: 10px 24px;
  border-radius: 999px; font-size: 28px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }}
.selo.standard {{ border: 3px solid rgba(246,243,234,.75); color: {CREME}; }}
.selo.premium {{ background: {AMARELO}; color: {TINTA}; }}
.frase {{ font-size: 30px; line-height: 1.35; color: #CFDBD2; margin-top: 26px; max-width: 760px; }}
.numero {{ font-size: 64px; font-weight: 800; color: {AMARELO}; margin-top: 22px; letter-spacing: -.02em; line-height: 1.05; }}
.numero small {{ font-size: 34px; color: {CREME}; font-weight: 700; letter-spacing: 0; }}
ul {{ list-style: none; padding: 0; margin-top: auto; display: flex; flex-direction: column; gap: 18px; }}
li {{ display: flex; align-items: center; gap: 18px; font-size: 31px; font-weight: 500; line-height: 1.25; }}
li::before {{ content: ''; flex: none; width: 40px; height: 40px; border-radius: 50%; background: {AMARELO}
  url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 12.5l4 4 8-9' fill='none' stroke='%231D2A23' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/26px no-repeat; }}
"""


def _icone(chave: str) -> str:
    return f'<div class="icone"><svg viewBox="0 0 24 24"><path d="{ICONES[chave]}"/></svg></div>'


def _pagina(icones: list[str], titulo: str, selo: str = "", frase: str = "", numero: str = "",
            beneficios: list[str] = ()) -> str:
    e = html.escape
    classe_icones = "icones varios" if len(icones) > 1 else "icones"
    selo_html = f'<span class="selo {e(selo.lower())}">{"★ " if selo == "Premium" else ""}{e(selo)}</span>' if selo else ""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="anel"></div><div class="conteudo">
  <div class="marca"><span class="logo">{LOGO}</span>Appfiliado</div>
  <div class="{classe_icones}">{''.join(_icone(i) for i in icones)}</div>
  <h1>{e(titulo)}</h1>{selo_html}
  {f'<div class="numero">{numero}</div>' if numero else ''}
  {f'<p class="frase">{e(frase)}</p>' if frase else ''}
  <ul>{''.join(f'<li>{e(b)}</li>' for b in beneficios)}</ul>
</div></body></html>"""


def artes() -> dict[str, str]:
    saida = {}
    for nome, (icone, titulo, frase), nivel, beneficios in AVULSOS:
        saida[nome] = _pagina([icone], titulo, nivel, frase, beneficios=beneficios)
    for nome, numero in FAIXAS:
        destaque = "Notas ilimitadas<br><small>por mês</small>" if numero is None else f"Até {numero} notas<br><small>por mês</small>"
        saida[f"nfse-{nome}"] = _pagina(["notas"], NOTAS[1], numero=destaque, beneficios=BENEFICIOS_NOTAS)
    tres = ["whatsapp", "site", "carrosseis"]
    saida["combo-standard"] = _pagina(tres, "Combo Standard", "Standard", "Bot de WhatsApp + Meu site + Gerador de carrosséis.",
                                      beneficios=["Os 3 módulos no plano Standard", "20% mais barato que separado",
                                                  "Uma assinatura só"])
    saida["combo-premium"] = _pagina(tres, "Combo Premium", "Premium", "Bot de WhatsApp + Meu site + Gerador de carrosséis.",
                                     beneficios=["Os 3 módulos no plano Premium", "20% mais barato que separado",
                                                 "Tudo liberado nos 3 módulos"])
    saida["combo-personalizado"] = _pagina(tres, "Combo personalizado", "", "Escolha os módulos e o plano de cada um.",
                                           beneficios=["10% off com 2 módulos", "20% off com 3 módulos",
                                                       "Standard ou Premium em cada módulo"])
    return saida


def main():
    from playwright.sync_api import sync_playwright

    PASTA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pagina = navegador.new_page(viewport={"width": 1000, "height": 1000})
        for nome, conteudo in artes().items():
            pagina.set_content(conteudo, wait_until="networkidle")
            pagina.screenshot(path=str(PASTA / f"{nome}.png"))
            print(nome)
        navegador.close()


if __name__ == "__main__":
    main()
