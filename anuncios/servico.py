"""Campanhas da Meta: conectar, ler os gastos (worker) e montar os números da tela.

- Conectar: Login do Facebook para Empresas (só ads_read). O token de 60 dias fica cifrado; perto de
  vencer, o painel pede para conectar de novo.
- Ler: o worker lê de hora em hora o gasto, as impressões e os cliques de cada campanha, por dia, das
  contas de anúncios que a pessoa escolheu (os últimos 3 dias; na primeira vez, 30).
- Tela: cada campanha ligada a um Sub ID da Shopee (pelo nome da campanha ou escolhido à mão), com o
  investimento mais o imposto da Meta, as vendas, a comissão estimada, a margem e o ROAS. Campanha que
  leva ao link de entrada (utm_campaign igual ao nome) mostra também quanto custou cada clique para
  entrar no grupo.

Em construção: só para contas com a chave beta_campanhas_meta (admin)."""

import base64
import hashlib
import hmac
import json
import logging
import re
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from painel import cripto

from . import meta
from .models import CampanhaMeta, ConexaoMeta, ContaAnuncios, DiaCampanha

logger = logging.getLogger(__name__)

LER_A_CADA = timedelta(hours=1)
DIAS_NA_PRIMEIRA_LEITURA = 30
DIAS_NAS_OUTRAS = 3  # a Meta ainda ajusta o gasto dos últimos dias
AVISAR_ANTES = timedelta(days=7)
CONEXOES_POR_VOLTA = 10
PERIODOS = [(7, "7 dias"), (15, "15 dias"), (30, "30 dias")]
CEM = Decimal(100)


class ErroConexao(Exception):
    """Mensagem pronta para mostrar à pessoa."""


def liberado(conta) -> bool:
    return bool(getattr(conta, "beta_campanhas_meta", False))


def chave(texto: str) -> str:
    """Para comparar nome de campanha com Sub ID: só letras e números, sem maiúsculas."""
    return re.sub(r"[^0-9a-z]", "", str(texto or "").lower())


# --- conectar e desconectar ------------------------------------------------------------------

def conectar(conta, codigo: str, redirect_uri: str) -> ConexaoMeta:
    try:
        curto = meta.trocar_codigo(codigo, redirect_uri)
        try:
            longo = meta.token_longo(curto["access_token"])
        except meta.ErroMeta:
            longo = curto  # o token do login já pode vir longo: segue com ele
        token = longo["access_token"]
        pessoa = meta.eu(token)
        contas = meta.contas_de_anuncios(token)
    except (meta.ErroMeta, KeyError) as erro:
        logger.warning("Meta: falha ao conectar a conta %s: %s", conta.pk, erro)
        raise ErroConexao("Não consegui conectar a sua conta de anúncios agora. Tente de novo em instantes.") from erro
    if not contas:
        raise ErroConexao("Nenhuma conta de anúncios foi liberada. Conecte de novo e marque a conta de anúncios.")
    segundos = int(longo.get("expires_in") or 60 * 86400)
    with transaction.atomic():
        conexao, _ = ConexaoMeta.objects.update_or_create(conta=conta, defaults={
            "usuario_id": str(pessoa.get("id") or "")[:64], "nome": str(pessoa.get("name") or "")[:150],
            "token_cifrado": cripto.cifrar(token), "token_expira_em": timezone.now() + timedelta(seconds=segundos),
            "erro": "", "pedido_em": timezone.now(),
        })
        vistas = []
        for c in contas:
            account_id = str(c.get("account_id") or "")
            if not account_id:
                continue
            vistas.append(account_id)
            ContaAnuncios.objects.update_or_create(conexao=conexao, account_id=account_id, defaults={
                "nome": str(c.get("name") or account_id)[:200], "moeda": str(c.get("currency") or "")[:8]})
        conexao.contas.exclude(account_id__in=vistas).delete()  # tirou o acesso a ela no login
    return conexao


def desconectar(conta) -> None:
    """Apaga a conexão e tudo o que foi lido (contas, campanhas e gastos)."""
    ConexaoMeta.objects.filter(conta=conta).delete()


def ler_signed_request(valor: str) -> dict | None:
    """Confere a assinatura do signed_request (HMAC-SHA256 com o segredo do app) e devolve o conteúdo."""
    try:
        assinatura, corpo = valor.split(".", 1)

        def b64(s):
            return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        esperado = hmac.new(meta.app_secret().encode(), corpo.encode(), hashlib.sha256).digest()
        if not meta.app_secret() or not hmac.compare_digest(esperado, b64(assinatura)):
            return None
        return json.loads(b64(corpo))
    except (ValueError, TypeError):
        return None


def apagar_por_usuario(usuario_id: str) -> int:
    if not usuario_id:
        return 0
    return ConexaoMeta.objects.filter(usuario_id=str(usuario_id)).delete()[1].get("anuncios.ConexaoMeta", 0)


# --- leitura (worker) --------------------------------------------------------------------------

