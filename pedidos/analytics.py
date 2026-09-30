from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Case, Count, DecimalField, F, Q, QuerySet, Sum, Value, When
from django.db.models.functions import ExtractMonth, ExtractYear, TruncDate
from django.utils import timezone

from accounts.models import Indicacao
from links.models import Click
from saques.models import Saque

from .models import Pedido

# Pedido sem usuário ("Fora do site" - importado da conta de afiliado Shopee sem ter
# sido gerado por um link daqui, ver OrigemFilter/origem_detalhada abaixo) não tem
# cashback de verdade pra mostrar/somar em lugar nenhum do admin - não existe ninguém
# pra receber esse valor, por mais que o campo valor_cashback tenha um número
# calculado (guardado só de referência). Essa expressão zera esse valor em qualquer
# agregação (Sum) sem precisar filtrar o queryset inteiro - assim comissão/contagem de
# pedidos continuam contando esses pedidos normalmente (a comissão é real, a Shopee
# pagou), só o cashback que fica de fora.
CASHBACK_REAL = Case(
    When(usuario__isnull=True, then=Value(Decimal("0"))),
    default=F("valor_cashback"),
    output_field=DecimalField(max_digits=10, decimal_places=2),
)

ORIGEM_DETALHADA_LABELS = {
    Click.TIPO_PRODUTO: "Link direto",
    Click.TIPO_VITRINE: "Vitrine de ofertas",
    Click.TIPO_HOME: "Venda indireta (Ir pra Shopee)",
}


def origem_detalhada(pedido: Pedido) -> str:
    """Rótulo de origem por pedido - distingue conversão de link direto, clique num
    card da vitrine de ofertas e venda indireta (botão "Ir pra Shopee"), além do caso
    sem Click (pedido não gerado por aqui - ver OrigemFilter em pedidos/admin.py)."""
    if not pedido.click:
        return "Fora do site"
    return ORIGEM_DETALHADA_LABELS.get(pedido.click.tipo, pedido.click.tipo)

FORMATO_MOEDA = '"R$" #,##0.00'
FORMATO_DATA = "dd/mm/yyyy hh:mm"
# "%" sem aspas faz o Excel multiplicar o valor por 100 (formato nativo de percentual,
# pensado pra frações tipo 0.5). Nosso percentual já vem calculado (ex: 170.6), então
# precisa do símbolo entre aspas - texto literal, sem a multiplicação automática.
FORMATO_PERCENTUAL = '0.0"%"'


def _no_periodo(queryset: QuerySet, campo_data: str, data_inicio, data_fim) -> QuerySet:
    if data_inicio:
        queryset = queryset.filter(**{f"{campo_data}__date__gte": data_inicio})
    if data_fim:
        queryset = queryset.filter(**{f"{campo_data}__date__lte": data_fim})
    return queryset


ORIGEM_SITE = "site"
ORIGEM_FORA = "fora"


def obter_pedidos_filtrados(data_inicio=None, data_fim=None, status=None, origem=None) -> QuerySet:
    """Pedidos filtrados por período (via data_compra), status e origem - base
    compartilhada entre a tela de analytics e as exportações, pra manter tudo batendo.

    "origem" distingue pedidos gerados por aqui (têm um Click vinculado, geram cashback
    de verdade pra um usuário) dos que sobram sem Click - outras campanhas, compras
    pessoais etc. (ver pedidos/admin.py::OrigemFilter) - continuam guardados no banco
    com um valor_cashback calculado, mas não são pagos a ninguém de verdade."""
    pedidos = _no_periodo(Pedido.objects.all(), "data_compra", data_inicio, data_fim)
    if status:
        pedidos = pedidos.filter(status=status)
    if origem == ORIGEM_SITE:
        pedidos = pedidos.filter(click__isnull=False)
    elif origem == ORIGEM_FORA:
        pedidos = pedidos.filter(click__isnull=True)
    return pedidos


