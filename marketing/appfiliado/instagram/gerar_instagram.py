"""Posts do feed (carrosséis 1080x1080, 1:1) e stories dos destaques (1080x1920) do Instagram do Appfiliado.

Uso (na raiz do repositório): python3 marketing/appfiliado/instagram/gerar_instagram.py [nome-do-post ...]
Sai em marketing/appfiliado/instagram/feed/<post>/NN.jpg, destaques/<destaque>/NN.jpg e uma folha de
contato (previa-<post>.jpg) para conferir tudo de uma vez. As legendas ficam em legendas.md.

Cores e símbolo da identidade (marketing/appfiliado/gerar_identidade.py), fonte DM Sans; as telas são os
prints do painel com a conta fictícia "Achadinhos da Bia" (landing/static/landing/prints/*-m.webp).
Regras de texto em VOZ.md (pra/pro, vírgulas).

Limites conferidos a cada slide (o script avisa se algo sair deles):
- feed: texto a 40 px ou mais das bordas, fonte de 26 px ou mais; na capa, o texto fica nos 810 px do meio
  porque a grade do perfil mostra os posts em 3:4 e corta as laterais de um post quadrado;
- stories: nada de texto nos 250 px de cima (barra de progresso e nome) nem nos 250 px de baixo (campo de
  resposta), e 60 px ou mais das laterais."""

import base64
import html
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
PRINTS = RAIZ / "landing" / "static" / "landing" / "prints"
FONTES = AQUI.parent / "identidade" / "fontes"
E = html.escape

VERDE, VERDE_2, VERDE_3, CREME, AMARELO, TINTA, SUAVE = "#1F3A2E", "#2D4B3D", "#17301F", "#F6F3EA", "#F2C230", "#1D2A23", "#AFC1B5"
SIMBOLO = ('<svg viewBox="3 8.25 36 36"><g fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round">'
           '<circle cx="21" cy="26" r="9.5"/><path d="M30.5 16.5V36"/></g><circle cx="21" cy="26" r="3.6" fill="currentColor"/></svg>')
ICONES = {
    "bot": "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z",
    "site": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "carrosseis": "M7 5h10v14H7zM3 7v10M21 7v10",
    "notas": "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
    "radar": "M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4",
    "conversor": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "resultados": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "chave": "M15 7a4 4 0 1 1-3.9 4.9L4 19v2h3v-2h2v-2h2l1.1-1.1A4 4 0 0 1 15 7zM16 9.5h.01",
    "duvidas": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01",
    "planos": "M4 7h16v12H4zM4 11h16M8 15h3",
    "sobre": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5h.01",
}


def _fonte(arquivo):
    return base64.b64encode((FONTES / arquivo).read_bytes()).decode()


def _print(nome):
    caminho = PRINTS / f"{nome}-m.webp"
    with Image.open(caminho) as im:
        largura, altura = im.size
    return f"data:image/webp;base64,{base64.b64encode(caminho.read_bytes()).decode()}", largura, altura


