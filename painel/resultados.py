"""Resultados da Shopee de cada conta: busca na API (em segundo plano, pelo comando
sincronizar_painel), guarda os totais por dia em ResultadoDiario/ResultadoSubIdDiario
e responde às telas com somas do banco.

As regras de cálculo são as mesmas do app do Appfiliado
(ConversorAfiliados.obter_resultados_periodo), conferidas contra o relatório de vendas
exportado da Shopee:
- faturamento e pedidos pela data da compra, sem pedidos CANCELLED/UNPAID;
- comissão estimada pela data da compra (a comissão da conversão, zerada se todos os
  pedidos dela foram cancelados);
- comissão validada pela data de validação de cada item (completeTime), só de pedidos
  COMPLETED.
"""

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import cripto
from .models import RegraSubId, ResultadoDiario, ResultadoSubIdDiario, SincronizacaoResultados, VendaItem
from .periodos import agrupar
from .shopee import buscar_conversoes

logger = logging.getLogger(__name__)

STATUS_PEDIDO_INVALIDOS = {"CANCELLED", "UNPAID"}
CAMPOS_COMISSAO_ESTIMADA = (
    "netCommission", "grossCommission", "cappedCommission", "totalCommission",
    "sellerCommission", "commission", "commissionAmount", "estCommission",
)
# A API só deixa consultar ~3 meses para trás (erro 11001 depois disso).
JANELA_API_DIAS = 89
# Pedidos mudam de status (pendente -> concluído/cancelado) por semanas; a comissão
# validada de um dia só fica completa quando as compras que validam nele estão dentro
# da janela - por isso ela é recalculada só nos últimos 60 dias, e os dias mais antigos
# ficam como estavam na última vez em que dava para calcular direito.
DIAS_RECALCULO_VALIDADA = 60
INTERVALO_SINCRONIZACAO_AUTOMATICA = timedelta(hours=3)
# Itens vendidos ficam guardados por 13 meses (dá para comparar com o mesmo mês do ano anterior).
DIAS_DE_HISTORICO_VENDAS = 395
STATUS_CANCELADOS = STATUS_PEDIDO_INVALIDOS | {"INVALID"}


# --- Números e Sub IDs (mesmas regras do app) ----------------------------------------

