"""A aba Resultados filtrada pela origem das vendas (painel/origens.py) e o mapa "Quando suas vendas
acontecem". Sem filtro, a aba usa os totais por dia de sempre (ResultadoDiario); com filtro, tudo sai
dos itens vendidos guardados (VendaItem), que têm a origem de cada venda."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate

from . import origens
from .models import RegraSubId, VendaItem
from .periodos import agrupar

DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
DIAS_POR_EXTENSO = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MINIMO_DE_PEDIDOS_NO_MAPA = 20
JANELA_DO_PICO = 4  # horas seguidas mais fortes, para comparar com o horário do bot


def origem_da_requisicao(get) -> str:
    """"" = todas."""
    origem = str(get.get("origem") or "")
    return origem if origem in origens.NOMES else ""


def _limites(inicio: date, fim: date):
    from .resultados import _limites

    return _limites(inicio, fim)


def itens(conta, inicio: date, fim: date, origem: str = ""):
    """Itens comprados no período (com os cancelados), da origem escolhida."""
    de, ate = _limites(inicio, fim)
    vendas = VendaItem.objects.filter(conta=conta, comprado_em__gte=de, comprado_em__lt=ate)
    return vendas.filter(origem=origem) if origem else vendas


def _validados(conta, inicio: date, fim: date, origem: str):
    de, ate = _limites(inicio, fim)
    vendas = VendaItem.objects.filter(conta=conta, situacao=VendaItem.CONCLUIDO, concluido_em__gte=de, concluido_em__lt=ate)
    return vendas.filter(origem=origem) if origem else vendas


def serie(conta, inicio: date, fim: date, modo: str, origem: str) -> list[dict]:
    """Como resultados.serie, mas dos itens vendidos da origem: pedidos, faturamento e comissão
    estimada pela data da compra (sem cancelados); validada pela data de validação."""
    compras = (itens(conta, inicio, fim, origem).exclude(situacao=VendaItem.CANCELADO).order_by()
               .annotate(dia=TruncDate("comprado_em")).values("dia")
               .annotate(pedidos=Count("pedido_id", distinct=True), faturamento=Sum("valor"), comissao=Sum("comissao")))
    por_dia = {c["dia"]: c for c in compras}
    validadas = dict(_validados(conta, inicio, fim, origem).order_by().annotate(dia=TruncDate("concluido_em"))
                     .values("dia").annotate(total=Sum("comissao")).values_list("dia", "total"))
    linhas = []
    for i in range((fim - inicio).days + 1):
        dia = inicio + timedelta(days=i)
        c = por_dia.get(dia) or {}
        linhas.append({"dia": dia, "pedidos": c.get("pedidos") or 0, "faturamento": c.get("faturamento") or Decimal(0),
                       "comissao_estimada": c.get("comissao") or Decimal(0), "comissao_validada": validadas.get(dia) or Decimal(0)})
    return agrupar(linhas, modo)


def totais(linhas_por_dia: list[dict]) -> dict:
    campos = ("pedidos", "faturamento", "comissao_estimada", "comissao_validada")
    return {c: sum((linha[c] for linha in linhas_por_dia), 0) for c in campos}


def por_sub_id(conta, inicio: date, fim: date, origem: str, limite: int = 8) -> list[dict]:
    """Como resultados.por_sub_id, dos itens vendidos da origem (vendas = conversões)."""
    from .resultados import nome_do_grupo

    brutos = (itens(conta, inicio, fim, origem).exclude(situacao=VendaItem.CANCELADO).order_by().values("sub_id")
              .annotate(vendas=Count("conversao_id", distinct=True), comissao=Sum("comissao")))
    regras = list(RegraSubId.objects.filter(conta=conta))
    grupos = {}
    for bruto in brutos:
        nome = nome_do_grupo(bruto["sub_id"], regras)
        grupo = grupos.setdefault(nome, {"sub_id": nome, "vendas": 0, "comissao": Decimal(0), "quantidade": 0})
        grupo["vendas"] += bruto["vendas"] or 0
        grupo["comissao"] += bruto["comissao"] or 0
        grupo["quantidade"] += 1
    return sorted(grupos.values(), key=lambda g: (g["comissao"], g["vendas"]), reverse=True)[:limite]


def resumo(conta, inicio: date, fim: date) -> dict:
    """Comissão estimada do período (itens sem cancelados) por origem, para a barra do topo."""
    somas = dict(itens(conta, inicio, fim).exclude(situacao=VendaItem.CANCELADO).order_by().values("origem")
                 .annotate(total=Sum("comissao")).values_list("origem", "total"))
    total = sum((v or 0 for v in somas.values()), Decimal(0))
    linhas = []
    for chave in origens.ORDEM:
        valor = somas.get(chave) or Decimal(0)
        linhas.append({"chave": chave, "nome": origens.NOMES[chave], "nome_curto": origens.NOMES_CURTOS[chave],
                       "cor": origens.CORES[chave], "comissao": valor,
                       "percentual": round(valor * 100 / total) if total else 0,
                       "largura": float(valor * 100 / total) if total else 0})
    return {"linhas": linhas, "total": total}


# --- Quando suas vendas acontecem ---------------------------------------------------------

def _hora(h: int) -> str:
    return f"{h % 24}h"


def mapa_de_horarios(conta, inicio: date, fim: date, origem: str, metrica: str = "pedidos", config_bot=None) -> dict:
    """Pedidos (ou comissão) de cada dia da semana em cada hora, pela hora da compra."""
    celulas = (itens(conta, inicio, fim, origem).exclude(situacao=VendaItem.CANCELADO).order_by()
               .annotate(dia=ExtractIsoWeekDay("comprado_em"), hora=ExtractHour("comprado_em"))
               .values("dia", "hora").annotate(pedidos=Count("pedido_id", distinct=True), comissao=Sum("comissao")))
    grade = [[Decimal(0)] * 24 for _ in range(7)]
    pedidos = 0
    for c in celulas:
        valor = Decimal(c["pedidos"] or 0) if metrica == "pedidos" else (c["comissao"] or Decimal(0))
        grade[c["dia"] - 1][c["hora"]] += valor
        pedidos += c["pedidos"] or 0
    total = sum((sum(linha) for linha in grade), Decimal(0))
    por_hora = [sum((grade[d][h] for d in range(7)), Decimal(0)) for h in range(24)]
    maior = max((v for linha in grade for v in linha), default=0) or 1
    maior_hora = max(por_hora) or 1
    fortes = sorted(((grade[d][h], d, h) for d in range(7) for h in range(24) if grade[d][h] > 0), reverse=True)[:3]
    marcadas = {(d, h) for _, d, h in fortes}
    melhor_hora = max(range(24), key=lambda h: por_hora[h]) if total else None
    return {
        "metrica": metrica,
        "pedidos": pedidos,
        "total": total,
        "poucos": pedidos < MINIMO_DE_PEDIDOS_NO_MAPA,
        "linhas": [{"dia": DIAS[d], "celulas": [{"hora": h, "valor": grade[d][h], "nivel": _nivel(grade[d][h], maior),
                                                 "forte": (d, h) in marcadas} for h in range(24)]} for d in range(7)],
        "por_hora": [{"hora": h, "valor": por_hora[h], "altura": round(por_hora[h] * 100 / maior_hora),
                      "melhor": h == melhor_hora} for h in range(24)],
        "destaques": _destaques(fortes, total, melhor_hora, por_hora),
        "dica_bot": _dica_do_bot(por_hora, config_bot) if total else None,
    }


def _nivel(valor, maior) -> int:
    """0 (sem venda) a 4 (o mais forte)."""
    if not valor:
        return 0
    return min(4, 1 + int(valor * 4 / maior)) if valor < maior else 4


def _destaques(fortes, total, melhor_hora, por_hora) -> list[dict]:
    """Os horários mais fortes (horas seguidas do mesmo dia viram uma faixa) e a hora que mais vende
    somando todos os dias."""
    faixas: list[dict] = []
    for valor, d, h in fortes:
        junto = next((f for f in faixas if f["dia"] == d and (h == f["ate"] or h + 1 == f["de"])), None)
        if junto:
            junto["de"], junto["ate"], junto["valor"] = min(junto["de"], h), max(junto["ate"], h + 1), junto["valor"] + valor
        else:
            faixas.append({"dia": d, "de": h, "ate": h + 1, "valor": valor})
    destaques = [{"titulo": f"{DIAS_POR_EXTENSO[f['dia']]}, {_hora(f['de'])}–{_hora(f['ate'])}",
                  "texto": f"{_pct(f['valor'], total)} do total da semana" + (f" em {f['ate'] - f['de']} horas" if f["ate"] - f["de"] > 1 else "")}
                 for f in faixas[:2]]
    if melhor_hora is not None:
        destaques.append({"titulo": f"Todo dia, {_hora(melhor_hora)}–{_hora(melhor_hora + 1)}",
                          "texto": f"a hora que mais vende somando todos os dias ({_pct(por_hora[melhor_hora], total)})"})
    return destaques


def _pct(valor, total) -> str:
    return f"{valor * 100 / total:.1f}%".replace(".", ",") if total else "0%"


def _dica_do_bot(por_hora, config) -> dict | None:
    """Compara as JANELA_DO_PICO horas seguidas mais fortes com o horário do bot."""
    if not config:
        return None
    def soma(h):
        return sum(por_hora[(h + i) % 24] for i in range(JANELA_DO_PICO))

    inicio = max(range(24), key=lambda h: (soma(h), -h))  # empate: a janela que começa mais cedo
    if not soma(inicio):
        return None
    fim = (inicio + JANELA_DO_PICO) % 24
    bot_de, bot_ate = config.horario_inicio.hour, config.horario_fim.hour + (1 if config.horario_fim.minute else 0)
    horas_do_bot = {h % 24 for h in range(bot_de, bot_ate if bot_ate > bot_de else bot_ate + 24)}
    pico = [(inicio + i) % 24 for i in range(JANELA_DO_PICO)]
    fora = [h for h in pico if h not in horas_do_bot]
    fim_bot = config.horario_fim
    texto_bot = f"{config.horario_inicio.hour}h às {fim_bot.hour}h" + (f"{fim_bot.minute:02d}" if fim_bot.minute else "")
    if not fora:
        situacao = ""
    elif len(fora) == len(pico):
        situacao = "ele não envia nesse horário"
    elif pico[0] in horas_do_bot:
        situacao = "ele para antes do fim do horário mais forte"
    else:
        situacao = "ele começa depois do início do horário mais forte"
    return {"de": _hora(inicio), "ate": _hora(fim), "bot": texto_bot, "situacao": situacao, "ok": not fora}
