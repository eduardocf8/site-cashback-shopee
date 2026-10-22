"""URLs da página de vendas, na raiz de appfiliado.com.br."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.pagina, name="landing"),
    path("emissao-de-notas/", views.notas, name="landing_notas"),
    path("robots.txt", views.robots, name="landing_robots"),
    path("sitemap.xml", views.sitemap, name="landing_sitemap"),
]

handler404 = "landing.views.nao_encontrada"
