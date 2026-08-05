from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("automacao/entrar/", views.AutomacaoLoginView.as_view(), name="automacao_login"),
    path(
        "automacao/sair/",
        auth_views.LogoutView.as_view(next_page="automacao_login"),
        name="automacao_logout",
    ),
    path("automacao/contas/", views.contas_lista, name="automacao_contas"),
    path("automacao/contas/<int:pk>/remover/", views.conta_remover, name="automacao_conta_remover"),
    path("automacao/", views.automacao_lista, name="automacao_lista"),
    path("automacao/nova/", views.automacao_nova, name="automacao_nova"),
    path("automacao/<int:pk>/editar/", views.automacao_editar, name="automacao_editar"),
    path("automacao/<int:pk>/alternar-ativa/", views.automacao_alternar_ativa, name="automacao_alternar_ativa"),
    path("automacao/historico/", views.historico, name="automacao_historico"),
]
