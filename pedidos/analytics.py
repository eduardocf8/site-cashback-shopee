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


MESES_PASSADOS_PADRAO = 6
MESES_FUTUROS_PADRAO = 2
MESES_PASSADOS_MAXIMO = 24
MESES_FUTUROS_MAXIMO = 12


def _somar_meses(ano: int, mes: int, delta: int) -> tuple[int, int]:
    total = mes - 1 + delta
    return ano + total // 12, total % 12 + 1


# Config compartilhada entre obter_saldos_por_mes (agregado por mês) e
# obter_saldo_por_usuario (quebra de 1 mês+tipo por usuário, ver tela de Saldos por
# mês) - fonte única de verdade de qual campo de data/valor cada "tipo" usa, pra não
# duplicar (e arriscar desalinhar) essa regra em 2 lugares.
#
# Cada status usa a data que faz sentido "financeiramente" pra ele, não sempre
# data_compra - é esse detalhe que faz a projeção futura funcionar:
# - pendente/cancelado: data_compra (ainda não têm previsão de liberação nenhuma).
# - validado: data_prevista_liberacao - é a projeção em si (mês da validação + 2, ver
#   pedidos/services.py::calcular_data_prevista_liberacao), geralmente caindo nos
#   próximos 1-2 meses (por isso aparece nos meses futuros mesmo sem compra nova).
# - liberado: data_liberacao (quando o comando liberar_saldo realmente processou).
# - pago: não é status de Pedido, é Saque (status pago, por Saque.pago_em) - o saldo
#   que de fato SAIU via Pix, depois do usuário pedir o saque.
#
# Todo tipo baseado em Pedido exclui quem não tem usuário vinculado ("Fora do site" -
# ver OrigemFilter/origem_detalhada em pedidos/admin.py: pedido importado da conta de
# afiliado Shopee sem ter sido gerado por um link daqui, então usuario=None desde a
# sincronização - ver pedidos/services.py). Sem esse exclude, esse valor entrava no
# total agregado mas sumia na quebra por usuário (que exclui usuario=None, já que não
# pertence a ninguém) - o total parecia ter "gente escondida" que não existia.
def _pedidos(status):
    return Pedido.objects.filter(status=status).exclude(usuario__isnull=True)


TIPOS_SALDO = {
    "pendente": {
        "queryset": lambda: _pedidos(Pedido.STATUS_PENDENTE),
        "campo_data": "data_compra",
        "campo_valor": "valor_cashback",
        "rotulo": "Pendente",
    },
    "validado_previsto": {
        "queryset": lambda: _pedidos(Pedido.STATUS_VALIDADO),
        "campo_data": "data_prevista_liberacao",
        "campo_valor": "valor_cashback",
        "rotulo": "Validado",
    },
    "liberado": {
        "queryset": lambda: _pedidos(Pedido.STATUS_LIBERADO),
        "campo_data": "data_liberacao",
        "campo_valor": "valor_cashback",
        "rotulo": "Liberado",
    },
    "cancelado": {
        "queryset": lambda: _pedidos(Pedido.STATUS_CANCELADO),
        "campo_data": "data_compra",
        "campo_valor": "valor_cashback",
        "rotulo": "Cancelado",
    },
    "pago": {
        "queryset": lambda: Saque.objects.filter(status=Saque.STATUS_PAGO),
        "campo_data": "pago_em",
        "campo_valor": "valor",
        "rotulo": "Pago (saques)",
    },
}

# data_prevista_liberacao é DateField (sem timezone) - único campo aqui que não precisa
# virar datetime com timezone antes de filtrar (os outros são DateTimeField; passar
# date puro ali funciona, mas dispara RuntimeWarning do Django de "naive datetime" -
# mesmo só filtrando, não salvando).
CAMPO_SEM_TIMEZONE = "data_prevista_liberacao"


