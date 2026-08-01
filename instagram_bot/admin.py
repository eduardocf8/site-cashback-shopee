from django.contrib import admin

from .models import RegistroPublicacao


@admin.register(RegistroPublicacao)
class RegistroPublicacaoAdmin(admin.ModelAdmin):
    list_display = (
        "data",
        "tipo",
        "conteudo_tipo",
        "status",
        "modo_simulacao",
        "criado_em",
    )
    list_filter = ("status", "tipo", "conteudo_tipo", "modo_simulacao")
    search_fields = ("legenda", "erro")
    readonly_fields = (
        "data",
        "tipo",
        "conteudo_tipo",
        "legenda",
        "imagem_url",
        "instagram_media_id",
        "modo_simulacao",
        "status",
        "sucesso",
        "erro",
        "criado_em",
    )