CSS = f"""
@font-face {{ font-family: DM; font-weight: 500; src: url(data:font/ttf;base64,{_fonte('dmsans-500.ttf')}); }}
@font-face {{ font-family: DM; font-weight: 800; src: url(data:font/ttf;base64,{_fonte('dmsans-800.ttf')}); }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: DM, sans-serif; font-weight: 500; color: {TINTA}; }}
.slide {{ width: var(--w); height: var(--h); position: relative; overflow: hidden; display: flex; flex-direction: column;
  padding: 72px var(--px, 84px) 64px; background: {CREME}; }}
.slide.capa {{ --px: 200px; }}  /* grade 3:4 mostra só os 810 px do meio: 135 px cortados + 65 px de margem */
.slide.capa h1 {{ font-size: 74px; }}
.slide.verde {{ background: radial-gradient(120% 90% at 88% 6%, {VERDE_2} 0%, {VERDE} 46%, {VERDE_3} 100%); color: {CREME}; }}
.slide.amarelo {{ background: {AMARELO}; }}
.marca {{ display: flex; align-items: center; gap: 16px; font-weight: 800; font-size: 34px; letter-spacing: -.01em; }}
.marca .ic {{ width: 64px; height: 64px; border-radius: 18px; background: {AMARELO}; color: {VERDE}; display: grid; place-items: center; }}
.marca .ic svg {{ width: 46px; height: 46px; }}
.verde .marca {{ color: {CREME}; }}
.chapeu {{ font-size: 26px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: #8A6A00; }}
.verde .chapeu {{ color: {AMARELO}; }}
h1 {{ font-weight: 800; letter-spacing: -.03em; line-height: 1.03; font-size: 80px; margin-top: 20px; }}
h1.menor {{ font-size: 66px; line-height: 1.07; }}
h1 em, h2 em {{ font-style: normal; background: linear-gradient(transparent 58%, {AMARELO} 58%, {AMARELO} 92%, transparent 92%); }}
.verde h1 em, .verde h2 em {{ background: none; color: {AMARELO}; }}
h2 {{ font-weight: 800; letter-spacing: -.025em; line-height: 1.07; font-size: 54px; margin-top: 16px; }}
.texto {{ font-size: 32px; line-height: 1.36; color: #4E5C53; margin-top: 22px; max-width: 900px; }}
.verde .texto {{ color: {SUAVE}; }}
.rodape {{ margin-top: auto; display: flex; align-items: center; justify-content: space-between; font-size: 28px; font-weight: 800; }}
.rodape .pagina {{ opacity: .55; }}
.seta {{ display: inline-flex; align-items: center; gap: 12px; }}
.selo {{ display: inline-flex; align-items: center; gap: 12px; background: {AMARELO}; color: {VERDE}; font-weight: 800;
  border-radius: 999px; padding: 18px 34px; font-size: 32px; }}
.selo.claro {{ background: rgba(246,243,234,.12); color: {CREME}; border: 2px solid rgba(246,243,234,.25); }}
.icone-grande {{ width: 150px; height: 150px; border-radius: 40px; background: {VERDE}; color: {AMARELO}; display: grid; place-items: center; }}
.verde .icone-grande {{ background: rgba(246,243,234,.10); border: 3px solid rgba(246,243,234,.16); }}
.icone-grande svg {{ width: 86px; height: 86px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }}
/* celular com a tela do painel */
.celular {{ position: relative; flex: none; margin: 40px auto 0; width: var(--cw); background: #101a14; border-radius: 64px;
  padding: 18px; box-shadow: 0 40px 90px rgba(23,48,31,.28), 0 0 0 3px rgba(23,48,31,.12); }}
.celular .tela {{ border-radius: 48px; overflow: hidden; background: #F6F3EA; padding-top: 78px; }}
.celular .tela div {{ height: 100%; background-repeat: no-repeat; background-size: 100% auto; }}
.celular::before {{ content: ""; position: absolute; top: 34px; left: 50%; width: 120px; height: 30px; margin-left: -60px; border-radius: 20px; background: #101a14; z-index: 2; }}
.lista {{ list-style: none; display: grid; gap: 16px; margin: auto 0; padding-top: 28px; }}
.lista li {{ display: flex; gap: 24px; align-items: flex-start; background: #fff; border: 2px solid #E6DFC9; border-radius: 28px; padding: 22px 30px; }}
.verde .lista li {{ background: rgba(246,243,234,.07); border-color: rgba(246,243,234,.14); }}
.lista .n {{ flex: none; width: 56px; height: 56px; border-radius: 50%; background: {AMARELO}; color: {VERDE}; font-weight: 800; font-size: 30px; display: grid; place-items: center; }}
.lista .ok {{ flex: none; width: 52px; height: 52px; border-radius: 50%; background: {VERDE}; display: grid; place-items: center; margin-top: 4px; }}
.verde .lista .ok {{ background: {AMARELO}; }}
.lista .ok svg {{ width: 30px; height: 30px; fill: none; stroke: {AMARELO}; stroke-width: 3.2; stroke-linecap: round; stroke-linejoin: round; }}
.verde .lista .ok svg {{ stroke: {VERDE}; }}
.lista b {{ display: block; font-size: 36px; font-weight: 800; letter-spacing: -.01em; line-height: 1.15; }}
.lista div > span {{ display: block; font-size: 29px; line-height: 1.32; color: #5B675F; margin-top: 6px; }}
.verde .lista div > span {{ color: {SUAVE}; }}
.premium {{ font-style: normal; display: inline-block; font-size: 26px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; background: {VERDE};
  color: {AMARELO}; border-radius: 999px; padding: 6px 16px; margin-left: 12px; vertical-align: 6px; }}
.numeros {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: auto 0; }}
.numeros div {{ background: #fff; border: 2px solid #E6DFC9; border-radius: 28px; padding: 30px; }}
.verde .numeros div {{ background: rgba(246,243,234,.07); border-color: rgba(246,243,234,.14); }}
.numeros b {{ display: block; font-size: 60px; font-weight: 800; letter-spacing: -.03em; line-height: 1; }}
.verde .numeros b {{ color: {AMARELO}; }}
.numeros span {{ display: block; font-size: 29px; color: #5B675F; margin-top: 12px; line-height: 1.3; }}
.verde .numeros span {{ color: {SUAVE}; }}
.precos {{ display: grid; gap: 12px; margin-top: 30px; }}
.precos div {{ display: flex; justify-content: space-between; align-items: baseline; gap: 20px; background: rgba(246,243,234,.07);
  border: 2px solid rgba(246,243,234,.14); border-radius: 24px; padding: 16px 30px; font-size: 32px; }}
.precos b {{ color: {AMARELO}; font-size: 36px; font-weight: 800; white-space: nowrap; }}
.precos small {{ font-size: 26px; color: {SUAVE}; }}
.balao {{ background: #fff; border-radius: 30px 30px 30px 8px; padding: 28px 32px; font-size: 32px; line-height: 1.38; box-shadow: 0 16px 40px rgba(23,48,31,.10);
  max-width: 820px; }}
.balao.meu {{ background: #DCF8C6; border-radius: 30px 30px 8px 30px; margin-left: auto; }}
/* listas curtas no feed: letras maiores para ocupar o quadrado */
.lista.folgada {{ gap: 20px; }}
.lista.folgada li {{ padding: 30px 34px; }}
.lista.folgada b {{ font-size: 40px; }}
.lista.folgada div > span {{ font-size: 31px; }}
/* stories: os tamanhos maiores, longe das faixas que o Instagram cobre (o slide é desenhado em 864x1536 e
   ampliado 1,25x: 200 px aqui = 250 px na imagem) */
.story .slide {{ justify-content: center; padding: 200px 56px; }}
.story .slide.capa {{ --px: 56px; }}
.story .capa-texto {{ margin: auto 0 !important; padding-bottom: 60px; }}
.story .slide.capa h1 {{ font-size: 112px; line-height: 1.02; }}
.story .slide.capa .texto {{ font-size: 38px; }}
.story h1 {{ font-size: 92px; }}
.story h1.menor {{ font-size: 72px; }}
.story h2 {{ font-size: 62px; }}
.story .texto {{ font-size: 35px; }}
.story .lista {{ gap: 22px; padding-top: 36px; }}
.story .lista li {{ padding: 32px 34px; border-radius: 32px; }}
.story .lista b {{ font-size: 40px; }}
.story .lista div > span {{ font-size: 31px; }}
.story .numeros {{ margin-top: 48px; }}
.story .numeros b {{ font-size: 66px; }}
.story .precos {{ gap: 16px; margin-top: 40px; }}
.story .precos div {{ padding: 24px 32px; font-size: 33px; }}
.story .precos b {{ font-size: 39px; }}
.story .slide.com-tela {{ justify-content: flex-start; }}
.story .rodape, .story .contador {{ display: none; }}
.story .lista {{ margin: 0; }}
.circulo-fundo {{ position: absolute; border-radius: 50%; border: 3px solid rgba(246,243,234,.10); }}
"""


