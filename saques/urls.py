from django.urls import path

from . import views

urlpatterns = [
    path("saques/pedir/", views.pedir_saque, name="pedir_saque"),
]
