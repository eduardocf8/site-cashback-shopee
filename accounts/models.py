from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_cpf


class User(AbstractUser):
    cpf = models.CharField(
        "CPF",
        max_length=11,
        unique=True,
        help_text="Apenas números, sem pontos ou traço.",
    )

    def clean(self):
        super().clean()
        if self.cpf:
            self.cpf = validar_cpf(self.cpf)

    def __str__(self):
        return self.username
