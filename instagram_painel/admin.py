"""Admin das Automações Instagram do Appfiliado: o que o Instagram mandou (avisos) e os anúncios vistos.

Serve para conferir, por exemplo, o que chega quando alguém responde um anúncio de reels que também roda
nos stories (se vem o ID do anúncio, o story, os dois ou nada)."""

import json

from django.contrib import admin
from django.utils.html import format_html

from .models import AnuncioVisto, AvisoRecebido


def _json(dados) -> str:
    return format_html("<pre style=\"white-space:pre-wrap;max-width:900px\">{}</pre>", json.dumps(dados or {}, ensure_ascii=False, indent=2))


@admin.register(AvisoRecebido)
class AvisoRecebidoAdmin(admin.ModelAdmin):
    list_display = ("recebido_em", "ig_id", "campo", "resumo")
    list_filter = ("campo",)
    search_fields = ("ig_id", "resumo")
    readonly_fields = ("ig_id", "campo", "resumo", "recebido_em", "o_que_veio")
    exclude = ("bruto",)

    @admin.display(description="o que veio do Instagram")
    def o_que_veio(self, obj):
        return _json(obj.bruto)

    def has_add_permission(self, request):
        return False


@admin.register(AnuncioVisto)
class AnuncioVistoAdmin(admin.ModelAdmin):
    list_display = ("ultima_em", "ig_id", "chave", "titulo", "do_perfil", "respostas", "ultimo_texto")
    list_filter = ("do_perfil",)
    search_fields = ("ig_id", "chave", "anuncio_id", "story_id", "titulo")
    readonly_fields = ("ig_id", "chave", "anuncio_id", "post_id", "story_id", "titulo", "imagem", "do_perfil", "respostas",
                       "ultimo_texto", "primeira_em", "ultima_em", "o_que_veio")
    exclude = ("bruto",)

    @admin.display(description="o que veio do Instagram (última resposta)")
    def o_que_veio(self, obj):
        return _json(obj.bruto)

    def has_add_permission(self, request):
        return False
