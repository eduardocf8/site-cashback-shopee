"""Montagem dos dados das telas de Resultados, Metas e Início (só leitura do banco -
ver painel/resultados.py)."""

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from . import metas as regras_metas
from . import fechamento, periodos, resultados
from .models import FechamentoMes, MetaMensal, SincronizacaoResultados, VendaItem

METRICAS = [
    ("faturamento", "Faturamento"),
    ("comissao_estimada", "Comissão estimada"),
    ("comissao_validada", "Comissão validada"),
    ("pedidos", "Pedidos"),
]
NOMES_METRICAS = dict(METRICAS)
MESES = periodos.MESES


def nome_mes(ano: int, mes: int) -> str:
    return f"{MESES[mes - 1].capitalize()}/{ano}"


def estado_sincronizacao(conta) -> SincronizacaoResultados | None:
    return SincronizacaoResultados.objects.filter(conta=conta).first()


def barras(linhas: list[dict], metrica: str) -> dict:
    """Dados do gráfico de barras: altura em % do maior valor, rótulos e dica."""
    valores = [float(linha.get(metrica) or 0) for linha in linhas]
    maior = max(valores, default=0)
    eh_dinheiro = metrica != "pedidos"
    itens = []
    passo = max(1, round(len(linhas) / 14))
    for i, (linha, valor) in enumerate(zip(linhas, valores)):
        altura = 0 if maior <= 0 else max(2 if valor > 0 else 0, round(valor / maior * 100))
        texto_valor = _dinheiro_texto(valor) if eh_dinheiro else f"{int(valor)} pedido{'s' if int(valor) != 1 else ''}"
        itens.append({
            "altura": altura,
            "rotulo": linha["rotulo_curto"] if (i % passo == 0 or i == len(linhas) - 1) else "",
            "dica": f"{linha['rotulo']}: {texto_valor}",
            "destaque": i == len(linhas) - 1,
        })
    return {"itens": itens, "tem_dados": maior > 0}


def _dinheiro_texto(valor) -> str:
    texto = f"{float(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


# --- Período escolhido na tela ------------------------------------------------------

