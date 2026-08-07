from django.contrib import admin

from .models import Pedido


class OrigemFilter(admin.SimpleListFilter):
    """Por padrão mostra só pedidos com um Click do site vinculado. A sincronização
    (pedidos/services.py) importa TODOS os pedidos da conta de afiliado Shopee, não só
    os gerados por aqui - o que sobra sem Click é ruído (outras campanhas, compras
    pessoais etc.), mas continua guardado no banco pra não perder o registro bruto."""

    title = "origem"
    parameter_name = "origem"

    def lookups(self, request, model_admin):
        return (
            ("site", "Gerados no site"),
            ("fora", "Fora do site (não identificados)"),
            ("todos", "Todos"),
        )

    def queryset(self, request, queryset):
        if self.value() == "fora":
            return queryset.filter(click__isnull=True)
        if self.value() == "todos":
            return queryset
        return queryset.filter(click__isnull=False)

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            selecionado = self.value() == lookup or (self.value() is None and lookup == "site")
            yield {
                "selected": selecionado,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }


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
    list_filter = (OrigemFilter, "status")
    search_fields = ("order_id", "conversion_id", "usuario__username", "usuario__cpf", "produto_nome")