def _pagina(slide_html: str, largura: int, altura: int) -> str:
    slide_html = slide_html.replace("e-mail", "e&#8209;mail")  # sem quebrar linha no hífen
    slide_html = slide_html.replace("R$ ", "R$&nbsp;")  # o "R$" não fica sozinho no fim da linha
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>:root{{--w:{largura}px;--h:{altura}px}}{CSS}</style></head>"
            f"<body class='{"story" if STORY["ativo"] else ""}'>{slide_html}</body></html>")


def _icone(nome, extra=""):
    return f'<div class="icone-grande" {extra}><svg viewBox="0 0 24 24"><path d="{ICONES[nome]}"/></svg></div>'


def _marca():
    return f'<div class="marca"><span class="ic">{SIMBOLO}</span>Appfiliado</div>'


STORY = {"ativo": False}


def _rodape(i, total, seta=True, texto=""):
    if STORY["ativo"]:
        return '<div class="rodape"></div>'
    direita = '<span class="seta">Arraste <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>' if seta else texto
    return f'<div class="rodape"><span class="pagina">{i}/{total}</span>{direita}</div>'


# --- tipos de slide ------------------------------------------------------------------------------
# Cada função devolve o HTML do slide; `i`/`total` entram no rodapé.

def capa(chapeu, titulo, texto="", icone=None, verde=True):
    def montar(i, total, w, h):
        topo = f'<div style="display:flex;justify-content:space-between;align-items:flex-start">{_marca()}{_icone(icone) if icone else ""}</div>'
        enfeite = ('<div class="circulo-fundo" style="width:900px;height:900px;right:-380px;bottom:-360px"></div>'
                   '<div class="circulo-fundo" style="width:560px;height:560px;right:-200px;bottom:-180px"></div>') if verde else ""
        return (f'<section class="slide capa{" verde" if verde else ""}">{enfeite}{topo}<div class="capa-texto" style="margin-top:auto;position:relative">'
                f'<p class="chapeu">{E(chapeu)}</p><h1>{titulo}</h1>{f"<p class=texto>{texto}</p>" if texto else ""}</div>'
                f'<div style="height:70px"></div>{_rodape(i, total)}</section>')
    return montar


def tela(chapeu, titulo, texto, imagem, recorte=0, verde=False):
    """Título em cima e o celular com o print logo abaixo, saindo pela borda de baixo."""
    def montar(i, total, w, h):
        dados, lw, _ = _print(imagem)
        largura_celular = 640 if STORY["ativo"] else 620
        escala = (largura_celular - 36) / lw
        return (f'<section class="slide com-tela{" verde" if verde else ""}"><div style="display:flex;justify-content:space-between;align-items:center">'
                f'<p class="chapeu">{E(chapeu)}</p><span class="chapeu contador" style="color:inherit;opacity:.45;letter-spacing:.04em">{i}/{total} →</span></div><h2>{titulo}</h2>'
                f'<p class="texto">{texto}</p>'
                f'<div class="celular" style="--cw:{largura_celular}px">'
                f'<div class="tela" style="height:{h}px"><div style="background-image:url({dados});background-position:0 -{recorte * escala:.0f}px"></div></div></div>'
                f'</section>')
    return montar


