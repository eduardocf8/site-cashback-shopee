import os
import re
import time
from datetime import datetime
from pathlib import Path

from config import (
    AGUARDAR_PREVIA_LINK,
    ESPERA_MINIMA_PREVIA_LINK_MS,
    TIMEOUT_IMAGEM_PREVIA_LINK_MS,
    TIMEOUT_PREVIA_LINK_MS,
)


class WhatsApp:
    def __init__(self, play, headless=False, app_config=None):
        self.aguardar_previa_link_config = getattr(
            app_config,
            "aguardar_previa_link",
            AGUARDAR_PREVIA_LINK,
        )
        self.timeout_previa_link_ms = getattr(
            app_config,
            "timeout_previa_link_ms",
            TIMEOUT_PREVIA_LINK_MS,
        )
        self.espera_minima_previa_link_ms = getattr(
            app_config,
            "espera_minima_previa_link_ms",
            ESPERA_MINIMA_PREVIA_LINK_MS,
        )
        self.timeout_imagem_previa_link_ms = getattr(
            app_config,
            "timeout_imagem_previa_link_ms",
            TIMEOUT_IMAGEM_PREVIA_LINK_MS,
        )
        profile_dir = getattr(app_config, "profile_dir", "perfil_whatsapp")
        self.diagnostico_dir = Path(profile_dir).resolve().parent / "diagnosticos_whatsapp"

        self.abrir_minimizado = bool(headless)
        browser_args = ["--window-size=1200,900"] if self.abrir_minimizado else ["--start-maximized"]
        if self.abrir_minimizado:
            # Flags que impedem o Chromium de "acalmar" (throttle) a
            # renderizacao/layout de paginas em janelas minimizadas ou em
            # segundo plano. Sem isso, elementos novos (como o editor de
            # midia que so e montado ao anexar uma foto) podem nao ter seu
            # layout recalculado enquanto a janela esta minimizada -
            # fazendo com que getBoundingClientRect() retorne 0/errado
            # mesmo que a interface esteja funcionando de verdade (a
            # screenshot de diagnostico, que forca uma renderizacao real,
            # mostra o estado correto; a consulta ao DOM via JS, nao).
            browser_args += [
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-background-timer-throttling",
                "--disable-background-media-suspend",
            ]

        # Tenta usar o Chrome de verdade instalado no PC (mesma "impressão
        # digital" usada no login manual - ver abrir_shopee_para_login no
        # app.py). Sites como a Shopee podem detectar e bloquear
        # especificamente o Chromium embutido do Playwright; usar o mesmo
        # navegador do login evita essa inconsistência. Se o Chrome não
        # estiver instalado, cai para o Chromium embutido normalmente.
        try:
            self.browser = play.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=False,
                no_viewport=True,
                args=browser_args,
            )
        except Exception:
            self.browser = play.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                no_viewport=True,
                args=browser_args,
            )

        if self.abrir_minimizado:
            # Reforco em nivel de pagina: engana a Page Visibility API para
            # que o WhatsApp Web (e o proprio motor de renderizacao do
            # Chromium) sempre acredite que a aba esta visivel e em foco,
            # mesmo com a janela minimizada. Isso e aplicado a toda pagina
            # nova (init script), antes de qualquer script da propria
            # pagina rodar.
            self.browser.add_init_script("""
                Object.defineProperty(document, 'hidden', {get: () => false, configurable: true});
                Object.defineProperty(document, 'visibilityState', {get: () => 'visible', configurable: true});
                document.hasFocus = () => true;
                const bloquear = (e) => { e.stopImmediatePropagation(); };
                document.addEventListener('visibilitychange', bloquear, true);
                window.addEventListener('blur', bloquear, true);
            """)

        self.page = self.browser.new_page()
        if self.abrir_minimizado:
            self.minimizar_janela()

        self.page.goto("https://web.whatsapp.com")
        if self.abrir_minimizado:
            self.minimizar_janela()

        print("Aguardando login...")
        try:
            self.page.wait_for_selector("div[data-testid='chat-list']", timeout=120000)
        except Exception as erro:
            raise Exception(
                "WhatsApp Web não carregou em até 2 minutos. "
                "Verifique se o celular está conectado, se o WhatsApp Web está logado "
                "e tente novamente com a janela do navegador visível."
            ) from erro
        if self.abrir_minimizado:
            self.minimizar_janela()
        print("WhatsApp conectado!")

    def minimizar_janela(self):
        try:
            session = self.browser.new_cdp_session(self.page)
            info = session.send("Browser.getWindowForTarget")
            window_id = info.get("windowId")
            if window_id:
                session.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": window_id,
                        "bounds": {"windowState": "minimized"},
                    },
                )
            session.detach()
        except Exception:
            pass

    def fechar_dialogos_sobrepostos(self):
        """Fecha apenas modais sobrepostos conhecidos, sem usar Escape no chat normal.

        Observação importante: no WhatsApp Web, apertar Escape quando não há
        modal/preview real pode fechar a conversa aberta e voltar para a tela
        inicial. Por isso esta função tenta clicar em botões de fechar dentro
        de dialogs e não usa Escape como fallback genérico.
        """
        try:
            for _ in range(4):
                fechado = self.page.evaluate("""
                () => {
                    const visivel = (el) => {
                        if (!el) return false;
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    };

                    const dialogs = [...document.querySelectorAll('div[role="dialog"]')].filter(visivel);
                    if (!dialogs.length) return false;

                    for (const d of dialogs) {
                        const candidatos = [
                            ...d.querySelectorAll('button[aria-label="Fechar"], button[aria-label="Close"], button[aria-label="Cancelar"], button[aria-label="Cancel"]'),
                            ...d.querySelectorAll('div[role="button"][aria-label="Fechar"], div[role="button"][aria-label="Close"], div[role="button"][aria-label="Cancelar"], div[role="button"][aria-label="Cancel"]')
                        ].filter(visivel);

                        if (candidatos.length) {
                            candidatos[0].click();
                            return true;
                        }
                    }

                    return false;
                }
                """)

                if not fechado:
                    break

                self.page.wait_for_timeout(500)

        except Exception:
            pass

    def abrir_grupo(self, nome):
        print(f"Abrindo grupo: {nome}")
        # Se o envio anterior foi para um canal (aba "Canais"), a lateral
        # esquerda está mostrando canais, não conversas. Garante a volta
        # para a aba normal antes de procurar o grupo de origem.
        self.ir_para_aba_conversas()
        self.fechar_dialogos_sobrepostos()
        self.fechar_visualizador_midia()

        # Mantém a ideia do método antigo que funcionava, mas limita a busca à lista lateral.
        # Isso evita clicar no título do chat, no botão de nova conversa ou em itens de modal.
        try:
            self.page.wait_for_selector("#pane-side", timeout=12000)
        except Exception:
            pass

        termo = (nome or "").lower().strip()
        resultado = self.page.evaluate("""
        (termo) => {
            const pane = document.querySelector('#pane-side') || document.querySelector('div[data-testid="chat-list"]');
            if (!pane) return {ok:false, motivo:'sem lista lateral'};

            const spans = [...pane.querySelectorAll('span[title]')];
            const alvo = spans.find(s => (s.getAttribute('title') || '').toLowerCase().includes(termo));
            if (!alvo) {
                return {ok:false, motivo:'titulo nao encontrado', titulos: spans.map(s => s.getAttribute('title')).filter(Boolean).slice(0, 20)};
            }

            const cell = alvo.closest('[data-testid="cell-frame-container"]') ||
                         alvo.closest('[role="listitem"]') ||
                         alvo.closest('[role="row"]') ||
                         alvo.closest('[tabindex]') || alvo;
            const r = cell.getBoundingClientRect();
            return {
                ok:true,
                titulo: alvo.getAttribute('title') || alvo.textContent || '',
                x: Math.round(r.left + Math.min(180, Math.max(50, r.width / 2))),
                y: Math.round(r.top + r.height / 2),
                w: Math.round(r.width),
                h: Math.round(r.height)
            };
        }
        """, termo)

        if not resultado or not resultado.get("ok"):
            print("DEBUG conversa não encontrada:", resultado)
            self.debug_conversas_visiveis()
            raise Exception(f"Não consegui abrir o grupo/conversa: {nome}")

        print(f"Conversa encontrada pelo título: {resultado.get('titulo')}")
        self.page.mouse.click(resultado["x"], resultado["y"])
        self.page.wait_for_timeout(2200)
        self.fechar_dialogos_sobrepostos()
        print("Grupo aberto!")
        return True

    def encontrar_lista_conversas(self):
        seletores = [
            "div[data-testid='chat-list']",
            "div[aria-label='Lista de conversas']",
            "div[aria-label='Chat list']",
            "div[role='grid']",
            "#pane-side",
        ]
        for seletor in seletores:
            try:
                loc = self.page.locator(seletor).first
                if loc.count() and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

    def clicar_conversa_visivel(self, nome):
        """Abre uma conversa lendo o atributo title do nome na lista lateral.
        Não depende da posição do grupo. Procura span[title] dentro de #pane-side,
        compara com o nome parcial e clica na linha clicável correspondente.
        """
        termo = (nome or "").lower().strip()
        if not termo:
            return False

        try:
            self.page.wait_for_selector("#pane-side", timeout=8000)
        except Exception:
            pass

        try:
            resultado = self.page.evaluate("""
            (termo) => {
                const pane = document.querySelector('#pane-side');
                if (!pane) return {ok:false, motivo:'sem #pane-side'};

                const spans = [...pane.querySelectorAll('span[title]')];
                const alvo = spans.find(s => (s.getAttribute('title') || '').toLowerCase().includes(termo));
                if (!alvo) {
                    return {
                        ok:false,
                        motivo:'titulo nao encontrado',
                        titulos: spans.slice(0, 25).map(s => s.getAttribute('title')).filter(Boolean)
                    };
                }

                let el = alvo;
                let melhor = null;

                // Sobe pelos pais até achar uma linha de conversa dentro da lateral.
                // Escolhe um ancestral largo/alto o bastante para representar a conversa inteira.
                while (el && el !== pane) {
                    const r = el.getBoundingClientRect();
                    if (r.width >= 250 && r.height >= 45) {
                        melhor = el;
                    }
                    el = el.parentElement;
                }

                const clicavel = (melhor || alvo).closest('[role="listitem"], [role="row"], [tabindex="0"], [tabindex="-1"]') || melhor || alvo;
                const r = clicavel.getBoundingClientRect();
                const titulo = alvo.getAttribute('title') || alvo.innerText || '';

                return {
                    ok:true,
                    titulo,
                    x: Math.round(r.left + Math.min(180, Math.max(40, r.width / 2))),
                    y: Math.round(r.top + r.height / 2),
                    w: Math.round(r.width),
                    h: Math.round(r.height)
                };
            }
            """, termo)

            if not resultado or not resultado.get("ok"):
                print("DEBUG conversa não encontrada:", resultado)
                self.debug_conversas_visiveis()
                return False

            print(f"Conversa encontrada pelo título: {resultado.get('titulo')}")
            print(f"DEBUG clique conversa: x={resultado.get('x')} y={resultado.get('y')} w={resultado.get('w')} h={resultado.get('h')}")
            self.page.mouse.click(resultado["x"], resultado["y"])
            self.page.wait_for_timeout(1500)
            return True

        except Exception as e:
            print(f"Falha ao clicar conversa por JS/título: {e}")
            self.debug_conversas_visiveis()
            return False

    def debug_conversas_visiveis(self, limite=20):
        try:
            print("DEBUG conversas visíveis na lateral:")
            titulos = self.page.locator("#pane-side span[title], div[data-testid='chat-list'] span[title]")
            total = min(titulos.count(), limite)
            vistos = set()
            for i in range(total):
                try:
                    valor = (titulos.nth(i).get_attribute("title") or "").strip()
                    if valor and valor not in vistos:
                        vistos.add(valor)
                        print(f"- {valor}")
                except Exception:
                    pass
        except Exception as e:
            print(f"DEBUG conversas visíveis falhou: {e}")

    def subir_para_item_conversa(self, alvo):
        ancestrais = [
            "xpath=ancestor::*[@role='listitem'][1]",
            "xpath=ancestor::*[@role='row'][1]",
            "xpath=ancestor::div[contains(@style, 'height')][1]",
        ]
        for anc in ancestrais:
            try:
                item = alvo.locator(anc)
                if item.count() and item.is_visible():
                    return item
            except Exception:
                continue
        return None

    def encontrar_campo_busca(self):
        # O WhatsApp Web muda bastante os atributos da busca.
        # Esta função tenta vários caminhos e evita pegar a caixa de mensagem do chat.
        seletores = [
            "xpath=//div[@contenteditable='true' and @role='textbox' and (contains(@aria-label, 'Pesquisar') or contains(@aria-label, 'Search') or contains(@aria-placeholder, 'Pesquisar') or contains(@aria-placeholder, 'Search'))]",
            "xpath=//input[contains(@placeholder, 'Pesquisar') or contains(@aria-label, 'Pesquisar') or contains(@placeholder, 'Search') or contains(@aria-label, 'Search')]",
            "div[aria-label*='Pesquisar'][contenteditable='true']",
            "div[aria-placeholder*='Pesquisar'][contenteditable='true']",
            "div[title*='Pesquisar'][contenteditable='true']",
            "div[role='textbox'][contenteditable='true']",
            "input[type='text']",
        ]

        for seletor in seletores:
            try:
                locs = self.page.locator(seletor)
                total = locs.count()
                for i in range(total):
                    loc = locs.nth(i)
                    if not loc.is_visible():
                        continue
                    # Não usar a caixa de mensagem dentro do footer como busca.
                    try:
                        dentro_footer = loc.locator("xpath=ancestor::footer").count() > 0
                        if dentro_footer:
                            continue
                    except Exception:
                        pass
                    return loc
            except Exception:
                continue

        # Fallback: clica no texto/placeholder da busca e depois tenta achar o textbox ativo.
        textos_busca = [
            "Pesquisar ou começar uma nova conversa",
            "Pesquisar",
            "Search or start a new chat",
            "Search",
        ]
        for texto in textos_busca:
            try:
                alvo = self.page.get_by_text(texto, exact=False).first
                if alvo.count() and alvo.is_visible():
                    alvo.click(force=True)
                    self.page.wait_for_timeout(500)
                    ativo = self.page.locator("xpath=//div[@contenteditable='true' and @role='textbox' and not(ancestor::footer)]").first
                    if ativo.count() and ativo.is_visible():
                        return ativo
            except Exception:
                continue

        self.debug_estado_tela()
        raise Exception("Não encontrei o campo de busca do WhatsApp.")

    def caixa_texto_existe(self):
        """Confirma se existe uma caixa de mensagem visível no painel de conversa.
        A sua versão do WhatsApp nem sempre expõe <footer>, então também valida
        o <p class="selectable-text copyable-text"> próximo ao rodapé da tela.
        """
        try:
            achou = self.page.evaluate("""
            () => {
                const selectors = [
                    'footer div[contenteditable="true"]',
                    'footer div[role="textbox"]',
                    'footer [data-lexical-editor="true"]',
                    'footer p.selectable-text.copyable-text',
                    'div[contenteditable="true"] p.selectable-text.copyable-text',
                    '[role="textbox"] p.selectable-text.copyable-text',
                    'div[aria-label*="Digite uma mensagem"][contenteditable="true"]',
                    'div[aria-placeholder*="Digite uma mensagem"][contenteditable="true"]',
                    'div[aria-label*="Type a message"][contenteditable="true"]',
                    'div[aria-placeholder*="Type a message"][contenteditable="true"]',
                    'p.selectable-text.copyable-text'
                ];

                const isVisibleComposer = (el) => {
                    if (!el) return false;
                    let cur = el;
                    for (let i = 0; i < 6 && cur; i++, cur = cur.parentElement) {
                        const r = cur.getBoundingClientRect();
                        if (r.width > 80 && r.height > 5 && r.bottom > window.innerHeight * 0.55 && r.left > window.innerWidth * 0.20) {
                            return true;
                        }
                    }
                    return false;
                };

                for (const sel of selectors) {
                    const els = [...document.querySelectorAll(sel)];
                    if (els.some(isVisibleComposer)) return true;
                }
                return false;
            }
            """)
            return bool(achou)
        except Exception:
            return False

    def chat_atual_parece_ser(self, nome):
        try:
            header = self.page.locator("header").last
            if header.count() and header.is_visible():
                texto = header.inner_text(timeout=2000)
                return nome.lower() in texto.lower()
        except Exception:
            pass
        return False

    def aguardar_chat_aberto(self, nome=None, timeout_ms=12000):
        fim = time.time() + (timeout_ms / 1000)
        while time.time() < fim:
            try:
                if self.caixa_texto_existe():
                    # Quando possível, confirma também o cabeçalho.
                    if nome is None or self.chat_atual_parece_ser(nome):
                        self.page.wait_for_timeout(600)
                        return True
                    # Em alguns layouts o cabeçalho demora; se a caixa existe, já é chat aberto.
                    self.page.wait_for_timeout(600)
                    return True
            except Exception:
                pass
            self.page.wait_for_timeout(300)
        return False

    def debug_estado_tela(self):
        try:
            print("DEBUG estado tela:")
            print("URL:", self.page.url)
            print("Tem footer:", self.page.locator("footer").count())
            print("Tem caixa footer:", self.page.locator("footer div[contenteditable='true']").count())
            print("Tem p caixa global:", self.page.locator("p.selectable-text.copyable-text").count())
            print("Headers:", self.page.locator("header").count())
        except Exception as e:
            print(f"DEBUG estado falhou: {e}")

    def capturar_mensagens(self):
        mensagens = []

        containers = self.page.locator("div[data-testid='msg-container']")
        total = containers.count()

        for i in range(total):
            msg = containers.nth(i)

            try:
                cabecalho = msg.locator("div.copyable-text").first
                id_mensagem = cabecalho.get_attribute("data-pre-plain-text") or ""

                texto = self.extrair_texto_da_mensagem(msg)

                links = re.findall(r"https?://[^\s]+", texto)
                link = links[0] if links else None

                tem_imagem = self.mensagem_tem_imagem(msg)

                mensagens.append({
                    "autor": id_mensagem,
                    "id_mensagem": id_mensagem,
                    "texto": texto,
                    "link": link,
                    "tem_imagem": tem_imagem,
                    "indice_mensagem": i
                })

            except Exception:
                continue

        return mensagens

    def extrair_texto_da_mensagem(self, msg):
        legenda = msg.locator("span[data-testid='image-caption selectable-text']")

        if legenda.count():
            return legenda.first.inner_text().strip()

        spans = msg.locator("span.selectable-text")

        if spans.count():
            return spans.first.inner_text().strip()

        return ""

    def mensagem_tem_imagem(self, msg):
        try:
            return msg.locator("div[role='button'][data-testid='image-thumb']").count() > 0
        except:
            return False

    def encontrar_caixa_texto_normal(self):
        seletores = [
            "footer div[contenteditable='true']",
            "footer div[role='textbox']",
            "footer [data-lexical-editor='true']",
            "xpath=//p[contains(@class, 'selectable-text') and contains(@class, 'copyable-text')]/ancestor::div[@contenteditable='true'][1]",
            "xpath=//p[contains(@class, 'selectable-text') and contains(@class, 'copyable-text')]/ancestor::*[@role='textbox'][1]",
            "footer p.selectable-text.copyable-text",
            "footer p[dir='auto']",
            "div[data-testid='conversation-compose-box-input']",
            "footer div[contenteditable='true']",
            "div[aria-label='Digite uma mensagem']",
            "div[aria-label*='Digite uma mensagem']",
            "div[aria-placeholder='Digite uma mensagem']",
            "div[contenteditable='true'][role='textbox']"
        ]

        for seletor in seletores:
            try:
                caixa = self.page.locator(seletor).last
                caixa.wait_for(state="visible", timeout=5000)
                return caixa
            except:
                continue

        raise Exception("Não encontrei caixa de mensagem.")

    def encontrar_botao_enviar(self):
        seletores = [
            "span[data-icon='send']",
            "span[data-icon='send-filled']",
            "button[aria-label='Enviar']",
            "div[aria-label='Enviar']",
            "[data-testid='send']"
        ]

        for seletor in seletores:
            try:
                elementos = self.page.locator(seletor)
                total = elementos.count()

                for i in range(total - 1, -1, -1):
                    botao = elementos.nth(i)

                    if botao.is_visible():
                        return botao
            except:
                continue

        return None

    def fechar_visualizador_midia(self):
        """Fecha somente visualizador/preview de mídia, sem usar ESC no chat normal.

        Antes esta função sempre apertava Escape. No WhatsApp Web isso pode tirar o
        foco/fechar o painel da conversa e voltar para a tela inicial. Por isso,
        agora só pressiona Escape quando há indício real de visualizador de mídia
        aberto, como imagem/vídeo em dialog, botão de download ou preview de anexo.
        """
        try:
            tem_visualizador = self.page.evaluate("""
            () => {
                const visivel = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };

                const dialogs = [...document.querySelectorAll('div[role="dialog"]')].filter(visivel);
                for (const d of dialogs) {
                    const texto = (d.innerText || '').toLowerCase();
                    if (
                        d.querySelector('img, video') ||
                        d.querySelector('span[data-icon="download"], span[data-icon="download-refreshed"]') ||
                        d.querySelector('button[aria-label*="Baixar"], button[aria-label*="Download"]') ||
                        texto.includes('adicionar legenda') ||
                        texto.includes('adicione uma legenda')
                    ) {
                        return true;
                    }
                }

                // Preview de envio de mídia no painel direito: tem imagem grande + botão enviar item selecionado.
                const temPreviewEnvio = [...document.querySelectorAll('button, div[role="button"]')].some(el => {
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && r.left > window.innerWidth * 0.25 &&
                           (aria.includes('enviar') || aria.includes('send'));
                }) && [...document.querySelectorAll('img, video')].some(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 80 && r.height > 80 && r.left > window.innerWidth * 0.25;
                });

                return temPreviewEnvio;
            }
            """)

            if tem_visualizador:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(800)
        except Exception:
            pass

    def fechar(self):
        self.browser.close()

    def limpar_preview_se_aberto(self):
        """Limpa preview de mídia somente quando existir preview real.

        Não pressiona Escape de forma cega, porque isso pode tirar o WhatsApp
        da conversa atual e voltar para a tela inicial.
        """
        try:
            tem_preview = self.page.evaluate("""
            () => {
                const visivel = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };

                const dialogs = [...document.querySelectorAll('div[role="dialog"]')].filter(visivel);
                for (const d of dialogs) {
                    const texto = (d.innerText || '').toLowerCase();
                    if (
                        d.querySelector('img, video') ||
                        texto.includes('legenda') ||
                        texto.includes('caption') ||
                        d.querySelector('span[data-icon="download"], span[data-icon="download-refreshed"]')
                    ) {
                        return true;
                    }
                }

                const temBotaoEnviarMidia = [...document.querySelectorAll('button, div[role="button"]')].some(el => {
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && r.left > window.innerWidth * 0.25 &&
                           (aria.includes('enviar') || aria.includes('send')) &&
                           (aria.includes('item') || aria.includes('selecionado') || aria.includes('selected'));
                });

                const temImagemGrande = [...document.querySelectorAll('img, video')].some(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 80 && r.height > 80 && r.left > window.innerWidth * 0.25;
                });

                return temBotaoEnviarMidia && temImagemGrande;
            }
            """)

            if tem_preview:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(700)

        except Exception:
            pass

    def confirmar_chat_destino_pronto(self, nome, timeout_ms=20000):
        """Confirma que o painel direito está no grupo destino e que existe caixa de mensagem."""
        fim = time.time() + (timeout_ms / 1000)
        while time.time() < fim:
            try:
                estado = self.page.evaluate("""
                (nome) => {
                    const headers = [...document.querySelectorAll('header')].map(x => x.innerText || '');
                    const textoHeader = headers.join('\n').toLowerCase();
                    const temHeader = textoHeader.includes(String(nome || '').toLowerCase());

                    const temCaixa = [...document.querySelectorAll('div[contenteditable="true"][role="textbox"], div[contenteditable="true"]')]
                        .some(el => {
                            const r = el.getBoundingClientRect();
                            const aria = (el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || '').toLowerCase();
                            return r.width > 100 && r.height > 5 &&
                                   r.left > window.innerWidth * 0.25 &&
                                   r.bottom > window.innerHeight * 0.60 &&
                                   (aria.includes('mensagem') || aria.includes('message'));
                        });

                    return {temHeader, temCaixa, headers};
                }
                """, nome)

                if estado.get("temHeader") and estado.get("temCaixa"):
                    return True
            except Exception:
                pass

            self.page.wait_for_timeout(350)

        try:
            print("DEBUG confirmação chat destino falhou:")
            print(self.page.evaluate("""
            () => ({
                headers: [...document.querySelectorAll('header')].map(x => x.innerText || ''),
                caixas: [...document.querySelectorAll('input, div[contenteditable="true"], p.selectable-text.copyable-text')]
                    .map(el => {
                        const r = el.getBoundingClientRect();
                        return {
                            tag: el.tagName,
                            aria: el.getAttribute('aria-label'),
                            placeholder: el.getAttribute('aria-placeholder') || el.getAttribute('placeholder'),
                            contenteditable: el.getAttribute('contenteditable'),
                            x: Math.round(r.left), y: Math.round(r.top),
                            w: Math.round(r.width), h: Math.round(r.height),
                            visible: r.width > 0 && r.height > 0
                        };
                    }).filter(x => x.visible)
            })
            """))
        except Exception:
            pass

        return False

    def conversa_atual_tem_nome(self, nome):
        """Verifica pelo cabeçalho se a conversa/painel direito atual parece ser o grupo indicado."""
        termo = (nome or "").lower().strip()
        if not termo:
            return False
        try:
            headers = self.page.locator("header")
            for i in range(headers.count()):
                try:
                    h = headers.nth(i)
                    if h.is_visible():
                        texto = h.inner_text(timeout=1000).lower()
                        if termo in texto:
                            return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def ir_para_fim_da_conversa(self):
        """Garante que o painel de mensagens esteja no fim sem usar teclas globais.

        Antes havia uso de teclas como End/Escape em alguns fluxos. Em algumas
        versões do WhatsApp Web isso pode tirar o foco da conversa ou voltar
        para a tela inicial. Aqui fazemos apenas rolagem por JS no painel direito.
        """
        try:
            self.page.evaluate("""
            () => {
                const paneSide = document.querySelector('#pane-side');
                const scrollers = [...document.querySelectorAll('div')]
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        if (paneSide && paneSide.contains(el)) return false;
                        return r.left > window.innerWidth * 0.25 &&
                               r.height > 180 &&
                               el.scrollHeight > el.clientHeight + 30;
                    })
                    .sort((a, b) => {
                        const ar = a.getBoundingClientRect();
                        const br = b.getBoundingClientRect();
                        return (br.height * br.width) - (ar.height * ar.width);
                    });

                for (const el of scrollers.slice(0, 3)) {
                    el.scrollTop = el.scrollHeight;
                }
            }
            """)
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def preparar_monitoramento_origem(self, nome_origem):
        """Garante o grupo de origem aberto e pronto para monitoramento.

        Esta versão evita qualquer Escape/click desnecessário para não fazer o
        WhatsApp sair da conversa e voltar para a tela inicial.
        """
        self.fechar_dialogos_sobrepostos()

        if not self.conversa_atual_tem_nome(nome_origem):
            self.abrir_grupo(nome_origem)
        else:
            print(f"Grupo de origem já está aberto: {nome_origem}")

        self.page.wait_for_timeout(900)
        self.ir_para_fim_da_conversa()

        # Confirma após a rolagem. Se por algum motivo a conversa fechou, reabre uma vez.
        if not self.conversa_atual_tem_nome(nome_origem):
            print("Grupo de origem não permaneceu aberto após preparar. Reabrindo uma vez...")
            self.abrir_grupo(nome_origem)
            self.page.wait_for_timeout(900)
            self.ir_para_fim_da_conversa()

        return True


    # ======================================================================
    # PATCH DEFINITIVO - ASSOCIAR IMAGEM SOMENTE À MENSAGEM QUE TEM O LINK
    # Nunca baixa imagem por índice visual solto para uma oferta.
    # Nunca reaproveita imagem baixada de mensagem sem link.
    # ======================================================================

    def _normalizar_link_capturado(self, link):
        if not link:
            return None
        return str(link).strip().rstrip('.,);]\u202c')

    def capturar_mensagens(self):
        """Captura mensagens visíveis.

        Regra importante:
        - tem_imagem continua informando se o container tem miniatura;
        - imagem_associada_ao_link só fica True quando o MESMO container
          possui imagem E possui link no próprio texto/legenda.

        Isso impede que uma imagem de alerta, meme ou mensagem separada seja
        baixada e enviada junto com uma oferta que estava em outro container.
        """
        mensagens = []

        containers = self.page.locator("div[data-testid='msg-container']")
        total = containers.count()

        for i in range(total):
            try:
                msg = containers.nth(i)
                cabecalho = msg.locator("div.copyable-text").first
                id_mensagem = cabecalho.get_attribute("data-pre-plain-text") or ""

                texto = self.extrair_texto_da_mensagem(msg) or ""
                links = re.findall(r"https?://[^\s]+", texto)
                link = self._normalizar_link_capturado(links[0]) if links else None

                tem_imagem = self.mensagem_tem_imagem(msg)

                mensagens.append({
                    "autor": id_mensagem,
                    "id_mensagem": id_mensagem,
                    "texto": texto,
                    "link": link,
                    "tem_imagem": tem_imagem,
                    "imagem_associada_ao_link": bool(link and tem_imagem),
                    "indice_mensagem": i,
                })

            except Exception:
                continue

        return mensagens

    def _normalizar_texto_dom(self, texto):
        if texto is None:
            return ""
        texto = str(texto).lower()
        # remove caracteres invisíveis comuns no WhatsApp
        for ch in ["\u202a", "\u202c", "\u200e", "\u200f", "\ufe0f"]:
            texto = texto.replace(ch, "")
        return " ".join(texto.split())

    def _estado_painel_direito(self, nome=None):
        """Retorna um diagnóstico pequeno do painel direito."""
        return self.page.evaluate("""
        (nome) => {
            const norm = (s) => String(s || '')
                .toLowerCase()
                .replace(/[\\u202a\\u202c\\u200e\\u200f\\ufe0f]/g, '')
                .replace(/\\s+/g, ' ')
                .trim();

            const termo = norm(nome);
            const headers = [...document.querySelectorAll('header')]
                .map(h => h.innerText || '')
                .filter(Boolean);

            const headerDireito = headers
                .filter(h => {
                    const r = [...document.querySelectorAll('header')]
                        .find(x => (x.innerText || '') === h)?.getBoundingClientRect();
                    return !r || r.left > window.innerWidth * 0.25;
                });

            const textoHeaders = norm(headers.join('\\n'));
            const textoHeaderDireito = norm(headerDireito.join('\\n'));
            const temNome = termo ? (textoHeaders.includes(termo) || textoHeaderDireito.includes(termo)) : false;

            const caixas = [...document.querySelectorAll('input, div[contenteditable="true"], p.selectable-text.copyable-text')]
                .map(el => {
                    const r = el.getBoundingClientRect();
                    return {
                        tag: el.tagName,
                        aria: el.getAttribute('aria-label'),
                        placeholder: el.getAttribute('aria-placeholder') || el.getAttribute('placeholder'),
                        contenteditable: el.getAttribute('contenteditable'),
                        text: (el.innerText || el.textContent || '').slice(0, 60),
                        x: Math.round(r.left),
                        y: Math.round(r.top),
                        w: Math.round(r.width),
                        h: Math.round(r.height),
                        visible: r.width > 0 && r.height > 0
                    };
                })
                .filter(x => x.visible);

            const temCaixaMensagemDestino = caixas.some(c => {
                const aria = norm((c.aria || '') + ' ' + (c.placeholder || ''));
                return c.x > window.innerWidth * 0.25 &&
                       c.w > 100 &&
                       c.h > 5 &&
                       (aria.includes('mensagem') || aria.includes('message'));
            });

            const anexar = [...document.querySelectorAll('button[aria-label*="Anexar"], button[aria-label*="Attach"]')]
                .map(b => {
                    const r = b.getBoundingClientRect();
                    return {
                        aria: b.getAttribute('aria-label'),
                        x: Math.round(r.left),
                        y: Math.round(r.top),
                        w: Math.round(r.width),
                        h: Math.round(r.height),
                        visible: r.width > 0 && r.height > 0
                    };
                })
                .filter(x => x.visible && x.x > window.innerWidth * 0.25);

            return {
                headers,
                temNome,
                temCaixaMensagemDestino,
                qtdAnexar: anexar.length,
                anexar,
                caixas
            };
        }
        """, nome)

    def _clicar_conversa_lateral_por_titulo(self, nome):
        """Clica na conversa na lateral usando o título real da linha."""
        termo = self._normalizar_texto_dom(nome)
        resultado = self.page.evaluate("""
        (termo) => {
            const norm = (s) => String(s || '')
                .toLowerCase()
                .replace(/[\\u202a\\u202c\\u200e\\u200f\\ufe0f]/g, '')
                .replace(/\\s+/g, ' ')
                .trim();

            const pane = document.querySelector('#pane-side') || document.querySelector('div[data-testid="chat-list"]');
            if (!pane) return {ok:false, motivo:'sem lista lateral'};

            const spans = [...pane.querySelectorAll('span[title]')];
            const alvo = spans.find(s => norm(s.getAttribute('title')).includes(termo));
            if (!alvo) {
                return {
                    ok:false,
                    motivo:'titulo nao encontrado',
                    titulos: spans.map(s => s.getAttribute('title')).filter(Boolean).slice(0, 20)
                };
            }

            const cell = alvo.closest('[data-testid="cell-frame-container"]') ||
                         alvo.closest('[role="listitem"]') ||
                         alvo.closest('[role="row"]') ||
                         alvo.closest('[tabindex]') ||
                         alvo.parentElement ||
                         alvo;

            cell.scrollIntoView({block:'center', inline:'nearest'});
            const r = cell.getBoundingClientRect();
            return {
                ok:true,
                titulo: alvo.getAttribute('title') || alvo.textContent || '',
                x: Math.round(r.left + Math.min(180, Math.max(60, r.width / 2))),
                y: Math.round(r.top + r.height / 2),
                w: Math.round(r.width),
                h: Math.round(r.height)
            };
        }
        """, termo)

        if not resultado or not resultado.get("ok"):
            print("DEBUG conversa destino não encontrada na lateral:", resultado)
            self.debug_conversas_visiveis()
            return False

        print(f"Conversa destino encontrada pelo título: {resultado.get('titulo')}")
        print(f"DEBUG clique destino: x={resultado.get('x')} y={resultado.get('y')} w={resultado.get('w')} h={resultado.get('h')}")
        self.page.mouse.click(resultado["x"], resultado["y"])
        self.page.wait_for_timeout(1200)
        return True

    def _clicar_item_lateral_generico_por_titulo(self, nome):
        """Clica em um item de lista lateral (canal, comunidade etc.) cujo
        texto bata com o nome informado, SEM depender do container
        `#pane-side` - que é específico da lista de Conversas/Grupos e
        continua presente no DOM (com o conteúdo antigo) mesmo quando outra
        aba, como "Canais", está sendo exibida por cima dele.

        Em vez disso, procura em todo o documento por elementos-folha
        (sem filhos) visíveis, restritos à faixa esquerda da tela (onde
        ficam as listas), comparando tanto o atributo `title` quanto o
        texto do próprio elemento.
        """
        termo = self._normalizar_texto_dom(nome)
        resultado = self.page.evaluate("""
        (termo) => {
            const norm = (s) => String(s || '')
                .toLowerCase()
                .replace(/[\\u202a\\u202c\\u200e\\u200f\\ufe0f]/g, '')
                .replace(/\\s+/g, ' ')
                .trim();

            const candidatosBrutos = [...document.querySelectorAll('span, div')]
                .filter(el => el.children.length === 0);

            const visiveisEsquerda = [];
            const candidatos = [];

            for (const el of candidatosBrutos) {
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                if (r.left >= window.innerWidth * 0.42) continue;

                const texto = (el.getAttribute('title') || el.textContent || '').trim();
                if (!texto) continue;

                visiveisEsquerda.push(texto);
                if (norm(texto).includes(termo)) {
                    candidatos.push({el, r, texto});
                }
            }

            if (!candidatos.length) {
                return {
                    ok: false,
                    motivo: 'titulo nao encontrado (busca generica)',
                    titulos: [...new Set(visiveisEsquerda)].slice(0, 40),
                };
            }

            candidatos.sort((a, b) => a.r.top - b.r.top);
            const alvo = candidatos[0];
            const cell = alvo.el.closest('[role="listitem"]') ||
                         alvo.el.closest('[role="row"]') ||
                         alvo.el.closest('[tabindex]') ||
                         alvo.el.parentElement ||
                         alvo.el;

            cell.scrollIntoView({block: 'center', inline: 'nearest'});
            const r = cell.getBoundingClientRect();
            return {
                ok: true,
                titulo: alvo.texto,
                x: Math.round(r.left + Math.min(180, Math.max(60, r.width / 2))),
                y: Math.round(r.top + r.height / 2),
            };
        }
        """, termo)

        if not resultado or not resultado.get("ok"):
            print("DEBUG item lateral (busca genérica) não encontrado:", resultado)
            return False

        print(f"Item lateral encontrado (busca genérica) pelo título/texto: {resultado.get('titulo')}")
        self.page.mouse.click(resultado["x"], resultado["y"])
        self.page.wait_for_timeout(1200)
        return True

    def _clicar_aba_navegacao(self, termos, timeout_ms=8000):
        """Clica em um item da navegação lateral esquerda do WhatsApp Web
        (ícones de Conversas/Status/Canais/Comunidades) cujo aria-label ou
        title bata com algum dos termos informados (sem acento, minúsculo).
        Usado para trocar entre a aba normal de conversas e a aba de Canais
        antes de abrir um destino. Retorna True se conseguiu clicar.
        """
        termos_norm = [self._normalizar_texto_dom(t) for t in termos]
        fim = time.time() + (timeout_ms / 1000)

        while time.time() < fim:
            resultado = self.page.evaluate("""
            (termos) => {
                const norm = (s) => String(s || '')
                    .toLowerCase()
                    .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/[\\u202a\\u202c\\u200e\\u200f\\ufe0f]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim();

                const candidatos = [...document.querySelectorAll(
                    'button, div[role="button"], a[role="button"], span[role="button"]'
                )].filter(el => {
                    const r = el.getBoundingClientRect();
                    // Ícones de navegação ficam colados na borda esquerda da tela.
                    return r.width > 0 && r.height > 0 && r.left < 110;
                });

                for (const el of candidatos) {
                    const rotulo = norm(
                        el.getAttribute('aria-label') || el.getAttribute('title') || ''
                    );
                    if (!rotulo) continue;
                    if (termos.some(t => rotulo.includes(t))) {
                        const r = el.getBoundingClientRect();
                        return {
                            ok: true,
                            rotulo,
                            x: Math.round(r.left + r.width / 2),
                            y: Math.round(r.top + r.height / 2),
                        };
                    }
                }
                return {ok: false};
            }
            """, termos_norm)

            if resultado and resultado.get("ok"):
                self.page.mouse.click(resultado["x"], resultado["y"])
                self.page.wait_for_timeout(900)
                return True

            self.page.wait_for_timeout(300)

        return False

    def ir_para_aba_canais(self, timeout_ms=90000):
        """Muda a navegação lateral para a aba de Canais do WhatsApp
        ("Updates"/"Canais"), que fica separada da aba normal de conversas
        e grupos. É nela que ficam listados os canais que a conta administra.

        O ícone de Canais só é adicionado à barra lateral depois que o
        WhatsApp Web termina de sincronizar esse recurso com o celular -
        isso pode levar cerca de 1 minuto após o login/carregamento
        inicial, mesmo com a conta já administrando um canal. Por isso o
        timeout aqui é bem maior que o das outras trocas de aba.
        """
        print("Procurando o ícone de 'Canais' na lateral (pode levar até 1 minuto após o WhatsApp Web carregar)...")
        self.fechar_dialogos_sobrepostos()
        if self._clicar_aba_navegacao(["canais", "channels", "updates", "atualizacoes"], timeout_ms=timeout_ms):
            self.page.wait_for_timeout(500)
            return True
        print("DEBUG: não encontrei o ícone de navegação para 'Canais' na lateral esquerda.")
        return False

    def ir_para_aba_conversas(self):
        """Garante que a navegação lateral esteja na aba normal de
        Conversas (chats/grupos), voltando da aba de Canais se necessário.
        """
        self.fechar_dialogos_sobrepostos()
        self._clicar_aba_navegacao(["conversas", "bate-papos", "chats", "chat"])

    def abrir_destino_para_envio(self, nome, tipo="grupo", timeout_ms=20000):
        """Abre o grupo/conversa OU canal destino e só retorna quando o
        painel direito realmente está nele.

        `tipo` é "grupo" (conversa/grupo normal, aba padrão do WhatsApp) ou
        "canal" (WhatsApp Channels, aba separada "Canais"). Não substitui
        preparar_monitoramento_origem(). Assim evitamos reintroduzir o bug
        de sair do OLAPROMOS.
        """
        tipo = "canal" if str(tipo or "grupo").strip().lower() == "canal" else "grupo"
        rotulo_tipo = "canal" if tipo == "canal" else "grupo"
        print(f"Abrindo {rotulo_tipo} destino para envio: {nome}")

        if tipo == "canal":
            self.ir_para_aba_canais()
        else:
            self.ir_para_aba_conversas()

        self.fechar_dialogos_sobrepostos()
        # Não chama fechar_visualizador_midia aqui: se não houver preview, ESC pode atrapalhar.

        fim = time.time() + (timeout_ms / 1000)
        tentativa = 0

        while time.time() < fim:
            estado = self._estado_painel_direito(nome)
            if estado.get("temNome") and (estado.get("temCaixaMensagemDestino") or estado.get("qtdAnexar", 0) > 0):
                print(f"{rotulo_tipo.capitalize()} destino confirmado no painel direito.")
                return True

            tentativa += 1
            if tentativa <= 5:
                if tipo == "canal":
                    # A lista de Canais não fica dentro do #pane-side (esse
                    # container é específico da lista de Conversas/Grupos),
                    # por isso usa a busca genérica em vez da busca de
                    # conversa normal.
                    if not self._clicar_item_lateral_generico_por_titulo(nome):
                        # Reforça a troca de aba: em alguns fluxos o clique
                        # no ícone de Canais some quando reaberto o app.
                        self.ir_para_aba_canais()
                else:
                    self._clicar_conversa_lateral_por_titulo(nome)
            else:
                self.page.wait_for_timeout(700)

        print(f"DEBUG: {rotulo_tipo} destino não confirmou no painel direito:")
        print(self._estado_painel_direito(nome))
        if tipo == "canal":
            raise Exception(
                f"Não consegui confirmar o canal destino aberto: {nome}. "
                "Confira se o nome está exatamente igual ao do canal e se essa conta "
                "administra esse canal (só admins conseguem publicar)."
            )
        raise Exception(f"Não consegui confirmar o grupo destino aberto: {nome}")

    def abrir_grupo_destino_para_envio(self, nome, timeout_ms=20000):
        """Mantido por compatibilidade; equivale a
        abrir_destino_para_envio(nome, tipo="grupo", timeout_ms=timeout_ms)."""
        return self.abrir_destino_para_envio(nome, tipo="grupo", timeout_ms=timeout_ms)

    def previa_link_esta_visivel(self):
        """Detecta a previa do link somente quando a imagem dela carregou."""
        try:
            return bool(self.page.evaluate("""
            () => {
                const visible = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };

                const editor = [...document.querySelectorAll('div[contenteditable="true"], [role="textbox"]')]
                    .filter(visible)
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.left > window.innerWidth * 0.25 &&
                               r.top > window.innerHeight * 0.45 &&
                               r.width > 120;
                    })
                    .sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top)[0];

                if (!editor) return false;

                const editorRect = editor.getBoundingClientRect();
                const footer = editor.closest('footer') || [...document.querySelectorAll('footer')]
                    .filter(visible)
                    .find(el => el.contains(editor));
                const linkish = (text) => {
                    const t = String(text || '').toLowerCase();
                    return t.includes('shopee') || t.includes('http') || t.includes('.com') || t.includes('.br');
                };

                const dentroEditor = (el) => {
                    return !!(
                        el.closest('div[contenteditable="true"]') ||
                        el.closest('[role="textbox"]') ||
                        el.isContentEditable
                    );
                };

                const imagemCarregada = (el) => {
                    const r = el.getBoundingClientRect();
                    if (r.width < 110 || r.height < 70) return false;

                    const tag = el.tagName.toLowerCase();
                    if (tag === 'img') {
                        if (!el.complete || el.naturalWidth < 110 || el.naturalHeight < 70) return false;
                        const src = String(el.currentSrc || el.src || '');
                        const alt = String(el.alt || '').toLowerCase();
                        if (src.startsWith('data:image/svg') || src.includes('emoji') || alt.includes('emoji')) return false;
                    }

                    return true;
                };

                const imagemDentroDoComposer = (el) => {
                    if (!visible(el)) return false;
                    if (dentroEditor(el)) return false;

                    const r = el.getBoundingClientRect();
                    if (footer && footer.contains(el)) {
                        return r.left > window.innerWidth * 0.25 &&
                               r.top < editorRect.top &&
                               r.bottom <= editorRect.top - 4 &&
                               r.bottom > 0 &&
                               r.width >= 110 &&
                               r.height >= 70;
                    }

                    const topoPreview = Math.max(0, editorRect.top - 220);
                    const basePreview = editorRect.top - 8;
                    return r.left > window.innerWidth * 0.25 &&
                           r.top >= topoPreview &&
                           r.bottom <= basePreview &&
                           r.width >= 110 &&
                           r.height >= 70;
                };

                const temContainerDePreview = (img) => {
                    let atual = img;
                    for (let i = 0; i < 7 && atual; i += 1) {
                        const r = atual.getBoundingClientRect();
                        const texto = atual.innerText || atual.textContent || '';
                        const href = [...atual.querySelectorAll('a[href]')]
                            .map(a => a.href || a.textContent || '')
                            .join(' ');
                        const parecePreview =
                            r.width >= 180 &&
                            r.height >= 75 &&
                            r.bottom <= editorRect.top - 2 &&
                            r.top >= Math.max(0, editorRect.top - 260) &&
                            (linkish(texto) || linkish(href));
                        if (parecePreview) return true;
                        atual = atual.parentElement;
                    }
                    return false;
                };

                const raizBusca = footer || document;
                const imagens = [...raizBusca.querySelectorAll('img, video, canvas')]
                    .filter(imagemDentroDoComposer)
                    .filter(imagemCarregada)
                    .filter(temContainerDePreview);

                return imagens.length > 0;
            }
            """))
        except Exception:
            return False

    def aguardar_previa_link(self, timeout_ms=None):
        timeout_ms = (
            timeout_ms
            or self.timeout_imagem_previa_link_ms
            or self.timeout_previa_link_ms
        )
        espera_minima = min(self.espera_minima_previa_link_ms, timeout_ms)
        if espera_minima > 0:
            self.page.wait_for_timeout(espera_minima)

        fim = time.time() + (timeout_ms / 1000)

        while time.time() < fim:
            if self.previa_link_esta_visivel():
                print("Previa do link carregada.")
                return True
            self.page.wait_for_timeout(500)

        print("Previa do link nao apareceu dentro do tempo limite. Enviando mesmo assim.")
        return False

    def enviar_texto(self, grupo_destino, texto, aguardar_previa=None, timeout_previa_ms=None, tipo_destino="grupo"):
        """Envia texto e, se configurado, espera a previa do link antes do Enter.

        `tipo_destino` é "grupo" (conversa/grupo normal) ou "canal" (WhatsApp
        Channels, em outra aba do app).
        """
        if aguardar_previa is None:
            aguardar_previa = self.aguardar_previa_link_config
        if timeout_previa_ms is None:
            timeout_previa_ms = self.timeout_previa_link_ms

        self.abrir_destino_para_envio(grupo_destino, tipo=tipo_destino, timeout_ms=25000)

        caixa = self.encontrar_caixa_texto_normal()
        caixa.click(force=True)
        try:
            caixa.fill(texto)
        except Exception:
            self.page.keyboard.insert_text(texto)

        if aguardar_previa:
            self.aguardar_previa_link(timeout_previa_ms)

        caixa.press("Enter")
        self.page.wait_for_timeout(1200)

    def enviar_texto_com_fallback_imagem(
        self,
        grupo_destino,
        texto,
        caminho_imagem=None,
        aguardar_previa=None,
        timeout_previa_ms=None,
        tipo_destino="grupo",
    ):
        """Envia com preview do link; se a preview falhar, usa imagem como fallback.

        `tipo_destino` é "grupo" (conversa/grupo normal) ou "canal" (WhatsApp
        Channels, em outra aba do app).
        """
        if aguardar_previa is None:
            aguardar_previa = self.aguardar_previa_link_config
        if timeout_previa_ms is None:
            timeout_previa_ms = self.timeout_previa_link_ms

        self.abrir_destino_para_envio(grupo_destino, tipo=tipo_destino, timeout_ms=25000)

        caixa = self.encontrar_caixa_texto_normal()
        caixa.click(force=True)
        try:
            caixa.fill(texto)
        except Exception:
            self.page.keyboard.insert_text(texto)

        if not aguardar_previa:
            caixa.press("Enter")
            self.page.wait_for_timeout(1200)
            return "texto"

        if self.aguardar_previa_link(timeout_previa_ms):
            caixa.press("Enter")
            self.page.wait_for_timeout(1200)
            return "preview"

        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self._limpar_texto_digitado(caixa, exigir_vazio=False)
            return "nao_enviado_sem_imagem"

        try:
            self._limpar_texto_digitado(caixa, exigir_vazio=True)
            self.enviar_imagem_com_legenda(None, caminho_imagem, texto)
            return "imagem"
        except Exception as erro:
            print(f"Falha ao enviar imagem de fallback: {erro}")
            try:
                self.fechar_visualizador_midia()
                self.limpar_preview_se_aberto()
                caixa = self.encontrar_caixa_texto_normal()
                caixa.click(force=True)
                self._limpar_texto_digitado(caixa, exigir_vazio=False)
                return f"nao_enviado_falha_imagem:{erro}"
            except Exception:
                raise erro

    def _limpar_texto_digitado(self, caixa, exigir_vazio=False):
        """Limpa o texto da caixa de mensagem antes de anexar uma imagem.

        Importante: a limpeza e feita SOMENTE via teclado nativo (Ctrl+A +
        Delete), igual a um usuario real faria. O WhatsApp Web mantem um
        estado interno do editor que nao e so o DOM visivel; manipular o
        DOM diretamente via JS (innerHTML='') pode deixar esse estado
        interno dessincronizado - o texto "some" da tela mas o WhatsApp
        ainda acha que ele existe, e ele reaparece (as vezes duplicado)
        quando a legenda da imagem e aberta. Por isso o hack de DOM
        (_limpar_composer_por_dom) so e usado como ultimo recurso, se a
        limpeza nativa falhar depois de varias tentativas.
        """
        try:
            self._fechar_previa_link_rascunho()
            for _ in range(6):
                try:
                    caixa = self.encontrar_caixa_texto_normal()
                    caixa.click(force=True)
                except Exception:
                    pass
                self.page.keyboard.press("Control+A")
                self.page.wait_for_timeout(80)
                self.page.keyboard.press("Delete")
                self.page.wait_for_timeout(300)
                self._fechar_previa_link_rascunho()
                if self._caixa_texto_esta_vazia(caixa) and self._composer_normal_esta_vazio():
                    # Espera extra para o estado interno do WhatsApp
                    # terminar de sincronizar com o DOM antes de abrir o
                    # menu de anexos. Sem essa pausa, o texto antigo pode
                    # "vazar" para a legenda da imagem.
                    self.page.wait_for_timeout(500)
                    return True

            # Ultimo recurso: forca via DOM. Pode dessincronizar o estado
            # interno do WhatsApp, entao so usar se o metodo nativo falhar
            # completamente. NUNCA usa Escape aqui - se nao houver modal
            # real aberto, Escape fecha a conversa inteira.
            self._fechar_menu_sem_sair_da_conversa()
            self._limpar_composer_por_dom()
            self._fechar_previa_link_rascunho()
            self.page.wait_for_timeout(800)
            if self._composer_normal_esta_vazio():
                return True
        except Exception as erro:
            if exigir_vazio:
                raise RuntimeError(f"Nao consegui limpar o texto antes do fallback: {erro}")

        if exigir_vazio:
            diagnostico = self.salvar_diagnostico_anexo("falha_limpar_texto")
            raise RuntimeError(f"Nao consegui limpar o texto antes de anexar imagem. Diagnostico: {diagnostico}")
        return False

    def _limpar_composer_por_dom(self):
        try:
            self.page.evaluate("""
            () => {
                const dispara = (el) => {
                    for (const tipo of ['beforeinput', 'input', 'change', 'keyup']) {
                        try {
                            el.dispatchEvent(new InputEvent(tipo, {
                                bubbles: true,
                                cancelable: true,
                                inputType: 'deleteContentBackward',
                                data: null,
                            }));
                        } catch {
                            el.dispatchEvent(new Event(tipo, {bubbles: true, cancelable: true}));
                        }
                    }
                };

                const candidatos = [...document.querySelectorAll(
                    'footer div[contenteditable="true"], footer [role="textbox"], footer p.selectable-text.copyable-text, div[contenteditable="true"][role="textbox"], [data-testid="conversation-compose-box-input"]'
                )].filter(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 40 &&
                           r.height > 0 &&
                           r.left > window.innerWidth * 0.25 &&
                           r.top > window.innerHeight * 0.55;
                });

                for (const el of candidatos) {
                    const editavel = el.closest('[contenteditable="true"]') || el;
                    try {
                        editavel.focus();
                        const range = document.createRange();
                        range.selectNodeContents(editavel);
                        const sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        document.execCommand('delete');
                        sel.removeAllRanges();
                    } catch {}
                    editavel.innerHTML = '';
                    editavel.textContent = '';
                    for (const filho of [...editavel.querySelectorAll('*')]) {
                        filho.innerHTML = '';
                        filho.textContent = '';
                        dispara(filho);
                    }
                    dispara(editavel);
                }
            }
            """)
        except Exception:
            pass

    def _fechar_previa_link_rascunho(self):
        try:
            self.page.evaluate("""
            () => {
                const normalizar = (txt) => String(txt || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '');

                const candidatos = [...document.querySelectorAll(
                    'footer button, footer div[role="button"], footer span[data-icon], button, div[role="button"], span[data-icon]'
                )].map(el => {
                    const clickEl = el.closest('button') || el.closest('div[role="button"]') || el;
                    const r = clickEl.getBoundingClientRect();
                    const texto = normalizar([
                        el.innerText,
                        el.textContent,
                        el.getAttribute('aria-label'),
                        el.getAttribute('title'),
                        el.getAttribute('data-testid'),
                        el.getAttribute('data-icon'),
                        el.querySelector('[data-icon]')?.getAttribute('data-icon'),
                    ].filter(Boolean).join(' '));
                    return {el: clickEl, r, texto};
                }).filter(item =>
                    item.r.width > 8 &&
                    item.r.height > 8 &&
                    item.r.left > window.innerWidth * 0.25 &&
                    item.r.top > window.innerHeight * 0.45 &&
                    (
                        item.texto.includes('x') ||
                        item.texto.includes('close') ||
                        item.texto.includes('fechar') ||
                        item.texto.includes('cancelar') ||
                        item.texto.includes('dismiss')
                    ) &&
                    !item.texto.includes('encaminhar') &&
                    !item.texto.includes('forward')
                );
                candidatos
                    .sort((a, b) => b.r.top - a.r.top)
                    .slice(0, 2)
                    .forEach(item => {
                        try { item.el.click(); } catch {}
                    });
            }
            """)
            self.page.wait_for_timeout(150)
        except Exception:
            pass

    def _composer_normal_esta_vazio(self):
        try:
            return bool(self.page.evaluate("""
            () => {
                const textoVisivel = [...document.querySelectorAll(
                    'footer div[contenteditable="true"], footer [role="textbox"], footer p.selectable-text.copyable-text, div[contenteditable="true"][role="textbox"], [data-testid="conversation-compose-box-input"]'
                )]
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.width > 40 &&
                               r.height > 0 &&
                               r.left > window.innerWidth * 0.25 &&
                               r.top > window.innerHeight * 0.55;
                    })
                    .map(el => (el.innerText || el.textContent || '')
                        .replace(/\\u200b/g, '')
                        .replace(/\\u00a0/g, ' ')
                        .trim())
                    .filter(Boolean)
                    .join(' ');
                return !textoVisivel;
            }
            """))
        except Exception:
            return False

    def _caixa_texto_esta_vazia(self, caixa):
        try:
            return bool(caixa.evaluate(
                """(el) => {
                    const texto = (el.innerText || el.textContent || '')
                        .replace(/\\u200b/g, '')
                        .replace(/\\u00a0/g, ' ')
                        .trim();
                    return !texto;
                }"""
            ))
        except Exception:
            return False

    def enviar_imagem_com_legenda(self, grupo_destino, caminho_imagem, legenda):
        if grupo_destino:
            self.abrir_grupo_destino_para_envio(grupo_destino, timeout_ms=25000)
        self.anexar_foto(caminho_imagem)
        self.aguardar_preview_midia()
        self.escrever_legenda_midia(legenda)
        self.clicar_enviar_preview_midia()

    def fechar_modal_encaminhar_se_aberto(self):
        try:
            aberto = self.page.evaluate("""
            () => {
                return [...document.querySelectorAll('[role="dialog"], div')]
                    .some(el => (el.innerText || '').includes('Encaminhar mensagem para'));
            }
            """)
            if aberto:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _menu_anexar_esta_aberto(self):
        """Confirma se o menu de anexo (Fotos/Documento/Camera/...) esta
        realmente aberto, em vez de so assumir que o clique funcionou.

        Checa varios sinais possiveis (aria-expanded, role=menu, e a
        presenca de pelo menos duas opcoes tipicas do menu de anexo de uma
        CONVERSA ABERTA, como Documento/Camera/Contato/Enquete/Adesivo/
        Evento). Exigir 2 ou mais evita falso-positivo com o painel de
        atalhos que aparece quando NENHUMA conversa esta aberta (que so
        mostra Documento/Contato/Meta AI, sem Fotos e videos).
        """
        try:
            return bool(self.page.evaluate("""
            () => {
                const expandido = [...document.querySelectorAll(
                    'button[aria-label="Anexar"], button[aria-label="Attach"], [aria-haspopup="menu"]'
                )].some(b => b.getAttribute('aria-expanded') === 'true');
                if (expandido) return true;

                const menuAberto = [...document.querySelectorAll('[role="menu"], ul[role="menu"], div[role="menu"]')]
                    .some(el => {
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    });
                if (menuAberto) return true;

                const normalizar = (txt) => String(txt || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '');

                const marcadores = ['fotos e v', 'photos', 'camera', 'câmera', 'documento', 'document', 'contato', 'contact', 'enquete', 'poll', 'adesivo', 'sticker', 'evento', 'event'];
                const encontrados = new Set();
                // Restringe a busca a elementos REALMENTE clicaveis
                // (botao/item de menu/li), nunca a texto solto de mensagens.
                // Sem essa restricao, uma oferta que mencione "documento",
                // "camera" etc. no proprio texto da mensagem gera falso
                // positivo, fazendo o bot achar que o menu abriu quando na
                // verdade nao abriu.
                for (const el of document.querySelectorAll('button, [role="button"], [role="menuitem"], li')) {
                    const r = el.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) continue;
                    const texto = normalizar(el.getAttribute('aria-label') || el.innerText || '');
                    for (const m of marcadores) {
                        if (texto.includes(m)) encontrados.add(m);
                    }
                }
                return encontrados.size >= 2;
            }
            """))
        except Exception:
            return False

    def _fechar_menu_sem_sair_da_conversa(self):
        """Fecha um menu suspenso (ex: menu de anexo aberto por engano)
        clicando numa area neutra do painel de mensagens.

        Importante: NUNCA usar Escape aqui. Quando nao ha nenhum modal
        real aberto, Escape fecha a conversa inteira e volta para a tela
        inicial do WhatsApp Web - foi exatamente isso que causou o bot
        sair do grupo de destino no meio do fluxo de anexo.

        As coordenadas do clique sao calculadas dinamicamente dentro do
        painel de mensagens (a direita da lista de conversas, abaixo do
        cabecalho e acima do rodape) para nao correr o risco de clicar
        sem querer numa conversa diferente na barra lateral.
        """
        try:
            ponto = self.page.evaluate("""
            () => {
                const painel = document.querySelector('#main') ||
                               document.querySelector('div[data-testid="conversation-panel-wrapper"]');
                if (painel) {
                    const r = painel.getBoundingClientRect();
                    return {
                        x: r.left + r.width / 2,
                        y: r.top + r.height * 0.4,
                    };
                }
                // Fallback: assume painel de mensagens ocupa a metade
                // direita da tela (a lista de conversas fica a esquerda).
                return {
                    x: window.innerWidth * 0.65,
                    y: window.innerHeight * 0.4,
                };
            }
            """)
            if ponto:
                self.page.mouse.click(ponto["x"], ponto["y"])
                self.page.wait_for_timeout(200)
        except Exception:
            pass

    def clicar_botao_anexar(self):
        """Clica no botao "Anexar" (clipe/+) da conversa e confirma que o
        menu de anexo realmente abriu antes de retornar.

        Prioriza seletores diretos e estaveis (aria-label / data-icon), que
        e exatamente como o WhatsApp Web marca esse botao hoje. So cai para
        a heuristica antiga (varrer a tela toda por pontuacao) se nenhum
        seletor direto funcionar - isso reduz muito o risco de clicar no
        elemento errado (ex: menu de figurinhas, status, etc.).

        Importante: um clique "bem sucedido" (sem excecao) nao significa
        que o menu abriu de verdade - por isso ha uma verificacao explicita
        (_menu_anexar_esta_aberto) com retentativas antes de considerar a
        acao concluida. As retentativas NUNCA usam Escape (isso fecha a
        conversa inteira se o menu ja tiver fechado sozinho) - usam apenas
        cliques normais e, se preciso, um clique numa area neutra da tela.
        """
        try:
            self.encontrar_caixa_texto_normal()
        except Exception:
            diagnostico = self.salvar_diagnostico_anexo("sem_conversa_aberta")
            raise RuntimeError(
                "Nao ha conversa aberta para anexar a imagem (a caixa de "
                f"mensagem nao foi encontrada). Diagnostico: {diagnostico}"
            )

        self.fechar_dialogos_sobrepostos()

        seletores_diretos = [
            "footer button[aria-label='Anexar']",
            "footer button[aria-label='Attach']",
            "button[aria-label='Anexar']",
            "button[aria-label='Attach']",
            "div[aria-label='Anexar']",
            "div[aria-label='Attach']",
            "span[data-icon='plus-rounded']",
            "span[data-icon='attach-menu-plus']",
            "span[data-icon='clip']",
        ]

        for tentativa in range(3):
            # Se o menu ja estiver aberto (por exemplo, de uma tentativa
            # anterior que na verdade funcionou), nao clica de novo - o
            # botao e um toggle e um segundo clique fecharia o menu.
            if self._menu_anexar_esta_aberto():
                return

            clicou = False
            for seletor in seletores_diretos:
                try:
                    # IMPORTANTE: nao checar loc.count()/is_visible() antes
                    # de clicar - essas checagens sao instantaneas e nao
                    # esperam nada. Se a conversa ainda estiver carregando
                    # (ex: historico grande, spinner na tela), o botao
                    # pode simplesmente nao existir ainda no exato momento
                    # da checagem, fazendo o bot pular esse seletor sem
                    # necessidade. O .click(timeout=X) do Playwright ja
                    # espera de verdade o elemento aparecer e ficar
                    # clicavel, entao chamamos ele diretamente.
                    self.page.locator(seletor).last.click(timeout=6000)
                    clicou = True
                    break
                except Exception:
                    continue

            if not clicou:
                try:
                    clicou = bool(self.page.evaluate("""
                    () => {
                        const btn = [...document.querySelectorAll(
                            'button[aria-label="Anexar"], button[aria-label="Attach"]'
                        )].find(b => {
                            const r = b.getBoundingClientRect();
                            return r.width > 0 && r.height > 0;
                        });
                        if (!btn) return false;
                        btn.click();
                        return true;
                    }
                    """))
                except Exception:
                    clicou = False

            # Espera mais generosa e com polling, em vez de um unico
            # cheque rapido, para reduzir falso-negativo de "menu nao
            # abriu" quando na verdade so estava demorando a renderizar.
            for _ in range(6):
                self.page.wait_for_timeout(300)
                if self._menu_anexar_esta_aberto():
                    return

        # Fallback: heuristica antiga (varre a tela por pontuacao), usada
        # somente se os seletores diretos acima nao existirem nessa versao
        # do WhatsApp Web.
        info = self.page.evaluate("""
        () => {
            const normalizar = (txt) => String(txt || '')
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g, '');

            const textoEl = (el) => normalizar([
                el.innerText,
                el.textContent,
                el.getAttribute('aria-label'),
                el.getAttribute('title'),
                el.getAttribute('data-testid'),
                el.getAttribute('data-icon'),
                el.querySelector('[data-icon]')?.getAttribute('data-icon'),
            ].filter(Boolean).join(' '));

            const banido = (texto) =>
                texto.includes('encaminhar') ||
                texto.includes('forward') ||
                texto.includes('share') ||
                texto.includes('compartilhar') ||
                texto.includes('status');

            const candidatos = [...document.querySelectorAll(
                'button, div[role="button"], span[data-icon], [data-testid], [aria-label], [title]'
            )].map(el => {
                const clickEl = el.closest('button') || el.closest('div[role="button"]') || el;
                const r = clickEl.getBoundingClientRect();
                const texto = textoEl(el) + ' ' + textoEl(clickEl);
                let pontos = 0;
                if (texto.includes('plus-rounded')) pontos += 12;
                if (texto.includes('attach-menu-plus')) pontos += 12;
                if (texto.includes('clip')) pontos += 8;
                if (texto.includes('anexar') || texto.includes('attach')) pontos += 10;
                if (texto.includes('adicionar') || texto.includes('add')) pontos += 4;
                if (banido(texto)) pontos -= 50;
                return {
                    pontos,
                    x: r.left + r.width / 2,
                    y: r.top + r.height / 2,
                    left: r.left,
                    top: r.top,
                    width: r.width,
                    height: r.height,
                    texto,
                };
            }).filter(item =>
                item.pontos >= 8 &&
                item.width > 12 &&
                item.height > 12 &&
                item.left > window.innerWidth * 0.25 &&
                item.left < window.innerWidth * 0.85 &&
                item.top > window.innerHeight * 0.70
            ).sort((a, b) => b.pontos - a.pontos || b.top - a.top || a.left - b.left);

            const item = candidatos[0];
            if (!item) return null;
            return {x: item.x, y: item.y, pontos: item.pontos, texto: item.texto};
        }
        """)
        if not info:
            diagnostico = self.salvar_diagnostico_anexo("sem_botao_anexar")
            raise RuntimeError(f"Nao achei o botao Anexar na conversa. Diagnostico: {diagnostico}")
        self.page.mouse.click(info["x"], info["y"])
        self.page.wait_for_timeout(700)

        if not self._menu_anexar_esta_aberto():
            diagnostico = self.salvar_diagnostico_anexo("menu_anexar_nao_abriu")
            raise RuntimeError(
                "Cliquei no botao Anexar, mas o menu de anexo nao abriu. "
                f"Diagnostico: {diagnostico}"
            )

    def fechar_dialogo_nativo_arquivo(self):
        """Fecha um dialogo nativo 'Abrir'/'Open' do Windows que tenha
        ficado travado por cima do navegador.

        Esse dialogo e uma janela do proprio Windows (nao faz parte do
        DOM da pagina), entao o Playwright nao consegue ve-lo nem
        fecha-lo - so a screenshot manual que o usuario mandou revelou
        que ele fica ali, parado, roubando o foco da janela do Chrome
        indefinidamente ate alguem fechar manualmente. Aqui usamos a API
        do Windows diretamente via ctypes (nenhuma dependencia extra
        necessaria, ja que e parte do sistema operacional) para procurar
        por essa janela pelo titulo e fecha-la mandando WM_CLOSE - o
        mesmo efeito de clicar no "Cancelar" ou no X dela.

        So faz sentido no Windows; em qualquer outro SO (ou se ctypes/
        user32 nao estiverem disponiveis por algum motivo) simplesmente
        nao faz nada.
        """
        if os.name != "nt":
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010
            # Titulos conhecidos do dialogo classico de selecao de
            # arquivo do Windows (varia pelo idioma do sistema).
            titulos_alvo = ("abrir", "open")

            encontradas = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def callback(hwnd, _lparam):
                tamanho = user32.GetWindowTextLengthW(hwnd)
                if tamanho == 0:
                    return True
                buffer = ctypes.create_unicode_buffer(tamanho + 1)
                user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
                titulo = (buffer.value or "").strip().lower()
                if titulo in titulos_alvo and user32.IsWindowVisible(hwnd):
                    encontradas.append(hwnd)
                return True

            user32.EnumWindows(callback, 0)

            for hwnd in encontradas:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

            return bool(encontradas)
        except Exception:
            return False

    def anexar_foto(self, caminho):
        """Anexa uma foto na conversa atual usando o fluxo real da UI.

        Ordem: primeiro tenta clicar de verdade em "Fotos e videos" (o
        mesmo caminho que um humano usa). So recorre ao truque de setar
        arquivo direto num <input type="file"> como ULTIMO recurso.

        Historico da ordem (para quem for mexer aqui de novo): ja tentamos
        varias vezes inverter essa ordem. O metodo de input direto
        (set_input_files) nunca abre dialogo nenhum, mas descobrimos que
        ele deixa o editor de midia "pela metade" - a imagem carrega, mas
        a caixa de legenda nunca e montada no DOM (nem um clique extra no
        canvas resolve isso). Ja o clique real na UI sempre produziu o
        editor completo, COM legenda, nos casos em que funcionou. O unico
        problema do clique real era travar em um dialogo nativo do SO
        quando o file chooser demorava demais - isso foi corrigido
        aumentando o timeout de espera (12s). Por isso o clique real volta
        a ser a primeira opcao.
        """
        caminho = os.path.abspath(caminho)
        if not os.path.exists(caminho):
            raise RuntimeError(f"Imagem nao existe: {caminho}")

        # Limpeza defensiva: se um dialogo nativo do Windows tiver
        # ficado travado de uma tentativa anterior (ver comentario em
        # fechar_dialogo_nativo_arquivo), ele fica roubando o foco da
        # janela indefinidamente. Fecha-lo aqui, antes de tentar
        # qualquer clique novo, evita que ele atrapalhe este anexo.
        self.fechar_dialogo_nativo_arquivo()
        self.fechar_modal_encaminhar_se_aberto()
        self.clicar_botao_anexar()

        seletores_fotos = [
            # Seletores por aria-label dentro do menu aberto - prioridade,
            # pois versoes mais novas do WhatsApp Web usam icones com
            # aria-label e sem texto visivel na tela.
            "[role='menu'] [aria-label='Fotos e vídeos']",
            "[role='menu'] [aria-label='Fotos e videos']",
            "[role='menu'] [aria-label*='Fotos e v']",
            "[role='menu'] [aria-label*='Photos']",
            "[aria-label='Fotos e vídeos']",
            "[aria-label='Fotos e videos']",
            "[aria-label*='Fotos e v']",
            "[aria-label*='Photos']",
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

        dialogo_nativo_suspeito = False

        for seletor in seletores_fotos:
            item = self.page.locator(seletor).last
            try:
                # IMPORTANTE: espera de verdade o item aparecer (nao so
                # checa count()/is_visible() instantaneamente). Se o menu
                # de anexo (ou a conversa) ainda estiver carregando, o
                # item pode nao existir ainda no exato momento de uma
                # checagem sincrona, fazendo o bot pular esse seletor sem
                # necessidade.
                item.wait_for(state="visible", timeout=6000)
            except Exception:
                continue

            try:
                with self.page.expect_file_chooser(timeout=12000) as file_chooser:
                    # SEM force=True aqui de proposito: o force pula a
                    # checagem de estabilidade do Playwright (que espera o
                    # elemento parar de se mover/animar antes de clicar).
                    # O menu de anexo tem uma pequena animacao de abertura;
                    # clicar "a forca" durante essa animacao pode acertar
                    # a posicao errada (ex: o item vizinho "Camera" em vez
                    # de "Fotos e videos", exatamente o que apareceu nos
                    # prints de diagnostico). Deixando o Playwright esperar
                    # a estabilidade normalmente evita isso.
                    item.click(timeout=6000)
                file_chooser.value.set_files(caminho)
                self.page.wait_for_timeout(2500)
                return
            except Exception:
                # O item existe e foi clicado, mas o file chooser
                # classico nunca chegou - isso indica um dialogo NATIVO
                # do SO (fora do alcance do Playwright) em vez do file
                # chooser classico. Registra o ocorrido, fecha o dialogo
                # via fechar_dialogo_nativo_arquivo (ver comentario la)
                # para nao deixa-lo travado roubando o foco da janela
                # pelo resto do ciclo, e marca a suspeita para pular a
                # segunda tentativa (que provavelmente tambem travaria
                # pelo mesmo motivo, so desperdicando mais tempo).
                self.salvar_diagnostico_anexo("possivel_dialogo_nativo_travado")
                self.fechar_dialogo_nativo_arquivo()
                dialogo_nativo_suspeito = True
                break

        # Segunda tentativa: localizar visualmente o item "Fotos e videos"
        # (cobre casos em que o texto exato mudou mas o icone/posicao
        # bate). Pulada se ja suspeitamos de um dialogo nativo travado,
        # ja que essa tentativa clicaria essencialmente no mesmo botao e
        # provavelmente travaria de novo, so desperdicando tempo.
        if not dialogo_nativo_suspeito:
            for _ in range(5):
                item_visual = self.localizar_item_fotos_anexo()
                if item_visual:
                    try:
                        with self.page.expect_file_chooser(timeout=12000) as file_chooser:
                            self.page.mouse.click(item_visual["x"], item_visual["y"])
                        file_chooser.value.set_files(caminho)
                        self.page.wait_for_timeout(2500)
                        return
                    except Exception:
                        self.salvar_diagnostico_anexo("possivel_dialogo_nativo_travado")
                        self.fechar_dialogo_nativo_arquivo()
                        break
                self.page.wait_for_timeout(400)

        # Ultimo recurso: seta o arquivo direto num input[type=file] pela
        # heuristica de "accept". So chega aqui se os cliques reais no menu
        # falharem completamente. Esse metodo tem duas fraquezas
        # conhecidas: risco de pegar um input de outra funcao, e o editor
        # resultante pode ficar sem caixa de legenda - mas nesses casos a
        # verificacao seguinte (aguardar_preview_midia) impede um envio
        # errado; na pior das hipoteses a oferta e pulada com seguranca.
        if self.tentar_upload_foto_por_input(caminho):
            return

        diagnostico = self.salvar_diagnostico_anexo("falha_fotos_videos")
        raise RuntimeError(
            "Nao achei a opcao Fotos e videos para anexar como imagem. "
            f"Diagnostico: {diagnostico}"
        )

    def tentar_upload_foto_por_input(self, caminho):
        try:
            enviado = self.page.evaluate_handle("""
            () => {
                const normalizar = (txt) => String(txt || '').toLowerCase();
                const inputs = [...document.querySelectorAll('input[type="file"]')];
                const candidatos = inputs.map((el, idx) => {
                    const accept = normalizar(el.getAttribute('accept'));
                    const aria = normalizar(el.getAttribute('aria-label'));
                    const outer = normalizar(el.outerHTML);
                    let pontos = 0;
                    // accept com imagem+video e o ideal (input classico de
                    // "Fotos e videos"), mas muitas versoes do WhatsApp Web
                    // usam um input so com accept="image/*" para esse mesmo
                    // botao - como a imagem enviada e sempre um JPG, isso e
                    // perfeitamente valido e NAO deve ser penalizado.
                    if (accept.includes('image') && accept.includes('video')) pontos += 20;
                    else if (accept.trim() === 'image/*') pontos += 15;
                    else if (accept.includes('image')) pontos += 10;
                    if (accept.includes('sticker') || outer.includes('sticker') || aria.includes('figurinha')) pontos -= 40;
                    if (accept.includes('document') && !accept.includes('image')) pontos -= 20;
                    if (aria.includes('perfil') || aria.includes('profile') || outer.includes('avatar')) pontos -= 30;
                    return {el, idx, pontos, accept, aria};
                })
                .filter(item => item.pontos >= 10)
                .sort((a, b) => b.pontos - a.pontos || b.idx - a.idx);

                return candidatos[0]?.el || null;
            }
            """)
            elemento = enviado.as_element()
            if not elemento:
                return False
            elemento.set_input_files(caminho, timeout=7000)
            self.page.wait_for_timeout(2000)

            # Um clique real na area do editor (ex: no canvas da imagem)
            # parece ser necessario para o WhatsApp terminar de montar a
            # caixa de legenda - so anexar o arquivo via set_input_files
            # (sem nenhum clique de usuario real) pode deixar o editor
            # "pela metade": imagem carregada, mas sem caixa de legenda
            # nenhuma no DOM. Um clique inofensivo no canvas nudge essa
            # montagem sem arriscar clicar em nenhum botao de acao.
            try:
                ponto = self.page.evaluate("""
                () => {
                    const canvas = document.querySelector('[data-testid="media-editor-canvas"]');
                    if (!canvas) return null;
                    const r = canvas.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) return null;
                    return {x: r.left + r.width / 2, y: r.top + r.height / 2};
                }
                """)
                if ponto:
                    self.page.mouse.click(ponto["x"], ponto["y"])
                    self.page.wait_for_timeout(800)
            except Exception:
                pass

            # Checagem final com polling, em vez de uma unica tentativa:
            # o editor de midia as vezes demora mais que meio segundo para
            # terminar de montar (legenda, canvas etc.), especialmente
            # apos um clique anterior ter falhado/demorado. Uma unica
            # checagem rapida aqui pode dar falso-negativo bem no
            # instante em que o editor estava prestes a ficar pronto.
            for _ in range(10):
                if self.preview_midia_esta_aberto():
                    return True
                self.page.wait_for_timeout(500)
            return False
        except Exception:
            return False

    def preview_midia_esta_aberto(self):
        try:
            return bool(self.page.evaluate("""
            () => {
                const visivel = (el) => {
                    const st = window.getComputedStyle(el);
                    if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity) === 0) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                const texto = (el) => [
                    el.innerText,
                    el.textContent,
                    el.getAttribute('aria-label'),
                    el.getAttribute('aria-placeholder'),
                    el.getAttribute('data-testid'),
                ].filter(Boolean).join(' ').toLowerCase();
                const temLegenda = [...document.querySelectorAll('[contenteditable="true"], [role="textbox"], p.selectable-text.copyable-text, [data-testid*="caption"]')]
                    .some(el => {
                        if (!visivel(el)) return false;
                        const r = el.getBoundingClientRect();
                        const t = texto(el);
                        const temTestidCaption = (el.getAttribute('data-testid') || '').toLowerCase().includes('caption');
                        return r.top > window.innerHeight * 0.30 &&
                               (
                                   temTestidCaption ||
                                   t.includes('legenda') ||
                                   t.includes('caption') ||
                                   t.includes('adicione uma legenda') ||
                                   t.includes('digite uma mensagem')
                               );
                    });
                const temMidiaGrande = [...document.querySelectorAll('img, video, canvas')]
                    .some(el => {
                        if (!visivel(el)) return false;
                        const r = el.getBoundingClientRect();
                        return r.width > 120 &&
                               r.height > 120 &&
                               r.left > window.innerWidth * 0.25;
                    });
                const temEditor = [...document.querySelectorAll('[role="dialog"], [data-testid], [aria-label]')]
                    .some(el => {
                        if (!visivel(el)) return false;
                        const t = texto(el);
                        return t.includes('visualizar') ||
                               t.includes('preview') ||
                               t.includes('mídia') ||
                               t.includes('midia') ||
                               t.includes('foto') ||
                               t.includes('photo');
                    });

                // NOTA: ja existiu aqui uma checagem "ehFigurinha" que
                // procurava a palavra "figurinha"/"sticker"/"adesivo" em
                // qualquer elemento visivel a direita da tela, para
                // rejeitar a tela de criacao de figurinha caso o input
                // errado fosse usado por engano. Essa abordagem foi
                // removida porque e uma luta sem fim: o WhatsApp Web tem
                // varios componentes que mencionam "figurinha" em algum
                // atributo mesmo sem estar relacionados ao anexo de foto -
                // por exemplo o botao "Figurinha" da propria barra de
                // ferramentas do editor de midia (data-testid=
                // "sticker-button") e a aba "Emojis, GIFs, figurinhas" do
                // seletor de emoji, que fica pre-montada na pagina mesmo
                // fechada. Cada um desses ja derrubou essa deteccao por
                // engano em algum momento. Nao ha necessidade real dessa
                // checagem: temLegenda ja exige uma caixa de legenda
                // (testid contendo "caption" ou texto "adicione uma
                // legenda"), e a tela de criacao de figurinha nao tem
                // caixa de legenda nenhuma - ela e distinta o suficiente
                // sem precisar de uma lista negra de palavras.

                return temLegenda && (temMidiaGrande || temEditor);
            }
            """))
        except Exception:
            return False

    def localizar_item_fotos_anexo(self):
        return self.page.evaluate("""
        () => {
            const visible = (el) => {
                if (!el) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 &&
                       r.left > window.innerWidth * 0.25 &&
                       r.left < window.innerWidth * 0.85 &&
                       r.top > window.innerHeight * 0.45;
            };

            const normalizar = (txt) => String(txt || '')
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g, '');

            const textoDe = (el) => normalizar([
                el.innerText,
                el.textContent,
                el.getAttribute('aria-label'),
                el.getAttribute('title'),
                el.getAttribute('data-testid'),
                el.querySelector('[data-icon]')?.getAttribute('data-icon'),
            ].filter(Boolean).join(' '));

            const banido = (texto) =>
                texto.includes('encaminhar') ||
                texto.includes('forward') ||
                texto.includes('share') ||
                texto.includes('compartilhar') ||
                texto.includes('status') ||
                texto.includes('camera') ||
                texto.includes('sticker') ||
                texto.includes('figurinha') ||
                texto.includes('document') ||
                texto.includes('documento');

            const score = (el) => {
                const texto = textoDe(el);

                let pontos = 0;
                if (texto.includes('attach-photo')) pontos += 14;
                if (texto.includes('fotos e videos') || texto.includes('fotos e videos')) pontos += 12;
                if (texto.includes('photos') && texto.includes('videos')) pontos += 12;
                if (texto.includes('foto') || texto.includes('photo')) pontos += 7;
                if (texto.includes('video')) pontos += 5;
                if ((texto.includes('midia') || texto.includes('media')) &&
                    (texto.includes('foto') || texto.includes('photo') || texto.includes('video') || texto.includes('attach-photo'))) {
                    pontos += 4;
                }
                if (banido(texto)) pontos -= 80;
                return pontos;
            };

            const candidatos = [...document.querySelectorAll(
                'li, button, div[role="button"], span[role="button"], [data-testid], [aria-label], [title]'
            )]
                .filter(visible)
                .map(el => {
                    const clickEl = el.closest('li') || el.closest('button') || el.closest('div[role="button"]') || el;
                    const r = clickEl.getBoundingClientRect();
                    const texto = textoDe(el) + ' ' + textoDe(clickEl);
                    return {
                        pontos: score(el) + score(clickEl),
                        x: r.left + r.width / 2,
                        y: r.top + r.height / 2,
                        top: r.top,
                        left: r.left,
                        texto,
                    };
                })
                .filter(item =>
                    item.pontos >= 12 &&
                    !banido(item.texto) &&
                    item.top > window.innerHeight * 0.45 &&
                    item.left > window.innerWidth * 0.25 &&
                    item.left < window.innerWidth * 0.85
                )
                .sort((a, b) => b.pontos - a.pontos || b.top - a.top);

            const item = candidatos[0];
            if (!item) return null;
            return {x: item.x, y: item.y, pontos: item.pontos, texto: item.texto};
        }
        """)

    def salvar_diagnostico_anexo(self, motivo):
        try:
            self.diagnostico_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = self.diagnostico_dir / f"{motivo}_{stamp}"
            screenshot = str(base.with_suffix(".png"))
            html_path = str(base.with_suffix(".html"))
            txt_path = str(base.with_suffix(".txt"))

            try:
                self.page.screenshot(path=screenshot, full_page=False)
            except Exception as erro:
                screenshot = f"falha ao salvar screenshot: {erro}"

            try:
                Path(html_path).write_text(self.page.content(), encoding="utf-8", errors="ignore")
            except Exception as erro:
                html_path = f"falha ao salvar html: {erro}"

            dados = self.coletar_estado_anexo()
            linhas = [
                f"Motivo: {motivo}",
                f"Screenshot: {screenshot}",
                f"HTML: {html_path}",
                "",
                "Inputs de arquivo encontrados:",
            ]
            for item in dados.get("inputs", []):
                linhas.append(
                    f"- accept={item.get('accept')} aria={item.get('aria')} "
                    f"visible={item.get('visible')} rect={item.get('rect')}"
                )
            linhas.append("")
            linhas.append("Candidatos visiveis no menu/tela:")
            for item in dados.get("candidatos", [])[:80]:
                linhas.append(
                    f"- score={item.get('score')} tag={item.get('tag')} "
                    f"role={item.get('role')} testid={item.get('testid')} "
                    f"aria={item.get('aria')} text={item.get('text')} rect={item.get('rect')}"
                )
            Path(txt_path).write_text("\n".join(linhas), encoding="utf-8", errors="ignore")
            return txt_path
        except Exception as erro:
            return f"falha ao gerar diagnostico: {erro}"

    def coletar_estado_anexo(self):
        try:
            return self.page.evaluate("""
            () => {
                const rect = (el) => {
                    const r = el.getBoundingClientRect();
                    return {
                        left: Math.round(r.left),
                        top: Math.round(r.top),
                        width: Math.round(r.width),
                        height: Math.round(r.height),
                    };
                };
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                const normalizar = (txt) => String(txt || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '');
                const score = (el) => {
                    const texto = normalizar([
                        el.innerText,
                        el.textContent,
                        el.getAttribute('aria-label'),
                        el.getAttribute('title'),
                        el.getAttribute('data-testid'),
                        el.getAttribute('accept'),
                        el.querySelector('[data-icon]')?.getAttribute('data-icon'),
                    ].filter(Boolean).join(' '));
                    let pontos = 0;
                    if (texto.includes('foto') || texto.includes('photo')) pontos += 5;
                    if (texto.includes('video')) pontos += 4;
                    if (texto.includes('midia') || texto.includes('media')) pontos += 3;
                    if (texto.includes('image')) pontos += 4;
                    if (texto.includes('attach-photo')) pontos += 6;
                    if (texto.includes('document') || texto.includes('documento')) pontos -= 4;
                    if (texto.includes('camera') || texto.includes('sticker') || texto.includes('figurinha')) pontos -= 5;
                    return pontos;
                };
                const inputs = [...document.querySelectorAll('input[type="file"]')].map(el => ({
                    accept: el.getAttribute('accept'),
                    aria: el.getAttribute('aria-label'),
                    visible: visible(el),
                    rect: rect(el),
                }));
                const candidatos = [...document.querySelectorAll(
                    'li, button, div[role="button"], span[role="button"], [data-testid], [aria-label], [title], input[type="file"]'
                )]
                    .filter(el => {
                        const r = el.getBoundingClientRect();
                        return r.width > 0 && r.height > 0 &&
                               r.left > window.innerWidth * 0.2 &&
                               r.top > window.innerHeight * 0.15;
                    })
                    .map(el => ({
                        tag: el.tagName,
                        role: el.getAttribute('role'),
                        testid: el.getAttribute('data-testid'),
                        aria: el.getAttribute('aria-label'),
                        title: el.getAttribute('title'),
                        accept: el.getAttribute('accept'),
                        text: String(el.innerText || el.textContent || '').trim().slice(0, 120),
                        score: score(el),
                        rect: rect(el),
                    }))
                    .sort((a, b) => b.score - a.score || b.rect.top - a.rect.top);
                return {inputs, candidatos};
            }
            """)
        except Exception as erro:
            return {"inputs": [], "candidatos": [{"text": f"falha ao coletar estado: {erro}"}]}

    def aguardar_preview_midia(self):
        # 45 tentativas x 500ms = ~22.5s. Diagnosticos mostraram o estado
        # valido (legenda + midia presentes) aparecendo bem perto do
        # limite antigo de 15s - um pouco mais de folga evita desistir
        # bem no instante em que o editor estava quase pronto.
        for _ in range(45):
            ok = self.page.evaluate("""
            () => {
                const texto = (el) => [
                    el.innerText,
                    el.textContent,
                    el.getAttribute('aria-label'),
                    el.getAttribute('aria-placeholder'),
                    el.getAttribute('data-testid'),
                ].filter(Boolean).join(' ').toLowerCase();

                const editorMidia = [...document.querySelectorAll('[data-testid="media-editor-canvas"], div[role="tab"][aria-label*="Abrir foto"], div[aria-label*="Abrir foto"], [role="dialog"], [data-testid*="media"]')]
                  .some(el => {
                    const r = el.getBoundingClientRect();
                    const t = texto(el);
                    return r.width > 40 && r.height > 40 && r.left > window.innerWidth * 0.25 &&
                           (
                             t.includes('media') ||
                             t.includes('midia') ||
                             t.includes('foto') ||
                             t.includes('photo') ||
                             t.includes('legenda') ||
                             t.includes('caption') ||
                             el.querySelector('img, video, canvas')
                           );
                  });

                // A legenda pode ser um div[contenteditable] classico OU,
                // em versoes mais novas do WhatsApp Web, um elemento com
                // data-testid contendo "caption" (ex: span[data-testid=
                // "image-caption"]), que pode ja vir preenchido com o
                // texto real (nao so o placeholder "Adicione uma legenda").
                // Por isso o testid sozinho ja e evidencia suficiente,
                // sem exigir que o texto bata com um placeholder especifico.
                const caption = [...document.querySelectorAll(
                    'div[contenteditable="true"][role="textbox"], div[contenteditable="true"], [role="textbox"], p.selectable-text.copyable-text, [data-testid*="caption"]'
                )]
                  .map(el => {
                    const r = el.getBoundingClientRect();
                    const t = texto(el);
                    const dentroFooter = !!el.closest('footer');
                    const temTestidCaption = (el.getAttribute('data-testid') || '').toLowerCase().includes('caption');
                    return {r, t, dentroFooter, temTestidCaption};
                  })
                  .some(x =>
                    x.r.width > 120 &&
                    x.r.height > 8 &&
                    x.r.left > window.innerWidth * 0.25 &&
                    x.r.top > window.innerHeight * 0.30 &&
                    !x.t.includes('para o grupo') &&
                    (
                      x.temTestidCaption ||
                      !x.dentroFooter ||
                      x.t.includes('legenda') ||
                      x.t.includes('caption') ||
                      x.t.includes('adicione uma legenda')
                    )
                  );

                // A imagem em preview tambem pode nao ser um <img>/<video>
                // puro - versoes mais novas costumam desenhar a foto num
                // <canvas> (editor de midia) ou num container com
                // data-testid especifico (media-editor-canvas,
                // media-url-provider, image-thumb). Aceita qualquer um
                // desses, alem de img/video, desde que grande o bastante.
                const blobImg = [...document.querySelectorAll(
                    'img, video, canvas, [data-testid="media-editor-canvas"], [data-testid="media-url-provider"], [data-testid="image-thumb"]'
                )].some(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 120 && r.height > 120 &&
                           r.left > window.innerWidth * 0.25 &&
                           r.top < window.innerHeight * 0.75;
                });

                // NOTA: a checagem "ehFigurinha" que existia aqui (lista
                // negra de qualquer elemento visivel a direita da tela
                // contendo "figurinha"/"sticker"/"adesivo") foi removida.
                // Ela pegava, alem do botao real "Figurinha" da barra de
                // ferramentas do editor de midia (data-testid=
                // "sticker-button"), TAMBEM a aba "Emojis, GIFs,
                // figurinhas" do seletor de emoji, que fica pre-montada na
                // pagina mesmo fechada - e possivelmente outros
                // componentes que ainda vamos descobrir. Excluir cada um
                // individualmente e uma luta sem fim. A checagem nao e
                // necessaria: "caption" ja exige uma caixa de legenda
                // real (testid contendo "caption" ou o texto "adicione
                // uma legenda"), e a tela de criacao de figurinha nao tem
                // caixa de legenda nenhuma - entao ela nunca vai passar
                // nessa condicao de qualquer forma.

                return editorMidia && caption && blobImg;
            }
            """)
            if ok:
                return True
            self.page.wait_for_timeout(500)
        diagnostico = self.salvar_diagnostico_anexo("falha_preview_midia")
        raise RuntimeError(f"Preview da imagem com legenda nao foi detectado. Diagnostico: {diagnostico}")

    def escrever_legenda_midia(self, legenda):
        handle = self.page.evaluate_handle("""
        () => {
            const texto = (el) => [
                el.innerText,
                el.textContent,
                el.getAttribute('aria-label'),
                el.getAttribute('aria-placeholder'),
                el.getAttribute('data-testid'),
            ].filter(Boolean).join(' ').toLowerCase();

            const editorMidia = [...document.querySelectorAll('[data-testid="media-editor-canvas"], div[role="tab"][aria-label*="Abrir foto"], div[aria-label*="Abrir foto"], [role="dialog"], [data-testid*="media"]')]
              .some(el => {
                const r = el.getBoundingClientRect();
                const t = texto(el);
                return r.width > 40 && r.height > 40 && r.left > window.innerWidth * 0.25 &&
                       (
                         t.includes('media') ||
                         t.includes('midia') ||
                         t.includes('foto') ||
                         t.includes('photo') ||
                         t.includes('legenda') ||
                         t.includes('caption') ||
                         el.querySelector('img, video, canvas')
                       );
              });
            if (!editorMidia) return null;

            const candidatos = [...document.querySelectorAll(
                'div[contenteditable="true"][role="textbox"], div[contenteditable="true"], [role="textbox"], p.selectable-text.copyable-text, [data-testid*="caption"]'
            )]
              .map(el => {
                const r = el.getBoundingClientRect();
                const t = texto(el);
                const dentroFooter = !!el.closest('footer');
                // Se o elemento encontrado tiver um ancestral contenteditable
                // (caso comum: um <span data-testid="image-caption"> dentro
                // de um wrapper editavel), escreve nesse ancestral editavel.
                // Caso contrario, escreve no proprio elemento encontrado -
                // necessario porque em algumas versoes do WhatsApp o
                // elemento com data-testid="image-caption" E o proprio
                // campo editavel (nao tem um contenteditable pai separado).
                const ancestralEditavel = el.closest('[contenteditable="true"]');
                const editavel = ancestralEditavel || el;
                return {el: editavel, r, texto: t, dentroFooter};
              })
              .filter(x =>
                x.r.width > 120 &&
                x.r.height > 8 &&
                x.r.left > window.innerWidth * 0.25 &&
                x.r.top > window.innerHeight * 0.30 &&
                !x.texto.includes('para o grupo')
              );

            const caption = candidatos.find(x =>
                x.texto.includes('media-caption') ||
                x.texto.includes('image-caption') ||
                x.texto.includes('legenda') ||
                x.texto.includes('caption') ||
                x.texto.includes('adicione uma legenda')
            );
            if (caption) return caption.el;

            const foraFooter = candidatos
                .filter(x => !x.dentroFooter)
                .sort((a, b) => b.r.top - a.r.top);
            if (foraFooter[0]) return foraFooter[0].el;

            const generico = candidatos.sort((a, b) => b.r.top - a.r.top)[0];
            return generico?.el || null;
        }
        """)
        elemento = handle.as_element()
        if not elemento:
            diagnostico = self.salvar_diagnostico_anexo("falha_caixa_legenda")
            raise RuntimeError(f"Nao achei a caixa de legenda da imagem. Diagnostico: {diagnostico}")

        # Usa apenas interacoes nativas de teclado (clique + Ctrl+A + Delete
        # + digitar), como um usuario real faria. O select-all/delete aqui
        # e defensivo: se o WhatsApp "herdou" algum texto que estava na
        # caixa de mensagem antes de anexar a imagem, isso garante que a
        # legenda final seja so o texto novo, sem duplicar.
        elemento.click(force=True)
        self.page.wait_for_timeout(150)
        self.page.keyboard.press("Control+A")
        self.page.wait_for_timeout(80)
        self.page.keyboard.press("Delete")
        self.page.wait_for_timeout(150)
        self.page.keyboard.insert_text(legenda)
        self.page.wait_for_timeout(700)

        # Verificacao final: confere se a legenda ficou exatamente igual ao
        # texto esperado (sem duplicacao). Se nao ficou, tenta corrigir mais
        # uma vez antes de seguir para o envio.
        try:
            texto_atual = (elemento.inner_text() or "").strip()
            esperado = (legenda or "").strip()
            if texto_atual and esperado and texto_atual != esperado:
                elemento.click(force=True)
                self.page.keyboard.press("Control+A")
                self.page.wait_for_timeout(80)
                self.page.keyboard.press("Delete")
                self.page.wait_for_timeout(150)
                self.page.keyboard.insert_text(legenda)
                self.page.wait_for_timeout(700)
        except Exception:
            pass

    def clicar_enviar_preview_midia(self):
        info = self.page.evaluate("""
        () => {
            const cand = [...document.querySelectorAll('button, div[role="button"], span[data-icon="send"], span[data-icon="send-filled"]')]
              .map(el => {
                const icon = el.getAttribute('data-icon') || '';
                const aria = el.getAttribute('aria-label') || '';
                const text = (el.innerText || el.textContent || '').trim();
                const isSend = icon.includes('send') || aria.toLowerCase().includes('enviar') || aria.toLowerCase().includes('send') || text === 'send' || text === 'Enviar';
                const clickEl = el.closest('button') || el.closest('div[role="button"]') || el;
                const r = clickEl.getBoundingClientRect();
                return {
                  isSend,
                  x: r.left + r.width/2,
                  y: r.top + r.height/2,
                  left: r.left,
                  top: r.top,
                  w: r.width,
                  h: r.height,
                  visible: r.width > 0 && r.height > 0
                };
              })
              .filter(x => x.isSend && x.visible && x.left > window.innerWidth * 0.25);

            cand.sort((a,b) => (b.top - a.top) || (b.left - a.left));
            return cand[0] || null;
        }
        """)
        if info:
            self.page.mouse.click(info["x"], info["y"])
        else:
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(3000)