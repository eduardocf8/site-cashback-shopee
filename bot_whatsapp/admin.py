from django.contrib import admin

from .models import ConexaoWhatsApp, EnvioWhatsApp, EventoWhatsApp


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