def _data(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


def periodo_da_requisicao(get, hoje: date) -> dict:
    """Lê ?periodo=&de=&ate=&agrupar=&metrica= e devolve o período validado."""
    chaves = dict(periodos.PRESETS)
    chave = get.get("periodo") or "mes"
    if chave not in chaves:
        chave = "mes"
    if chave == "personalizado":
        inicio, fim = _data(get.get("de")), _data(get.get("ate"))
        if not inicio or not fim:
            inicio, fim = periodos.intervalo_do_preset("mes", hoje)
        if inicio > fim:
            inicio, fim = fim, inicio
        fim = min(fim, hoje)
        inicio = max(min(inicio, fim), fim - timedelta(days=365))
    else:
        inicio, fim = periodos.intervalo_do_preset(chave, hoje)

    agrupamentos = dict(periodos.AGRUPAMENTOS)
    agrupar = get.get("agrupar")
    if agrupar not in agrupamentos:
        agrupar = periodos.agrupamento_sugerido(inicio, fim)
    metrica = get.get("metrica") if get.get("metrica") in NOMES_METRICAS else "faturamento"
    return {
        "chave": chave, "inicio": inicio, "fim": fim, "agrupar": agrupar, "metrica": metrica,
        "descricao": periodos.descrever_periodo(inicio, fim),
    }


# --- Metas ----------------------------------------------------------------------------

def faixas_do_mes(conta, ano: int, mes: int) -> list[dict]:
    meta = MetaMensal.objects.filter(conta=conta, ano=ano, mes=mes).first()
    return regras_metas.normalizar(meta.faixas if meta else [])


# A meta de um mês fecha 30 dias depois do último dia do mês, às 11h (quando a Shopee manda o e-mail da
# meta mensal - painel/fechamento.py): até lá, pedidos do mês ainda podem ser validados ou cancelados, e
# no fechamento conta só o validado. Por isso a meta tem três fases:
# - prévia: o mês em andamento, com o faturamento estimado (validado + pendente) e a projeção;
# - em fechamento: até o fechamento, separando o validado (garantido), o pendente e o cancelado;
# - fechada: o validado guardado no fechamento (FechamentoMes), que não muda mais (é o que vale para o
#   bônus). Sem fechamento guardado (mês antigo, worker parado), o validado dos pedidos guardados.
PREVIA, FECHAMENTO, FECHADA = "previa", "fechamento", "fechada"
NOMES_FASES = {PREVIA: "Prévia", FECHAMENTO: "Em fechamento", FECHADA: "Fechada"}


def fase_da_meta(ano: int, mes: int, hoje: date) -> tuple[str, date]:
    """(fase, dia em que o resultado fecha: 30 dias depois do último dia do mês). No próprio dia do
    fechamento a fase é "em fechamento" - situacao_meta passa para "fechada" quando o fechamento das
    11h já foi guardado."""
    fim = periodos.ultimo_dia_do_mes(date(ano, mes, 1))
    fecha_em = fechamento.dia_do_fechamento(ano, mes)
    if hoje <= fim:
        return PREVIA, fecha_em
    return (FECHAMENTO if hoje <= fecha_em else FECHADA), fecha_em


def faturamento_por_situacao(conta, inicio: date, fim: date) -> dict | None:
    """Faturamento dos pedidos comprados no período, separado em validado, pendente e cancelado
    (VendaItem). None se o Appfiliado não guarda os pedidos desde o começo do período."""
    estado = estado_sincronizacao(conta)
    if not estado or not estado.vendas_desde or timezone.localtime(estado.vendas_desde).date() > inicio:
        return None
    de = timezone.make_aware(datetime.combine(inicio, time.min))
    ate = timezone.make_aware(datetime.combine(fim + timedelta(days=1), time.min))
    somas = dict(VendaItem.objects.filter(conta=conta, comprado_em__gte=de, comprado_em__lt=ate).order_by()
                 .values("situacao").annotate(total=Sum("valor")).values_list("situacao", "total"))
    return {"validado": float(somas.get(VendaItem.CONCLUIDO) or 0), "pendente": float(somas.get(VendaItem.PENDENTE) or 0),
            "cancelado": float(somas.get(VendaItem.CANCELADO) or 0)}


def situacao_meta(conta, ano: int, mes: int, hoje: date) -> dict:
    inicio = date(ano, mes, 1)
    fim = periodos.ultimo_dia_do_mes(inicio)
    fase, fecha_em = fase_da_meta(ano, mes, hoje)
    guardado = FechamentoMes.objects.filter(conta=conta, ano=ano, mes=mes).first() if fase != PREVIA else None
    if guardado:
        fase = FECHADA
        partes = {"validado": float(guardado.validado), "pendente": float(guardado.pendente),
                  "cancelado": float(guardado.cancelado)}
    else:
        partes = faturamento_por_situacao(conta, inicio, fim) if fase != PREVIA else None
    # Na prévia (ou sem os pedidos guardados), o faturamento estimado; depois do mês, só o validado.
    faturamento = partes["validado"] if partes else float(resultados.totais(conta, inicio, min(fim, hoje))["faturamento"])
    possivel = (partes["validado"] + partes["pendente"]) if partes else faturamento
    faixas = faixas_do_mes(conta, ano, mes)
    situacao = regras_metas.situacao(faturamento, faixas, hoje, ano, mes)
    maior = faixas[-1]["faturamento"] if faixas else 0
    em_fechamento = fase == FECHAMENTO and partes is not None

    def estado(faixa):
        if faturamento >= faixa["faturamento"]:
            return "batida"
        if em_fechamento:
            return "possivel" if possivel >= faixa["faturamento"] else "fora"
        return "fora" if fase == FECHADA else "falta"

    faixas_tela = [
        {
            **faixa,
            "nome": regras_metas.nome_faixa(faixa),
            "batida": faturamento >= faixa["faturamento"],
            "estado": estado(faixa),
            "posicao": round(faixa["faturamento"] / maior * 100) if maior else 0,
            "falta": max(0.0, faixa["faturamento"] - faturamento),
            "gmv": faixa.get("gmv") or 0,
        }
        for faixa in faixas
    ]
    barra = min(100, round(situacao["fracao"] * 100))
    # A faixa que ainda depende dos pendentes: quanto falta validar e quanto pode ser cancelado sem perdê-la.
    em_jogo = next((f for f in faixas_tela if f["estado"] == "possivel"), None)
    situacao.update({
        "faturamento": faturamento,
        "nome_mes": nome_mes(ano, mes),
        "faixas_tela": faixas_tela,
        "porcentagem_barra": barra,
        "nome_proxima": regras_metas.nome_faixa(situacao["proxima"]) if situacao.get("proxima") else "",
        "nome_faixa_projetada": (
            regras_metas.nome_faixa(situacao["faixa_projetada"]) if situacao.get("faixa_projetada") else ""
        ),
        "mes_valor": f"{ano}-{mes:02d}",
        "nome_faixa_batida": regras_metas.nome_faixa(situacao["batidas"][-1]) if situacao["batidas"] else "",
        "fase": fase, "nome_fase": NOMES_FASES[fase], "fecha_em": fecha_em, "previa": fase == PREVIA,
        "fechado_em": guardado.fechado_em if guardado else None,
        "em_fechamento": em_fechamento, "fechada": fase == FECHADA,
        "sem_pedidos_guardados": fase != PREVIA and partes is None,
        "validado": partes["validado"] if partes else None,
        "pendente": partes["pendente"] if partes else None,
        "cancelado": partes["cancelado"] if partes else None,
        "possivel": possivel,
        "porcentagem_pendente": (min(100 - barra, round(partes["pendente"] / maior * 100)) if em_fechamento and maior else 0),
        "faixa_em_jogo": em_jogo,
        "falta_validar": (em_jogo["faturamento"] - faturamento) if em_jogo else 0.0,
        "pode_perder": (possivel - em_jogo["faturamento"]) if em_jogo else 0.0,
    })
    if situacao.get("modo_gmv") and em_fechamento:
        meta_gmv = faixas[0]
        situacao["bonus_possivel"] = round(possivel * meta_gmv["gmv"] / 100, 2) if possivel >= meta_gmv["faturamento"] else 0.0
    situacao["frase_possivel"] = _frase_possivel(situacao) if em_fechamento else ""
    return situacao


def _frase_possivel(m: dict) -> str:
    """Mês em fechamento: até onde chega se todo o pendente for validado, e se bate alguma faixa."""
    from .templatetags.painel_extras import brl, brl0

    base = f"Se todo o pendente for validado, {m['nome_mes'].split('/')[0].lower()} chega a {brl(m['possivel'])}"
    alcancadas = [f for f in m["faixas_tela"] if m["possivel"] >= f["faturamento"]]
    if m.get("modo_gmv"):
        meta = m["faixas_tela"][0]
        if alcancadas:
            ja = " (a meta já está garantida)" if meta["batida"] else ""
            return f"{base} e bate a meta{ja}: bônus de {brl(m['bonus_possivel'])} ({m['gmv_percentual']:g}% do GMV)."
        return f"{base}, ainda abaixo da meta (faltariam {brl(meta['faturamento'] - m['possivel'])})."
    if not alcancadas:
        primeira = m["faixas_tela"][0]
        return (f"{base}, ainda abaixo da primeira faixa (faltariam {brl(primeira['faturamento'] - m['possivel'])} "
                f"para a {primeira['nome']}).")
    melhor = alcancadas[-1]
    bonus = f" (bônus {brl0(melhor['bonus'])})" if melhor.get("bonus") else ""
    proxima = next((f for f in m["faixas_tela"] if m["possivel"] < f["faturamento"]), None)
    resto = f" A faixa {proxima['nome']} ficaria a {brl(proxima['faturamento'] - m['possivel'])}." if proxima else ""
    if melhor["batida"]:
        return f"{base} e continua na faixa {melhor['nome']}{bonus}, que já está garantida.{resto}"
    return f"{base} e bate a faixa {melhor['nome']}{bonus}.{resto}"


def metas_dos_tres_meses(conta, hoje: date) -> list[dict]:
    """Dois meses atrás (fechada), o mês passado (em fechamento) e o atual (prévia), só os que têm meta.
    Do mais recente para o mais antigo."""
    atual = date(hoje.year, hoje.month, 1)
    passado = periodos.primeiro_dia_do_mes(atual - timedelta(days=1))
    retrasado = periodos.primeiro_dia_do_mes(passado - timedelta(days=1))
    lista = []
    for d in (atual, passado, retrasado):
        if faixas_do_mes(conta, d.year, d.month):
            lista.append(situacao_meta(conta, d.year, d.month, hoje))
    return lista


def ler_numero_br(texto: str) -> float | None:
    """"30.000,00", "30000", "30.000", "1250,5" -> float. Vazio -> None."""
    texto = re.sub(r"[^\d.,]", "", str(texto or ""))
    if not texto:
        return None
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    elif texto.count(".") > 1 or (texto.count(".") == 1 and len(texto.split(".")[1]) == 3):
        texto = texto.replace(".", "")  # ponto de milhar: "30.000"
    try:
        return float(texto)
    except ValueError:
        return None


def faixas_do_formulario(post, quantidade: int = 3) -> list[dict]:
    """Lê percentual_N, faturamento_N e bonus_N. Linha com percentual mas sem
    faturamento é calculada a partir da primeira linha completa (ex: 125% de uma
    meta de 100% = R$ 30.000 vira R$ 37.500)."""
    linhas = []
    for i in range(1, quantidade + 1):
        linhas.append({
            "percentual": ler_numero_br(post.get(f"percentual_{i}")),
            "faturamento": ler_numero_br(post.get(f"faturamento_{i}")),
            "bonus": ler_numero_br(post.get(f"bonus_{i}")),
        })
    base = next((l for l in linhas if l["percentual"] and l["faturamento"]), None)
    for linha in linhas:
        if base and linha["percentual"] and not linha["faturamento"]:
            linha["faturamento"] = round(base["faturamento"] * linha["percentual"] / base["percentual"], 2)
    return [
        {"percentual": l["percentual"] or 0, "faturamento": l["faturamento"], "bonus": l["bonus"] or 0}
        for l in linhas if l["faturamento"]
    ]


def faixa_em_gmv_do_formulario(post) -> list[dict]:
    """Afiliado agenciado: uma meta de faturamento e o bônus em % do GMV (o bônus não é digitado)."""
    faturamento, gmv = ler_numero_br(post.get("meta_gmv_faturamento")), ler_numero_br(post.get("meta_gmv_percentual"))
    if not faturamento or not gmv or gmv <= 0 or gmv > 100:
        return []
    return [{"percentual": 100, "faturamento": faturamento, "bonus": 0, "gmv": gmv}]


def meses_para_metas(hoje: date) -> list[tuple[int, int]]:
    """Dois meses atrás (fechada), o mês passado (em fechamento), este (prévia) e o próximo (para cadastrar)."""
    atual = date(hoje.year, hoje.month, 1)
    anterior = periodos.primeiro_dia_do_mes(atual - timedelta(days=1))
    retrasado = periodos.primeiro_dia_do_mes(anterior - timedelta(days=1))
    proximo = periodos.ultimo_dia_do_mes(atual) + timedelta(days=1)
    return [(d.year, d.month) for d in (retrasado, anterior, atual, proximo)]


def hoje() -> date:
    return timezone.localdate()


def decimal(valor) -> Decimal:
    return Decimal(str(valor or 0))


# --- Conferência do faturamento (página escondida /resultados/conferir/) ---------------------------

def conferencia_faturamento(conta, ano: int, mes: int) -> dict:
    """O faturamento do mês contado de três jeitos, para comparar com o painel da Shopee:
    - feitos: pedidos comprados no mês, sem os cancelados (o jeito do Appfiliado hoje);
    - feitos e já validados: dos comprados no mês, só os concluídos;
    - validados no mês: pedidos concluídos no mês, comprados em qualquer data.
    Valor = o pago pelo comprador menos reembolsos de cada item (VendaItem.valor)."""
    from django.db.models import Count, Q

    inicio = date(ano, mes, 1)
    fim = periodos.ultimo_dia_do_mes(inicio)
    de = timezone.make_aware(datetime.combine(inicio, time.min))
    ate = timezone.make_aware(datetime.combine(fim + timedelta(days=1), time.min))
    itens = VendaItem.objects.filter(conta=conta).order_by()

    def somar(filtro):
        r = itens.filter(filtro).aggregate(valor=Sum("valor"), pedidos=Count("pedido_id", distinct=True))
        return {"valor": r["valor"] or Decimal(0), "pedidos": r["pedidos"] or 0}

    comprados = Q(comprado_em__gte=de, comprado_em__lt=ate)
    validados_no_mes = Q(situacao=VendaItem.CONCLUIDO, concluido_em__gte=de, concluido_em__lt=ate)
    estado = estado_sincronizacao(conta)
    desde = timezone.localtime(estado.vendas_desde).date() if estado and estado.vendas_desde else None
    return {
        "nome_mes": nome_mes(ano, mes), "inicio": inicio, "fim": fim,
        "painel": resultados.totais(conta, inicio, fim)["faturamento"],
        "feitos": somar(comprados & ~Q(situacao=VendaItem.CANCELADO)),
        "feitos_validados": somar(comprados & Q(situacao=VendaItem.CONCLUIDO)),
        "feitos_pendentes": somar(comprados & Q(situacao=VendaItem.PENDENTE)),
        "feitos_cancelados": somar(comprados & Q(situacao=VendaItem.CANCELADO)),
        "validados_no_mes": somar(validados_no_mes),
        "validados_no_mes_comprados_antes": somar(validados_no_mes & Q(comprado_em__lt=de)),
        "pedidos_desde": desde,
        # Pedido validado no mês pode ter sido comprado até uns 2 meses antes: sem os pedidos guardados
        # desde então, o terceiro número fica menor do que é.
        "cobertura_incompleta": not desde or desde > periodos.primeiro_dia_do_mes(inicio - timedelta(days=45)),
    }
