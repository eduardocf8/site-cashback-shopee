from django.contrib import admin

from .models import BotaoSite, CliqueSite, ProdutoSite, SiteAfiliado


class BotaoInline(admin.TabularInline):
    model = BotaoSite
    extra = 0


@admin.register(SiteAfiliado)
class SiteAfiliadoAdmin(admin.ModelAdmin):
    list_display = ("endereco", "conta", "publicado", "vitrine", "vitrine_atualizada_em")
    list_filter = ("publicado", "vitrine")
    search_fields = ("endereco", "conta__email", "nome")
    exclude = ("foto",)
    inlines = [BotaoInline]


@admin.register(ProdutoSite)
class ProdutoSiteAdmin(admin.ModelAdmin):
    list_display = ("nome", "site", "fonte", "preco", "posicao_em")
    list_filter = ("fonte",)
    search_fields = ("nome", "site__endereco")


@admin.register(CliqueSite)
class CliqueSiteAdmin(admin.ModelAdmin):
    list_display = ("dia", "site", "tipo", "alvo_nome", "total")
    list_filter = ("tipo",)
