from django.urls import path

from . import views

urlpatterns = [
    path("previa-campanha/", views.previa_campanha, name="previa_campanha"),
]
