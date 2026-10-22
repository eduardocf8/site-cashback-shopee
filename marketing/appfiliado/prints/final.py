import io, os
from playwright.sync_api import sync_playwright
from PIL import Image
AQUI = os.path.dirname(os.path.abspath(__file__))
B = "http://localhost:8765"
OUT = os.path.abspath(os.path.join(AQUI, "..", "..", "..", "landing", "static", "landing", "prints")) + "/" if "marketing" in AQUI else "/home/user/site-cashback-shopee/landing/static/landing/prints/"
TEXTO = """🔥 OFERTAS 11.11 NA SHOPEE 🔥

Fone Bluetooth com cancelamento de ruído
👉 https://shopee.com.br/Fone-Bluetooth-TWS-i.123.456789

Air Fryer Digital 4L
👉 https://shopee.com.br/Air-Fryer-4L-i.321.987654

Garrafa Térmica 1L Inox
👉 https://shopee.com.br/Garrafa-Termica-i.555.112233

Entre no nosso grupo: https://chat.whatsapp.com/AbCdEf123"""
CSS = ".menu{display:none!important}.app{display:block!important}.conteudo{max-width:none!important}"
OCULTAR = """(()=>{document.querySelectorAll('*').forEach(e=>{const s=getComputedStyle(e); if((s.position==='fixed'||s.position==='sticky') && /salvar/i.test(e.textContent||'') && e.offsetHeight<80) e.style.display='none';});})()"""
LIMPA = "(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){n.nodeValue=n.nodeValue.replace('http://localhost:8765/s/achadinhosdabia/','https://achadinhosdabia.appfiliado.com.br').replace('localhost:8765/s/','https://');}})()"
RADAR_TXT = """(()=>{const p=[...document.querySelectorAll('p')].find(e=>/produtos da Shopee com comiss/.test(e.textContent)); if(p) p.innerHTML=p.innerHTML.replace(/^\\s*\\d+ produtos/,'30.412 produtos');})()"""

def converter(pg):
    pg.fill("textarea", TEXTO); pg.fill("input[name=sub_id]", "grupovip"); pg.click("button:has-text('Converter')")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(600)
    pg.evaluate("document.querySelectorAll('textarea').forEach(t=>{t.style.height=(t.scrollHeight+4)+'px'})")

def topo(sel):
    return lambda pg: pg.evaluate(f"document.querySelector({sel!r}).closest('section,.card,article').getBoundingClientRect().top+scrollY-16")
def cartao_do_titulo(rx):
    return f"""(()=>{{const h=[...document.querySelectorAll('h2,h3')].find(e=>/{rx}/.test(e.textContent.trim())); return h.closest('section,.card,article');}})()"""
def botoes(pg):
    return pg.evaluate("(()=>{const h=[...document.querySelectorAll('h2,h3')].find(e=>/^Botões/.test(e.textContent.trim())); return h.closest('section,.card').getBoundingClientRect().top+scrollY-16;})()")
def cartoes(pg):
    return pg.evaluate("(()=>{const i=[...document.querySelectorAll('main img')].find(e=>/8766/.test(e.src)); return i.closest('article,li,.card').getBoundingClientRect().top+scrollY-16;})()")
def fim_titulos(*rxs):
    """Termina o recorte no fim do cartão mais baixo entre os títulos dados (nunca no meio de uma seção)."""
    def f(pg, tag):
        return max(pg.evaluate(f"(()=>{{const h=[...document.querySelectorAll('h2,h3')].find(e=>/{rx}/.test(e.textContent.trim())); const c=h.closest('section,.card,article'); return c.getBoundingClientRect().bottom+scrollY+16;}})()") for rx in rxs)
    return f
def antes_do_titulo(rx):
    def f(pg, tag):
        return pg.evaluate(f"(()=>{{const h=[...document.querySelectorAll('h2,h3')].find(e=>/{rx}/.test(e.textContent.trim())); return h.closest('section,.card,article').getBoundingClientRect().top+scrollY-12;}})()")
    return f
