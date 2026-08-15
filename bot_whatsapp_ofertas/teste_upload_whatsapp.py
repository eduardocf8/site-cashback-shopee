import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Ajuste se precisar
GRUPO_DESTINO = "Ofertas @vegrassi"
IMAGEM_TESTE = r"midias\WhatsApp Image 2026-07-03 at 20.42.10.jpeg"
LEGENDA_TESTE = "TESTE FOTO COM LEGENDA - pode apagar depois"


def esperar_whatsapp(page):
    print("Aguardando WhatsApp carregar...")
    page.goto("https://web.whatsapp.com/")
    page.wait_for_selector("#pane-side, div[data-testid='chat-list']", timeout=0)
    print("WhatsApp carregado.")


def abrir_conversa(page, nome):
    print(f"Abrindo conversa: {nome}")
    termo = nome.lower().strip()
    page.wait_for_selector("#pane-side", timeout=20000)

    resultado = page.evaluate("""
    (termo) => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return {ok:false, motivo:'sem pane-side'};

        const spans = [...pane.querySelectorAll('span[title]')];
        const alvo = spans.find(s => (s.getAttribute('title') || '').toLowerCase().includes(termo));
        if (!alvo) return {ok:false, motivo:'nao achou titulo', titulos: spans.map(s => s.getAttribute('title')).filter(Boolean).slice(0,20)};

        const cell = alvo.closest('[data-testid="cell-frame-container"]') ||
                     alvo.closest('[role="listitem"]') ||
                     alvo.closest('[role="row"]') ||
                     alvo.closest('[tabindex]') ||
                     alvo;
        const r = cell.getBoundingClientRect();
        return {
            ok:true,
            titulo: alvo.getAttribute('title'),
            x: r.left + Math.min(190, Math.max(60, r.width / 2)),
            y: r.top + r.height / 2,
            w: r.width,
            h: r.height
        };
    }
    """, termo)

    print("Resultado conversa:", resultado)
    if not resultado.get("ok"):
        raise RuntimeError(f"Não achei conversa: {resultado}")

    page.mouse.click(resultado["x"], resultado["y"])
    page.wait_for_timeout(1800)

    # Confirma pelo header e pela caixa de mensagem do grupo
    ok = page.evaluate("""
    (nome) => {
        const h = [...document.querySelectorAll('header')].map(x => x.innerText || '').join('\\n').toLowerCase();
        const temHeader = h.includes(nome.toLowerCase());
        const temCaixa = [...document.querySelectorAll('div[contenteditable="true"][role="textbox"], div[contenteditable="true"]')]
            .some(el => {
                const r = el.getBoundingClientRect();
                const aria = (el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || '').toLowerCase();
                return r.width > 100 && r.height > 5 && r.left > window.innerWidth * 0.25 && r.bottom > window.innerHeight * 0.60 &&
                       (aria.includes('mensagem') || aria.includes('message'));
            });
        return {temHeader, temCaixa, headers:[...document.querySelectorAll('header')].map(x => x.innerText || '')};
    }
    """, nome)

    print("Confirmação chat:", ok)
    if not ok["temHeader"]:
        raise RuntimeError("Cliquei na conversa, mas o header não confirma o grupo.")
    if not ok["temCaixa"]:
        raise RuntimeError("Grupo abriu, mas não achei caixa de mensagem.")


def diagnostico(page, titulo="DIAGNOSTICO"):
    dados = page.evaluate("""
    () => {
      const rect = el => {
        const r = el.getBoundingClientRect();
        return {x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height), visible:r.width>0&&r.height>0};
      };
      return {
        url: location.href,
        headers: [...document.querySelectorAll('header')].map(x => (x.innerText || '').trim()).filter(Boolean),
        attachButtons: [...document.querySelectorAll('button, div[role="button"], span[data-testid], span[data-icon]')]
          .map((el,i)=>({i, tag:el.tagName, text:(el.innerText||el.textContent||'').trim().slice(0,80), aria:el.getAttribute('aria-label'), testid:el.getAttribute('data-testid'), icon:el.getAttribute('data-icon'), ...rect(el)}))
          .filter(x => x.visible && (String(x.aria||'').toLowerCase().includes('anex') || String(x.text||'').includes('plus') || String(x.testid||'').includes('plus') || String(x.icon||'').includes('send') || String(x.aria||'').toLowerCase().includes('enviar')))
          .slice(-80),
        textboxes: [...document.querySelectorAll('input, div[contenteditable="true"], p.selectable-text.copyable-text')]
          .map((el,i)=>({i, tag:el.tagName, text:(el.innerText||el.textContent||'').trim().slice(0,80), aria:el.getAttribute('aria-label'), placeholder:el.getAttribute('aria-placeholder')||el.getAttribute('placeholder'), contenteditable:el.getAttribute('contenteditable'), ...rect(el)}))
          .filter(x => x.visible)
          .slice(-20),
        inputs: [...document.querySelectorAll('input[type=file]')].map((el,i)=>({i, accept:el.getAttribute('accept'), visible:rect(el).visible}))
      };
    }
    """)
    print(f"\n===== {titulo} =====")
    for k, v in dados.items():
        print(f"{k}: {v}")
    print(f"===== FIM {titulo} =====\n")