def lista(chapeu, titulo, itens, numerada=False, verde=False, texto=""):
    """itens: [(titulo, texto, premium?)]"""
    def montar(i, total, w, h):
        lis = ""
        for k, item in enumerate(itens, 1):
            nome, desc = item[0], item[1]
            premium = '<em class="premium">Premium</em>' if len(item) > 2 and item[2] else ""
            marca = f'<span class="n">{k}</span>' if numerada else '<span class="ok"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>'
            lis += f"<li>{marca}<div><b>{nome}{premium}</b>{f'<span>{desc}</span>' if desc else ''}</div></li>"
        return (f'<section class="slide{" verde" if verde else ""}"><p class="chapeu">{E(chapeu)}</p><h2>{titulo}</h2>'
                f'{f"<p class=texto>{texto}</p>" if texto else ""}'
                f'<ul class="lista{" folgada" if len(itens) <= 4 else ""}">{lis}</ul><div style="height:50px"></div>{_rodape(i, total)}</section>')
    return montar


def numeros(chapeu, titulo, pares, verde=True):
    def montar(i, total, w, h):
        cel = "".join(f"<div><b>{E(a)}</b><span>{E(b)}</span></div>" for a, b in pares)
        return (f'<section class="slide{" verde" if verde else ""}"><p class="chapeu">{E(chapeu)}</p><h2>{titulo}</h2>'
                f'<div class="numeros">{cel}</div><div style="height:40px"></div>{_rodape(i, total)}</section>')
    return montar


def precos(chapeu, titulo, linhas, nota=""):
    """linhas: [(nome, preço, detalhe)]"""
    def montar(i, total, w, h):
        cel = "".join(f"<div><span>{E(n)}{f'<br><small>{E(d)}</small>' if d else ''}</span><b>{E(p)}</b></div>" for n, p, d in linhas)
        return (f'<section class="slide verde"><p class="chapeu">{E(chapeu)}</p><h2>{titulo}</h2><div class="precos">{cel}</div>'
                f'{f"<p class=texto style=font-size:29px;margin-top:24px>{nota}</p>" if nota else ""}'
                f'<div style="height:40px"></div>{_rodape(i, total)}</section>')
    return montar


def cta(titulo, texto, botao="Link na bio"):
    def montar(i, total, w, h):
        return (f'<section class="slide verde"><div class="circulo-fundo" style="width:1000px;height:1000px;left:-420px;top:-420px"></div>'
                f'{_marca()}<div style="margin:auto 0;position:relative"><h1 class="menor">{titulo}</h1><p class="texto">{texto}</p>'
                f'<div style="display:flex;gap:18px;margin-top:46px;flex-wrap:wrap"><span class="selo">{E(botao)} ↗</span>'
                f'<span class="selo claro">appfiliado.com.br</span></div></div>{_rodape(i, total, seta=False, texto="Salve para ver depois")}</section>')
    return montar


def conversa(chapeu, titulo, baloes, verde=False):
    """Um pedaço de conversa de WhatsApp (baloes: [(texto, meu?)])."""
    def montar(i, total, w, h):
        b = "".join(f'<div class="balao{" meu" if meu else ""}">{t}</div>' for t, meu in baloes)
        return (f'<section class="slide{" verde" if verde else ""}" style="background:#E9E2D3"><p class="chapeu">{E(chapeu)}</p><h2>{titulo}</h2>'
                f'<div style="display:grid;gap:22px;margin-top:46px">{b}</div><div style="height:40px"></div>{_rodape(i, total)}</section>')
    return montar


# --- conteúdo ---------------------------------------------------------------------------------------
# Ordem de publicação: do 1 ao 9 (o 9 fica no topo do perfil). No grid, o 1 (apresentação) acaba no
# canto de baixo à direita; por isso a apresentação é republicada fixada (ver legendas.md).