def fim_cartoes(desktop, celular):
    def f(pg, tag):
        n = celular if tag else desktop
        return pg.evaluate(f"(()=>{{const c=[...document.querySelectorAll('main img')].filter(e=>/8766/.test(e.src)).map(e=>e.closest('article,li,.card'))[{n}-1]; return c.getBoundingClientRect().bottom+scrollY+16;}})()")
    return f
def antes_dos_cartoes(pg, tag):
    return cartoes(pg) - 8

# nome, url, ação antes, onde começa, onde termina (função) ou altura fixa
SHOTS = [
 ("inicio", "/", None, None, None),
 ("resultados", "/resultados/?periodo=mes", None, None, antes_do_titulo("^Detalhe por dia")),
 ("resultados-produtos", "/resultados/?periodo=mes", None, topo("#produtos"), fim_titulos("^Vendas do período")),
 ("metas", "/metas/", None, None, None),
 ("radar", "/radar/", RADAR_TXT, None, antes_dos_cartoes),
 ("radar-produtos", "/radar/", None, cartoes, fim_cartoes(8, 3)),
 ("conversor", "/conversor/", converter, None, None),
 ("bot-conexao", "/whatsapp/", None, None, None),
 ("bot-ofertas", "/whatsapp/ofertas/", None, None, fim_titulos("^Onde e quando")),
 ("bot-campanhas", "/whatsapp/campanhas/", None, None, fim_titulos("^Ritmo nesses dias", "^Como funciona", "^Prévia de uma oferta")),
 ("bot-alerta", "/whatsapp/alertas/", None, None, fim_titulos("^Quando avisar", "^Prévia da mensagem")),
 ("site-editor", "/meu-site/", None, None, fim_titulos("^Perfil", "^Prévia")),
 ("site-botoes", "/meu-site/", None, botoes, fim_titulos("^Conversor de links")),
 ("carrossel-editor", "/carrosseis/2/", "espera", None, None),
 ("notas-lote", "/notas/lote/2/", None, None, lambda pg, tag: 1250 if not tag else 1700),
 ("notas", "/notas/", None, None, fim_titulos("^Notas dos vendedores", "^Nota da Shopee")),
]

def tirar(browser, vp, dsf, tag, indice):
    ctx = browser.new_context(viewport=vp, device_scale_factor=dsf); pg = ctx.new_page()
    pg.goto(B + "/entrar/"); pg.fill("input[name=email]", "bia@exemplo.com"); pg.fill("input[type=password]", "uma-senha-boa-123"); pg.click("button[type=submit]"); pg.wait_for_load_state()
    for nome, url, acao, onde, fim in SHOTS:
        pg.goto(B + url); pg.wait_for_load_state("networkidle"); pg.add_style_tag(content=CSS); pg.wait_for_timeout(1200 if acao != "espera" else 3000)
        if callable(acao): acao(pg); pg.add_style_tag(content=CSS)
        elif isinstance(acao, str) and acao != "espera": pg.evaluate(acao)
        pg.wait_for_timeout(300)
        pg.evaluate(OCULTAR); pg.evaluate(LIMPA); pg.wait_for_timeout(250)
        y0 = max(0, int(onde(pg))) if onde else 0
        png = pg.screenshot(full_page=True)
        im = Image.open(io.BytesIO(png)).convert("RGB")
        y1 = int(fim(pg, tag)) if fim else im.height // int(dsf)
        y1 = min(y1, y0 + (2400 if not tag else 2300))
        crop = im.crop((0, int(y0 * dsf), im.width, min(im.height, int(y1 * dsf))))
        crop.save(f"{OUT}{nome}{tag}.webp", "WEBP", quality=82 if tag == "" else 80, method=6)
        indice[nome + tag] = (crop.width // int(dsf), crop.height // int(dsf)); print(nome + tag, crop.size)
    ctx.close()

if __name__ == "__main__":
    indice = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        tirar(b, {"width": 1100, "height": 900}, 1, "", indice)
        tirar(b, {"width": 420, "height": 900}, 2, "-m", indice)
        b.close()
    import json; json.dump(indice, open(AQUI + "/tamanhos.json", "w"))
