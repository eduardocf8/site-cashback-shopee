"""URLs de quem acessa pelo domínio do painel (app.appfiliado.com.br) - ver
painel/middleware.py. Só o painel e a API de licenças; nada da cash-b."""

from django.urls import include, path

from cashback_shopee.views import healthcheck

urlpatterns = [
    path("", include("painel.urls")),
    path("", include("licencas.urls")),
    path("healthz/", healthcheck),
]

handler404 = "painel.views.erro_404"
handler500 = "painel.views.erro_500"
