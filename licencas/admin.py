from django.contrib import admin

from .models import EventoWebhookKiwify, Licenca


@admin.register(Licenca)
class LicencaAdmin(admin.ModelAdmin):
    list_display = ("chave", "email", "status", "plano", "expira_em", "atualizada_em")
    list_filter = ("status",)
    search_fields = ("chave", "email", "kiwify_subscription_id")
    readonly_fields = ("chave", "criada_em", "atualizada_em")


@admin.register(EventoWebhookKiwify)
class EventoWebhookKiwifyAdmin(admin.ModelAdmin):
    list_display = (
        "webhook_event_type", "order_status", "subscription_status", "email",
        "assinatura_valida", "processado_com_sucesso", "recebido_em",
    )
    list_filter = ("assinatura_valida", "processado_com_sucesso", "webhook_event_type")
    search_fields = ("email", "kiwify_subscription_id", "corpo_bruto")
    readonly_fields = [f.name for f in EventoWebhookKiwify._meta.fields]

    def has_add_permission(self, request):
        return False