PRECO_MIN = "R$ 19,90"
FEED = {
    "01-apresentacao": [
        capa("Para afiliados da Shopee", "Tudo que você usa para divulgar <em>num painel só.</em>",
             "Ofertas no automático, link na bio, carrosséis, resultados e notas fiscais."),
        tela("Bot de WhatsApp", "Ofertas no automático nos seus grupos", "Ele escolhe as ofertas, gera o seu link e publica no ritmo que você definir.", "bot-ofertas", 0),
        tela("Meu site", "Seu link na bio com vitrine e conversor", "Uma página em seunome.appfiliado.com.br com botões, redes e ofertas.", "site-editor", 0),
        tela("Gerador de carrosséis", "Cole um link e receba um carrossel pronto", "A IA escreve os slides, a legenda e as hashtags. Você ajusta e baixa.", "carrossel-editor", 0),
        tela("Incluído em todos os planos", "Radar, Conversor e Resultados", "Ache o produto certo, troque links pelo seu e veja quanto cada divulgação vendeu.", "radar-produtos", 0),
        tela("Emissor NFS-e", "As notas dos vendedores direto do relatório da Shopee", "Para afiliado pessoa jurídica: uma nota por loja, com e-mail para cada vendedor.", "notas-lote", 0),
        cta("Comece hoje a partir de <span style='color:#F2C230'>" + PRECO_MIN + "/mês.</span>",
            "Monte o seu combo e pague menos. 7 dias de garantia e cancelamento quando quiser."),
    ],
    "02-api-da-shopee": [
        capa("Antes de começar", "Libere a <em>API da Shopee</em> na sua conta de afiliado.",
             "É ela que gera o seu link e traz os seus números. O pedido é feito direto à Shopee.", icone="chave"),
        lista("Passo a passo", "Como pedir a API", [
            ("Tenha o cadastro de afiliado aprovado", "No Programa de Afiliados da Shopee."),
            ("Envie o formulário de ajuda da Shopee", "Escolha o cenário \"Quero ativar a API\"."),
            ("Aguarde a análise", "A Shopee tem até 5 dias úteis para responder."),
            ("Clique em Aplicar", "Na página Open API do portal de afiliados."),
            ("Cole o AppID e o Secret no Appfiliado", "Em Configurações do painel. Pronto!"),
        ], numerada=True),
        lista("No formulário", "Como preencher", [
            ("Já é afiliado da Shopee?", "Sim"),
            ("Problema de login ou conta?", "Não, estou com outras dificuldades / dúvidas"),
            ("ID de afiliado e telefone", "Os mesmos do seu cadastro no Programa de Afiliados"),
            ("Tema", "Tenho dúvidas/ dificuldades com meu cadastro / conta"),
            ("Cenário", "Quero ativar a API"),
        ]),
        lista("Dica de ouro", "Não espere o e-mail", [
            ("Olhe todo dia a página Open API", "affiliate.shopee.com.br/open_api"),
            ("Apareceu o botão Aplicar?", "A API foi liberada: clique e a Shopee cria o AppID e o Secret."),
            ("Guarde o Secret com cuidado", "No Appfiliado ele fica criptografado e nunca aparece de novo."),
        ], verde=True),
        cta("Com a API liberada, <span style='color:#F2C230'>é só conectar e usar.</span>",
            "O link do formulário e o passo a passo também estão no site e no painel."),
    ],
    "03-bot-de-whatsapp": [
        capa("Bot de WhatsApp", "Seus grupos com <em>ofertas no automático.</em>", "Sem instalar nada e sem deixar o computador ligado.", icone="bot"),
        tela("Conexão", "Conecte pelo QR Code em minutos", "O servidor fica conectado como mais um aparelho e volta sozinho se a conexão cair.", "bot-conexao", 120),
        tela("Automação", "Você decide o que, quando e quanto", "Busca por palavra-chave, loja ou categoria, filtros, horários e intervalo entre as ofertas.", "bot-ofertas", 470),
        tela("Modo campanha", "Datas da Shopee no piloto automático", "No 11.11 e na Black Friday o bot muda o ritmo, o texto e o cupom sozinho.", "bot-campanhas", 380),
        tela("Alerta de preço", "Avisa quando o produto baixa", "Escolha os produtos e receba o aviso no e-mail ou direto nos grupos.", "bot-alerta", 380),
        lista("Só no Premium", "Recursos que fazem diferença", [
            ("Copia ofertas de outros grupos", "E troca pelo seu link de afiliado.", True),
            ("Revisão do texto com IA", "Mensagens mais caprichadas, sem você reescrever.", True),
            ("Até 50 grupos e 300 ofertas por dia", "Em cada grupo ou canal.", True),
        ]),
        cta("Bot de WhatsApp a partir de <span style='color:#F2C230'>R$ 49,90/mês.</span>", "Comece com o modo simulação: ele faz tudo sem enviar nada."),
    ],
    "04-meu-site": [
        capa("Meu site", "Um link na bio que <em>vende por você.</em>", "seunome.appfiliado.com.br com botões, redes, vitrine e conversor.", icone="site"),
        tela("Do seu jeito", "Nome, foto, cores e botões", "Veja a prévia ao vivo enquanto edita e publique quando estiver bom.", "site-editor", 0),
        tela("Botões de link", "Seus links com os cliques de cada um", "Organize como quiser e veja quantos cliques cada botão recebeu.", "site-botoes", 0),
        lista("Na sua página", "O que o visitante encontra", [
            ("Vitrine de ofertas", "As ofertas do bot ou uma busca na Shopee, com o seu link."),
            ("Conversor de links", "O visitante cola o link e compra pelo seu link de afiliado."),
            ("Suas redes sociais", "Instagram, TikTok, YouTube, WhatsApp e mais."),
        ]),
        cta("Meu site a partir de <span style='color:#F2C230'>R$ 22,90/mês.</span>", "No Premium: mais botões, produtos escolhidos por você e sem a assinatura do Appfiliado."),
    ],
    "05-gerador-de-carrosseis": [
        capa("Gerador de carrosséis", "Cole um link da Shopee. <em>O carrossel sai pronto.</em>", "Roteiro, legenda e hashtags escritos por IA.", icone="carrosseis"),
        tela("Editor", "Ajuste tudo antes de baixar", "Textos, modelos, cores e slides. O preço vem sempre certo da Shopee.", "carrossel-editor", 0),
        numeros("Em números", "Feito pro Instagram", [("10", "modelos de carrossel"), ("2 a 10", "slides por carrossel"),
                                                        ("1080×1350", "PNG no formato do feed"), ("3 a 10", "carrosséis por dia")]),
        lista("Só no Premium", "Para quem posta todo dia", [
            ("Foto própria com remoção de fundo", "", True), ("Cores e fontes livres", "", True), ("Outra versão do texto com IA", "", True),
        ]),
        cta("Carrosséis a partir de <span style='color:#F2C230'>R$ 19,90/mês.</span>", "Cada carrossel já sai com o seu link de afiliado e o Sub ID \"instagram\"."),
    ],
    "06-radar-de-ofertas": [
        capa("Radar de ofertas", "Ache o produto certo <em>em segundos.</em>", "Incluído em todos os planos.", icone="radar"),
        tela("Catálogo", "Mais de 30 mil produtos com comissão", "Filtre por comissão, desconto, preço e categoria. Atualizado todo dia.", "radar-produtos", 0),
        lista("Num clique", "O que fazer com o produto", [
            ("Copiar o seu link de afiliado", ""), ("Mandar no grupo", "Com o Bot de WhatsApp."),
            ("Acompanhar o preço", "Com o alerta de preço do bot."), ("Gerar um carrossel", "Com o Gerador de carrosséis."),
        ]),
        cta("O Radar vem em <span style='color:#F2C230'>todos os planos.</span>", "Escolha um módulo e ele já está no seu painel."),
    ],
    "07-conversor-de-links": [
        capa("Conversor de links", "Troque os links de qualquer texto <em>pelo seu.</em>", "Incluído em todos os planos.", icone="conversor"),
        tela("Como funciona", "Cole, converta e encaminhe", "Até 20 links por vez. Links curtos da Shopee também funcionam.", "conversor", 0),
        lista("Feito para afiliado", "Detalhes que importam", [
            ("Mantém o texto e troca só os links", "Ou devolve só a lista de links convertidos."),
            ("Link limpo do produto", "Sem o rastreio de quem divulgou antes."),
            ("Sub ID opcional", "Para medir cada divulgação em Resultados."),
            ("Direto pro grupo", "Com o Bot de WhatsApp, sem sair da tela."),
        ]),
        cta("O Conversor vem em <span style='color:#F2C230'>todos os planos.</span>", "E no Meu site os seus visitantes também podem converter."),
    ],
    "08-resultados-e-metas": [
        capa("Resultados e metas", "Veja quanto vendeu <em>e de onde veio.</em>", "Incluído em todos os planos.", icone="resultados"),
        tela("Resultados", "Faturamento, comissão e pedidos", "Por dia, semana ou mês, com os produtos mais vendidos.", "resultados", 1150),
        tela("Metas", "Quanto falta pro bônus da Shopee", "Para agenciado: cadastre as faixas e acompanhe a projeção do mês.", "metas", 760),
        lista("Sempre à mão", "Sem abrir planilha", [
            ("Comissão por Sub ID", "Descubra qual grupo, site ou post vende mais."),
            ("Relatório diário por e-mail", "Os números de ontem toda manhã."),
            ("Vendas em Excel", "Com um clique."),
        ]),
        cta("Resultados e metas vêm em <span style='color:#F2C230'>todos os planos.</span>", "Conecte a sua conta da Shopee uma vez e pronto."),
    ],
    "09-emissor-nfse": [
        capa("Emissor NFS-e", "As notas da comissão extra <em>em poucos cliques.</em>", "Para afiliado pessoa jurídica (MEI ou Simples Nacional).", icone="notas"),
        tela("Como funciona", "Do relatório da Shopee às notas", "Envie o Relatório Mensal: sai uma nota por loja no Emissor Nacional.", "notas", 1130),
        tela("Lote", "Cada vendedor recebe a nota por e-mail", "Com o PDF e o XML, no horário que você escolher.", "notas-lote", 0),
        precos("Planos", "Pague pela quantidade de notas", [
            ("Até 100 notas", "R$ 17,90", ""), ("Até 500 notas", "R$ 49,90", ""), ("Até 2.000 notas", "R$ 89,90", ""),
            ("Até 5.000 notas", "R$ 129,90", ""), ("Até 10.000 notas", "R$ 169,90", ""), ("Ilimitadas", "R$ 229,90", ""),
        ], nota="Por mês. Notas de teste não contam e nota cancelada libera a vaga."),
        cta("Emita com <span style='color:#F2C230'>o seu certificado A1.</span>", "Comece pelo ambiente de testes do governo, sem valor fiscal."),
    ],
}

