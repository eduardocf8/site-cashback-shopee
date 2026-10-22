"""URLs da página de vendas, na raiz de appfiliado.com.br."""

from django.urls import path

from cashback_shopee.views import healthcheck

from . import views

urlpatterns = [
    path("", views.pagina, name="landing"),
    path("emissao-de-notas/", views.notas, name="landing_notas"),
    path("bot-de-whatsapp/", views.recursos, {"modulo": "bot"}, name="landing_bot"),
    path("meu-site/", views.recursos, {"modulo": "site"}, name="landing_site"),
    path("gerador-de-carrosseis/", views.recursos, {"modulo": "carrosseis"}, name="landing_carrosseis"),
    path("healthz/", healthcheck),  # o Render confere a saúde pelo domínio personalizado
    path("robots.txt", views.robots, name="landing_robots"),
    path("sitemap.xml", views.sitemap, name="landing_sitemap"),
]

handler404 = "landing.views.nao_encontrada"
