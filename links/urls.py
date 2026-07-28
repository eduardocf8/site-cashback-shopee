from django.urls import path

from . import views

urlpatterns = [
    path("links/", views.gerar_link, name="gerar_link"),
]