DESTAQUES = {
    "sobre": [
        capa("Sobre o Appfiliado", "Feito para quem é <em>afiliado Shopee.</em>",
             "As ferramentas do dia a dia do afiliado num painel só.", icone="sobre"),
        lista("Sobre o Appfiliado", "Escolha os seus módulos", [
            ("Bot de WhatsApp", "Ofertas no automático nos seus grupos."),
            ("Meu site", "Link na bio com vitrine e conversor."),
            ("Gerador de carrosséis", "Carrossel pronto a partir de um link."),
            ("Emissor NFS-e", "As notas da comissão em poucos cliques."),
        ]),
        lista("Em todos os planos", "Já vem junto", [
            ("Radar de ofertas", "Mais de 30 mil produtos com comissão."),
            ("Conversor de links", "Troca os links de qualquer texto pelo seu."),
            ("Resultados e metas", "Quanto vendeu e de onde veio."),
        ], verde=True),
        lista("Sobre o Appfiliado", "Pode ficar tranquilo", [
            ("API oficial da Shopee", "A comissão cai direto na sua conta de afiliado."),
            ("Sem instalar nada", "Tudo roda no navegador e no nosso servidor."),
            ("7 dias de garantia", "E cancelamento quando quiser, sem multa."),
        ]),
        cta("Conheça o <span style='color:#F2C230'>Appfiliado.</span>", "Planos, prints e perguntas frequentes no site.", botao="Link na bio"),
    ],
    "comece-aqui": [
        capa("Comece aqui", "1. Libere a <em>API da Shopee</em>", "Peça direto à Shopee: a resposta sai em até 5 dias úteis.", icone="chave"),
        lista("Comece aqui", "Depois da compra", [
            ("Confira o e-mail", "Chega o link para criar a senha."), ("Entre no painel", "app.appfiliado.com.br"),
            ("Conecte a Shopee", "AppID e Secret em Configurações."), ("Use o seu módulo", "O menu mostra o que está liberado."),
        ], numerada=True, verde=True),
        cta("Ficou alguma dúvida?", "Chame a gente no WhatsApp. O link está na bio.", botao="Falar no WhatsApp"),
    ],
    "planos": [
        precos("Planos", "Módulos por mês", [
            ("Bot de WhatsApp", "R$ 49,90", "Premium R$ 89,90"), ("Meu site", "R$ 22,90", "Premium R$ 35,90"),
            ("Gerador de carrosséis", "R$ 19,90", "Premium R$ 35,90"), ("Emissor NFS-e", "R$ 17,90", "por quantidade de notas"),
        ], nota="Radar, Conversor e Resultados vêm em todos os planos. Plano anual com 17% de desconto."),
        lista("Combos", "Junte módulos e pague menos", [
            ("2 módulos", "10% de desconto"), ("3 módulos", "20% de desconto"),
            ("7 dias de garantia", "Não gostou? Devolvemos o valor."),
        ], verde=True),
        cta("Monte o seu combo", "No site você escolhe Standard ou Premium em cada módulo.", botao="Ver planos"),
    ],
    "duvidas": [
        conversa("Dúvidas", "Preciso deixar o computador ligado?", [("Preciso deixar o computador ligado pro bot funcionar?", True),
                 ("Não! O bot roda no servidor do Appfiliado. Você conecta pelo QR Code e pode desligar tudo.", False)]),
        conversa("Dúvidas", "A comissão cai para mim?", [("A comissão das vendas cai na minha conta?", True),
                 ("Cai direto na sua conta da Shopee. Todos os links saem com o seu link de afiliado.", False)]),
        conversa("Dúvidas", "E se eu não gostar?", [("E se eu não gostar?", True),
                 ("Você tem 7 dias para pedir o reembolso integral e pode cancelar quando quiser, sem multa.", False)]),
    ],
}
for nome, icone, post in (("bot", "bot", "03-bot-de-whatsapp"), ("meu-site", "site", "04-meu-site"),
                          ("carrosseis", "carrosseis", "05-gerador-de-carrosseis"), ("notas", "notas", "09-emissor-nfse")):
    DESTAQUES[nome] = [s for s in FEED[post][1:-1]]


