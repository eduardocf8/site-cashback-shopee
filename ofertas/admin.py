from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse

from .models import CashbackMaximoCache, NomeCurtoCache, Oferta, OfertaDestaqueManual, OfertaManual


class _PreviewCashbackMixin:
    """Campo readonly "Cashback calculado" compartilhado entre OfertaManualAdmin e
    OfertaDestaqueManualAdmin - só reflete o que já foi salvo (é uma property Python,
    não recalcula ao digitar)."""

    @admin.display(description="Cashback calculado")
    def preview_cashback(self, obj):
        if not obj.percentual_comissao:
            return "—"
        return f"{obj.percentual_cashback}% (R$ {obj.valor_cashback_estimado} de volta)"


class _CriarStoryMixin:
    """Chama instagram_bot.services.publicar_story_oferta_curada e converte o
    resultado em mensagem do admin - compartilhado entre a ação em lote de
    OfertaManualAdmin e o botão avulso de OfertaDestaqueManualAdmin (ver
    "Criar story" nos dois abaixo). Usa a mesma oferta cadastrada à mão (preço,
    desconto, comissão), sem buscar nada de novo na Shopee."""

    def _criar_story(self, request, oferta):
        from instagram_bot.services import publicar_story_oferta_curada

        try:
            registro = publicar_story_oferta_curada(oferta, request)
        except Exception as erro:
            self.message_user(request, f"{oferta.nome}: falhou ao criar story - {erro}", level=messages.ERROR)
            return
        self.message_user(request, f"{oferta.nome}: story criado (status: {registro.get_status_display()}).")


@admin.register(Oferta)
class OfertaAdmin(admin.ModelAdmin):
    list_display = (
        "nome_curto",
        "nome",
        "preco_min",
        "percentual_desconto",
        "categoria_nome",
        "vendas",
        "criado_em",
    )
    list_filter = ("categoria_nome",)
    search_fields = ("nome", "nome_curto", "loja_nome")
    readonly_fields = tuple(f.name for f in Oferta._meta.fields)

    def has_add_permission(self, request):
        # Ofertas só existem via sincronizar_ofertas() - a tela de admin é só consulta.
        return False


@admin.register(NomeCurtoCache)
class NomeCurtoCacheAdmin(admin.ModelAdmin):
    list_display = ("nome_original", "nome_curto", "item_id", "atualizado_em")
    search_fields = ("nome_original", "nome_curto")
    readonly_fields = ("item_id", "nome_original", "nome_curto", "atualizado_em")

    def has_add_permission(self, request):
        return False


@admin.register(OfertaManual)
class OfertaManualAdmin(_PreviewCashbackMixin, _CriarStoryMixin, admin.ModelAdmin):
    list_display = (
        "nome",
        "preco_novo",
        "percentual_comissao",
        "preview_cashback",
        "imperdivel",
        "criado_em",
    )
    list_filter = ("imperdivel",)
    search_fields = ("nome",)
    readonly_fields = ("preview_cashback",)
    fields = (
        "product_link",
        "nome",
        "imagem_url",
        "preco_antigo",
        "preco_novo",
        "preco_avista",
        "percentual_desconto",
        "percentual_comissao",
        "preview_cashback",
        "imperdivel",
    )
    actions = ["criar_story_de_oferta"]

    @admin.action(description="Criar story dessa(s) oferta(s) e mandar pra aprovação")
    def criar_story_de_oferta(self, request, queryset):
        for oferta in queryset:
            self._criar_story(request, oferta)


@admin.register(OfertaDestaqueManual)
class OfertaDestaqueManualAdmin(_PreviewCashbackMixin, _CriarStoryMixin, admin.ModelAdmin):
    """Página dedicada só pra "Oferta do dia" manual - diferente de OfertaManual (uma
    lista, pode ter várias), aqui só existe um registro (ver OfertaDestaqueManual.save).
    changelist_view nunca mostra lista nenhuma: vai direto pro formulário de
    edição (se já existe um registro) ou de criação (se ainda não existe) - clicar no
    item do menu lateral já cai na tela certa, sem passo intermediário."""

    readonly_fields = ("preview_cashback",)
    fields = (
        "product_link",
        "nome",
        "imagem_url",
        "preco_antigo",
        "preco_novo",
        "preco_avista",
        "percentual_desconto",
        "percentual_comissao",
        "preview_cashback",
    )
    # Como não existe lista (changelist_view sempre redireciona), a ação em lote de
    # OfertaManualAdmin não tem como aparecer aqui - o botão "Criar story" (template
    # change_form.html) chama essa URL própria em vez disso.
    change_form_template = "admin/ofertas/ofertadestaquemanual/change_form.html"

    def changelist_view(self, request, extra_context=None):
        atual = OfertaDestaqueManual.objects.first()
        if atual:
            url = reverse("admin:ofertas_ofertadestaquemanual_change", args=[atual.pk])
        else:
            url = reverse("admin:ofertas_ofertadestaquemanual_add")
        return redirect(url)

    def has_add_permission(self, request):
        # Singleton - com um registro já salvo, "adicionar" só sobrescreveria o mesmo
        # (ver OfertaDestaqueManual.save), então nem oferece a opção.
        return not OfertaDestaqueManual.objects.exists()

    def get_urls(self):
        urls = [
            path(
                "<int:object_id>/criar-story/",
                self.admin_site.admin_view(self.criar_story_view),
                name="ofertas_ofertadestaquemanual_criar_story",
            ),
        ]
        return urls + super().get_urls()

    def criar_story_view(self, request, object_id):
        oferta = get_object_or_404(OfertaDestaqueManual, pk=object_id)
        self._criar_story(request, oferta)
        return redirect(reverse("admin:ofertas_ofertadestaquemanual_change", args=[object_id]))


@admin.register(CashbackMaximoCache)
class CashbackMaximoCacheAdmin(admin.ModelAdmin):
    list_display = ("percentual_maximo", "atualizado_em")
    readonly_fields = ("percentual_maximo", "atualizado_em")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
