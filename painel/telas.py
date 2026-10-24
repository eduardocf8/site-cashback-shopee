"""Montagem dos dados das telas de Resultados, Metas e Início (só leitura do banco -
ver painel/resultados.py)."""

import re
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from . import metas as regras_metas
from . import periodos, resultados
from .models import MetaMensal, SincronizacaoResultados

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


def situacao_meta(conta, ano: int, mes: int, hoje: date) -> dict:
    inicio = date(ano, mes, 1)
    fim = periodos.ultimo_dia_do_mes(inicio)
    faturamento = float(resultados.totais(conta, inicio, min(fim, hoje))["faturamento"])
    faixas = faixas_do_mes(conta, ano, mes)
    situacao = regras_metas.situacao(faturamento, faixas, hoje, ano, mes)
    maior = faixas[-1]["faturamento"] if faixas else 0
    situacao.update({
        "faturamento": faturamento,
        "nome_mes": nome_mes(ano, mes),
        "faixas_tela": [
            {
                **faixa,
                "nome": regras_metas.nome_faixa(faixa),
                "batida": faturamento >= faixa["faturamento"],
                "posicao": round(faixa["faturamento"] / maior * 100) if maior else 0,
                "falta": max(0.0, faixa["faturamento"] - faturamento),
                "gmv": faixa.get("gmv") or 0,
            }
            for faixa in faixas
        ],
        "porcentagem_barra": min(100, round(situacao["fracao"] * 100)),
        "nome_proxima": regras_metas.nome_faixa(situacao["proxima"]) if situacao.get("proxima") else "",
        "nome_faixa_projetada": (
            regras_metas.nome_faixa(situacao["faixa_projetada"]) if situacao.get("faixa_projetada") else ""
        ),
    })
    return situacao


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
    """Mês passado, este e o próximo."""
    atual = date(hoje.year, hoje.month, 1)
    anterior = periodos.primeiro_dia_do_mes(atual - timedelta(days=1))
    proximo = periodos.ultimo_dia_do_mes(atual) + timedelta(days=1)
    return [(d.year, d.month) for d in (anterior, atual, proximo)]


def hoje() -> date:
    return timezone.localdate()


def decimal(valor) -> Decimal:
    return Decimal(str(valor or 0))
