import csv
from datetime import datetime
from decimal import Decimal

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from accounts.funil import obter_cadastros_por_dia, obter_funil
from cashback_shopee import admin_grupos

from .analytics import (
    INDICADORES_SERIE_DIARIA,
    MESES_GRAFICO_SACADO_PADRAO,
    ORIGEM_FORA,
    ORIGEM_SEM_CADASTRO,
    ORIGEM_SITE,
    ROTULOS_TIPO_SALDO,
    gerar_planilha_analytics,
    obter_analytics,
    obter_grafico_sacado,
    obter_pedidos_filtrados,
    obter_resumo_liberado,
    obter_saldo_disponivel,
    obter_saldo_por_usuario,
    obter_serie_diaria,
    origem_detalhada as origem_detalhada_pedido,
)
from .models import CampanhaCashback, Pedido, ReclamacaoPedido
from .reclamacoes import ReclamacaoInvalida, cashback_previsto, recusar, vincular


def _parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_inteiro(valor, padrao):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


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
            ("sem_cadastro", "Sem cadastro (clique anônimo, sem cashback ainda)"),
            ("fora", "Fora do site (não identificados)"),
            ("todos", "Todos"),
        )

    def queryset(self, request, queryset):
        if self.value() == "sem_cadastro":
            return queryset.filter(click__isnull=False, usuario__isnull=True)
        if self.value() == "fora":
            return queryset.exclude(Pedido.filtro_do_site())
        if self.value() == "todos":
            return queryset
        return queryset.filter(Pedido.filtro_do_site())

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
    class Media:
        # Barra de rolagem própria da tabela + botão de expandir - ver os
        # arquivos pra entender por quê (tabela larga demais pra tela,
        # muitas colunas em list_display).
        css = {"all": ("css/admin_pedidos.css",)}
        js = ("js/admin_pedidos.js",)

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
        "valor_cashback_exibido",
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

    @admin.display(description="Valor cashback", ordering="valor_cashback")
    def valor_cashback_exibido(self, obj):
        # Pedido "Fora do site" (sem usuário, ver OrigemFilter) não tem cashback de
        # verdade - não existe ninguém pra receber esse valor, mesmo o campo tendo um
        # número calculado guardado só de referência.
        if not obj.usuario_id:
            return "—"
        return obj.valor_cashback

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
            path(
                "analytics/resumo-financeiro/",
                self.admin_site.admin_view(self.resumo_financeiro_view),
                name="pedidos_resumo_financeiro",
            ),
            path(
                "analytics/resumo-financeiro/usuarios/",
                self.admin_site.admin_view(self.saldo_por_usuario_view),
                name="pedidos_saldo_por_usuario",
            ),
        ]
        return urls + super().get_urls()

    def _filtros_da_request(self, request):
        origem = request.GET.get("origem") or None
        if origem not in (ORIGEM_SITE, ORIGEM_FORA, ORIGEM_SEM_CADASTRO):
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
            "funil_sem_conta": obter_funil(data_inicio, data_fim),
            "cadastros_por_dia": obter_cadastros_por_dia(data_inicio, data_fim),
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
                    pedido.valor_cashback if pedido.usuario_id else Decimal("0"),
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

    def resumo_financeiro_view(self, request):
        meses_passados = _parse_inteiro(request.GET.get("meses_passados"), MESES_GRAFICO_SACADO_PADRAO)
        linha_disponivel = {
            "rotulo": "Disponível para saque",
            "eh_atual": False,
            "eh_projecao": False,
            "eh_disponivel": True,
            "valor": obter_saldo_disponivel(),
        }
        contexto = {
            **self.admin_site.each_context(request),
            "title": "Resumo financeiro",
            "grafico_sacado": obter_grafico_sacado(meses_passados),
            "tabela_liberado": [linha_disponivel, *obter_resumo_liberado()],
            "meses_passados": meses_passados,
        }
        return TemplateResponse(request, "admin/resumo_financeiro.html", contexto)

    def saldo_por_usuario_view(self, request):
        tipo = request.GET.get("tipo")
        if tipo not in ROTULOS_TIPO_SALDO:
            return redirect("admin:pedidos_resumo_financeiro")

        if tipo == "disponivel":
            contexto = {
                **self.admin_site.each_context(request),
                "title": f"Saldo por usuário — {ROTULOS_TIPO_SALDO[tipo]}",
                "linhas": obter_saldo_por_usuario(None, None, tipo),
                "rotulo_tipo": ROTULOS_TIPO_SALDO[tipo],
                "eh_acumulado": True,
            }
            return TemplateResponse(request, "admin/saldo_por_usuario.html", contexto)

        ano = _parse_inteiro(request.GET.get("ano"), None)
        mes = _parse_inteiro(request.GET.get("mes"), None)
        if not ano or not mes or not (1 <= mes <= 12):
            return redirect("admin:pedidos_resumo_financeiro")

        contexto = {
            **self.admin_site.each_context(request),
            "title": f"Saldo por usuário — {ROTULOS_TIPO_SALDO[tipo]} em {mes:02d}/{ano}",
            "linhas": obter_saldo_por_usuario(ano, mes, tipo),
            "rotulo_tipo": ROTULOS_TIPO_SALDO[tipo],
            "rotulo_mes": f"{mes:02d}/{ano}",
            "eh_acumulado": False,
        }
        return TemplateResponse(request, "admin/saldo_por_usuario.html", contexto)


