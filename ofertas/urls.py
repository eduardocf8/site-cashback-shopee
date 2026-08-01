from django.urls import path

from . import views

urlpatterns = [
    path("ofertas/", views.lista, name="ofertas_lista"),
    path("ofertas/<int:oferta_id>/ir/", views.ir_para_oferta, name="ofertas_ir"),
]
