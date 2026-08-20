from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ConfiguracaoIndicacao, Indicacao, PushSubscription, User
from .push import enviar_push


class UserAdmin(BaseUserAdmin):
    # CPF é obrigatório e único no model (accounts.models.User) - sem incluir aqui
    # também na tela de criação, ela salva com cpf="" e o segundo usuário criado
    # pelo Admin esbarra na restrição de unicidade (erro 500 genérico).
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Dados adicionais", {"fields": ("cpf",)}),)
    fieldsets = BaseUserAdmin.fieldsets + (("Dados adicionais", {"fields": ("cpf", "codigo_indicacao")}),)
    list_display = ("username", "email", "cpf", "codigo_indicacao", "is_staff")
    readonly_fields = ("codigo_indicacao",)


@admin.register(Indicacao)
class IndicacaoAdmin(admin.ModelAdmin):
    list_display = ("indicador", "indicado", "pedido_bonus_indicado", "pedido_bonus_indicador", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("indicador__username", "indicado__username")
    autocomplete_fields = ("indicador", "indicado")


@admin.register(ConfiguracaoIndicacao)
class ConfiguracaoIndicacaoAdmin(admin.ModelAdmin):
    # Linha única (pk=1, criada pela migração 0006) - só dá pra editar o campo "ativa",
    # não criar outra linha nem apagar a que existe.
    list_display = ("ativa",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "criado_em")
    search_fields = ("usuario__username",)
    autocomplete_fields = ("usuario",)
    actions = ["mandar_notificacao_de_teste"]

    @admin.action(description="Mandar notificação de teste")
    def mandar_notificacao_de_teste(self, request, queryset):
        usuarios = {inscricao.usuario for inscricao in queryset}
        total_enviado = sum(
            enviar_push(
                usuario,
                "Notificação de teste",
                "Se você recebeu isso, as notificações da cash-b estão funcionando!",
                url="/dashboard/",
            )
            for usuario in usuarios
        )
        if total_enviado:
            self.message_user(request, f"Notificação de teste enviada com sucesso ({total_enviado}).")
        else:
            self.message_user(
                request,
                "Não saiu nenhuma notificação - o envio falhou no servidor. Procure por "
                '"Falha ao enviar push" nos logs do Render pra ver o erro exato.',
                level=messages.WARNING,
            )


admin.site.register(User, UserAdmin)
