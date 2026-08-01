from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from paginas.sitemaps import PaginasEstaticasSitemap

from . import views

sitemaps = {"estaticas": PaginasEstaticasSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("links.urls")),
    path("", include("accounts.urls")),
    path("", include("saques.urls")),
    path("", include("paginas.urls")),
    path("tarefas/executar/", views.executar_tarefas_agendadas, name="executar_tarefas_agendadas"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
]
