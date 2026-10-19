"""URLs do site do afiliado. No subdomínio (seunome.appfiliado.com.br) ficam na raiz;
pelo painel, debaixo de /s/<endereco>/ (ver painel/urls.py)."""

from django.urls import path

from . import publico

urlpatterns = [
    path("", publico.pagina, name="site_pagina"),
    path("b/<int:botao_id>/", publico.ir_botao, name="site_botao"),
    path("p/<int:produto_id>/", publico.ir_produto, name="site_produto"),
    path("r/<slug:rede>/", publico.ir_rede, name="site_rede"),
    path("ir/", publico.converter, name="site_converter"),
    path("foto.jpg", publico.foto, name="site_foto"),
]

handler404 = "meusite.publico.nao_encontrado"
