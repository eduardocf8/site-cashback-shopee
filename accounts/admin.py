from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


class UserAdmin(BaseUserAdmin):
    # CPF é obrigatório e único no model (accounts.models.User) - sem incluir aqui
    # também na tela de criação, ela salva com cpf="" e o segundo usuário criado
    # pelo Admin esbarra na restrição de unicidade (erro 500 genérico).
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Dados adicionais", {"fields": ("cpf",)}),)
    fieldsets = BaseUserAdmin.fieldsets + (("Dados adicionais", {"fields": ("cpf",)}),)
    list_display = ("username", "email", "cpf", "is_staff")


admin.site.register(User, UserAdmin)