def obter_saldos_por_mes(meses_passados: int = MESES_PASSADOS_PADRAO, meses_futuros: int = MESES_FUTUROS_PADRAO) -> list[dict]:
    """Saldo de cashback por mês, separado por tipo (ver TIPOS_SALDO) - pensado pra
    planejamento de caixa: um pedido validado só vira liberado (disponível pro usuário
    sacar) 2 meses depois da validação, então os próximos meses já têm uma previsão
    real de quanto vai ser preciso ter disponível, mesmo sem nenhuma compra nova
    acontecer nesse meio tempo.

    "pago" não entra na soma de "total" (que é só o fluxo de Pedido) pra não contar a
    mesma grana 2x - dinheiro liberado que depois é sacado aparece em "liberado" no mês
    da liberação E em "pago" no mês (possivelmente diferente, quase sempre posterior)
    em que o saque foi efetivamente pago.
    """
    meses_passados = max(0, min(meses_passados, MESES_PASSADOS_MAXIMO))
    meses_futuros = max(0, min(meses_futuros, MESES_FUTUROS_MAXIMO))

    hoje = timezone.localdate()
    meses = [_somar_meses(hoje.year, hoje.month, delta) for delta in range(-meses_passados, meses_futuros + 1)]

    data_minima = date(meses[0][0], meses[0][1], 1)
    ano_limite, mes_limite = _somar_meses(meses[-1][0], meses[-1][1], 1)
    data_limite = date(ano_limite, mes_limite, 1)  # exclusiva - 1º dia do mês seguinte ao último

    datetime_minimo = timezone.make_aware(datetime.combine(data_minima - timedelta(days=1), datetime.min.time()))
    datetime_maximo = timezone.make_aware(datetime.combine(data_limite + timedelta(days=1), datetime.min.time()))

    linhas = {
        (ano, mes): {
            "ano": ano,
            "mes": mes,
            "rotulo": date(ano, mes, 1).strftime("%m/%Y"),
            "eh_atual": (ano, mes) == (hoje.year, hoje.month),
            "eh_futuro": (ano, mes) > (hoje.year, hoje.month),
            **{chave: Decimal("0") for chave in TIPOS_SALDO},
        }
        for ano, mes in meses
    }

    for chave, config in TIPOS_SALDO.items():
        campo_data = config["campo_data"]
        if campo_data == CAMPO_SEM_TIMEZONE:
            limite_inicio, limite_fim = data_minima - timedelta(days=1), data_limite + timedelta(days=1)
        else:
            limite_inicio, limite_fim = datetime_minimo, datetime_maximo

        # limite_inicio/limite_fim só delimitam a consulta (com folga de 1 dia) - quem
        # realmente decide o mês de cada linha é o Extract abaixo, que já usa o fuso
        # local (ver settings.TIME_ZONE).
        agregados = (
            config["queryset"]()
            .filter(**{f"{campo_data}__gte": limite_inicio, f"{campo_data}__lt": limite_fim})
            .annotate(ano=ExtractYear(campo_data), mes=ExtractMonth(campo_data))
            .values("ano", "mes")
            .annotate(total=Sum(config["campo_valor"]))
        )
        for linha in agregados:
            chave_mes = (linha["ano"], linha["mes"])
            if chave_mes in linhas:
                linhas[chave_mes][chave] = linha["total"] or Decimal("0")

    linhas_ordenadas = [linhas[chave] for chave in meses]
    for linha in linhas_ordenadas:
        linha["total"] = linha["pendente"] + linha["validado_previsto"] + linha["liberado"] + linha["cancelado"]
    return linhas_ordenadas


def obter_saldo_por_usuario(ano: int, mes: int, tipo: str) -> list[dict]:
    """Quebra o saldo de 1 mês+tipo (1 célula da tela de Saldos por mês) por usuário -
    responde "desse total, quanto é de cada pessoa", útil pra achar quem já tem saldo
    suficiente pra sacar escondido dentro de um total agregado."""
    config = TIPOS_SALDO.get(tipo)
    if not config:
        return []

    campo_data = config["campo_data"]
    inicio_mes = date(ano, mes, 1)
    ano_seguinte, mes_seguinte = _somar_meses(ano, mes, 1)
    fim_mes = date(ano_seguinte, mes_seguinte, 1)

    if campo_data == CAMPO_SEM_TIMEZONE:
        limite_inicio, limite_fim = inicio_mes, fim_mes
    else:
        limite_inicio = timezone.make_aware(datetime.combine(inicio_mes, datetime.min.time()))
        limite_fim = timezone.make_aware(datetime.combine(fim_mes, datetime.min.time()))

    agregados = (
        config["queryset"]()
        .filter(**{f"{campo_data}__gte": limite_inicio, f"{campo_data}__lt": limite_fim})
        .values("usuario_id", "usuario__username")
        .annotate(total=Sum(config["campo_valor"]))
        .order_by("-total")
    )
    return [
        {"usuario_id": linha["usuario_id"], "username": linha["usuario__username"], "total": linha["total"] or Decimal("0")}
        for linha in agregados
    ]
