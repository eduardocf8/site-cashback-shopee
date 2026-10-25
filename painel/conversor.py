"""Conversor de links do painel: a pessoa cola um texto (por exemplo, a mensagem que a
Shopee manda no canal dela) e os links da Shopee viram links de afiliado da conta.

Dois modos:
- "texto": o texto continua igual, só os links da Shopee são trocados. Links que não
  são da Shopee (convite de grupo, outras lojas, afiliado de outra pessoa) saem.
- "links": sai só a lista dos links convertidos, um por linha.

Cada link vira o link "limpo" do produto antes de ir para a Shopee, sem o rastreio de
quem divulgou: pela própria URL quando dá, ou abrindo o link curto (como o modo copiar
do bot). Os links são convertidos em paralelo, para não deixar a tela esperando."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bot_whatsapp import copia, shopee_ofertas
from bot_whatsapp.formatador import PADRAO_LINK_QUALQUER

logger = logging.getLogger(__name__)

MODO_TEXTO, MODO_LINKS = "texto", "links"
MODOS = [(MODO_TEXTO, "Manter o texto e trocar os links"), (MODO_LINKS, "Só os links convertidos")]
MAXIMO_LINKS = 20
MAXIMO_CARACTERES = 6000
SUB_ID_PADRAO = "conversor"
EM_PARALELO = 6

# Loja + produto na própria URL: "-i.<loja>.<produto>" ou "/product/<loja>/<produto>".
PADRAO_PRODUTO = re.compile(r"-i\.(\d+)\.(\d+)|/product/(\d+)/(\d+)")
# Parâmetros de rastreio de quem divulgou o link (o resto, como ?keyword=, fica).
RASTREIO_PREFIXOS = ("utm_", "af_", "mmp_", "uls_", "sp_", "gads_")
RASTREIO = {"smtt", "xptdk", "deep_and_deferred", "share_channel_code", "pid", "c", "is_from_login"}


class ErroConversor(Exception):
    """Mensagem pronta para mostrar na tela."""


def _link_limpo_sem_rede(link: str) -> str:
    """O link do produto sem rastreio, quando dá para saber só pela URL. Para página que
    não é de produto (campanha, loja, busca), tira só os parâmetros de rastreio."""
    achado = PADRAO_PRODUTO.search(link)
    if achado:
        loja, item = (achado.group(1), achado.group(2)) if achado.group(1) else (achado.group(3), achado.group(4))
        return f"https://shopee.com.br/product/{loja}/{item}"
    partes = urlsplit(link)
    host = (partes.hostname or "").lower()
    if host in {"s.shopee.com.br", "shp.ee", "shope.ee", "br.shp.ee"} or host.endswith(".shp.ee"):
        return ""  # link curto: precisa abrir para saber o destino
    parametros = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
                  if k.lower() not in RASTREIO and not k.lower().startswith(RASTREIO_PREFIXOS)]
    return urlunsplit((partes.scheme or "https", partes.netloc, partes.path, urlencode(parametros), ""))


def _origem(app_id: str, secret: str, link: str) -> str:
    """De qual endereço gerar o link de afiliado."""
    limpo = _link_limpo_sem_rede(link)
    if limpo:
        return limpo
    item_id = copia.identificar_produto(link)  # abre o link curto (até ~10s)
    if item_id:
        try:
            produto = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id)
        except Exception:  # noqa: BLE001 - sem o produto, vai do link como veio
            produto = None
        if produto and produto.get("link"):
            return produto["link"]
    return link


def _gerar(app_id: str, secret: str, origem: str, sub_ids: list[str]) -> str:
    """O link de afiliado, ou "" se a Shopee recusou."""
    try:
        return shopee_ofertas.gerar_link_afiliado(app_id, secret, origem, sub_ids)
    except Exception:  # noqa: BLE001
        logger.warning("Conversor: a Shopee não converteu %s", origem, exc_info=True)
        return ""


def tem_link_da_shopee(texto: str) -> bool:
    return any(p[3] for p in _pedacos(texto or ""))


def _pedacos(texto: str):
    """Cada link do texto: (início, fim, link sem pontuação colada, link normalizado ou ""
    se não for da Shopee). E-mail ("fulano@gmail.com") não conta como link."""
    for achado in PADRAO_LINK_QUALQUER.finditer(texto):
        inicio, fim = achado.span()
        if inicio and texto[inicio - 1] == "@":
            continue
        bruto = achado.group(0)
        limpo = copia.limpar_link(bruto)
        if not limpo:
            continue
        inicio_limpo = inicio + bruto.find(limpo)
        normalizado = copia._com_https(limpo)
        yield inicio_limpo, inicio_limpo + len(limpo), limpo, normalizado if copia.eh_link_shopee(normalizado) else ""


def converter(conta, texto: str, modo: str, sub_id: str = "", *, sub_ids: list[str] | None = None,
              manter_outros_links: bool = False) -> dict:
    """{"texto", "convertidos", "falharam", "removidos"}. Levanta ErroConversor.
    sub_ids: a lista inteira (mensagem avulsa do bot, com os Sub IDs de cada grupo).
    manter_outros_links: os links que não são da Shopee ficam no texto (mensagem avulsa)."""
    texto = (texto or "").replace("\r\n", "\n")
    if not texto.strip():
        raise ErroConversor("Cole um texto ou um link da Shopee.")
    if len(texto) > MAXIMO_CARACTERES:
        raise ErroConversor(f"O texto passou de {MAXIMO_CARACTERES:,} caracteres. Divida em partes.".replace(",", "."))
    if not conta.shopee_configurada:
        raise ErroConversor("Conecte sua conta da Shopee em Configurações para converter links.")
    if sub_ids is None:
        sub_ids = [sub_id.strip()] if (sub_id or "").strip() else [SUB_ID_PADRAO]
    try:
        shopee_ofertas.validar_sub_ids(sub_ids)
    except shopee_ofertas.SubIdInvalido as erro:
        raise ErroConversor(str(erro)) from erro

    pedacos = list(_pedacos(texto))
    unicos = list(dict.fromkeys(p[3] for p in pedacos if p[3]))
    if not unicos:
        raise ErroConversor("Não achei nenhum link da Shopee no texto.")
    if len(unicos) > MAXIMO_LINKS:
        raise ErroConversor(f"O texto tem {len(unicos)} links da Shopee. Converta até {MAXIMO_LINKS} por vez.")

    from bot_whatsapp.ofertas import credenciais
    app_id, secret = credenciais(conta)
    with ThreadPoolExecutor(max_workers=min(EM_PARALELO, len(unicos))) as fila:
        # 1) de onde gerar cada link (o mesmo produto com e sem rastreio vira um só);
        origens = dict(zip(unicos, fila.map(lambda link: _origem(app_id, secret, link), unicos)))
        destinos = list(dict.fromkeys(origens.values()))
        # 2) um link de afiliado por produto.
        gerados = dict(zip(destinos, fila.map(lambda origem: _gerar(app_id, secret, origem, sub_ids), destinos)))
    novo = {link: gerados[origens[link]] for link in unicos}
    convertidos = [gerados[o] for o in destinos if gerados[o]]
    falharam = [l for l in unicos if not novo[l]]
    if not convertidos:
        raise ErroConversor("A Shopee não converteu nenhum link. Confira se os links abrem e tente de novo.")

    if modo == MODO_LINKS:
        return {"texto": "\n".join(convertidos), "convertidos": len(convertidos), "falharam": falharam, "removidos": 0}

    partes, ultimo, removidos = [], 0, 0
    for inicio, fim, _limpo, normalizado in pedacos:
        partes.append(texto[ultimo:inicio])
        if normalizado:
            partes.append(novo[normalizado] or normalizado)  # não converteu: fica o da Shopee, e a tela avisa
        elif manter_outros_links:
            partes.append(texto[inicio:fim])
        else:
            removidos += 1
        ultimo = fim
    partes.append(texto[ultimo:])
    return {"texto": _arrumar(texto, "".join(partes)), "convertidos": len(convertidos), "falharam": falharam,
            "removidos": removidos}


def _arrumar(original: str, novo: str) -> str:
    """Tira espaços duplos e as linhas que ficaram vazias porque só tinham um link
    removido (as linhas em branco do original continuam)."""
    linhas_originais = original.split("\n")
    saida = []
    for i, linha in enumerate(novo.split("\n")):
        linha = re.sub(r"[ \t]{2,}", " ", linha).rstrip()
        estava_vazia = i < len(linhas_originais) and not linhas_originais[i].strip()
        if not linha.strip() and not estava_vazia:
            continue
        saida.append(linha)
    return "\n".join(saida).strip()