def para_ler(agora) -> list[ConexaoMeta]:
    from django.db.models import F, Q

    vencidas = Q(lido_em__isnull=True) | Q(lido_em__lt=agora - LER_A_CADA) | Q(pedido_em__gt=F("lido_em"))
    return list(ConexaoMeta.objects.filter(vencidas, conta__beta_campanhas_meta=True)
                .exclude(token_expira_em__lt=agora).select_related("conta").order_by("lido_em")[:CONEXOES_POR_VOLTA])


def _decimal(valor) -> Decimal:
    try:
        return Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    except (ArithmeticError, ValueError):
        return Decimal(0)


def ler(conexao: ConexaoMeta, agora=None) -> str:
    """Lê as campanhas e os gastos por dia das contas acompanhadas. Devolve uma linha de log."""
    agora = agora or timezone.now()
    hoje = timezone.localdate(agora)
    desde = hoje - timedelta(days=(DIAS_NAS_OUTRAS if conexao.lido_em else DIAS_NA_PRIMEIRA_LEITURA) - 1)
    token, linhas = conexao.token, 0
    try:
        for conta_anuncios in conexao.contas.filter(acompanhar=True):
            existentes = {c.campanha_id: c for c in conta_anuncios.campanhas.all()}
            for c in meta.campanhas(token, conta_anuncios.account_id):
                campanha = existentes.get(str(c.get("id")))
                criada = _data_da_meta(c.get("created_time"))
                if campanha is None:
                    campanha = CampanhaMeta.objects.create(
                        conta_anuncios=conta_anuncios, campanha_id=str(c.get("id")), nome=str(c.get("name") or "")[:300],
                        situacao=str(c.get("effective_status") or "")[:40], criada_na_meta=criada)
                    existentes[campanha.campanha_id] = campanha
                else:
                    campanha.nome, campanha.situacao = str(c.get("name") or campanha.nome)[:300], str(c.get("effective_status") or "")[:40]
                    campanha.criada_na_meta = criada or campanha.criada_na_meta
                    campanha.save(update_fields=["nome", "situacao", "criada_na_meta"])
            for linha in meta.gastos_por_dia(token, conta_anuncios.account_id, desde, hoje):
                campanha = existentes.get(str(linha.get("campaign_id")))
                if campanha is None:  # campanha apagada na Meta, mas com gasto no período
                    campanha = CampanhaMeta.objects.create(
                        conta_anuncios=conta_anuncios, campanha_id=str(linha.get("campaign_id")),
                        nome=str(linha.get("campaign_name") or "")[:300], situacao="DELETED")
                    existentes[campanha.campanha_id] = campanha
                DiaCampanha.objects.update_or_create(campanha=campanha, dia=linha.get("date_start"), defaults={
                    "gasto": _decimal(linha.get("spend")), "impressoes": int(linha.get("impressions") or 0),
                    "cliques": int(linha.get("inline_link_clicks") or 0)})
                linhas += 1
        conexao.erro = ""
    except meta.ErroMeta as erro:
        logger.warning("Meta: falha ao ler a conta %s: %s", conexao.conta_id, erro)
        conexao.erro = ("O acesso à sua conta de anúncios expirou ou foi retirado. Conecte de novo."
                        if erro.codigo == meta.TOKEN_INVALIDO else f"Não deu para ler as campanhas agora: {erro}")[:300]
    conexao.lido_em = agora
    conexao.save(update_fields=["erro", "lido_em", "atualizada_em"])
    return f"Meta: conta {conexao.conta_id}, {linhas} linha(s) de gasto" + (f" (erro: {conexao.erro})" if conexao.erro else "")


def _data_da_meta(texto):
    from django.utils.dateparse import parse_datetime

    try:
        return parse_datetime(str(texto or "").replace("+0000", "+00:00")) if texto else None
    except ValueError:
        return None


def sincronizar(agora=None) -> list[str]:
    """Chamado pelo worker do painel a cada volta."""
    agora = agora or timezone.now()
    return [ler(conexao, agora) for conexao in para_ler(agora)]


# --- tela ----------------------------------------------------------------------------------------

def sub_ids_conhecidos(conta, hoje) -> list[str]:
    """Os Sub IDs (um por um) das vendas dos últimos 90 dias, para escolher à mão."""
    from painel.models import ResultadoSubIdDiario
    from painel.resultados import SEM_SUB_ID

    vistos = set()
    for rotulo in (ResultadoSubIdDiario.objects.filter(conta=conta, dia__gte=hoje - timedelta(days=90))
                   .exclude(sub_id=SEM_SUB_ID).values_list("sub_id", flat=True).distinct()):
        vistos.update(p for p in rotulo.split("-") if p)
    return sorted(vistos, key=str.lower)


def sub_id_da_campanha(campanha: CampanhaMeta, conhecidos: dict[str, str]) -> tuple[str, bool]:
    """(Sub ID, escolhido à mão). Sem escolha, o Sub ID com o mesmo nome da campanha."""
    if campanha.sub_id:
        return campanha.sub_id, True
    return conhecidos.get(chave(campanha.nome), ""), False


