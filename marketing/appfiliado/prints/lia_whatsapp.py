"""Print da Lia (a assistente do Appfiliado no WhatsApp) pra página de Resultados e metas na landing: uma
conversa de exemplo, com números fictícios, montada em HTML no visual do WhatsApp e colocada na mesma
moldura de celular do site_pronto.py. Os textos seguem o formato das respostas de atendimento/comandos.py.

Não precisa de servidor. Rode: python lia_whatsapp.py (depois atualize TAMANHOS em landing/recursos.py com o
tamanho que ele imprimir, dividido por 2 pro tamanho na tela)."""

import base64
import html
import io
import os
import re

from PIL import Image
from playwright.sync_api import sync_playwright

from site_pronto import SAIDA, celular

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "..", "..", "..", "painel", "static", "painel", "email-logo.png")
LARGURA_NA_TELA = 340  # px de tela na página (a imagem sai com o dobro, pra ficar nítida)

# (quem, texto, hora). "eu" = o afiliado; "lia" = a resposta. *negrito* como no WhatsApp.
CONVERSA = [
    ("eu", "resultados", "08:12"),
    ("lia", """📊 *Seus resultados na Shopee*

*Ontem (27/10)*
Pedidos: 48
Faturamento: R$ 3.912,40
Comissão estimada: R$ 287,15
Comissão validada: R$ 214,60

*Últimos 7 dias (21/10 a 27/10)*
Pedidos: 301
Faturamento: R$ 24.180,90
Comissão estimada: R$ 1.796,33
Comissão validada: R$ 1.402,18

*Outubro/2026 até ontem*
Pedidos: 1.198
Faturamento: R$ 96.540,20
Comissão estimada: R$ 7.120,85
Comissão validada: R$ 6.880,40

Atualizado às 08:00.""", "08:12"),
    ("eu", "validada", "08:13"),
    ("lia", "Buscando a comissão validada de hoje na Shopee ⏳ Em até 1 minuto te mando aqui.", "08:13"),
    ("lia", """✅ *Comissão validada hoje (28/10)*
R$ 96,30

Ontem (27/10): R$ 214,60
Outubro/2026 até agora: R$ 6.976,70""", "08:14"),
]


def _texto(t: str) -> str:
    t = html.escape(t)
    return re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", t).replace("\n", "<br>")


def pagina() -> str:
    logo = base64.b64encode(open(LOGO, "rb").read()).decode()
    baloes = []
    for quem, texto, hora in CONVERSA:
        visto = '<span class="visto">✓✓</span>' if quem == "eu" else ""
        baloes.append(f'<div class="balao {quem}"><div class="txt">{_texto(texto)}</div>'
                      f'<span class="hora">{hora}{visto}</span></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; }}
body {{ width: 390px; font-family: Inter, "Noto Color Emoji", sans-serif; background: #EFEAE2; color: #111B21; }}
.status {{ height: 54px; background: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 30px;
          font-size: 15px; font-weight: 600; }}
.topo {{ display: flex; align-items: center; gap: 10px; padding: 6px 14px 10px; background: #fff; border-bottom: 1px solid #E9EDEF; }}
.voltar {{ font-size: 26px; color: #111B21; line-height: 1; }}
.avatar {{ width: 38px; height: 38px; border-radius: 50%; background: #F2B705 url(data:image/png;base64,{logo}) center/72% no-repeat; }}
.nome {{ font-weight: 600; font-size: 16px; }}
.sub {{ font-size: 12.5px; color: #667781; }}
.conversa {{ padding: 12px 12px 18px; display: flex; flex-direction: column; gap: 6px; }}
.dia {{ align-self: center; background: #fff; color: #54656F; font-size: 12px; padding: 5px 10px; border-radius: 8px; margin-bottom: 4px;
        box-shadow: 0 1px .5px rgba(11,20,26,.13); }}
.balao {{ max-width: 84%; padding: 7px 9px 6px; border-radius: 8px; font-size: 14.2px; line-height: 1.38; position: relative;
          box-shadow: 0 1px .5px rgba(11,20,26,.13); }}
.balao.eu {{ align-self: flex-end; background: #D9FDD3; border-top-right-radius: 0; }}
.balao.lia {{ align-self: flex-start; background: #fff; border-top-left-radius: 0; }}
.balao.lia + .balao.lia {{ border-top-left-radius: 8px; }}
.hora {{ display: block; text-align: right; font-size: 11px; color: #667781; margin-top: 2px; }}
.visto {{ color: #53BDEB; margin-left: 3px; letter-spacing: -3px; }}
.escrever {{ display: flex; gap: 8px; align-items: center; padding: 8px 10px 26px; background: #EFEAE2; }}
.campo {{ flex: 1; background: #fff; border-radius: 22px; padding: 11px 16px; color: #8696A0; font-size: 15px; }}
.mic {{ width: 44px; height: 44px; border-radius: 50%; background: #25D366; display: flex; align-items: center; justify-content: center; }}
.icones {{ display: flex; align-items: center; gap: 7px; }}
.sinal {{ display: flex; align-items: flex-end; gap: 2px; height: 12px; }}
.sinal i {{ width: 3px; background: #111B21; border-radius: 1px; }}
.sinal i:nth-child(1) {{ height: 4px; }} .sinal i:nth-child(2) {{ height: 6px; }} .sinal i:nth-child(3) {{ height: 9px; }} .sinal i:nth-child(4) {{ height: 12px; }}
.bateria {{ width: 25px; height: 12px; border: 1.5px solid #111B21; border-radius: 4px; padding: 1.5px; }}
.bateria i {{ display: block; width: 80%; height: 100%; background: #111B21; border-radius: 1.5px; }}
</style></head><body>
<div class="status"><span>08:14</span><span class="icones"><span class="sinal"><i></i><i></i><i></i><i></i></span><span class="bateria"><i></i></span></span></div>
<div class="topo"><span class="voltar">‹</span><span class="avatar"></span>
  <div><div class="nome">Appfiliado</div><div class="sub">Lia · assistente do Appfiliado</div></div></div>
<div class="conversa"><span class="dia">Hoje</span>{''.join(baloes)}</div>
<div class="escrever"><span class="campo">Mensagem</span><span class="mic"><svg viewBox="0 0 24 24" width="22" height="22" fill="#fff"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg></span></div>
</body></html>"""


def main():
    with sync_playwright() as p:
        try:
            navegador = p.chromium.launch()
        except Exception:  # noqa: BLE001 - versão do Playwright diferente do navegador instalado
            navegador = p.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
        aba = navegador.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        aba.set_content(pagina(), wait_until="load")
        aba.wait_for_timeout(300)
        tela = Image.open(io.BytesIO(aba.screenshot(full_page=True))).convert("RGB")
        navegador.close()
    imagem = celular(tela)
    # A página mostra com LARGURA_NA_TELA px; a imagem fica com o dobro pra telas de alta densidade.
    largura = LARGURA_NA_TELA * 2
    imagem = imagem.resize((largura, round(imagem.height * largura / imagem.width)), Image.LANCZOS)
    imagem.save(os.path.join(SAIDA, "lia-whatsapp.webp"), quality=86, method=6)
    print("lia-whatsapp:", imagem.size, "-> na tela:", (LARGURA_NA_TELA, round(imagem.height / 2)))


if __name__ == "__main__":
    main()