def clicar_botao_anexar(page):
    # Clica no BUTTON com aria-label Anexar, não no emoji/figurinha.
    info = page.evaluate("""
    () => {
        const botoes = [...document.querySelectorAll('button[aria-label="Anexar"], button[aria-label*="Anexar"], button[aria-label*="Attach"]')];
        const itens = botoes.map(b => {
            const r = b.getBoundingClientRect();
            return {x:r.left+r.width/2, y:r.top+r.height/2, left:r.left, top:r.top, w:r.width, h:r.height, aria:b.getAttribute('aria-label'), visible:r.width>0&&r.height>0};
        }).filter(x => x.visible && x.left > window.innerWidth * 0.25 && x.top > window.innerHeight * 0.55);
        itens.sort((a,b) => b.top - a.top);
        return itens[0] || null;
    }
    """)
    print("Botão Anexar escolhido:", info)
    if not info:
        diagnostico(page, "SEM BOTAO ANEXAR")
        raise RuntimeError("Não achei button[aria-label='Anexar'] na conversa.")

    page.mouse.click(info["x"], info["y"])
    page.wait_for_timeout(700)


def anexar_foto(page, caminho):
    caminho = os.path.abspath(caminho)
    if not os.path.exists(caminho):
        raise RuntimeError(f"Imagem não existe: {caminho}")

    clicar_botao_anexar(page)
    diagnostico(page, "APOS CLICAR ANEXAR")

    seletores_fotos = [
        "li[data-testid='attach-photo']",
        "[data-testid='attach-photo']",
        "span:has-text('Fotos e vídeos')",
        "div:has-text('Fotos e vídeos')",
        "text=Fotos e vídeos",
        "span:has-text('Fotos e videos')",
        "text=Fotos e videos",
        "span:has-text('Photos & videos')",
        "text=Photos & videos",
    ]

    # Primeiro tenta o fluxo real com file chooser.
    for sel in seletores_fotos:
        try:
            loc = page.locator(sel).last
            if loc.count() and loc.is_visible():
                print(f"Clicando em Fotos e vídeos por: {sel}")
                with page.expect_file_chooser(timeout=7000) as fc:
                    loc.click(force=True)
                chooser = fc.value
                chooser.set_files(caminho)
                page.wait_for_timeout(2500)
                return
        except Exception as e:
            print(f"Falhou file chooser em {sel}: {e}")

    # Fallback seguro: só input image/*, nunca accept=*.
    print("Tentando fallback input image/*...")
    inputs = page.locator("input[type='file'][accept='image/*']")
    if inputs.count() == 0:
        diagnostico(page, "SEM INPUT IMAGE")
        raise RuntimeError("Não achei input accept=image/*.")

    inputs.last.set_input_files(caminho)
    page.wait_for_timeout(2500)


def aguardar_tela_preview(page):
    # Não depende de dialog: no seu WhatsApp o preview aparece no painel principal.
    for _ in range(30):
        ok = page.evaluate("""
        () => {
            const send = [...document.querySelectorAll('span[data-icon="send"], span[data-icon="send-filled"], button[aria-label*="Enviar"], button[aria-label*="Send"]')]
              .some(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && r.left > window.innerWidth * 0.25;
              });

            const caption = [...document.querySelectorAll('div[contenteditable="true"][role="textbox"], div[contenteditable="true"]')]
              .some(el => {
                const r = el.getBoundingClientRect();
                const aria = (el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || '').toLowerCase();
                return r.width > 100 && r.height > 8 && r.left > window.innerWidth * 0.25 &&
                       (aria === 'digite uma mensagem' || aria.includes('legenda') || aria.includes('caption'));
              });

            const blobImg = [...document.querySelectorAll('img, video')].some(el => {
                const r = el.getBoundingClientRect();
                return r.width > 80 && r.height > 80 && r.left > window.innerWidth * 0.25;
            });

            return {ok: send || caption || blobImg, send, caption, blobImg};
        }
        """)
        if ok["ok"]:
            print("Preview detectado:", ok)
            return True
        page.wait_for_timeout(500)

    diagnostico(page, "PREVIEW NAO DETECTADO")
    raise RuntimeError("Preview não foi detectado.")


