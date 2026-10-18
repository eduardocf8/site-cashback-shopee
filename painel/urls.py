from django.urls import path

from . import views, views_whatsapp

urlpatterns = [
    path("", views.inicio, name="painel_inicio"),
    path("entrar/", views.entrar, name="painel_entrar"),
    path("sair/", views.sair, name="painel_sair"),
    path("senha/esqueci/", views.esqueci_senha, name="painel_esqueci_senha"),
    path("senha/definir/<uidb64>/<token>/", views.definir_senha, name="painel_definir_senha"),
    path("plano/", views.plano, name="painel_plano"),
    path("resultados/", views.resultados_view, name="painel_resultados"),
    path("resultados/atualizar/", views.atualizar_resultados, name="painel_atualizar_resultados"),
    path("resultados/estado/", views.estado_resultados, name="painel_estado_resultados"),
    path("metas/", views.metas_view, name="painel_metas"),
    path("configuracoes/", views.configuracoes, name="painel_configuracoes"),
    path("whatsapp/", views_whatsapp.whatsapp, name="painel_whatsapp"),
    path("whatsapp/estado/", views_whatsapp.whatsapp_estado, name="painel_whatsapp_estado"),
    path("whatsapp/conectar/", views_whatsapp.whatsapp_conectar, name="painel_whatsapp_conectar"),
    path("whatsapp/desconectar/", views_whatsapp.whatsapp_desconectar, name="painel_whatsapp_desconectar"),
    path("whatsapp/grupos/", views_whatsapp.whatsapp_grupos, name="painel_whatsapp_grupos"),
    path("whatsapp/enviar/", views_whatsapp.whatsapp_enviar, name="painel_whatsapp_enviar"),
    path("m/<slug:slug>/", views.modulo, name="painel_modulo"),
]