def obter_analytics(data_inicio=None, data_fim=None, status=None, origem=None) -> dict:
    """Agrega os números do negócio pro período/status/origem informado - usado pela
    tela /admin/pedidos/pedido/analytics/. Cada bloco filtra pela sua própria data
    "natural" (pedido por data_compra, saque por criado_em, indicação por criado_em,
    usuário por date_joined), porque não faz sentido contar, por exemplo, um saque
    solicitado fora do período só porque o pedido que originou aquele cashback foi
    comprado dentro dele. O filtro de origem só se aplica aos pedidos - saques,
    indicações e novos usuários não têm essa distinção.
    """
    pedidos = obter_pedidos_filtrados(data_inicio, data_fim, status, origem)

    totais_pedidos = pedidos.aggregate(
        total_comissao=Sum("valor_comissao"), total_cashback=Sum(CASHBACK_REAL), total=Count("id")
    )
    total_comissao = totais_pedidos["total_comissao"] or Decimal("0")
    total_cashback = totais_pedidos["total_cashback"] or Decimal("0")
    total_pedidos = totais_pedidos["total"] or 0

    por_status_bruto = {
        linha["status"]: linha
        for linha in pedidos.values("status").annotate(
            total=Count("id"), comissao=Sum("valor_comissao"), cashback=Sum(CASHBACK_REAL)
        )
    }
    resumo_status = [
        {
            "status": chave,
            "status_label": label,
            "total": (por_status_bruto.get(chave) or {}).get("total") or 0,
            "comissao": (por_status_bruto.get(chave) or {}).get("comissao") or Decimal("0"),
            "cashback": (por_status_bruto.get(chave) or {}).get("cashback") or Decimal("0"),
        }
        for chave, label in Pedido.STATUS_CHOICES
    ]
    cashback_por_status = {linha["status"]: linha["cashback"] for linha in resumo_status}

    saques = _no_periodo(Saque.objects.all(), "criado_em", data_inicio, data_fim)
    totais_saques = saques.aggregate(total_valor=Sum("valor"), total=Count("id"))
    saques_por_status_bruto = {
        linha["status"]: linha
        for linha in saques.values("status").annotate(total=Count("id"), valor=Sum("valor"))
    }
    saques_por_status = [
        {
            "status": chave,
            "status_label": label,
            "total": (saques_por_status_bruto.get(chave) or {}).get("total") or 0,
            "valor": (saques_por_status_bruto.get(chave) or {}).get("valor") or Decimal("0"),
        }
        for chave, label in Saque.STATUS_CHOICES
    ]

    indicacoes = _no_periodo(Indicacao.objects.all(), "criado_em", data_inicio, data_fim)
    total_indicacoes = indicacoes.count()
    indicacoes_concluidas = indicacoes.filter(pedido_bonus_indicador__isnull=False).count()
    ranking_indicadores = list(
        indicacoes.values("indicador__username")
        .annotate(
            total_indicacoes=Count("id"),
            concluidas=Count("id", filter=Q(pedido_bonus_indicador__isnull=False)),
        )
        .order_by("-total_indicacoes", "-concluidas")[:20]
    )

    novos_usuarios = _no_periodo(get_user_model().objects.all(), "date_joined", data_inicio, data_fim).count()

    return {
        "total_comissao": total_comissao,
        "total_cashback": total_cashback,
        "total_pedidos": total_pedidos,
        "margem_retida": total_comissao - total_cashback,
        "percentual_repassado": (total_cashback / total_comissao * 100) if total_comissao else Decimal("0"),
        "ticket_medio_cashback": (total_cashback / total_pedidos) if total_pedidos else Decimal("0"),
        "resumo_status": resumo_status,
        "saldo_a_liberar": cashback_por_status.get(Pedido.STATUS_PENDENTE, Decimal("0"))
        + cashback_por_status.get(Pedido.STATUS_VALIDADO, Decimal("0")),
        "saldo_liberado": cashback_por_status.get(Pedido.STATUS_LIBERADO, Decimal("0")),
        "total_saques_valor": totais_saques["total_valor"] or Decimal("0"),
        "total_saques": totais_saques["total"] or 0,
        "saques_por_status": saques_por_status,
        "total_indicacoes": total_indicacoes,
        "indicacoes_concluidas": indicacoes_concluidas,
        "ranking_indicadores": ranking_indicadores,
        "novos_usuarios": novos_usuarios,
    }


DIAS_PADRAO_SERIE_DIARIA = 30
DIAS_MAXIMO_SERIE_DIARIA = 180  # evita um gráfico com centenas/milhares de pontos se alguém filtrar anos

