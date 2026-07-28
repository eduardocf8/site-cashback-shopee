import re

from django.core.exceptions import ValidationError


def _apenas_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _calcular_digito_verificador(cpf_parcial: str) -> int:
    tamanho = len(cpf_parcial)
    soma = sum(int(digito) * peso for digito, peso in zip(cpf_parcial, range(tamanho + 1, 1, -1)))
    resto = (soma * 10) % 11
    return 0 if resto == 10 else resto


def validar_cpf(cpf: str) -> str:
    """Valida um CPF (formatado ou não) e retorna apenas os 11 dígitos."""
    digitos = _apenas_digitos(cpf)

    if len(digitos) != 11:
        raise ValidationError("CPF deve conter 11 dígitos.")

    if digitos == digitos[0] * 11:
        raise ValidationError("CPF inválido.")

    primeiro_dv = _calcular_digito_verificador(digitos[:9])
    segundo_dv = _calcular_digito_verificador(digitos[:9] + str(primeiro_dv))

    if digitos[-2:] != f"{primeiro_dv}{segundo_dv}":
        raise ValidationError("CPF inválido.")

    return digitos
