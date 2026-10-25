"""Print do Meu site pronto (o que o visitante vê), em moldura de celular, pra página do Meu site na
landing. Usa o mesmo banco de exemplo e o mesmo servidor do README (servidor_demo.py na 8765 e as
fotos na 8766): tira o print do site público inteiro e monta duas imagens:

site-pronto.webp: o site inteiro, de cima a baixo, dentro de um celular (vale pro computador e pro celular).

Rode: python site_pronto.py (depois atualize TAMANHOS em landing/recursos.py com o que ele imprimir)."""

import io
import os

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.abspath(os.path.join(AQUI, "..", "..", "..", "landing", "static", "landing", "prints"))
URL = "http://localhost:8765/s/achadinhosdabia/"
MOLDURA, BORDA, RAIO = "#1D2A23", 22, 78


def print_do_site() -> Image.Image:
    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch()
        except Exception:  # noqa: BLE001 - versão do Playwright diferente do navegador instalado
            navegador = p.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
        pagina = navegador.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pagina.goto(URL, wait_until="networkidle")
        pagina.wait_for_timeout(800)
        imagem = Image.open(io.BytesIO(pagina.screenshot(full_page=True))).convert("RGB")
        navegador.close()
    return imagem


def celular(tela: Image.Image) -> Image.Image:
    w, h = tela.size
    fora = Image.new("RGBA", (w + 2 * BORDA, h + 2 * BORDA), (0, 0, 0, 0))
    ImageDraw.Draw(fora).rounded_rectangle((0, 0, fora.width - 1, fora.height - 1), RAIO, fill=MOLDURA)
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), RAIO - BORDA, fill=255)
    fora.paste(tela, (BORDA, BORDA), mascara)
    ImageDraw.Draw(fora).rounded_rectangle((fora.width / 2 - 60, BORDA + 18, fora.width / 2 + 60, BORDA + 50), 16, fill=MOLDURA)
    return fora


def main():
    sozinho = celular(print_do_site())
    sozinho.save(os.path.join(SAIDA, "site-pronto.webp"), quality=86, method=6)
    print("site-pronto:", sozinho.size)


if __name__ == "__main__":
    main()