def _comissoes(conta, sub_ids: set[str], inicio, fim) -> dict:
    """{(chave do Sub ID, dia): {"vendas", "comissao"}}: soma as vendas em que o Sub ID aparece no link."""
    from painel.models import ResultadoSubIdDiario

    resultado = defaultdict(lambda: {"vendas": 0, "comissao": Decimal(0)})
    if not sub_ids:
        return resultado
    for r in ResultadoSubIdDiario.objects.filter(conta=conta, dia__gte=inicio, dia__lte=fim):
        partes = {chave(p) for p in r.sub_id.split("-")}
        for s in partes & sub_ids:
            item = resultado[(s, r.dia)]
            item["vendas"] += r.vendas
            item["comissao"] += r.comissao_estimada
    return resultado


def _cliques_no_grupo(conta, inicio, fim) -> dict:
    """{(chave da utm_campaign, dia): cliques no botão do link de entrada}."""
    from bot_whatsapp.models import AcessoEntrada

    resultado = defaultdict(int)
    for a in AcessoEntrada.objects.filter(link__conta=conta, dia__gte=inicio, dia__lte=fim).exclude(campanha=""):
        resultado[(chave(a.campanha), a.dia)] += a.cliques
    return resultado


def _numeros(gasto, imposto, vendas, comissao, cliques, cliques_grupo) -> dict:
    investimento = (gasto * (1 + imposto / CEM)).quantize(Decimal("0.01"))
    return {
        "gasto": gasto, "investimento": investimento, "vendas": vendas, "comissao": comissao,
        "margem": comissao - investimento, "roas": (comissao / investimento) if investimento else None,
        "cliques": cliques, "cpc": (investimento / cliques) if cliques else None,
        "cliques_grupo": cliques_grupo, "custo_grupo": (investimento / cliques_grupo) if cliques_grupo else None,
    }


def tela(conexao: ConexaoMeta, dias: int, hoje=None) -> dict:
    """Os números de cada campanha no período (com os dias) e o total."""
    hoje = hoje or timezone.localdate()
    inicio = hoje - timedelta(days=dias - 1)
    conta = conexao.conta
    conhecidos = {chave(s): s for s in sub_ids_conhecidos(conta, hoje)}
    campanhas = list(CampanhaMeta.objects.filter(conta_anuncios__conexao=conexao, conta_anuncios__acompanhar=True)
                     .select_related("conta_anuncios"))
    gastos = defaultdict(dict)
    for d in DiaCampanha.objects.filter(campanha__in=campanhas, dia__gte=inicio, dia__lte=hoje):
        gastos[d.campanha_id][d.dia] = d
    vinculos = {c.pk: sub_id_da_campanha(c, conhecidos) for c in campanhas}
    comissoes = _comissoes(conta, {chave(s) for s, _ in vinculos.values() if s}, inicio, hoje)
    grupo = _cliques_no_grupo(conta, inicio, hoje)
    linhas, total = [], defaultdict(lambda: Decimal(0))
    for c in campanhas:
        if not gastos[c.pk]:
            continue  # sem gasto no período
        sub_id, manual = vinculos[c.pk]
        k_sub, k_nome = chave(sub_id), chave(c.nome)
        por_dia = []
        for i in range(dias):
            dia = hoje - timedelta(days=i)
            g = gastos[c.pk].get(dia)
            venda = comissoes.get((k_sub, dia), {"vendas": 0, "comissao": Decimal(0)}) if k_sub else {"vendas": 0, "comissao": Decimal(0)}
            if not g and not venda["vendas"]:
                continue
            por_dia.append({"dia": dia, **_numeros(g.gasto if g else Decimal(0), conexao.imposto, venda["vendas"],
                                                    venda["comissao"], g.cliques if g else 0, grupo.get((k_nome, dia), 0))})
        soma = {k: sum((d[k] for d in por_dia), Decimal(0) if k in ("gasto", "comissao") else 0)
                for k in ("gasto", "vendas", "comissao", "cliques", "cliques_grupo")}
        numeros = _numeros(soma["gasto"], conexao.imposto, soma["vendas"], soma["comissao"], soma["cliques"], soma["cliques_grupo"])
        linhas.append({"campanha": c, "sub_id": sub_id, "manual": manual, "dias": por_dia, **numeros,
                       "ativa": c.situacao == "ACTIVE"})
        for k in ("gasto", "vendas", "comissao", "cliques"):
            total[k] += soma[k]
    linhas.sort(key=lambda linha: -linha["investimento"])
    return {
        "linhas": linhas, "inicio": inicio, "fim": hoje, "dias": dias,
        "total": _numeros(total["gasto"], conexao.imposto, int(total["vendas"]), total["comissao"], int(total["cliques"]), 0),
        "sub_ids": sorted(conhecidos.values(), key=str.lower),
        "sem_sub_id": sum(1 for linha in linhas if not linha["sub_id"]),
        "vence_logo": bool(conexao.token_expira_em and conexao.token_expira_em - timezone.now() < AVISAR_ANTES),
        "outra_moeda": sorted({c.moeda for c in conexao.contas.filter(acompanhar=True) if c.moeda and c.moeda != "BRL"}),
    }
