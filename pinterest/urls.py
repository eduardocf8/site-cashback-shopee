from django.urls import path

from . import views

urlpatterns = [
    path(
        "pinterest/pin/<int:categoria_id>/<str:chave>/<str:assinatura>.jpg",
        views.imagem_pin,
        name="pinterest_imagem_pin",
    ),
    path("pinterest/planilha.csv", views.planilha_semana, name="pinterest_planilha"),
]