def escrever_legenda(page, legenda):
    # No preview, a legenda aparece como aria "Digite uma mensagem" sem "para o grupo".
    handle = page.evaluate_handle("""
    () => {
        const candidatos = [...document.querySelectorAll('div[contenteditable="true"][role="textbox"], div[contenteditable="true"]')]
          .map(el => {
            const r = el.getBoundingClientRect();
            const aria = (el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || '').toLowerCase();
            return {el, r, aria};
          })
          .filter(x => x.r.width > 100 && x.r.height > 8 && x.r.left > window.innerWidth * 0.25);

        // Prioriza a caixa do preview/caption, que normalmente é "Digite uma mensagem",
        // e evita a caixa normal "Digite uma mensagem para o grupo..."
        const caption = candidatos.find(x =>
            (x.aria === 'digite uma mensagem' || x.aria.includes('legenda') || x.aria.includes('caption')) &&
            !x.aria.includes('para o grupo')
        );
        if (caption) return caption.el;

        // Fallback: pega a caixa visível mais alta no painel direito, pois o preview fica acima do footer.
        candidatos.sort((a,b) => a.r.top - b.r.top);
        return candidatos[0]?.el || null;
    }
    """)
    el = handle.as_element()
    if not el:
        diagnostico(page, "SEM CAIXA LEGENDA")
        raise RuntimeError("Não achei caixa de legenda.")

    print("Escrevendo legenda...")
    el.click(force=True)
    page.keyboard.insert_text(legenda)
    page.wait_for_timeout(700)


def clicar_enviar_preview(page):
    # Busca o botão de enviar no painel direito. Se houver mais de um, escolhe o mais baixo/direito.
    info = page.evaluate("""
    () => {
        const cand = [...document.querySelectorAll('button, div[role="button"], span[data-icon="send"], span[data-icon="send-filled"]')]
          .map(el => {
            const icon = el.getAttribute('data-icon') || '';
            const aria = el.getAttribute('aria-label') || '';
            const text = (el.innerText || el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            const isSend = icon.includes('send') || aria.toLowerCase().includes('enviar') || aria.toLowerCase().includes('send') || text === 'send' || text === 'Enviar';
            let clickEl = el.closest('button') || el.closest('div[role="button"]') || el;
            const cr = clickEl.getBoundingClientRect();
            return {
              isSend,
              x: cr.left + cr.width/2,
              y: cr.top + cr.height/2,
              left: cr.left,
              top: cr.top,
              w: cr.width,
              h: cr.height,
              icon, aria, text,
              visible: cr.width > 0 && cr.height > 0
            };
          })
          .filter(x => x.isSend && x.visible && x.left > window.innerWidth * 0.25);

        cand.sort((a,b) => (b.top - a.top) || (b.left - a.left));
        return cand[0] || null;
    }
    """)
    print("Botão enviar escolhido:", info)

    if info:
        page.mouse.click(info["x"], info["y"])
        page.wait_for_timeout(3000)
        return True

    diagnostico(page, "SEM BOTAO ENVIAR")
    print("Tentando enviar por Enter...")
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir="perfil_whatsapp",
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )
        page = browser.new_page()
        esperar_whatsapp(page)
        abrir_conversa(page, GRUPO_DESTINO)
        diagnostico(page, "INICIAL")

        anexar_foto(page, IMAGEM_TESTE)
        diagnostico(page, "APOS SETAR IMAGEM")

        aguardar_tela_preview(page)
        escrever_legenda(page, LEGENDA_TESTE)
        diagnostico(page, "APOS LEGENDA")

        clicar_enviar_preview(page)

        print("Teste finalizado. Verifique no WhatsApp se foi como FOTO com legenda.")
        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    main()
