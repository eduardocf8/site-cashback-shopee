"""Download de imagens de endereços que vêm de fora (link digitado na mensagem de teste,
foto do produto que a API da Shopee devolve).

Só busca endereço público (nada de rede interna do servidor, localhost ou o endereço de
metadados da nuvem), confere de novo a cada redirecionamento, e limita o tamanho e o
tempo total - um link lento ou gigante não pode travar o bot de todo mundo."""

import ipaddress
import logging
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests

logger = logging.getLogger(__name__)

MAXIMO_BYTES = 8 * 1024 * 1024
TEMPO_TOTAL = 15  # segundos
MAXIMO_REDIRECIONAMENTOS = 4
# Imagens maiores que isso (em pixels) nem são abertas: uma "bomba" de 20 KB pode virar
# vários GB na memória ao ser descompactada.
MAXIMO_PIXELS = 30_000_000


def endereco_publico(url: str) -> bool:
    """http(s), sem usuário/senha no endereço, porta padrão, e o host só aponta para IPs
    públicos da internet."""
    try:
        partes = urlsplit(str(url or "").strip())
        host, porta = partes.hostname, partes.port
    except ValueError:
        return False
    if partes.scheme.lower() not in ("http", "https") or not host or partes.username is not None or "@" in partes.netloc:
        return False
    if porta not in (None, 80, 443):
        return False
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(host, porta or 443, type=socket.SOCK_STREAM)}
    except (socket.gaierror, UnicodeError, OSError):
        return False
    try:
        return bool(enderecos) and all(ipaddress.ip_address(ip.split("%")[0]).is_global for ip in enderecos)
    except ValueError:
        return False


def baixar(url: str, maximo_bytes: int = MAXIMO_BYTES, tempo_total: float = TEMPO_TOTAL) -> bytes | None:
    """Os bytes do arquivo, ou None se o endereço não for público, passar do tamanho ou do
    tempo, ou der erro."""
    limite = time.monotonic() + tempo_total
    atual = str(url or "").strip()
    try:
        for _ in range(MAXIMO_REDIRECIONAMENTOS + 1):
            if not endereco_publico(atual):
                logger.warning("Download recusado (endereço não público): %s", atual[:200])
                return None
            restante = limite - time.monotonic()
            if restante <= 0:
                return None
            with requests.get(atual, stream=True, allow_redirects=False, timeout=min(restante, 10),
                              headers={"User-Agent": "Mozilla/5.0 (Appfiliado)"}) as resposta:
                if resposta.is_redirect and resposta.headers.get("Location"):
                    atual = urljoin(atual, resposta.headers["Location"])
                    continue
                resposta.raise_for_status()
                declarado = resposta.headers.get("Content-Length")
                if declarado and declarado.isdigit() and int(declarado) > maximo_bytes:
                    return None
                pedacos, total = [], 0
                for pedaco in resposta.iter_content(chunk_size=65536):
                    total += len(pedaco)
                    if total > maximo_bytes or time.monotonic() > limite:
                        return None
                    pedacos.append(pedaco)
                return b"".join(pedacos)
        return None
    except requests.RequestException:
        logger.warning("Não consegui baixar %s", atual[:200])
        return None


def abrir_imagem(dados: bytes):
    """A imagem do Pillow, só se ela não for grande demais em pixels (ValueError se for)."""
    import io

    from PIL import Image

    imagem = Image.open(io.BytesIO(dados))
    largura, altura = imagem.size
    if largura * altura > MAXIMO_PIXELS:
        raise ValueError("Imagem grande demais.")
    return imagem
