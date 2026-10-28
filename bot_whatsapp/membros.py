"""Painel de membros dos grupos (aba Membros do Bot de WhatsApp).

A pessoa escolhe até MAXIMO_GRUPOS grupos. O worker (gerenciador.py) lê a contagem de membros de
todos de uma vez, uma vez por hora (get_joined_groups traz os participantes de cada grupo), e o
WhatsApp avisa na hora quando alguém entra ou sai (GroupInfoEv): daí saem as entradas e saídas do
dia. Guarda só números, nunca quem entrou ou saiu.

O histórico começa quando o grupo é escolhido: o WhatsApp não conta o passado."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from .models import DiaMembros, GrupoMonitorado, LeituraMembros

MAXIMO_GRUPOS = 500
LIMITE_DO_WHATSAPP = 1024  # membros por grupo
QUASE_CHEIO = 95  # % do limite
INTERVALO_DE_LEITURA = timedelta(hours=1)
GUARDA_LEITURAS = timedelta(days=2)
GUARDA_DIAS = 395  # 13 meses, como as vendas


# --- Escolha dos grupos (painel) ---------------------------------------------------------

def grupos_possiveis(conexao) -> list[dict]:
    """Os grupos do número do bot (sem os canais), com quantos membros têm agora."""
    return [g for g in (conexao.grupos if conexao else []) or []
            if g.get("tipo", "grupo") == "grupo" and str(g.get("jid", "")).endswith("@g.us")]


def escolher(conta, jids: list[str], conexao) -> int:
    """Troca os grupos monitorados pelos escolhidos (até MAXIMO_GRUPOS). Os que saem perdem o
    histórico; os novos aparecem com a contagem que a conexão já conhece e o worker lê de novo
    na próxima volta. Devolve quantos ficaram."""
    possiveis = {g["jid"]: g for g in grupos_possiveis(conexao)}
    escolhidos = [j for j in dict.fromkeys(jids) if j in possiveis][:MAXIMO_GRUPOS]
    with transaction.atomic():
        GrupoMonitorado.objects.filter(conta=conta).exclude(jid__in=escolhidos).delete()
        existentes = set(GrupoMonitorado.objects.filter(conta=conta).values_list("jid", flat=True))
        GrupoMonitorado.objects.bulk_create([
            GrupoMonitorado(conta=conta, jid=jid, nome=str(possiveis[jid].get("nome", ""))[:200],
                            admin=bool(possiveis[jid].get("admin")), membros=possiveis[jid].get("participantes"))
            for jid in escolhidos if jid not in existentes
        ])
    return len(escolhidos)


# --- Coleta (worker) ---------------------------------------------------------------------

def contas_para_ler(agora) -> list[int]:
    """Contas com algum grupo monitorado sem leitura há uma hora (ou recém-escolhido)."""
    vencidos = Q(lido_em__isnull=True) | Q(lido_em__lt=agora - INTERVALO_DE_LEITURA)
    return list(GrupoMonitorado.objects.filter(vencidos).order_by().values_list("conta_id", flat=True).distinct())


def atualizar(conta_id: int, dados: dict[str, dict], agora) -> int:
    """dados = {jid: {"membros", "nome", "admin"}} de todos os grupos do número (uma leitura só).
    Grava a leitura dos monitorados; o que não veio é grupo de onde o bot saiu."""
    hoje = timezone.localtime(agora).date()
    lidos = 0
    for grupo in GrupoMonitorado.objects.filter(conta_id=conta_id):
        info = dados.get(grupo.jid)
        if not info:
            if grupo.no_grupo:
                grupo.no_grupo, grupo.lido_em = False, agora
                grupo.save(update_fields=["no_grupo", "lido_em"])
            else:
                GrupoMonitorado.objects.filter(pk=grupo.pk).update(lido_em=agora)
            continue
        grupo.membros, grupo.lido_em, grupo.no_grupo = int(info["membros"]), agora, True
        grupo.nome = str(info.get("nome") or grupo.nome)[:200]
        grupo.admin = bool(info.get("admin"))
        grupo.save(update_fields=["membros", "lido_em", "no_grupo", "nome", "admin"])
        LeituraMembros.objects.create(grupo=grupo, em=agora, membros=grupo.membros)
        DiaMembros.objects.update_or_create(grupo=grupo, dia=hoje, defaults={"membros": grupo.membros})
        lidos += 1
    return lidos


def registrar_mudanca(conta_id: int, jid: str, entradas: int, saidas: int, agora) -> None:
    """Alguém entrou ou saiu (aviso do WhatsApp na hora): soma no dia e ajusta a contagem."""
    grupo = GrupoMonitorado.objects.filter(conta_id=conta_id, jid=jid).first()
    if not grupo or not (entradas or saidas):
        return
    hoje = timezone.localtime(agora).date()
    if grupo.membros is not None:
        grupo.membros = max(0, grupo.membros + entradas - saidas)
        grupo.save(update_fields=["membros"])
    dia, _ = DiaMembros.objects.get_or_create(grupo=grupo, dia=hoje)
    DiaMembros.objects.filter(pk=dia.pk).update(entradas=F("entradas") + entradas, saidas=F("saidas") + saidas,
                                                membros=grupo.membros)


def limpar(agora) -> None:
    LeituraMembros.objects.filter(em__lt=agora - GUARDA_LEITURAS).delete()
    DiaMembros.objects.filter(dia__lt=timezone.localtime(agora).date() - timedelta(days=GUARDA_DIAS)).delete()


# --- Tela --------------------------------------------------------------------------------

def _membros_ate(dias_do_grupo: dict, dia) -> int | None:
    """A última contagem guardada até esse dia (inclusive)."""
    anteriores = [d for d in dias_do_grupo if d <= dia and dias_do_grupo[d] is not None]
    return dias_do_grupo[max(anteriores)] if anteriores else None


def _variacao(atual, antes):
    return None if atual is None or antes is None else atual - antes


def painel(conta, agora=None) -> dict:
    """Tudo o que a aba Membros mostra: os grupos (com variação, lotação e comissão por Sub ID
    próprio), os totais e o gráfico dos últimos 30 dias."""
    from painel.models import ResultadoSubIdDiario

    from .models import ConfiguracaoOfertas

    agora = agora or timezone.now()
    hoje = timezone.localtime(agora).date()
    grupos = list(GrupoMonitorado.objects.filter(conta=conta))
    ids = [g.pk for g in grupos]

    # Contagem de 24 h atrás: a última leitura até lá (das últimas 30 h, pra não pegar velha demais).
    ha_24h = {}
    for grupo_id, membros in (LeituraMembros.objects.filter(grupo_id__in=ids, em__lte=agora - timedelta(hours=24),
                                                            em__gte=agora - timedelta(hours=30))
                              .order_by("grupo_id", "-em").values_list("grupo_id", "membros")):
        ha_24h.setdefault(grupo_id, membros)
    dias = defaultdict(dict)
    hoje_por_grupo = {}
    for d in DiaMembros.objects.filter(grupo_id__in=ids, dia__gte=hoje - timedelta(days=31)):
        dias[d.grupo_id][d.dia] = d.membros
        if d.dia == hoje:
            hoje_por_grupo[d.grupo_id] = d

    # Membros x vendas: só os grupos com Sub ID próprio na Automação dão pra separar.
    config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
    chaves = {}
    for g in grupos:
        if config and (config.sub_ids_por_grupo or {}).get(g.jid):
            chaves[g.jid] = "-".join(config.lista_sub_ids(g.jid))
    inicio_mes, ontem = hoje.replace(day=1), hoje - timedelta(days=1)
    comissoes = dict(ResultadoSubIdDiario.objects.filter(conta=conta, sub_id__in=set(chaves.values()), dia__gte=inicio_mes,
                                                         dia__lte=ontem)
                     .values("sub_id").annotate(total=Sum("comissao_estimada")).values_list("sub_id", "total")) if chaves else {}

    linhas = []
    for g in grupos:
        do_dia = hoje_por_grupo.get(g.pk)
        comissao = comissoes.get(chaves.get(g.jid), Decimal("0")) if g.jid in chaves else None
        lotacao = round((g.membros or 0) * 100 / LIMITE_DO_WHATSAPP)
        linhas.append({
            "grupo": g, "membros": g.membros,
            "var_24h": _variacao(g.membros, ha_24h.get(g.pk)),
            "var_7d": _variacao(g.membros, _membros_ate(dias[g.pk], hoje - timedelta(days=7))),
            "var_30d": _variacao(g.membros, _membros_ate(dias[g.pk], hoje - timedelta(days=30))),
            "entradas": do_dia.entradas if do_dia else 0, "saidas": do_dia.saidas if do_dia else 0,
            "lotacao": min(100, lotacao), "quase_cheio": lotacao >= QUASE_CHEIO,
            "sub_id": chaves.get(g.jid, ""), "comissao": comissao,
            "por_membro": (comissao / g.membros) if comissao is not None and g.membros else None,
        })
    linhas.sort(key=lambda linha: (-(linha["membros"] or 0), linha["grupo"].nome.lower()))

    def soma(chave):
        valores = [linha[chave] for linha in linhas if linha[chave] is not None]
        return sum(valores) if valores else None

    serie = []
    for i in range(29, -1, -1):
        dia = hoje - timedelta(days=i)
        valores = [g.membros if dia == hoje else _membros_ate(dias[g.pk], dia) for g in grupos]
        serie.append({"dia": dia, "membros": sum(v for v in valores if v is not None)})
    return {
        "linhas": linhas, "quantos": len(linhas), "maximo": MAXIMO_GRUPOS,
        "total": soma("membros") or 0, "var_24h": soma("var_24h"), "var_7d": soma("var_7d"), "var_30d": soma("var_30d"),
        "entradas": sum(linha["entradas"] for linha in linhas), "saidas": sum(linha["saidas"] for linha in linhas),
        "quase_cheios": sum(1 for linha in linhas if linha["quase_cheio"]),
        "tem_comissao": bool(chaves), "serie": serie,
        "lido_em": max((g.lido_em for g in grupos if g.lido_em), default=None),
        "monitorando_desde": min((g.criado_em for g in grupos), default=None),
    }