# Página inicial e menu do admin por produto > assunto > tabela. Os botões de analytics e de
# comunicação por e-mail ficam embaixo de "Site Cash-B" (ver cashback_shopee/admin_grupos.py).
admin_grupos.instalar(admin.site)


class SituacaoReclamacaoFilter(admin.SimpleListFilter):
    """Abre direto nas que esperam decisão do admin (em análise)."""

    title = "situação"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return [*ReclamacaoPedido.STATUS_CHOICES, ("todas", "Todas")]

    def queryset(self, request, queryset):
        valor = self.value() or ReclamacaoPedido.STATUS_EM_ANALISE
        if valor == "todas":
            return queryset
        return queryset.filter(status=valor)

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            selecionado = self.value() == lookup or (
                self.value() is None and lookup == ReclamacaoPedido.STATUS_EM_ANALISE
            )
            yield {
                "selected": selecionado,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }


@admin.register(ReclamacaoPedido)
class ReclamacaoPedidoAdmin(admin.ModelAdmin):
    """Reclamações de compra não registrada (Fase 64). Compare o que a pessoa informou
    (data e produto) com o pedido encontrado e use a ação "Vincular" ou "Recusar".
    Para recusar com uma explicação própria, escreva no campo "Resposta pra pessoa"
    antes (abrindo a reclamação) e depois use a ação."""

    list_display = (
        "order_id",
        "usuario",
        "status",
        "data_informada",
        "data_real",
        "data_confere",
        "produto_informado",
        "produto_real",
        "valor_pedido",
        "cashback_se_vincular",
        "criado_em",
    )
    list_filter = (SituacaoReclamacaoFilter,)
    search_fields = ("order_id", "usuario__username", "usuario__email", "produto_informado")
    list_select_related = ("usuario", "pedido")
    readonly_fields = (
        "usuario", "order_id", "data_compra_informada", "produto_informado", "pedido",
        "status", "criado_em", "resolvido_em",
    )
    fields = readonly_fields[:6] + ("resposta",) + readonly_fields[6:]
    actions = ("acao_vincular", "acao_recusar")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Data informada", ordering="data_compra_informada")
    def data_informada(self, obj):
        return obj.data_compra_informada.strftime("%d/%m/%Y")

    @admin.display(description="Data real")
    def data_real(self, obj):
        if not obj.pedido or not obj.pedido.data_compra:
            return "—"
        return timezone.localtime(obj.pedido.data_compra).strftime("%d/%m/%Y")

    @admin.display(description="Data bate?", boolean=True)
    def data_confere(self, obj):
        if not obj.pedido or not obj.pedido.data_compra:
            return None
        dias = abs((timezone.localtime(obj.pedido.data_compra).date() - obj.data_compra_informada).days)
        return dias <= 1

    @admin.display(description="Produto real")
    def produto_real(self, obj):
        return obj.pedido.produto_nome if obj.pedido else "—"

    @admin.display(description="Valor do pedido")
    def valor_pedido(self, obj):
        return obj.pedido.valor_pedido if obj.pedido else "—"

    @admin.display(description="Cashback se vincular")
    def cashback_se_vincular(self, obj):
        if not obj.pedido or obj.pedido.usuario_id:
            return "—"
        return cashback_previsto(obj.pedido)

    @admin.action(description="Vincular pedido à conta de quem reclamou")
    def acao_vincular(self, request, queryset):
        feitas, erros = 0, []
        for reclamacao in queryset.select_related("usuario", "pedido"):
            try:
                vincular(reclamacao)
                feitas += 1
            except ReclamacaoInvalida as erro:
                erros.append(f"{reclamacao.order_id}: {erro}")
        if feitas:
            self.message_user(request, f"{feitas} pedido(s) vinculado(s). A pessoa recebe um e-mail.")
        for erro in erros:
            self.message_user(request, erro, level=messages.WARNING)

    @admin.action(description="Recusar (avisa a pessoa)")
    def acao_recusar(self, request, queryset):
        feitas, erros = 0, []
        for reclamacao in queryset.select_related("usuario"):
            try:
                recusar(reclamacao, reclamacao.resposta)
                feitas += 1
            except ReclamacaoInvalida as erro:
                erros.append(f"{reclamacao.order_id}: {erro}")
        if feitas:
            self.message_user(request, f"{feitas} reclamação(ões) recusada(s).")
        for erro in erros:
            self.message_user(request, erro, level=messages.WARNING)