def para_numero(valor) -> float:
    """'12,34', '12.34', '1.234,56', números ou None -> float."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^\d.,-]", "", str(valor).strip())
    if not texto:
        return 0.0
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _primeiro_numero(objeto, nomes):
    """Primeiro campo de `nomes` encontrado (procurando também dentro de listas e
    dicionários aninhados); listas somam."""
    if isinstance(objeto, dict):
        for nome in nomes:
            if nome in objeto and objeto[nome] not in (None, ""):
                return para_numero(objeto[nome])
        for valor in objeto.values():
            if isinstance(valor, (dict, list)):
                achado = _primeiro_numero(valor, nomes)
                if achado is not None:
                    return achado
    elif isinstance(objeto, list):
        achados = [n for n in (_primeiro_numero(item, nomes) for item in objeto) if n is not None]
        if achados:
            return sum(achados)
    return None


def comissao_estimada(conversao: dict) -> float:
    comissao = _primeiro_numero(conversao, CAMPOS_COMISSAO_ESTIMADA) or 0.0
    pedidos = conversao.get("orders")
    if isinstance(pedidos, list) and pedidos:
        status = [str((p or {}).get("orderStatus") or "").strip().upper() for p in pedidos if isinstance(p, dict)]
        if status and all(s in STATUS_PEDIDO_INVALIDOS for s in status):
            return 0.0
    return comissao


SEM_SUB_ID = "sem_subid"
NOME_SEM_SUB_ID = "Sem Sub ID"


def _textos(valor) -> list[str]:
    if isinstance(valor, list):
        return [t for item in valor for t in _textos(item)]
    if isinstance(valor, dict):
        return [t for item in valor.values() for t in _textos(item)]
    texto = str(valor or "").strip()
    return [texto] if texto else []


def sub_id(conversao: dict) -> str:
    """O utmContent da Shopee traz os 5 Sub IDs do link juntos, separados por "-"
    (ex: "grupoA-story---", ou "----" quando não tem nenhum). Sub ID só aceita
    letras e números, então o "-" não aparece dentro deles. Cada venda fica com um
    rótulo só, com os campos preenchidos: "grupoA-story"."""
    partes = [
        parte.strip()
        for texto in _textos(conversao.get("utmContent"))
        for parte in re.split(r"[-|;,]", texto)
        if parte.strip()
    ]
    return "-".join(partes)[:120] or SEM_SUB_ID


def _dia_local(ts: int) -> date:
    return timezone.localtime(datetime.fromtimestamp(ts, tz=dt_timezone.utc)).date()


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


# --- Cálculo ------------------------------------------------------------------------

def calcular_por_dia(conversoes: list[dict]) -> tuple[dict, dict]:
    """(por_dia, por_sub_id) a partir das conversões cruas da API.

    por_dia[dia] = {"pedidos": set, "faturamento", "comissao_estimada", "comissao_validada"}
    por_sub_id[(dia, sub_id)] = {"vendas", "comissao_estimada"}"""
    por_dia = defaultdict(lambda: {"pedidos": set(), "faturamento": 0.0,
                                   "comissao_estimada": 0.0, "comissao_validada": 0.0})
    por_sub_id = defaultdict(lambda: {"vendas": 0, "comissao_estimada": 0.0})

    for conversao in conversoes:
        if not isinstance(conversao, dict):
            continue
        compra = _inteiro(conversao.get("purchaseTime"))
        dia_compra = _dia_local(compra) if compra is not None else None

        if dia_compra:
            estimada = comissao_estimada(conversao)
            por_dia[dia_compra]["comissao_estimada"] += estimada
            item = por_sub_id[(dia_compra, sub_id(conversao))]
            item["vendas"] += 1
            item["comissao_estimada"] += estimada

        pedidos = conversao.get("orders")
        for pedido in pedidos if isinstance(pedidos, list) else []:
            if not isinstance(pedido, dict):
                continue
            status = str(pedido.get("orderStatus") or "").strip().upper()
            itens = [i for i in pedido.get("items") or [] if isinstance(i, dict)]

            if dia_compra and status not in STATUS_PEDIDO_INVALIDOS:
                por_dia[dia_compra]["faturamento"] += sum(
                    para_numero(i.get("itemPrice")) * (para_numero(i.get("qty")) or 1) for i in itens
                )
                por_dia[dia_compra]["pedidos"].add(pedido.get("orderId"))

            if status == "COMPLETED":
                for item in itens:
                    validacao = _inteiro(item.get("completeTime"))
                    if validacao is not None:
                        por_dia[_dia_local(validacao)]["comissao_validada"] += para_numero(
                            item.get("itemTotalCommission")
                        )
    return por_dia, por_sub_id


def _momento(ts):
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc) if ts is not None else None


def _texto(valor, tamanho: int) -> str:
    return str(valor or "").strip()[:tamanho]


def itens_vendidos(conta, conversoes: list[dict]) -> list[VendaItem]:
    """Um VendaItem por produto de cada pedido (ainda não salvos)."""
    itens = []
    for conversao in conversoes:
        if not isinstance(conversao, dict):
            continue
        compra = _momento(_inteiro(conversao.get("purchaseTime")))
        if not compra:
            continue
        rotulo = sub_id(conversao)
        conversao_id = _texto(conversao.get("conversionId"), 40)
        pedidos = conversao.get("orders")
        for pedido in pedidos if isinstance(pedidos, list) else []:
            if not isinstance(pedido, dict):
                continue
            status = str(pedido.get("orderStatus") or "").strip().upper()
            if status == "COMPLETED":
                situacao = VendaItem.CONCLUIDO
            elif status in STATUS_CANCELADOS:
                situacao = VendaItem.CANCELADO
            else:
                situacao = VendaItem.PENDENTE
            produtos = [i for i in pedido.get("items") or [] if isinstance(i, dict)]
            for posicao, item in enumerate(produtos):
                quantidade = int(para_numero(item.get("qty")) or 1)
                preco = para_numero(item.get("itemPrice"))
                itens.append(VendaItem(
                    conta=conta, conversao_id=conversao_id, pedido_id=_texto(pedido.get("orderId"), 40),
                    posicao=posicao, item_id=_texto(item.get("itemId"), 30),
                    nome=_texto(item.get("itemName"), 300), imagem_url=_texto(item.get("imageUrl"), 500),
                    loja=_texto(item.get("shopName"), 200), quantidade=max(quantidade, 1),
                    preco=_dinheiro(preco), valor=_dinheiro(preco * max(quantidade, 1)),
                    comissao=_dinheiro(para_numero(item.get("itemTotalCommission"))),
                    status_shopee=status[:20], situacao=situacao, sub_id=rotulo, comprado_em=compra,
                    concluido_em=_momento(_inteiro(item.get("completeTime"))) if situacao == VendaItem.CONCLUIDO else None,
                ))
    return itens


def _dinheiro(valor: float) -> Decimal:
    return Decimal(str(round(valor or 0.0, 2)))


def sincronizar_conta(conta, agora: datetime | None = None) -> dict:
    """Busca os últimos ~3 meses na Shopee e atualiza os totais guardados.

    - faturamento, pedidos, comissão estimada e Sub IDs: recalculados em todos os dias
      da janela (o primeiro dia fica de fora, porque a janela começa no meio dele);
    - comissão validada: só nos últimos DIAS_RECALCULO_VALIDADA dias."""
    agora = agora or timezone.now()
    secret = cripto.decifrar(conta.shopee_secret_cifrado)
    if not conta.shopee_app_id or not secret:
        raise ValueError("Conta sem credenciais da Shopee.")

    inicio_janela = agora - timedelta(days=JANELA_API_DIAS)
    conversoes = buscar_conversoes(conta.shopee_app_id, secret, int(inicio_janela.timestamp()), int(agora.timestamp()))
    por_dia, por_sub_id = calcular_por_dia(conversoes)

    hoje = timezone.localtime(agora).date()
    primeiro_dia_completo = timezone.localtime(inicio_janela).date() + timedelta(days=1)
    inicio_validada = hoje - timedelta(days=DIAS_RECALCULO_VALIDADA - 1)
    dias_compra = [primeiro_dia_completo + timedelta(days=i) for i in range((hoje - primeiro_dia_completo).days + 1)]

    with transaction.atomic():
        existentes = {r.dia: r for r in ResultadoDiario.objects.filter(conta=conta, dia__gte=primeiro_dia_completo)}
        for dia in dias_compra:
            dados = por_dia.get(dia)
            registro = existentes.get(dia) or ResultadoDiario(conta=conta, dia=dia)
            registro.pedidos = len(dados["pedidos"]) if dados else 0
            registro.faturamento = _dinheiro(dados["faturamento"] if dados else 0)
            registro.comissao_estimada = _dinheiro(dados["comissao_estimada"] if dados else 0)
            # dias antigos só entram na primeira vez (incompletos, mas melhor que zero)
            if dia >= inicio_validada or registro._state.adding:
                registro.comissao_validada = _dinheiro(dados["comissao_validada"] if dados else 0)
            registro.save()

        ResultadoSubIdDiario.objects.filter(conta=conta, dia__gte=primeiro_dia_completo).delete()
        ResultadoSubIdDiario.objects.bulk_create([
            ResultadoSubIdDiario(
                conta=conta, dia=dia, sub_id=sub_id,
                vendas=valores["vendas"], comissao_estimada=_dinheiro(valores["comissao_estimada"]),
            )
            for (dia, sub_id), valores in por_sub_id.items()
            if primeiro_dia_completo <= dia <= hoje
        ])

        # Itens vendidos: a janela inteira é trocada pelo que a API devolveu agora (status
        # e comissão mudam); o que é mais velho que a janela fica como estava.
        VendaItem.objects.filter(conta=conta, comprado_em__gte=inicio_janela).delete()
        VendaItem.objects.bulk_create(itens_vendidos(conta, conversoes), batch_size=1000, ignore_conflicts=True)
        VendaItem.objects.filter(conta=conta, comprado_em__lt=agora - timedelta(days=DIAS_DE_HISTORICO_VENDAS)).delete()

        estado, _ = SincronizacaoResultados.objects.get_or_create(conta=conta)
        if not estado.cobertura_inicio or primeiro_dia_completo < estado.cobertura_inicio:
            estado.cobertura_inicio = primeiro_dia_completo
            estado.save(update_fields=["cobertura_inicio"])

    return {"conversoes": len(conversoes), "dias": len(dias_compra)}


# --- Fila de sincronização ------------------------------------------------------------

def pedir_atualizacao(conta):
    estado, _ = SincronizacaoResultados.objects.get_or_create(conta=conta)
    estado.pedido_em = timezone.now()
    estado.save(update_fields=["pedido_em"])
    return estado


def contas_pendentes(agora: datetime | None = None):
    """Contas com Shopee conectada que pediram atualização ou estão há mais de
    INTERVALO_SINCRONIZACAO_AUTOMATICA sem sincronizar - pedidos manuais primeiro."""
    from licencas.models import ContaAppfiliado

    agora = agora or timezone.now()
    limite = agora - INTERVALO_SINCRONIZACAO_AUTOMATICA
    pedidas, vencidas = [], []
    contas = (ContaAppfiliado.objects.exclude(shopee_app_id="").exclude(shopee_secret_cifrado="")
              .filter(shopee_validado_em__isnull=False).select_related("sincronizacao_resultados"))
    for conta in contas:
        estado = getattr(conta, "sincronizacao_resultados", None)
        if estado and estado.aguardando:
            pedidas.append((estado.pedido_em, conta))
        elif not estado or not estado.iniciada_em or estado.iniciada_em < limite:
            vencidas.append(conta)
    return [c for _, c in sorted(pedidas, key=lambda par: par[0])] + vencidas


def processar(conta) -> str:
    estado, _ = SincronizacaoResultados.objects.get_or_create(conta=conta)
    estado.iniciada_em = timezone.now()
    estado.save(update_fields=["iniciada_em"])
    try:
        resumo = sincronizar_conta(conta)
    except Exception as erro:
        logger.exception("Painel: falha ao sincronizar resultados da conta %s", conta.pk)
        estado.erro = str(erro)[:500]
        estado.concluida_em = timezone.now()
        estado.save(update_fields=["erro", "concluida_em"])
        return f"{conta.email}: erro - {erro}"
    estado.erro = ""
    estado.concluida_em = timezone.now()
    estado.save(update_fields=["erro", "concluida_em"])
    return f"{conta.email}: {resumo['conversoes']} conversões, {resumo['dias']} dias"


# --- Consultas das telas ----------------------------------------------------------------

CAMPOS = ("pedidos", "faturamento", "comissao_estimada", "comissao_validada")


def totais(conta, inicio: date, fim: date) -> dict:
    somas = ResultadoDiario.objects.filter(conta=conta, dia__gte=inicio, dia__lte=fim).aggregate(
        **{campo: Sum(campo) for campo in CAMPOS}
    )
    return {campo: somas[campo] or 0 for campo in CAMPOS}


def serie(conta, inicio: date, fim: date, modo: str = "dia") -> list[dict]:
    """Uma linha por dia/semana/mês do período, com zeros nos dias sem venda."""
    guardados = {r.dia: r for r in ResultadoDiario.objects.filter(conta=conta, dia__gte=inicio, dia__lte=fim)}
    linhas = []
    for i in range((fim - inicio).days + 1):
        dia = inicio + timedelta(days=i)
        r = guardados.get(dia)
        linhas.append({
            "dia": dia,
            **{campo: (getattr(r, campo) if r else 0) for campo in CAMPOS},
        })
    return agrupar(linhas, modo)


def nome_do_grupo(sub_id_bruto: str, regras) -> str:
    if sub_id_bruto == SEM_SUB_ID:
        return NOME_SEM_SUB_ID
    for regra in regras:
        if regra.casa(sub_id_bruto):
            return regra.nome
    return sub_id_bruto


def por_sub_id(conta, inicio: date, fim: date, limite: int = 8) -> list[dict]:
    """Comissão estimada e vendas por Sub ID no período, já com os agrupamentos da
    conta aplicados (ver RegraSubId)."""
    brutos = (
        ResultadoSubIdDiario.objects.filter(conta=conta, dia__gte=inicio, dia__lte=fim)
        .values("sub_id")
        .annotate(vendas=Sum("vendas"), comissao=Sum("comissao_estimada"))
    )
    regras = list(RegraSubId.objects.filter(conta=conta))
    grupos = {}
    for bruto in brutos:
        nome = nome_do_grupo(bruto["sub_id"], regras)
        grupo = grupos.setdefault(nome, {"sub_id": nome, "vendas": 0, "comissao": Decimal(0), "quantidade": 0})
        grupo["vendas"] += bruto["vendas"] or 0
        grupo["comissao"] += bruto["comissao"] or 0
        grupo["quantidade"] += 1
    ordenados = sorted(grupos.values(), key=lambda g: (g["comissao"], g["vendas"]), reverse=True)
    return ordenados[:limite]


def resumo_das_regras(conta, hoje: date) -> list[dict]:
    """Cada regra com quantos Sub IDs dos últimos 90 dias ela junta (e exemplos)."""
    regras = list(RegraSubId.objects.filter(conta=conta))
    pegos = {regra.pk: [] for regra in regras}
    brutos = (
        ResultadoSubIdDiario.objects.filter(conta=conta, dia__gte=hoje - timedelta(days=90))
        .values_list("sub_id", flat=True).distinct()
    )
    for bruto in brutos:
        if bruto == SEM_SUB_ID:
            continue
        regra = next((r for r in regras if r.casa(bruto)), None)
        if regra:
            pegos[regra.pk].append(bruto)
    return [
        {"regra": regra, "quantidade": len(pegos[regra.pk]), "exemplos": sorted(pegos[regra.pk])[:2]}
        for regra in regras
    ]


# --- Vendas (itens vendidos) -------------------------------------------------------------

VENDAS_POR_PAGINA = 20
VENDAS_POR_PAGINA_CELULAR = 10  # no celular cada venda vira um cartão mais alto
COOKIE_TELA = "appf_tela"  # "celular" ou "computador", marcado pelo vendas.js
ORDENS_VENDAS = {"recentes": ("-comprado_em", "pedido_id", "posicao"), "comissao": ("-comissao", "-comprado_em")}
FILTROS_SITUACAO = [("", "Todos"), (VendaItem.PENDENTE, "Pendentes"), (VendaItem.CONCLUIDO, "Concluídos"),
                    (VendaItem.CANCELADO, "Cancelados")]


def _limites(inicio: date, fim: date):
    fuso = timezone.get_current_timezone()
    return (datetime.combine(inicio, datetime.min.time(), tzinfo=fuso),
            datetime.combine(fim + timedelta(days=1), datetime.min.time(), tzinfo=fuso))


def vendas_do_periodo(conta, inicio: date, fim: date):
    de, ate = _limites(inicio, fim)
    return VendaItem.objects.filter(conta=conta, comprado_em__gte=de, comprado_em__lt=ate)


def grupos_das_vendas(conta, vendas) -> dict[str, list[str]]:
    """{nome mostrado: [Sub IDs guardados]} das vendas, com os agrupamentos da conta."""
    regras = list(RegraSubId.objects.filter(conta=conta))
    grupos: dict[str, list[str]] = {}
    for bruto in vendas.order_by().values_list("sub_id", flat=True).distinct():
        grupos.setdefault(nome_do_grupo(bruto, regras), []).append(bruto)
    return dict(sorted(grupos.items(), key=lambda par: par[0].lower()))


def filtrar_vendas(conta, inicio: date, fim: date, parametros) -> dict:
    """Vendas do período com os filtros da tela (busca, Sub ID/grupo, situação e ordem)."""
    vendas = vendas_do_periodo(conta, inicio, fim)
    grupos = grupos_das_vendas(conta, vendas)
    busca = str(parametros.get("busca") or "").strip()[:100]
    grupo = str(parametros.get("sub") or "")
    situacao = str(parametros.get("situacao") or "")
    ordem = parametros.get("ordem") if parametros.get("ordem") in ORDENS_VENDAS else "recentes"
    if busca:
        vendas = vendas.filter(nome__icontains=busca)
    if grupo in grupos:
        vendas = vendas.filter(sub_id__in=grupos[grupo])
    else:
        grupo = ""
    if situacao in dict(FILTROS_SITUACAO) and situacao:
        vendas = vendas.filter(situacao=situacao)
    else:
        situacao = ""
    regras = list(RegraSubId.objects.filter(conta=conta))
    return {
        "vendas": vendas.order_by(*ORDENS_VENDAS[ordem]),
        "grupos": list(grupos),
        "filtros": {"busca": busca, "sub": grupo, "situacao": situacao, "ordem": ordem},
        "nome_do_grupo": lambda bruto: nome_do_grupo(bruto, regras),
    }


def ranking_produtos(vendas, limite: int | None = 5) -> list[dict]:
    """Produtos mais vendidos (sem os cancelados): unidades, faturamento e comissão."""
    from django.db.models import Count, Max

    linhas = (
        vendas.exclude(situacao=VendaItem.CANCELADO).order_by()
        .values("item_id")
        .annotate(unidades=Sum("quantidade"), faturamento=Sum("valor"), comissao=Sum("comissao"),
                  nome=Max("nome"), imagem_url=Max("imagem_url"), loja=Max("loja"), pedidos=Count("id"))
        .order_by("-unidades", "-comissao")
    )
    linhas = list(linhas[:limite] if limite else linhas)
    maior = max((l["unidades"] for l in linhas), default=0) or 1
    for linha in linhas:
        linha["barra"] = round(100 * linha["unidades"] / maior)
    return linhas
