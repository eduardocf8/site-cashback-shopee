from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.static import serve

from paginas.sitemaps import PaginasEstaticasSitemap

from . import views

sitemaps = {"estaticas": PaginasEstaticasSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("links.urls")),
    path("", include("accounts.urls")),
    path("", include("saques.urls")),
    path("", include("paginas.urls")),
    path("", include("ofertas.urls")),
    path("", include("instagram_bot.urls")),
    path("", include("automacao_instagram.urls")),
    path("tarefas/executar/", views.executar_tarefas_agendadas, name="executar_tarefas_agendadas"),
    path("tarefas/encurtar-nomes/", views.executar_encurtamento_nomes, name="executar_encurtamento_nomes"),
    path("tarefas/postar-story-oferta/", views.executar_story_oferta, name="executar_story_oferta"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    # Serve as imagens geradas pelo bot do Instagram (precisam de URL pública pra API
    # buscar). Só isso mora em MEDIA_ROOT - não é usado pra upload de usuário nenhum,
    # então servir fora do modo DEBUG aqui é seguro.
    path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT}),
]
