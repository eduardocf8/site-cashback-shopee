from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("ir-para-shopee/", views.ir_para_shopee, name="ir_para_shopee"),
    path("continuar/", views.continuar_sem_cadastro, name="continuar_sem_cadastro"),
    path("links/", views.gerar_link, name="gerar_link"),
    path("cashback-estimado/", views.cashback_estimado, name="cashback_estimado"),
]
