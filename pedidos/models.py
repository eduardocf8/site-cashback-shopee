from decimal import Decimal

from django.conf import settings
from django.db import models

from links.models import Click


class Pedido(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_VALIDADO = "validado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_VALIDADO, "Validado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    order_id = models.CharField(max_length=64, unique=True)
    conversion_id = models.CharField(max_length=64)
    click = models.ForeignKey(Click, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    status_shopee_bruto = models.CharField(
        max_length=64, help_text="Valor original retornado pela Shopee, guardado para conferência."
    )
    valor_comissao = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    valor_cashback = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    data_compra = models.DateTimeField(null=True, blank=True)
    data_validacao = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_compra"]

    def __str__(self):
        return f"Pedido {self.order_id} ({self.get_status_display()})"
