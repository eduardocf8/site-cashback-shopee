import csv
from datetime import datetime

from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path

from .analytics import (
    INDICADORES_SERIE_DIARIA,
    ORIGEM_FORA,
    ORIGEM_SITE,
    gerar_planilha_analytics,
    obter_analytics,
    obter_pedidos_filtrados,
    obter_serie_diaria,
    origem_detalhada as origem_detalhada_pedido,
)
from .models import CampanhaCashback, Pedido


def _parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


class OrigemFilter(admin.SimpleListFilter):
    """Por padrão mostra só pedidos com um Click do site vinculado. A sincronização
    (pedidos/services.py) importa TODOS os pedidos da conta de afiliado Shopee, não só
    os gerados por aqui - o que sobra sem Click é ruído (outras campanhas, compras
    pessoais etc.), mas continua guardado no banco pra não perder o registro bruto."""

    title = "origem"
    parameter_name = "origem"

    def lookups(self, request, model_admin):
        return (
            ("site", "Gerados no site"),
            ("fora", "Fora do site (não identificados)"),
            ("todos", "Todos"),
        )

    def queryset(self, request, queryset):
        if self.value() == "fora":
            return queryset.filter(click__isnull=True)
        if self.value() == "todos":
            return queryset
        return queryset.filter(click__isnull=False)

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            selecionado = self.value() == lookup or (self.value() is None and lookup == "site")
            yield {
                "selected": selecionado,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }


@admin.register(CampanhaCashback)
class CampanhaCashbackAdmin(admin.ModelAdmin):
    """Liga/desliga campanhas de cashback em dobro (ou outro multiplicador) só
    cadastrando uma janela de datas aqui - sem precisar mexer no .env nem fazer
    deploy, e sem o risco de horário que existia antes (ver CampanhaCashback e
    ROADMAP.md, Fase 44)."""

    list_display = ("__str__", "multiplicador", "inicio", "fim")
    ordering = ("-inicio",)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "produto_nome",
        "usuario",
        "origem_detalhada",
        "status",
        "status_shopee_bruto",
        "motivo_cancelamento",
        "valor_pedido",
        "valor_comissao",
        "valor_cashback",
        "multiplicador_campanha",
        "data_compra",
        "data_validacao",
        "data_prevista_liberacao",
        "data_liberacao",
    )
    # Filtrar por multiplicador é o jeito de conferir quais pedidos entraram numa
    # campanha de cashback extra (e que continuam com o valor dobrado depois dela).
    list_filter = (OrigemFilter, "click__tipo", "status", "multiplicador_campanha")
    search_fields = ("order_id", "conversion_id", "usuario__username", "usuario__cpf", "produto_nome")
    list_select_related = ("click", "usuario")

    @admin.display(description="Origem")
    def origem_detalhada(self, obj):
        return origem_detalhada_pedido(obj)

    def get_urls(self):
        urls = [
            path("analytics/", self.admin_site.admin_view(self.analytics_view), name="pedidos_analytics"),
            path(
                "analytics/exportar/",
                self.admin_site.admin_view(self.analytics_exportar_csv),
                name="pedidos_analytics_exportar",
            ),
            path(
                "analytics/exportar-excel/",
                self.admin_site.admin_view(self.analytics_exportar_excel),
                name="pedidos_analytics_exportar_excel",
            ),
        ]
        return urls + super().get_urls()

    def _filtros_da_request(self, request):
        origem = request.GET.get("origem") or None
        if origem not in (ORIGEM_SITE, ORIGEM_FORA):
            origem = None
        return (
            _parse_data(request.GET.get("data_inicio")),
            _parse_data(request.GET.get("data_fim")),
            request.GET.get("status") or None,
            origem,
        )

    def analytics_view(self, request):
        data_inicio, data_fim, status, origem = self._filtros_da_request(request)
        contexto = {
            **self.admin_site.each_context(request),
            "title": "Analytics",
            "dados": obter_analytics(data_inicio, data_fim, status, origem),
            "serie_diaria": obter_serie_diaria(data_inicio, data_fim, status, origem),
            "indicadores_serie_diaria": INDICADORES_SERIE_DIARIA,
            "status_choices": Pedido.STATUS_CHOICES,
            "filtro_data_inicio": request.GET.get("data_inicio", ""),
            "filtro_data_fim": request.GET.get("data_fim", ""),
            "filtro_status": status or "",
            "filtro_origem": origem or "",
        }
        return TemplateResponse(request, "admin/analytics.html", contexto)

    def analytics_exportar_csv(self, request):
        data_inicio, data_fim, status, origem = self._filtros_da_request(request)
        pedidos = (
            obter_pedidos_filtrados(data_inicio, data_fim, status, origem)
            .select_related("usuario", "click")
            .order_by("-data_compra")
        )

        resposta = HttpResponse(content_type="text/csv")
        resposta["Content-Disposition"] = 'attachment; filename="pedidos_analytics.csv"'
        escritor = csv.writer(resposta)
        escritor.writerow(
            [
                "order_id",
                "usuario",
                "origem",
                "status",
                "valor_pedido",
                "valor_comissao",
                "valor_cashback",
                "data_compra",
                "data_validacao",
                "data_liberacao",
            ]
        )
        for pedido in pedidos.iterator():
            escritor.writerow(
                [
                    pedido.order_id,
                    pedido.usuario.username if pedido.usuario else "",
                    origem_detalhada_pedido(pedido),
                    pedido.get_status_display(),
                    pedido.valor_pedido,
                    pedido.valor_comissao,
                    pedido.valor_cashback,
                    pedido.data_compra.strftime("%Y-%m-%d %H:%M") if pedido.data_compra else "",
                    pedido.data_validacao.strftime("%Y-%m-%d %H:%M") if pedido.data_validacao else "",
                    pedido.data_liberacao.strftime("%Y-%m-%d %H:%M") if pedido.data_liberacao else "",
                ]
            )
        return resposta

    def analytics_exportar_excel(self, request):
        data_inicio, data_fim, status, origem = self._filtros_da_request(request)
        livro = gerar_planilha_analytics(data_inicio, data_fim, status, origem)

        resposta = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resposta["Content-Disposition"] = 'attachment; filename="analytics.xlsx"'
        livro.save(resposta)
        return resposta


# Mostra um link pra tela de analytics no topo da página inicial do admin. Precisa ser um
# nome de template DIFERENTE de "admin/index.html" - senão o {% extends %} dentro dele
# resolveria pra ele mesmo (mesmo caminho) e entraria em recursão infinita.
admin.site.index_template = "admin/index_customizado.html"
