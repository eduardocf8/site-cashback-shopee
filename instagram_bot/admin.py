from django.contrib import admin

from .models import RegistroPublicacao


@admin.register(RegistroPublicacao)
class RegistroPublicacaoAdmin(admin.ModelAdmin):
    list_display = (
        "data",
        "tipo",
        "conteudo_tipo",
        "sucesso",
        "modo_simulacao",
        "criado_em",
    )
    list_filter = ("tipo", "conteudo_tipo", "sucesso", "modo_simulacao")
    search_fields = ("legenda", "erro")
    readonly_fields = (
        "data",
        "tipo",
        "conteudo_tipo",
        "legenda",
        "imagem_url",
        "instagram_media_id",
        "modo_simulacao",
        "sucesso",
        "erro",
        "criado_em",
    )