INDICADORES_SERIE_DIARIA = {
    "pedidos": "Pedidos (quantidade)",
    "comissao": "Comissão total (R$)",
    "cashback": "Cashback repassado (R$)",
    "novos_usuarios": "Novos usuários",
    "saques_quantidade": "Saques (quantidade)",
    "saques_valor": "Valor sacado (R$)",
    "indicacoes": "Indicações",
}


def obter_serie_diaria(data_inicio=None, data_fim=None, status=None, origem=None) -> dict:
    """Série dia a dia de cada indicador em INDICADORES_SERIE_DIARIA, pro gráfico de
    linha da tela de analytics - o usuário escolhe qual indicador ver, e o próprio
    JavaScript troca a linha exibida sem precisar recarregar a página (todas as séries
    já vêm calculadas de uma vez).

    Sempre limitado a um período (por padrão, os últimos DIAS_PADRAO_SERIE_DIARIA dias
    até hoje, se nenhuma data foi escolhida no filtro principal da tela) - sem isso o
    gráfico teria um ponto por dia desde o primeiro pedido, o que não cabe legível numa
    tela. Um período escolhido maior que DIAS_MAXIMO_SERIE_DIARIA é recortado pro fim
    dele, pelo mesmo motivo (os cards/tabelas continuam mostrando o total do período
    inteiro normalmente - só o gráfico é limitado).
    """
    fim = data_fim or timezone.localdate()
    inicio = data_inicio or (fim - timedelta(days=DIAS_PADRAO_SERIE_DIARIA - 1))
    if (fim - inicio).days >= DIAS_MAXIMO_SERIE_DIARIA:
        inicio = fim - timedelta(days=DIAS_MAXIMO_SERIE_DIARIA - 1)

    dias = [inicio + timedelta(days=deslocamento) for deslocamento in range((fim - inicio).days + 1)]

    pedidos = obter_pedidos_filtrados(inicio, fim, status, origem)
    pedidos_por_dia = {
        linha["dia"]: linha
        for linha in pedidos.annotate(dia=TruncDate("data_compra"))
        .values("dia")
        .annotate(total=Count("id"), comissao=Sum("valor_comissao"), cashback=Sum(CASHBACK_REAL))
    }

    saques = _no_periodo(Saque.objects.all(), "criado_em", inicio, fim)
    saques_por_dia = {
        linha["dia"]: linha
        for linha in saques.annotate(dia=TruncDate("criado_em")).values("dia").annotate(total=Count("id"), valor=Sum("valor"))
    }

    indicacoes = _no_periodo(Indicacao.objects.all(), "criado_em", inicio, fim)
    indicacoes_por_dia = {
        linha["dia"]: linha["total"]
        for linha in indicacoes.annotate(dia=TruncDate("criado_em")).values("dia").annotate(total=Count("id"))
    }

    usuarios = _no_periodo(get_user_model().objects.all(), "date_joined", inicio, fim)
    usuarios_por_dia = {
        linha["dia"]: linha["total"]
        for linha in usuarios.annotate(dia=TruncDate("date_joined")).values("dia").annotate(total=Count("id"))
    }

    series = {chave: [] for chave in INDICADORES_SERIE_DIARIA}
    for dia in dias:
        pedido_do_dia = pedidos_por_dia.get(dia)
        saque_do_dia = saques_por_dia.get(dia)
        series["pedidos"].append(pedido_do_dia["total"] if pedido_do_dia else 0)
        series["comissao"].append(float(pedido_do_dia["comissao"] or 0) if pedido_do_dia else 0)
        series["cashback"].append(float(pedido_do_dia["cashback"] or 0) if pedido_do_dia else 0)
        series["novos_usuarios"].append(usuarios_por_dia.get(dia, 0))
        series["saques_quantidade"].append(saque_do_dia["total"] if saque_do_dia else 0)
        series["saques_valor"].append(float(saque_do_dia["valor"] or 0) if saque_do_dia else 0)
        series["indicacoes"].append(indicacoes_por_dia.get(dia, 0))

    return {
        "rotulos": [dia.strftime("%d/%m") for dia in dias],
        "series": series,
    }


