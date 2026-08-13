import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_cpf

# Sem caracteres ambíguos (0/O, 1/I/L) - o código é pra gente compartilhar em texto/voz.
ALFABETO_CODIGO_INDICACAO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO_INDICACAO = 8


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
    codigo_indicacao = models.CharField(
        "Código de indicação", max_length=TAMANHO_CODIGO_INDICACAO, unique=True, blank=True
    )

    def clean(self):
        super().clean()
        if self.cpf:
            self.cpf = validar_cpf(self.cpf)

    def save(self, *args, **kwargs):
        if not self.codigo_indicacao:
            self.codigo_indicacao = self._gerar_codigo_indicacao()
        super().save(*args, **kwargs)

    @classmethod
    def _gerar_codigo_indicacao(cls):
        while True:
            codigo = "".join(secrets.choice(ALFABETO_CODIGO_INDICACAO) for _ in range(TAMANHO_CODIGO_INDICACAO))
            if not cls.objects.filter(codigo_indicacao=codigo).exists():
                return codigo

    def __str__(self):
        return self.username


class Indicacao(models.Model):
    """Vínculo entre quem indicou e quem se cadastrou pelo link - e os pedidos que
    dispararam o bônus de cashback em dobro de cada lado (ver pedidos/services.py)."""

    indicador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="indicacoes_feitas"
    )
    indicado = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="indicacao_recebida"
    )
    pedido_bonus_indicado = models.ForeignKey(
        "pedidos.Pedido", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="1ª compra validada do indicado - dispara o cashback em dobro dela.",
    )
    pedido_bonus_indicador = models.ForeignKey(
        "pedidos.Pedido", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Próxima compra validada de quem indicou depois do bônus acima - cashback em dobro dela.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.indicador} indicou {self.indicado}"
