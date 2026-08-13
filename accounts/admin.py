from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Indicacao, User


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


admin.site.register(User, UserAdmin)
