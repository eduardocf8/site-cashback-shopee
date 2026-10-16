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


def validar_celular(celular: str) -> str:
    """Celular brasileiro: DDD + 9 + 8 dígitos. Aceita formatado e com +55; devolve só
    os 11 dígitos."""
    digitos = _apenas_digitos(celular)
    if len(digitos) == 13 and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) != 11 or digitos[2] != "9" or digitos[0] == "0":
        raise ValidationError("Informe um celular válido com DDD, ex: (11) 98765-4321.")
    return digitos


def validar_nome_completo(nome: str) -> str:
    """Nome e sobrenome - é comparado com o titular da chave Pix."""
    nome = " ".join((nome or "").split())
    if len(nome.split(" ")) < 2:
        raise ValidationError("Informe seu nome completo (nome e sobrenome).")
    return nome