CAPAS_DOS_DESTAQUES = {"sobre": "sobre", "comece-aqui": "chave", "planos": "planos", "duvidas": "duvidas", "bot": "bot", "meu-site": "site",
                       "carrosseis": "carrosseis", "notas": "notas"}


def capa_do_destaque(icone):
    """Capa do destaque: só o círculo central (~600 px) aparece no perfil."""
    def montar(i, total, w, h):
        return (f'<section class="slide verde" style="align-items:center;justify-content:center">'
                f'<div style="width:620px;height:620px;border-radius:50%;background:rgba(246,243,234,.10);border:6px solid rgba(246,243,234,.16);'
                f'display:grid;place-items:center"><svg viewBox="0 0 24 24" style="width:330px;height:330px;fill:none;stroke:{AMARELO};'
                f'stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round"><path d="{ICONES[icone]}"/></svg></div></section>')
    return montar


CHECAR = """() => {
  const W = innerWidth, H = innerHeight, story = document.body.classList.contains('story');
  const cima = story ? 200 : 40, baixo = story ? H - 200 : H - 40, lado = story ? 48 : 40, fonteMin = story ? 24 : 26;
  const capa = !story && document.querySelector('.slide.capa');
  const erros = [];
  for (const el of document.querySelectorAll('h1,h2,p,b,li,.selo,.balao,.precos div,.numeros div,.rodape span,.lista div > span')) {
    if (el.closest('.celular')) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const t = el.textContent.trim().slice(0, 45);
    if (r.top < cima - 1 || r.bottom > baixo + 1 || r.left < lado - 1 || r.right > W - lado + 1)
      erros.push(`fora da área segura: "${t}" (${[r.left, r.top, r.right, r.bottom].map(Math.round)})`);
    if (capa && (r.left < 175 || r.right > W - 175))
      erros.push(`perto demais da borda da grade 3:4: "${t}"`);
    if (el.scrollWidth > el.clientWidth + 2) erros.push(`texto vazando na largura: "${t}"`);
    const temTexto = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (temTexto && parseFloat(getComputedStyle(el).fontSize) < fonteMin) erros.push(`fonte pequena (${getComputedStyle(el).fontSize}): "${t}"`);
  }
  return [...new Set(erros)];
}"""


