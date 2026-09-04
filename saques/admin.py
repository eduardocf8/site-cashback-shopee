from django.contrib import admin

from .models import Saque
from .services import processar_saque_asaas, processar_saque_inter


def _aprovar_e_pagar(modeladmin, request, queryset, processar, nome_provedor):
    processados = 0
    pagos = 0
    for saque in queryset.filter(status=Saque.STATUS_SOLICITADO):
        processar(saque)
        processados += 1
        if saque.status == Saque.STATUS_PAGO:
            pagos += 1

    if processados == 0:
        modeladmin.message_user(request, "Nenhum saque selecionado estava com status 'Solicitado'.")
    else:
        modeladmin.message_user(
            request, f"{processados} saque(s) enviado(s) pra {nome_provedor}, {pagos} pago(s) com sucesso."
        )


@admin.action(description="Aprovar e pagar via Pix (Asaas)")
def aprovar_e_pagar_asaas(modeladmin, request, queryset):
    _aprovar_e_pagar(modeladmin, request, queryset, processar_saque_asaas, "Asaas")


@admin.action(description="Aprovar e pagar via Pix (Inter) - em pausa até virar Simples Nacional")
def aprovar_e_pagar_inter(modeladmin, request, queryset):
    _aprovar_e_pagar(modeladmin, request, queryset, processar_saque_inter, "Inter")


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
        "provedor",
        "tipo_chave_pix",
        "chave_pix",
        "criado_em",
        "pago_em",
    )
    list_filter = ("status", "provedor")
    search_fields = ("usuario__username", "usuario__cpf", "chave_pix", "asaas_transfer_id", "inter_codigo_solicitacao")
    actions = [aprovar_e_pagar_asaas, aprovar_e_pagar_inter, cancelar_solicitacao]
