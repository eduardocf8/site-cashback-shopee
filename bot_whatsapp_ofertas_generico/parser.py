import hashlib
import re
from urllib.parse import urlparse


DOMINIOS_SHOPEE = (
    "shopee.com.br",
    "shopee.com",
    "s.shopee.com.br",
    "s.shopee",
    "shope.ee",
    "shoope.top",
)


def limpar_link(link):
    if not link:
        return link

    return link.strip().strip(".,;:!?)\"]}>")


def extrair_links(texto):
    if not texto:
        return []

    links = re.findall(r"https?://[^\s]+", texto)
    return [limpar_link(link) for link in links if limpar_link(link)]


def eh_link_shopee(link):
    if not link:
        return False

    link_limpo = limpar_link(link).lower()

    try:
        host = urlparse(link_limpo).netloc.lower()
    except Exception:
        host = ""

    alvo = host or link_limpo
    return any(dominio in alvo for dominio in DOMINIOS_SHOPEE)


def extrair_links_shopee(texto):
    return [link for link in extrair_links(texto) if eh_link_shopee(link)]


def gerar_id_mensagem(autor, texto, link):
    base = f"{autor}|{texto}|{link or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
