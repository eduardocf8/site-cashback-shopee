"""Cifra os segredos que o painel guarda das contas (ex: Secret da API da Shopee).

A chave vem de APPFILIADO_CHAVE_CRIPTOGRAFIA (uma chave Fernet). Sem ela, é
derivada do DJANGO_SECRET_KEY - funciona, mas trocar o SECRET_KEY depois
deixaria os segredos salvos ilegíveis, por isso vale configurar a variável
própria em produção."""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    chave = settings.APPFILIADO_CHAVE_CRIPTOGRAFIA
    if not chave:
        digest = hashlib.sha256(f"appfiliado-painel:{settings.SECRET_KEY}".encode()).digest()
        chave = base64.urlsafe_b64encode(digest).decode()
    return Fernet(chave.encode() if isinstance(chave, str) else chave)


def cifrar(texto: str) -> str:
    if not texto:
        return ""
    return _fernet().encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(cifrado: str) -> str:
    """Texto original, ou "" se não der para decifrar (chave trocada)."""
    if not cifrado:
        return ""
    try:
        return _fernet().decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("Painel: não consegui decifrar um segredo salvo (a chave mudou?).")
        return ""
