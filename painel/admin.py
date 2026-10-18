from django.contrib import admin

from .models import MetaMensal, RegraSubId, SincronizacaoResultados


@admin.register(SincronizacaoResultados)
class SincronizacaoResultadosAdmin(admin.ModelAdmin):
    list_display = ("conta", "pedido_em", "iniciada_em", "concluida_em", "cobertura_inicio", "tem_erro")
    search_fields = ("conta__email",)
    readonly_fields = ("conta", "pedido_em", "iniciada_em", "concluida_em", "erro", "cobertura_inicio")
    actions = ["pedir_atualizacao"]

    @admin.display(boolean=True, description="Erro")
    def tem_erro(self, obj):
        return bool(obj.erro)

    @admin.action(description="Buscar os números na Shopee de novo")
    def pedir_atualizacao(self, request, queryset):
        from django.utils import timezone

        queryset.update(pedido_em=timezone.now())


@admin.register(MetaMensal)
class MetaMensalAdmin(admin.ModelAdmin):
    list_display = ("conta", "ano", "mes")
    list_filter = ("ano", "mes")
    search_fields = ("conta__email",)


@admin.register(RegraSubId)
class RegraSubIdAdmin(admin.ModelAdmin):
    list_display = ("conta", "operador", "texto", "nome")
    search_fields = ("conta__email", "texto", "nome")
