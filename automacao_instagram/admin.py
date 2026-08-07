from django.contrib import admin

from .models import AutomacaoComentario, ComentarioProcessado, ContaInstagramConectada


@admin.register(ContaInstagramConectada)
class ContaInstagramConectadaAdmin(admin.ModelAdmin):
    list_display = ("nome_exibicao", "usuario", "instagram_business_account_id", "criado_em")
    list_filter = ("usuario",)
    search_fields = ("nome_exibicao", "instagram_business_account_id")


@admin.register(AutomacaoComentario)
class AutomacaoComentarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "conta", "ativa", "responder_comentario", "enviar_dm", "criado_em")
    list_filter = ("ativa", "conta")
    search_fields = ("nome", "instagram_media_id", "palavras_chave")


@admin.register(ComentarioProcessado)
class ComentarioProcessadoAdmin(admin.ModelAdmin):
    list_display = (
        "automacao", "autor_username", "palavra_chave_encontrada",
        "resposta_publica_enviada", "dm_enviada", "dm_respondida", "criado_em",
    )
    list_filter = ("automacao", "resposta_publica_enviada", "dm_enviada", "dm_respondida")
    search_fields = ("autor_username", "texto_comentario")
    readonly_fields = [f.name for f in ComentarioProcessado._meta.fields]

    def has_add_permission(self, request):
        return False
