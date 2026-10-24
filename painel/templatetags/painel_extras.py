from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _formatar(valor, casas: int) -> str:
    try:
        numero = Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        numero = Decimal(0)
    texto = f"{numero:,.{casas}f}"  # 1,234.56
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter
def brl(valor):
    """1234.5 -> "R$ 1.234,50"."""
    return f"R$ {_formatar(valor, 2)}"


@register.filter
def brl0(valor):
    """1234.5 -> "R$ 1.235" (sem centavos, para números grandes)."""
    return f"R$ {_formatar(valor, 0)}"


@register.filter
def numero(valor):
    return _formatar(valor, 0)


@register.filter
def porcento(valor):
    try:
        return f"{float(valor) * 100:.0f}%"
    except (TypeError, ValueError):
        return "0%"


@register.filter
def sem_quebra(texto):
    """Troca os espaços por espaço que não quebra ("R$ 1.234,50" não se parte em duas
    linhas no e-mail do celular)."""
    return str(texto).replace(" ", " ")
