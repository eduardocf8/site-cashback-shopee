"""Checagem automática das regras de voz que dá para conferir só olhando o texto.

Não substitui ler a resposta (tom, se a informação está certa), mas pega na hora os
deslizes mais comuns. Usada no relatório de comparação entre modelos e, quando o bot
existir, para marcar no admin as respostas que precisam de revisão.
"""

import re

REGRAS = [
    # (descrição do problema, expressão que o encontra)
    ('"PIX" em maiúsculas (o certo é "Pix")', re.compile(r"\bPIX\b")),
    ('percentual com sinal de mais (o certo é "50% a mais")', re.compile(r"\+\s?\d+(?:[.,]\d+)?\s?%")),
    (
        'cashback como condicional ("pode voltar/gerar/cair")',
        re.compile(r"\bpode(?:m)?\s+(?:voltar|gerar|cair)\b", re.IGNORECASE),
    ),
    (
        'marca no masculino ("o/no/do/ao/pelo cash-b")',
        re.compile(r"\b(?:o|no|do|ao|pelo)\s+cash-b\b", re.IGNORECASE),
    ),
    ('negrito com dois asteriscos (no WhatsApp aparece "**" literal)', re.compile(r"\*\*")),
    ("título em Markdown (no WhatsApp aparece \"#\" literal)", re.compile(r"^\s*#{1,6}\s", re.MULTILINE)),
]

_NOME_DA_MARCA = re.compile(r"\bcash-?b\b", re.IGNORECASE)


def problemas_de_voz(texto: str) -> list[str]:
    """Lista de problemas encontrados no texto (vazia se nenhum)."""
    problemas = [descricao for descricao, padrao in REGRAS if padrao.search(texto)]
    grafias_erradas = sorted({m.group(0) for m in _NOME_DA_MARCA.finditer(texto)} - {"cash-b"})
    if grafias_erradas:
        problemas.append(f'nome da marca escrito como {", ".join(grafias_erradas)} (o certo é "cash-b")')
    return problemas
