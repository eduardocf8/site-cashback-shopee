from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_cpf


class User(AbstractUser):
    TIPO_CHAVE_CPF = "CPF"
    TIPO_CHAVE_CNPJ = "CNPJ"
    TIPO_CHAVE_EMAIL = "EMAIL"
    TIPO_CHAVE_TELEFONE = "PHONE"
    TIPO_CHAVE_ALEATORIA = "EVP"
    TIPO_CHAVE_CHOICES = [
        (TIPO_CHAVE_CPF, "CPF"),
        (TIPO_CHAVE_CNPJ, "CNPJ"),
        (TIPO_CHAVE_EMAIL, "E-mail"),
        (TIPO_CHAVE_TELEFONE, "Telefone"),
        (TIPO_CHAVE_ALEATORIA, "Chave aleatória"),
    ]

    cpf = models.CharField(
        "CPF",
        max_length=11,
        unique=True,
        help_text="Apenas números, sem pontos ou traço.",
    )
    chave_pix = models.CharField("Chave PIX", max_length=140, blank=True)
    tipo_chave_pix = models.CharField(
        "Tipo da chave PIX", max_length=10, choices=TIPO_CHAVE_CHOICES, blank=True
    )
    email_verificado = models.BooleanField("E-mail verificado", default=False)

    def clean(self):
        super().clean()
        if self.cpf:
            self.cpf = validar_cpf(self.cpf)

    def __str__(self):
        return self.username
