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
    path("radar-de-ofertas/", views.recursos, {"modulo": "radar"}, name="landing_radar"),
    path("conversor-de-links/", views.recursos, {"modulo": "conversor"}, name="landing_conversor"),
    path("resultados-e-metas/", views.recursos, {"modulo": "resultados"}, name="landing_resultados"),
    path("healthz/", healthcheck),  # o Render confere a saúde pelo domínio personalizado
    path("robots.txt", views.robots, name="landing_robots"),
    path("sitemap.xml", views.sitemap, name="landing_sitemap"),
]

handler404 = "landing.views.nao_encontrada"
