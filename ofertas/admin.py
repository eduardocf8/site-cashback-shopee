from django.contrib import admin

from .models import NomeCurtoCache, Oferta


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
