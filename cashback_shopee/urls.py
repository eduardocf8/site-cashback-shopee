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
    path("", include("licencas.urls")),
    path("", include("pinterest.urls")),
    path("", include("pedidos.urls")),
    path("healthz/", views.healthcheck, name="healthcheck"),
    path("tarefas/executar/", views.executar_tarefas_agendadas, name="executar_tarefas_agendadas"),
    path(
        "tarefas/sincronizacao-semanal/",
        views.executar_sincronizacao_semanal,
        name="executar_sincronizacao_semanal",
    ),
    path("tarefas/publicar-instagram/", views.executar_publicacoes_instagram, name="executar_publicacoes_instagram"),
    path("tarefas/encurtar-nomes/", views.executar_encurtamento_nomes, name="executar_encurtamento_nomes"),
    path(
        "tarefas/resolver-item-alvo/",
        views.executar_resolucao_item_id_alvo,
        name="executar_resolucao_item_id_alvo",
    ),
    path("tarefas/postar-story-oferta/", views.executar_story_oferta, name="executar_story_oferta"),
    path(
        "tarefas/lembrete-verificacao-email/",
        views.executar_lembrete_verificacao_email,
        name="executar_lembrete_verificacao_email",
    ),
    path(
        "tarefas/lembrete-primeira-compra/",
        views.executar_lembrete_primeira_compra,
        name="executar_lembrete_primeira_compra",
    ),
    path(
        "tarefas/lembrete-venda-indireta/",
        views.executar_lembrete_venda_indireta,
        name="executar_lembrete_venda_indireta",
    ),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    # Serve as imagens geradas pelo bot do Instagram (precisam de URL pública pra API
    # buscar). Só isso mora em MEDIA_ROOT - não é usado pra upload de usuário nenhum,
    # então servir fora do modo DEBUG aqui é seguro.
    path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT}),
]
