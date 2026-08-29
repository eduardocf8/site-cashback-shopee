from django.urls import path

from . import views

urlpatterns = [
    path("ofertas/", views.lista, name="ofertas_lista"),
    path("ofertas/<int:oferta_id>/ir/", views.ir_para_oferta, name="ofertas_ir"),
    path("ofertas/manual/<int:oferta_manual_id>/ir/", views.ir_para_oferta_manual, name="ofertas_manual_ir"),
]
