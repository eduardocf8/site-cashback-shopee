from django.contrib import admin
from django.utils import timezone

from . import services
from .models import EstadoTokenInstagram, RegistroPublicacao


@admin.register(EstadoTokenInstagram)
class EstadoTokenInstagramAdmin(admin.ModelAdmin):
    list_display = ("renovado_em", "ultimo_lembrete_em")
    actions = ["marcar_renovado_hoje"]

    def has_add_permission(self, request):
        # Só faz sentido uma linha (singleton) - ver EstadoTokenInstagram.get_or_create.
        return not EstadoTokenInstagram.objects.exists()

    @admin.action(description="Marcar token como renovado hoje")
    def marcar_renovado_hoje(self, request, queryset):
        queryset.update(renovado_em=timezone.localdate(), ultimo_lembrete_em=None)


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
        "imagem_urls",
        "instagram_media_id",
        "oferta_categoria_id",
        "oferta_item_id",
        "oferta_nome",
        "link_produto_original",
        "modo_simulacao",
        "status",
        "sucesso",
        "erro",
        "criado_em",
    )
    actions = ["tentar_publicar_de_novo"]

    @admin.action(description="Tentar publicar de novo (converte a arte pra JPEG se precisar)")
    def tentar_publicar_de_novo(self, request, queryset):
        for registro in queryset:
            if registro.status != RegistroPublicacao.STATUS_ERRO:
                self.message_user(
                    request, f"Registro {registro.pk}: ignorado (status não é 'Erro').", level="warning"
                )
                continue
            try:
                services.tentar_publicar_de_novo(registro, request)
                self.message_user(request, f"Registro {registro.pk}: publicado com sucesso!")
            except Exception as erro:
                registro.erro = str(erro)
                registro.save(update_fields=["erro"])
                self.message_user(
                    request, f"Registro {registro.pk}: falhou de novo - {erro}", level="error"
                )