def gerar_planilha_analytics(data_inicio=None, data_fim=None, status=None, origem=None):
    """Gera a planilha (.xlsx) de analytics já formatada - mesma base de dados de
    obter_analytics()/obter_pedidos_filtrados(), pra bater exatamente com o que a tela
    mostra. Import do openpyxl fica dentro da função de propósito: só é usado aqui, não
    precisa pagar esse custo de import em todo o resto do admin."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    dados = obter_analytics(data_inicio, data_fim, status, origem)
    pedidos = (
        obter_pedidos_filtrados(data_inicio, data_fim, status, origem)
        .select_related("usuario", "click")
        .order_by("-data_compra")
    )

    fonte_titulo = Font(bold=True, size=14)
    fonte_subtitulo = Font(italic=True, color="666666")
    fonte_secao = Font(bold=True, size=12)
    fonte_cabecalho = Font(bold=True, color="FFFFFF")
    preenchimento_cabecalho = PatternFill("solid", fgColor="205067")

    def escrever_cabecalho(planilha, linha, coluna_inicial, titulos):
        for deslocamento, titulo in enumerate(titulos):
            celula = planilha.cell(row=linha, column=coluna_inicial + deslocamento, value=titulo)
            celula.font = fonte_cabecalho
            celula.fill = preenchimento_cabecalho
        return linha + 1

    def definir_larguras(planilha, valores):
        for indice, valor in enumerate(valores, start=1):
            planilha.column_dimensions[get_column_letter(indice)].width = valor

    livro = Workbook()

    resumo = livro.active
    resumo.title = "Resumo"
    definir_larguras(resumo, [32, 16, 16, 16])
    resumo["A1"] = "Analytics — cash-b"
    resumo["A1"].font = fonte_titulo
    periodo = "{} a {}".format(
        data_inicio.strftime("%d/%m/%Y") if data_inicio else "—",
        data_fim.strftime("%d/%m/%Y") if data_fim else "—",
    )
    status_label = dict(Pedido.STATUS_CHOICES).get(status, "todos") if status else "todos"
    origem_label = {ORIGEM_SITE: "gerados no site", ORIGEM_FORA: "fora do site"}.get(origem, "todos")
    resumo["A2"] = f"Período: {periodo}  ·  Status do pedido: {status_label}  ·  Origem: {origem_label}"
    resumo["A2"].font = fonte_subtitulo

    linha = 4
    resumo.cell(row=linha, column=1, value="Indicadores gerais").font = fonte_secao
    linha += 1
    linha = escrever_cabecalho(resumo, linha, 1, ["Indicador", "Valor"])
    kpis = [
        ("Comissão total", dados["total_comissao"], FORMATO_MOEDA),
        ("Cashback repassado", dados["total_cashback"], FORMATO_MOEDA),
        ("Margem retida", dados["margem_retida"], FORMATO_MOEDA),
        ("% da comissão repassado", dados["percentual_repassado"], FORMATO_PERCENTUAL),
        ("Total de pedidos", dados["total_pedidos"], "0"),
        ("Ticket médio de cashback", dados["ticket_medio_cashback"], FORMATO_MOEDA),
        ("Saldo a liberar (pendente + validado)", dados["saldo_a_liberar"], FORMATO_MOEDA),
        ("Saldo liberado", dados["saldo_liberado"], FORMATO_MOEDA),
        ("Total sacado", dados["total_saques_valor"], FORMATO_MOEDA),
        ("Nº de saques no período", dados["total_saques"], "0"),
        ("Novos usuários no período", dados["novos_usuarios"], "0"),
        ("Indicações no período", dados["total_indicacoes"], "0"),
        ("Indicações concluídas (dobro pago)", dados["indicacoes_concluidas"], "0"),
    ]
    for rotulo, valor, formato in kpis:
        resumo.cell(row=linha, column=1, value=rotulo)
        resumo.cell(row=linha, column=2, value=valor).number_format = formato
        linha += 1

    linha += 2
    resumo.cell(row=linha, column=1, value="Pedidos por status").font = fonte_secao
    linha += 1
    linha = escrever_cabecalho(resumo, linha, 1, ["Status", "Pedidos", "Comissão", "Cashback"])
    for item in dados["resumo_status"]:
        resumo.cell(row=linha, column=1, value=item["status_label"])
        resumo.cell(row=linha, column=2, value=item["total"])
        resumo.cell(row=linha, column=3, value=item["comissao"]).number_format = FORMATO_MOEDA
        resumo.cell(row=linha, column=4, value=item["cashback"]).number_format = FORMATO_MOEDA
        linha += 1

    linha += 2
    resumo.cell(row=linha, column=1, value="Saques por status").font = fonte_secao
    linha += 1
    linha = escrever_cabecalho(resumo, linha, 1, ["Status", "Saques", "Valor"])
    for item in dados["saques_por_status"]:
        resumo.cell(row=linha, column=1, value=item["status_label"])
        resumo.cell(row=linha, column=2, value=item["total"])
        resumo.cell(row=linha, column=3, value=item["valor"]).number_format = FORMATO_MOEDA
        linha += 1

    linha += 2
    resumo.cell(row=linha, column=1, value="Ranking de indicadores").font = fonte_secao
    linha += 1
    if dados["ranking_indicadores"]:
        linha = escrever_cabecalho(resumo, linha, 1, ["Usuário", "Indicações", "Concluídas"])
        for item in dados["ranking_indicadores"]:
            resumo.cell(row=linha, column=1, value=item["indicador__username"])
            resumo.cell(row=linha, column=2, value=item["total_indicacoes"])
            resumo.cell(row=linha, column=3, value=item["concluidas"])
            linha += 1
    else:
        resumo.cell(row=linha, column=1, value="Nenhuma indicação no período filtrado.")

    aba_pedidos = livro.create_sheet("Pedidos")
    definir_larguras(aba_pedidos, [22, 20, 22, 14, 14, 14, 14, 20, 20, 20])
    escrever_cabecalho(
        aba_pedidos,
        1,
        1,
        [
            "Order ID",
            "Usuário",
            "Origem",
            "Status",
            "Valor do pedido",
            "Comissão",
            "Cashback",
            "Data da compra",
            "Data de validação",
            "Data de liberação",
        ],
    )
    aba_pedidos.freeze_panes = "A2"
    linha = 2
    for pedido in pedidos.iterator():
        aba_pedidos.cell(row=linha, column=1, value=pedido.order_id)
        aba_pedidos.cell(row=linha, column=2, value=pedido.usuario.username if pedido.usuario else "")
        aba_pedidos.cell(row=linha, column=3, value=origem_detalhada(pedido))
        aba_pedidos.cell(row=linha, column=4, value=pedido.get_status_display())
        aba_pedidos.cell(row=linha, column=5, value=pedido.valor_pedido).number_format = FORMATO_MOEDA
        aba_pedidos.cell(row=linha, column=6, value=pedido.valor_comissao).number_format = FORMATO_MOEDA
        cashback_exibido = pedido.valor_cashback if pedido.usuario_id else Decimal("0")
        aba_pedidos.cell(row=linha, column=7, value=cashback_exibido).number_format = FORMATO_MOEDA
        for coluna, valor_data in ((8, pedido.data_compra), (9, pedido.data_validacao), (10, pedido.data_liberacao)):
            # Excel não aceita datetime com timezone - convertemos pro horário local e
            # removemos o tzinfo antes de escrever na célula.
            if valor_data:
                celula = aba_pedidos.cell(row=linha, column=coluna, value=timezone.localtime(valor_data).replace(tzinfo=None))
                celula.number_format = FORMATO_DATA
        linha += 1

    return livro


MESES_GRAFICO_SACADO_PADRAO = 6
MESES_GRAFICO_SACADO_MAXIMO = 24

# Rótulos dos "tipo" aceitos por obter_saldo_por_usuario - usado tanto pra validar o
# parâmetro quanto pro título da tela (ver pedidos/admin.py::saldo_por_usuario_view).
ROTULOS_TIPO_SALDO = {
    "liberado": "Liberado",
    "projecao": "Projeção de liberação",
    "pago": "Pago (saques)",
}


def _somar_meses(ano: int, mes: int, delta: int) -> tuple[int, int]:
    total = mes - 1 + delta
    return ano + total // 12, total % 12 + 1


def _limites_do_mes_datetime(ano: int, mes: int) -> tuple[datetime, datetime]:
    """Início (inclusive) e fim (exclusivo) de 1 mês como datetime com timezone - pra
    filtrar campo DateTimeField (data_compra, data_liberacao, pago_em) sem disparar o
    RuntimeWarning de "naive datetime" do Django (mesmo só filtrando, não salvando)."""
    inicio = timezone.make_aware(datetime(ano, mes, 1))
    ano_seguinte, mes_seguinte = _somar_meses(ano, mes, 1)
    fim = timezone.make_aware(datetime(ano_seguinte, mes_seguinte, 1))
    return inicio, fim


def _limites_do_mes_date(ano: int, mes: int) -> tuple[date, date]:
    """Igual acima, mas em date puro - pra filtrar data_prevista_liberacao (DateField,
    sem timezone)."""
    ano_seguinte, mes_seguinte = _somar_meses(ano, mes, 1)
    return date(ano, mes, 1), date(ano_seguinte, mes_seguinte, 1)


def obter_grafico_sacado(meses_passados: int = MESES_GRAFICO_SACADO_PADRAO) -> list[dict]:
    """Valor sacado (Saque pago, por Saque.pago_em) por mês - últimos N meses até o mês
    atual (não existe "saque futuro" pra projetar, diferente do saldo liberado). Usado
    no gráfico de barras da tela de Resumo financeiro."""
    meses_passados = max(0, min(meses_passados, MESES_GRAFICO_SACADO_MAXIMO))
    hoje = timezone.localdate()
    meses = [_somar_meses(hoje.year, hoje.month, delta) for delta in range(-meses_passados, 1)]

    inicio, _ = _limites_do_mes_datetime(*meses[0])
    _, fim = _limites_do_mes_datetime(hoje.year, hoje.month)

    agregados = {
        (linha["ano"], linha["mes"]): linha["total"] or Decimal("0")
        for linha in (
            Saque.objects.filter(status=Saque.STATUS_PAGO, pago_em__gte=inicio, pago_em__lt=fim)
            .annotate(ano=ExtractYear("pago_em"), mes=ExtractMonth("pago_em"))
            .values("ano", "mes")
            .annotate(total=Sum("valor"))
        )
    }
    return [
        {
            "ano": ano, "mes": mes, "rotulo": date(ano, mes, 1).strftime("%m/%Y"),
            "valor": agregados.get((ano, mes), Decimal("0")),
        }
        for ano, mes in meses
    ]


def obter_resumo_liberado() -> list[dict]:
    """Saldo liberado dos próximos 3 meses (mês atual + 2 à frente) - a tabela da tela
    de Resumo financeiro. Mês atual é o saldo real (já processado pelo comando
    liberar_saldo); os 2 meses seguintes são uma projeção, somando:
    - validado: usa data_prevista_liberacao (mês da validação + 2 - a regra de
      verdade, ver pedidos/services.py::calcular_data_prevista_liberacao) - cai
      certinho num dos 2 meses futuros.
    - pendente: ainda não tem data de validação real (só a Shopee confirma depois),
      então projeta otimisticamente a partir da data da compra (mês da compra + 2,
      mesma regra do validado) - é uma estimativa, não uma certeza.
    Pedido sem usuário ("Fora do site") nunca conta - não tem cashback de verdade."""
    hoje = timezone.localdate()
    mes_atual = (hoje.year, hoje.month)
    mes_mais_1 = _somar_meses(hoje.year, hoje.month, 1)
    mes_mais_2 = _somar_meses(hoje.year, hoje.month, 2)
    meses_futuros = {mes_mais_1, mes_mais_2}

    inicio_atual, fim_atual = _limites_do_mes_datetime(*mes_atual)
    liberado_real = (
        Pedido.objects.filter(
            status=Pedido.STATUS_LIBERADO, data_liberacao__gte=inicio_atual, data_liberacao__lt=fim_atual
        )
        .exclude(usuario__isnull=True)
        .aggregate(total=Sum("valor_cashback"))["total"]
    ) or Decimal("0")

    valores = {mes_atual: liberado_real, mes_mais_1: Decimal("0"), mes_mais_2: Decimal("0")}

    for linha in (
        Pedido.objects.filter(status=Pedido.STATUS_VALIDADO)
        .exclude(usuario__isnull=True)
        .annotate(ano=ExtractYear("data_prevista_liberacao"), mes=ExtractMonth("data_prevista_liberacao"))
        .values("ano", "mes")
        .annotate(total=Sum("valor_cashback"))
    ):
        chave = (linha["ano"], linha["mes"])
        if chave in meses_futuros:
            valores[chave] += linha["total"] or Decimal("0")

    for linha in (
        Pedido.objects.filter(status=Pedido.STATUS_PENDENTE)
        .exclude(usuario__isnull=True)
        .annotate(ano=ExtractYear("data_compra"), mes=ExtractMonth("data_compra"))
        .values("ano", "mes")
        .annotate(total=Sum("valor_cashback"))
    ):
        chave_projetada = _somar_meses(linha["ano"], linha["mes"], 2)
        if chave_projetada in meses_futuros:
            valores[chave_projetada] += linha["total"] or Decimal("0")

    return [
        {
            "ano": ano, "mes": mes, "rotulo": date(ano, mes, 1).strftime("%m/%Y"),
            "eh_atual": (ano, mes) == mes_atual, "eh_projecao": (ano, mes) != mes_atual,
            "valor": valores[(ano, mes)],
        }
        for ano, mes in [mes_atual, mes_mais_1, mes_mais_2]
    ]


def obter_saldo_por_usuario(ano: int, mes: int, tipo: str) -> list[dict]:
    """Quebra por usuário de 1 valor da tela de Resumo financeiro:
    - "liberado": saldo real do mês atual (mesma consulta de obter_resumo_liberado).
    - "projecao": meses futuros - combina pendente (projetado por data_compra + 2) e
      validado (por data_prevista_liberacao) do mesmo jeito que obter_resumo_liberado.
    - "pago": 1 barra do gráfico de saques pagos.
    Sempre ordenado do maior pro menor - útil pra achar quem já tem saldo suficiente
    pra sacar escondido dentro de um total agregado."""
    if tipo == "liberado":
        inicio, fim = _limites_do_mes_datetime(ano, mes)
        agregados = (
            Pedido.objects.filter(status=Pedido.STATUS_LIBERADO, data_liberacao__gte=inicio, data_liberacao__lt=fim)
            .exclude(usuario__isnull=True)
            .values("usuario_id", "usuario__username")
            .annotate(total=Sum("valor_cashback"))
        )
    elif tipo == "pago":
        inicio, fim = _limites_do_mes_datetime(ano, mes)
        agregados = (
            Saque.objects.filter(status=Saque.STATUS_PAGO, pago_em__gte=inicio, pago_em__lt=fim)
            .values("usuario_id", "usuario__username")
            .annotate(total=Sum("valor"))
        )
    elif tipo == "projecao":
        ano_compra, mes_compra = _somar_meses(ano, mes, -2)
        inicio_compra, fim_compra = _limites_do_mes_datetime(ano_compra, mes_compra)
        inicio_prevista, fim_prevista = _limites_do_mes_date(ano, mes)

        pendentes = (
            Pedido.objects.filter(
                status=Pedido.STATUS_PENDENTE, data_compra__gte=inicio_compra, data_compra__lt=fim_compra
            )
            .exclude(usuario__isnull=True)
            .values("usuario_id", "usuario__username")
            .annotate(total=Sum("valor_cashback"))
        )
        validados = (
            Pedido.objects.filter(
                status=Pedido.STATUS_VALIDADO,
                data_prevista_liberacao__gte=inicio_prevista, data_prevista_liberacao__lt=fim_prevista,
            )
            .exclude(usuario__isnull=True)
            .values("usuario_id", "usuario__username")
            .annotate(total=Sum("valor_cashback"))
        )
        combinados: dict = {}
        for linha in list(pendentes) + list(validados):
            chave = linha["usuario_id"]
            acumulado = combinados.setdefault(
                chave, {"usuario_id": chave, "username": linha["usuario__username"], "total": Decimal("0")}
            )
            acumulado["total"] += linha["total"] or Decimal("0")
        return sorted(combinados.values(), key=lambda linha: linha["total"], reverse=True)
    else:
        return []

    return sorted(
        (
            {
                "usuario_id": linha["usuario_id"], "username": linha["usuario__username"],
                "total": linha["total"] or Decimal("0"),
            }
            for linha in agregados
        ),
        key=lambda linha: linha["total"], reverse=True,
    )
