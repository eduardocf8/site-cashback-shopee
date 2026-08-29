from django.contrib import admin

from .models import CashbackMaximoCache, NomeCurtoCache, Oferta, OfertaManual


@admin.register(Oferta)
class OfertaAdmin(admin.ModelAdmin):
    list_display = (
        "nome_curto",
        "nome",
        "preco_min",
        "percentual_desconto",
        "categoria_nome",
        "vendas",
        "criado_em",
    )
    list_filter = ("categoria_nome",)
    search_fields = ("nome", "nome_curto", "loja_nome")
    readonly_fields = tuple(f.name for f in Oferta._meta.fields)

    def has_add_permission(self, request):
        # Ofertas só existem via sincronizar_ofertas() - a tela de admin é só consulta.
        return False


@admin.register(NomeCurtoCache)
class NomeCurtoCacheAdmin(admin.ModelAdmin):
    list_display = ("nome_original", "nome_curto", "item_id", "atualizado_em")
    search_fields = ("nome_original", "nome_curto")
    readonly_fields = ("item_id", "nome_original", "nome_curto", "atualizado_em")

    def has_add_permission(self, request):
        return False


@admin.register(OfertaManual)
class OfertaManualAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "preco_novo",
        "percentual_comissao",
        "preview_cashback",
        "imperdivel",
        "criado_em",
    )
    list_filter = ("imperdivel",)
    search_fields = ("nome",)
    readonly_fields = ("preview_cashback",)
    fields = (
        "product_link",
        "nome",
        "imagem_url",
        "preco_antigo",
        "preco_novo",
        "preco_avista",
        "percentual_desconto",
        "percentual_comissao",
        "preview_cashback",
        "imperdivel",
    )

    @admin.display(description="Cashback calculado")
    def preview_cashback(self, obj):
        if not obj.percentual_comissao:
            return "—"
        return f"{obj.percentual_cashback}% (R$ {obj.valor_cashback_estimado} de volta)"


@admin.register(CashbackMaximoCache)
class CashbackMaximoCacheAdmin(admin.ModelAdmin):
    list_display = ("percentual_maximo", "atualizado_em")
    readonly_fields = ("percentual_maximo", "atualizado_em")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
