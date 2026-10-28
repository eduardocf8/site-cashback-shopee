from django.contrib import admin
from django.utils import timezone

from .models import Conversa, Mensagem, RespostaAprendida


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    fields = ("criada_em", "autor", "texto")
    readonly_fields = ("criada_em", "autor", "texto")
    can_delete = False
    ordering = ("criada_em", "id")


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "telefone", "estado", "conta", "motivo_humano", "ultima_recebida_em")
    list_filter = ("estado",)
    search_fields = ("nome", "telefone", "chat", "mensagens__texto", "conta__email")
    readonly_fields = ("chat", "telefone", "criada_em", "ultima_recebida_em", "humano_desde", "vinculada_em")
    raw_id_fields = ("conta",)
    inlines = [MensagemInline]
    actions = ["devolver_ao_agente", "pausar_agente"]

    @admin.action(description="Devolver ao agente (ele volta a responder)")
    def devolver_ao_agente(self, request, queryset):
        queryset.update(estado=Conversa.IA, motivo_humano="", humano_desde=None)

    @admin.action(description="Pausar o agente (você responde)")
    def pausar_agente(self, request, queryset):
        queryset.update(estado=Conversa.HUMANO, humano_desde=timezone.now())


@admin.register(RespostaAprendida)
class RespostaAprendidaAdmin(admin.ModelAdmin):
    """O que o agente aprendeu com você. Só as aprovadas entram no que ele sabe (vale na hora)."""

    list_display = ("pergunta", "resposta", "estado", "criada_em")
    list_filter = ("estado",)
    list_editable = ("estado",)
    search_fields = ("pergunta", "resposta")
    fields = ("estado", "pergunta", "resposta", "conversa", "criada_em", "enviada_em", "decidida_em")
    readonly_fields = ("conversa", "criada_em", "enviada_em", "decidida_em")
    actions = ["aprovar", "descartar"]

    def get_changeform_initial_data(self, request):
        return {"estado": RespostaAprendida.APROVADA}  # criada à mão: já vale

    def save_model(self, request, obj, form, change):
        if "estado" in form.changed_data and obj.estado != RespostaAprendida.SUGERIDA:
            obj.decidida_em = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Aprovar (o agente passa a usar)")
    def aprovar(self, request, queryset):
        queryset.update(estado=RespostaAprendida.APROVADA, decidida_em=timezone.now())

    @admin.action(description="Descartar")
    def descartar(self, request, queryset):
        queryset.update(estado=RespostaAprendida.DESCARTADA, decidida_em=timezone.now())
