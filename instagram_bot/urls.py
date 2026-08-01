from django.urls import path

from . import views

urlpatterns = [
    path("instagram/aprovar/<str:token>/", views.aprovar_publicacao, name="instagram_aprovar"),
]
