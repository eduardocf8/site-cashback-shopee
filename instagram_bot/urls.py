from django.urls import path

from . import views

urlpatterns = [
    path("instagram/aprovar/<str:token>/", views.aprovar_publicacao, name="instagram_aprovar"),
    path("instagram/webhook/", views.webhook_instagram, name="instagram_webhook"),
    path("instagram/story/<int:registro_id>/ir/", views.ir_para_story_de_oferta, name="instagram_story_ir"),
]
