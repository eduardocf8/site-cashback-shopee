from django.urls import path

from . import views

urlpatterns = [
    path("licencas/webhook/kiwify/", views.webhook_kiwify, name="licenca_webhook_kiwify"),
    path("licencas/validar/", views.validar_licenca, name="licenca_validar"),
]
