from django.contrib import admin

from .models import Click


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "tipo", "link_gerado", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("usuario__username", "usuario__cpf", "link_gerado")
