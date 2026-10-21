from django.contrib import admin

from .models import (
    AlertaDisparado, AlertaPreco, CampanhaBot, ConexaoWhatsApp, EnvioWhatsApp, EventoWhatsApp, OfertaRecebida,
    ProdutoAcompanhado,
)


@admin.register(ConexaoWhatsApp)
class ConexaoWhatsAppAdmin(admin.ModelAdmin):
    list_display = ("conta", "estado", "numero", "conectado_em", "atualizado_em")
    list_filter = ("estado",)
    search_fields = ("conta__email", "numero")
    exclude = ("jid", "qr_codigo")
    readonly_fields = ("estado", "numero", "nome", "conectado_em", "grupos", "grupos_em", "qr_em", "erro")


@admin.register(EnvioWhatsApp)
class EnvioWhatsAppAdmin(admin.ModelAdmin):
    list_display = ("conta", "destino_nome", "estado", "criado_em", "enviado_em")
    list_filter = ("estado",)
    search_fields = ("conta__email", "destino_nome")


@admin.register(EventoWhatsApp)
class EventoWhatsAppAdmin(admin.ModelAdmin):
    list_display = ("conta", "tipo", "detalhe", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("conta__email",)


@admin.register(OfertaRecebida)
class OfertaRecebidaAdmin(admin.ModelAdmin):
    list_display = ("conta", "origem_nome", "produto", "estado", "recebida_em")
    list_filter = ("estado",)
    search_fields = ("conta__email", "origem_nome", "produto")


@admin.register(CampanhaBot)
class CampanhaBotAdmin(admin.ModelAdmin):
    list_display = ("conta", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("conta__email",)


@admin.register(AlertaPreco)
class AlertaPrecoAdmin(admin.ModelAdmin):
    list_display = ("conta", "ativo", "intervalo_minutos", "queda_minima", "ultima_conferencia_em", "ultimo_erro")
    list_filter = ("ativo",)
    search_fields = ("conta__email",)
    readonly_fields = ("proxima_conferencia_em", "ultima_conferencia_em", "pedido_conferir_em", "ultimo_erro")


@admin.register(ProdutoAcompanhado)
class ProdutoAcompanhadoAdmin(admin.ModelAdmin):
    list_display = ("conta", "nome", "preco_inicial", "preco_atual", "menor_preco", "indisponivel", "conferido_em")
    list_filter = ("indisponivel",)
    search_fields = ("conta__email", "nome", "item_id")


@admin.register(AlertaDisparado)
class AlertaDisparadoAdmin(admin.ModelAdmin):
    list_display = ("conta", "nome", "preco_antes", "preco_agora", "queda", "enviado_email", "postado_grupos", "criado_em")
    search_fields = ("conta__email", "nome")
