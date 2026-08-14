from django.urls import path

from . import views

urlpatterns = [
    path("saques/pedir/", views.pedir_saque, name="pedir_saque"),
    path("saques/webhook/validacao/", views.webhook_validacao_asaas, name="webhook_validacao_asaas"),
]
