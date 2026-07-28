from django.contrib import admin

from .models import Pedido


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "usuario",
        "status",
        "status_shopee_bruto",
        "valor_comissao",
        "valor_cashback",
        "data_compra",
    )
    list_filter = ("status",)
    search_fields = ("order_id", "conversion_id", "usuario__username", "usuario__cpf")
