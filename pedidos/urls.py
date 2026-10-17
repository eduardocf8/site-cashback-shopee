from django.urls import path

from . import views

urlpatterns = [
    path("previa-campanha/", views.previa_campanha, name="previa_campanha"),
    path("compra-nao-apareceu/", views.compra_nao_apareceu, name="compra_nao_apareceu"),
]
