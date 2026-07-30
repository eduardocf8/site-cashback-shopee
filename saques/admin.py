from django.contrib import admin

from .models import Saque
from .services import processar_saque


@admin.action(description="Aprovar e pagar via PIX (Asaas)")
def aprovar_e_pagar(modeladmin, request, queryset):
    processados = 0
    pagos = 0
    for saque in queryset.filter(status=Saque.STATUS_SOLICITADO):
        processar_saque(saque)
        processados += 1
        if saque.status == Saque.STATUS_PAGO:
            pagos += 1

    if processados == 0:
        modeladmin.message_user(request, "Nenhum saque selecionado estava com status 'Solicitado'.")
    else:
        modeladmin.message_user(request, f"{processados} saque(s) processado(s), {pagos} pago(s) com sucesso.")


@admin.action(description="Cancelar solicitação (devolve o saldo)")
def cancelar_solicitacao(modeladmin, request, queryset):
    total = queryset.filter(status=Saque.STATUS_SOLICITADO).update(status=Saque.STATUS_CANCELADO)
    modeladmin.message_user(request, f"{total} saque(s) cancelado(s).")


@admin.register(Saque)
class SaqueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "valor",
        "status",
        "tipo_chave_pix",
        "chave_pix",
        "asaas_transfer_id",
        "criado_em",
        "pago_em",
    )
    list_filter = ("status",)
    search_fields = ("usuario__username", "usuario__cpf", "chave_pix", "asaas_transfer_id")
    actions = [aprovar_e_pagar, cancelar_solicitacao]
