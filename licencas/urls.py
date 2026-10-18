from django.urls import path

from . import views

urlpatterns = [
    path("licencas/webhook/zouti/", views.webhook_zouti, name="licenca_webhook_zouti"),
    path("licencas/validar/", views.validar_licenca, name="licenca_validar"),
]
