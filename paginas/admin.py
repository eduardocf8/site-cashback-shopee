from django.contrib import admin

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("texto", "link", "ativo", "ordem")
    list_editable = ("ativo", "ordem")
    list_filter = ("ativo",)
