from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="painel_inicio"),
    path("entrar/", views.entrar, name="painel_entrar"),
    path("sair/", views.sair, name="painel_sair"),
    path("senha/esqueci/", views.esqueci_senha, name="painel_esqueci_senha"),
    path("senha/definir/<uidb64>/<token>/", views.definir_senha, name="painel_definir_senha"),
    path("plano/", views.plano, name="painel_plano"),
    path("configuracoes/", views.configuracoes, name="painel_configuracoes"),
    path("m/<slug:slug>/", views.modulo, name="painel_modulo"),
]
