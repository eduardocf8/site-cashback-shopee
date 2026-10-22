import os
AQUI = os.path.dirname(os.path.abspath(__file__))
from playwright.sync_api import sync_playwright
from PIL import Image
import io
B="http://localhost:8765"; OUT = os.path.abspath(os.path.join(AQUI, "..", "..", "..", "landing", "static", "landing", "prints")) + "/"
TEXTO = """🔥 OFERTAS 11.11 NA SHOPEE 🔥

Fone Bluetooth com cancelamento de ruído
👉 https://shopee.com.br/Fone-Bluetooth-TWS-i.123.456789

Air Fryer Digital 4L
👉 https://shopee.com.br/Air-Fryer-4L-i.321.987654

Garrafa Térmica 1L Inox
👉 https://shopee.com.br/Garrafa-Termica-i.555.112233

Entre no nosso grupo: https://chat.whatsapp.com/AbCdEf123"""
OCULTAR="""(()=>{document.querySelectorAll('*').forEach(e=>{const s=getComputedStyle(e); if((s.position==='fixed'||s.position==='sticky') && /salvar/i.test(e.textContent||'') && e.offsetHeight<80) e.style.display='none';});})()"""
def salvar(nome, png):
    im=Image.open(io.BytesIO(png)).convert("RGB"); im.save(OUT+nome+".webp","WEBP",quality=84,method=6); print(nome, im.size)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx=b.new_context(viewport={"width":1280,"height":860}); pg=ctx.new_page()
    pg.goto(B+"/entrar/"); pg.fill("input[name=email]","bia@exemplo.com"); pg.fill("input[type=password]","uma-senha-boa-123"); pg.click("button[type=submit]"); pg.wait_for_load_state()
    LIMPA = "(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){n.nodeValue=n.nodeValue.replace('http://localhost:8765/s/achadinhosdabia/','https://achadinhosdabia.appfiliado.com.br').replace('localhost:8765/s/','https://');}document.querySelectorAll('a[href*=localhost]').forEach(a=>{});})()"
    def ir(url, h=860, y=0, depois=None):
        pg.set_viewport_size({"width":1280,"height":h}); pg.goto(B+url); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(700)
        if depois: depois()
        if y: pg.evaluate(f"window.scrollTo(0,{y})")
        pg.evaluate(OCULTAR); pg.evaluate(LIMPA); pg.wait_for_timeout(250)
    def rolar_ate(sel, folga=24):
        return lambda: pg.evaluate(f"(()=>{{const e=document.querySelector('{sel}'); window.scrollTo(0, e.getBoundingClientRect().top+scrollY-{folga});}})()")
    # início, resultados, metas
    ir("/", 780); salvar("inicio", pg.screenshot())
    ir("/resultados/?periodo=mes", 900); salvar("resultados", pg.screenshot())
    ir("/resultados/?periodo=mes", 900, depois=rolar_ate("#produtos")); salvar("resultados-produtos", pg.screenshot())
    ir("/resultados/?periodo=mes", 900, depois=rolar_ate("#vendas")); salvar("resultados-vendas", pg.screenshot())
    ir("/metas/", 700); salvar("metas", pg.screenshot())
    # radar
    def texto_radar():
        pg.evaluate("""(()=>{const p=[...document.querySelectorAll('p')].find(e=>/produtos da Shopee com comiss/.test(e.textContent)); if(p) p.innerHTML=p.innerHTML.replace(/^\\s*\\d+ produtos/,'30.412 produtos');})()""")
    ir("/radar/", 700, depois=texto_radar); salvar("radar", pg.screenshot())
    ir("/radar/", 900, y=610); salvar("radar-produtos", pg.screenshot())
    # conversor
    def converter():
        pg.fill("textarea",TEXTO); pg.fill("input[name=sub_id]","grupovip"); pg.click("button:has-text('Converter')"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(600)
        pg.evaluate("document.querySelectorAll('textarea').forEach(t=>{t.style.height=(t.scrollHeight+4)+'px'})")
    ir("/conversor/", 1010, depois=converter); salvar("conversor", pg.screenshot())
    # bot
    ir("/whatsapp/", 700); salvar("bot-conexao", pg.screenshot())
    ir("/whatsapp/ofertas/", 900); salvar("bot-ofertas", pg.screenshot())
    ir("/whatsapp/alertas/", 900); salvar("bot-alerta", pg.screenshot())
    ir("/whatsapp/campanhas/", 900); salvar("bot-campanhas", pg.screenshot())
    # meu site
    ir("/meu-site/", 900); salvar("site-editor", pg.screenshot())
    def ate_botoes():
        pg.evaluate("""(()=>{const h=[...document.querySelectorAll('h2,h3')].find(e=>/^Botões/.test(e.textContent.trim())); const c=h.closest('section,.card')||h; window.scrollTo(0,c.getBoundingClientRect().top+scrollY-24);})()""")
    ir("/meu-site/", 900, depois=ate_botoes); salvar("site-botoes", pg.screenshot())
    # carrosséis
    ir("/carrosseis/2/", 960, depois=lambda: pg.wait_for_timeout(2500)); salvar("carrossel-editor", pg.screenshot())
    # notas
    ir("/notas/lote/2/", 860); salvar("notas-lote", pg.screenshot())
    ir("/notas/", 860, y=190); salvar("notas", pg.screenshot())
    b.close()