def _renderizar(slides, pasta: Path, largura, altura, navegador, escala=1.0):
    """`escala` > 1 desenha numa tela menor e amplia (stories: tudo 25% maior, para ler no celular)."""
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in [*pasta.glob("*.png"), *pasta.glob("*.jpg")]:
        antigo.unlink()
    largura, altura = round(largura / escala), round(altura / escala)
    pagina = navegador.new_page(viewport={"width": largura, "height": altura}, device_scale_factor=escala)
    arquivos = []
    for i, montar in enumerate(slides, 1):
        pagina.set_content(_pagina(montar(i, len(slides), largura, altura), largura, altura))
        pagina.wait_for_timeout(150)
        for erro in pagina.evaluate(CHECAR):
            print(f"  ATENÇÃO {pasta.name}/{i:02d}: {erro}")
        destino = pasta / f"{i:02d}.jpg"
        pagina.screenshot(path=str(destino), type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": largura, "height": altura})
        arquivos.append(destino)
    pagina.close()
    return arquivos


def _previa(arquivos, destino: Path, colunas=4, lado=360):
    imagens = [Image.open(a) for a in arquivos]
    alt = int(lado * imagens[0].height / imagens[0].width)
    linhas = (len(imagens) + colunas - 1) // colunas
    folha = Image.new("RGB", (colunas * lado + (colunas + 1) * 12, linhas * alt + (linhas + 1) * 12), "#D9D2BF")
    for k, im in enumerate(imagens):
        folha.paste(im.convert("RGB").resize((lado, alt)), (12 + (k % colunas) * (lado + 12), 12 + (k // colunas) * (alt + 12)))
    folha.save(destino, quality=85)


def main():
    from playwright.sync_api import sync_playwright

    filtro = set(sys.argv[1:])
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for nome, slides in FEED.items():
            if filtro and nome not in filtro:
                continue
            arquivos = _renderizar(slides, AQUI / "feed" / nome, 1080, 1080, navegador)
            _previa(arquivos, AQUI / "feed" / f"previa-{nome}.jpg")
            print(nome, len(arquivos))
        for nome, slides in DESTAQUES.items():
            if filtro and nome not in filtro:
                continue
            STORY["ativo"] = True
            arquivos = _renderizar(slides, AQUI / "destaques" / nome, 1080, 1920, navegador, escala=1.25)
            STORY["ativo"] = False
            _previa(arquivos, AQUI / "destaques" / f"previa-{nome}.jpg", lado=300)
            print("destaque", nome, len(arquivos))
        if not filtro or "capas" in filtro:
            pasta = AQUI / "destaques" / "capas"
            for nome, icone in CAPAS_DOS_DESTAQUES.items():
                _renderizar([capa_do_destaque(icone)], pasta / nome, 1080, 1920, navegador)
                (pasta / nome / "01.jpg").replace(pasta / f"{nome}.jpg")
                (pasta / nome).rmdir()
            print("capas dos destaques", len(CAPAS_DOS_DESTAQUES))
        navegador.close()


if __name__ == "__main__":
    main()
