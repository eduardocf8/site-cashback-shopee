from django.contrib import admin

from .models import Pedido


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "produto_nome",
        "usuario",
        "status",
        "status_shopee_bruto",
        "motivo_cancelamento",
        "valor_comissao",
        "valor_cashback",
        "data_compra",
        "data_validacao",
        "data_prevista_liberacao",
        "data_liberacao",
    )
    list_filter = ("status",)
    search_fields = ("order_id", "conversion_id", "usuario__username", "usuario__cpf", "produto_nome")
