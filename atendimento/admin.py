from django.contrib import admin
from django.utils import timezone

from .models import Conversa, Mensagem


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    fields = ("criada_em", "autor", "texto")
    readonly_fields = ("criada_em", "autor", "texto")
    can_delete = False
    ordering = ("criada_em", "id")


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "telefone", "estado", "motivo_humano", "ultima_recebida_em")
    list_filter = ("estado",)
    search_fields = ("nome", "telefone", "chat", "mensagens__texto")
    readonly_fields = ("chat", "telefone", "criada_em", "ultima_recebida_em", "humano_desde")
    inlines = [MensagemInline]
    actions = ["devolver_ao_agente", "pausar_agente"]

    @admin.action(description="Devolver ao agente (ele volta a responder)")
    def devolver_ao_agente(self, request, queryset):
        queryset.update(estado=Conversa.IA, motivo_humano="", humano_desde=None)

    @admin.action(description="Pausar o agente (você responde)")
    def pausar_agente(self, request, queryset):
        queryset.update(estado=Conversa.HUMANO, humano_desde=timezone.now())
