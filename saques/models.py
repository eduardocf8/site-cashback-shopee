from django.conf import settings
from django.db import models


class Saque(models.Model):
    STATUS_SOLICITADO = "solicitado"
    STATUS_PROCESSANDO = "processando"
    STATUS_PAGO = "pago"
    STATUS_FALHOU = "falhou"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_SOLICITADO, "Solicitado"),
        (STATUS_PROCESSANDO, "Processando"),
        (STATUS_PAGO, "Pago"),
        (STATUS_FALHOU, "Falhou"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    PROVEDOR_ASAAS = "asaas"
    PROVEDOR_INTER = "inter"
    PROVEDOR_CHOICES = [
        (PROVEDOR_ASAAS, "Asaas"),
        (PROVEDOR_INTER, "Inter"),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saques")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    chave_pix = models.CharField(
        max_length=140, help_text="Cópia da chave Pix do usuário no momento da solicitação."
    )
    tipo_chave_pix = models.CharField(max_length=10)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_SOLICITADO)
    provedor = models.CharField(
        max_length=10, choices=PROVEDOR_CHOICES, blank=True,
        help_text="Qual provedor pagou (ou tentou pagar) este saque - definido na hora da aprovação manual.",
    )
    asaas_transfer_id = models.CharField(max_length=64, blank=True)
    resposta_asaas = models.TextField(
        blank=True, help_text="Resposta (ou erro) bruta da Asaas, guardada para conferência."
    )
    inter_codigo_solicitacao = models.CharField(max_length=64, blank=True)
    resposta_inter = models.TextField(
        blank=True, help_text="Resposta (ou erro) bruta do Inter, guardada para conferência."
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    pago_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Saque de R$ {self.valor} - {self.usuario} ({self.get_status_display()})"
