from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("links.urls")),
    path("", include("accounts.urls")),
    path("", include("saques.urls")),
    path("", include("paginas.urls")),
    path("tarefas/executar/", views.executar_tarefas_agendadas, name="executar_tarefas_agendadas"),
]
