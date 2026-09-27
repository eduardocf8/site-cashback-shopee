# -*- coding: utf-8 -*-
"""
Protege campos sensiveis (segredo da API Shopee, senha de app do Gmail)
gravados em config_usuario.json - antes desse modulo, esses campos
ficavam la em texto puro, entao qualquer um que abrisse o arquivo (ou
recebesse ele por email/nuvem, ex: usando "Exportar configurações")
via as credenciais sem esforço nenhum.

Estratégia: no Windows (onde o app roda de verdade, distribuído como
.exe), cifra o valor com o DPAPI do próprio Windows (via pywin32/
win32crypt) antes de salvar. O DPAPI amarra a cifragem à conta do
usuário do Windows na máquina atual - ninguém mais, nem em outra
máquina com o mesmo arquivo, consegue decifrar sem estar logado como
esse mesmo usuário. Não exige senha nenhuma de quem usa o app - é
transparente.

Fora do Windows (ex: ambiente de desenvolvimento/testes) ou se o
pywin32 não estiver instalado, os campos ficam em texto puro mesmo -
degrada de forma segura (nunca trava o app, nunca perde o dado), só
não tem a proteção extra.

Efeito colateral esperado e por design: um valor cifrado num
computador NÃO decifra em outro computador (ou outro usuário do
Windows) - é exatamente o caso de usar "Exportar/Importar
configurações" ou "Restaurar backup" pra migrar de máquina. Quem chama
revelar() pode passar uma lista `falhas` pra saber se isso aconteceu e
avisar quem usa o app que precisa preencher a credencial de novo, em
vez de deixar a API falhar silenciosamente com uma credencial vazia.
"""

import base64
import sys

PREFIXO_CIFRADO = "dpapi:v1:"


def _dpapi_disponivel():
    if not sys.platform.startswith("win"):
        return False
    try:
        import win32crypt  # noqa: F401
    except ImportError:
        return False
    return True


def _dpapi_criptografar_bytes(dados):
    import win32crypt

    return win32crypt.CryptProtectData(dados, None, None, None, None, 0)


def _dpapi_descriptografar_bytes(dados):
    import win32crypt

    _descricao, texto = win32crypt.CryptUnprotectData(dados, None, None, None, 0)
    return texto


def proteger(valor):
    """Cifra `valor` pra gravar em disco. Vazio continua vazio. Um valor
    já cifrado (começa com o prefixo) é devolvido sem mexer, pra não
    cifrar em cima de cifrado a cada save(). Se não for possível cifrar
    (fora do Windows, sem pywin32, ou qualquer falha inesperada),
    devolve o valor original em texto puro - nunca lança exceção pra
    quem chama, salvar as configurações não pode travar por causa
    disso."""
    valor = str(valor or "")
    if not valor or valor.startswith(PREFIXO_CIFRADO):
        return valor
    if not _dpapi_disponivel():
        return valor
    try:
        cifrado = _dpapi_criptografar_bytes(valor.encode("utf-8"))
        return PREFIXO_CIFRADO + base64.b64encode(cifrado).decode("ascii")
    except Exception:
        return valor


def revelar(valor, falhas=None):
    """Decifra um valor gravado por proteger(). Um valor que não começa
    com o prefixo é tratado como texto puro legado (config antiga, ou
    ambiente sem suporte a DPAPI) e devolvido como está. Se o valor foi
    cifrado mas não dá pra decifrar aqui (ex: o arquivo veio de outra
    máquina/usuário do Windows), devolve "" e registra a falha na lista
    `falhas`, se ela for passada - quem chama decide como avisar o
    usuário, em vez de arriscar usar bytes decifrados errados como se
    fossem a credencial de verdade."""
    valor = str(valor or "")
    if not valor.startswith(PREFIXO_CIFRADO):
        return valor
    try:
        bruto = base64.b64decode(valor[len(PREFIXO_CIFRADO):])
        return _dpapi_descriptografar_bytes(bruto).decode("utf-8")
    except Exception:
        if falhas is not None:
            falhas.append(valor)
        return ""
