"""Modo "copiar de grupos e canais": transforma uma mensagem com link da Shopee que
chegou num grupo/canal de origem na mesma oferta com o link de afiliado da conta.

1. acha os links da Shopee no texto (mesmos domínios do app de Windows, parser.py);
2. descobre o produto do primeiro link - na própria URL ou abrindo o link curto
   (mesma função que o site da cash-b usa: ofertas.services.resolver_item_id_*);
3. busca o produto na API com as credenciais da conta: dá o link "limpo" do produto
   (sem o rastreio de quem postou a oferta), o nome e a foto;
4. gera o link de afiliado da conta (com os Sub IDs de cada grupo) a partir dele -
   ou do link original, se não deu para descobrir o produto;
5. o texto passa pelo mesmo formatador do app (título, preços, "Compre aqui")."""

import hashlib
import re
from urllib.parse import urlparse

from ofertas.services import resolver_item_id_com_rede, resolver_item_id_sem_rede

from . import shopee_ofertas

DOMINIOS_SHOPEE = ("shopee.com.br", "shopee.com", "s.shopee.com.br", "s.shopee", "shope.ee", "shp.ee", "shoope.top")
PADRAO_LINK = re.compile(r"https?://[^\s]+")


def limpar_link(link: str) -> str:
    link = str(link or "").replace("‪", "").replace("‬", "").strip()
    link = link.strip(" \t\r\n\"'<>[](){}*_~")
    # Pontuação colada no fim ("...AbC)." ou "AbC!*") não faz parte do link.
    return re.sub(r"[.,;:!?)\]}>\"'*_~]+$", "", link)


def eh_link_shopee(link: str) -> bool:
    try:
        host = urlparse(link.lower()).netloc
    except ValueError:
        host = ""
    return any(dominio in (host or link.lower()) for dominio in DOMINIOS_SHOPEE)


def links_shopee(texto: str) -> list[str]:
    return [link for link in (limpar_link(l) for l in PADRAO_LINK.findall(texto or "")) if link and eh_link_shopee(link)]


def texto_da_mensagem(mensagem) -> str:
    """Texto de uma mensagem do WhatsApp (proto waE2E.Message): texto simples, texto
    com prévia ou legenda de foto/vídeo."""
    if mensagem.conversation:
        return mensagem.conversation
    if mensagem.HasField("extendedTextMessage"):
        return mensagem.extendedTextMessage.text
    if mensagem.HasField("imageMessage"):
        return mensagem.imageMessage.caption
    if mensagem.HasField("videoMessage"):
        return mensagem.videoMessage.caption
    return ""


def tem_foto(mensagem) -> bool:
    return mensagem.HasField("imageMessage")


def identificar_produto(link: str) -> str:
    """item_id do produto do link ("" se não deu): primeiro pela própria URL, depois
    abrindo o link curto (pode levar alguns segundos - roda no worker)."""
    item = resolver_item_id_sem_rede(link) or resolver_item_id_com_rede(link, timeout=10)
    return str(item or "")


def chave_do_produto(item_id: str, link: str) -> str:
    """Para o "não repetir": o item_id ou, sem ele, um resumo do link."""
    return item_id or "link:" + hashlib.sha1(link.encode()).hexdigest()[:20]


def preparar(app_id: str, secret: str, texto: str) -> dict:
    """{"link_origem", "item_id", "produto" (dict ou None), "texto_base"} da oferta.
    Levanta ValueError se não houver link da Shopee."""
    links = links_shopee(texto)
    if not links:
        raise ValueError("A mensagem não tem link da Shopee.")
    principal = links[0]
    item_id = identificar_produto(principal)
    produto = None
    if item_id:
        try:
            produto = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id)
        except Exception:  # noqa: BLE001 - sem os dados do produto, usa o link original
            produto = None
    return {
        "link_origem": (produto or {}).get("link") or principal,
        "item_id": item_id,
        "produto": produto,
        "texto_base": texto,
    }
