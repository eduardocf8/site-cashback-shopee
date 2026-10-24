"""Medição do funil de quem chega sem conta (ROADMAP 13.11): quantos visitantes
esbarram no pedido de cadastro, quantos se cadastram (formulário ou Google) e quantos
geram o primeiro link depois. A partir de 24/10/2026, também decide quem clica sem
cadastro (página de escolha) e mede quantos desses seguem pra Shopee."""
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import EventoFunil
from .ratelimit import _incrementar_contador, _obter_ip

SESSION_KEY_FUNIL = "funil_sem_conta_id"
# Prévias de link (WhatsApp, Facebook, Pinterest), buscadores, ferramentas de SEO e
# scripts batem nessas URLs sem ser gente - contá-los inflaria as "tentativas".
# "externalagent" pega o robô da Meta que abre links compartilhados no Instagram
# (meta-externalagent) e o de catálogo (facebookcatalog).
PADRAO_ROBO = re.compile(
    r"bot|crawl|spider|slurp|preview|scrap|fetch|headless|lighthouse|pagespeed|"
    r"facebookexternalhit|externalagent|facebookcatalog|whatsapp|pinterest|telegram|"
    r"discord|slack|skype|embedly|google-inspectiontool|googleother|"
    r"python|curl|wget|go-http-client|okhttp|axios|java/|libwww|httpclient|"
    r"semrush|ahrefs|gtmetrix",
    re.I,
)
TAMANHO_USER_AGENT = 255


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")


def _eh_robo(request) -> bool:
    user_agent = _user_agent(request)
    # Navegador de verdade sempre manda User-Agent; vazio é script.
    return not user_agent.strip() or bool(PADRAO_ROBO.search(user_agent))


def _funil_id(request, criar: bool) -> str | None:
    funil_id = request.session.get(SESSION_KEY_FUNIL)
    if not funil_id and criar:
        funil_id = secrets.token_hex(16)
        request.session[SESSION_KEY_FUNIL] = funil_id
    return funil_id


def _registrar(funil_id, etapa, **campos):
    try:
        EventoFunil.objects.get_or_create(funil_id=funil_id, etapa=etapa, defaults=campos)
    except IntegrityError:  # duas requisições simultâneas do mesmo visitante
        pass


def registrar_tentativa(request, origem: str) -> None:
    if request.user.is_authenticated or _eh_robo(request):
        return
    _registrar(
        _funil_id(request, criar=True), EventoFunil.TENTATIVA,
        origem=origem, user_agent=_user_agent(request)[:TAMANHO_USER_AGENT],
    )


def registrar_cadastro(request, metodo: str) -> None:
    """Todo cadastro novo entra - com ou sem tentativa antes (quem já chegou decidido)."""
    _registrar(
        _funil_id(request, criar=True), EventoFunil.CADASTRO,
        metodo=metodo, user_agent=_user_agent(request)[:TAMANHO_USER_AGENT],
    )


def registrar_primeiro_link(request) -> None:
    funil_id = _funil_id(request, criar=False)
    if funil_id and EventoFunil.objects.filter(funil_id=funil_id, etapa=EventoFunil.CADASTRO).exists():
        _registrar(funil_id, EventoFunil.PRIMEIRO_LINK)


def registrar_clique_sem_conta(request, origem: str) -> None:
    _registrar(
        _funil_id(request, criar=True), EventoFunil.CLICOU_SEM_CONTA,
        origem=origem, user_agent=_user_agent(request)[:TAMANHO_USER_AGENT],
    )


def exigir_login_medindo(origem: str):
    """Como @login_required, mas registra a tentativa de quem esbarrou no login."""
    def decorador(view):
        @wraps(view)
        def envolvida(request, *args, **kwargs):
            if not request.user.is_authenticated:
                registrar_tentativa(request, origem)
                return redirect_to_login(request.get_full_path())
            return view(request, *args, **kwargs)
        return envolvida
    return decorador


PARAMETRO_CONTINUAR_SEM_CADASTRO = "continuar"
VALOR_CONTINUAR_SEM_CADASTRO = "sem_cadastro"
# Só limita quem está nesse caminho específico (sem conta) - quem já tem conta não
# tem limite nenhum aqui, é só o normal de usar o site. 20/hora dá folga de sobra pra
# alguém navegando várias ofertas antes de decidir se cadastra, e ainda protege a
# cota da API Shopee (gerar_click chama ela) de um script batendo direto na URL.
LIMITE_CLIQUES_ANONIMOS_POR_HORA = 20
JANELA_CLIQUES_ANONIMOS_SEGUNDOS = 3600


def _clique_anonimo_permitido(request) -> bool:
    chave = f"ratelimit:click_anonimo:{_obter_ip(request)}"
    return _incrementar_contador(chave, JANELA_CLIQUES_ANONIMOS_SEGUNDOS) <= LIMITE_CLIQUES_ANONIMOS_POR_HORA


def exigir_login_ou_pagina_de_escolha(origem: str):
    """Como exigir_login_medindo, mas em vez de forçar login de cara, manda pra página
    de escolha (links/views.py::continuar_sem_cadastro, ROADMAP 13.11 - decisão de
    24/10/2026): "cadastrar e continuar" (ganha cashback) ou "continuar sem cadastro"
    (vai pra Shopee sem cashback, clique fica anônimo - ver Click.usuario em
    links/models.py). Só deixa passar sem conta quando a pessoa já escolheu a segunda
    opção ali (volta com ?continuar=sem_cadastro na mesma URL)."""
    def decorador(view):
        @wraps(view)
        def envolvida(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view(request, *args, **kwargs)
            if request.GET.get(PARAMETRO_CONTINUAR_SEM_CADASTRO) == VALOR_CONTINUAR_SEM_CADASTRO:
                if not _clique_anonimo_permitido(request):
                    return HttpResponse(
                        "Muitas tentativas sem cadastro. Crie uma conta pra continuar.", status=429
                    )
                registrar_tentativa(request, origem)
                registrar_clique_sem_conta(request, origem)
                return view(request, *args, **kwargs)
            registrar_tentativa(request, origem)
            proximo = request.get_full_path()
            return redirect(f"{reverse('continuar_sem_cadastro')}?{urlencode({'next': proximo, 'origem': origem})}")
        return envolvida
    return decorador


def _taxa(parte, total):
    return round(100 * parte / total, 1) if total else None


def obter_funil(data_inicio=None, data_fim=None) -> dict:
    """Coorte = visitantes cuja TENTATIVA caiu no período; as etapas seguintes contam
    mesmo se aconteceram depois do fim do período."""
    from pedidos.analytics import _no_periodo

    tentativas = _no_periodo(EventoFunil.objects.filter(etapa=EventoFunil.TENTATIVA), "criado_em", data_inicio, data_fim)
    ids = tentativas.values("funil_id")
    clicaram_sem_conta_coorte = EventoFunil.objects.filter(etapa=EventoFunil.CLICOU_SEM_CONTA, funil_id__in=ids)
    cadastros_coorte = EventoFunil.objects.filter(etapa=EventoFunil.CADASTRO, funil_id__in=ids)
    links_coorte = EventoFunil.objects.filter(etapa=EventoFunil.PRIMEIRO_LINK, funil_id__in=ids)

    total = tentativas.count()
    clicaram_sem_conta = clicaram_sem_conta_coorte.count()
    cadastraram = cadastros_coorte.count()
    geraram_link = links_coorte.count()
    cadastros_periodo = _no_periodo(EventoFunil.objects.filter(etapa=EventoFunil.CADASTRO), "criado_em", data_inicio, data_fim)
    return {
        "tentativas": total,
        "tentativas_por_origem": {
            origem: tentativas.filter(origem=origem).count()
            for origem in ("conversor", "ir_shopee", "oferta", "story")
        },
        # Desde a decisão de 24/10/2026 (ROADMAP 13.11): quem esbarrou no login e
        # escolheu "continuar sem cadastro" na página de escolha, e quantos desses
        # se cadastraram depois (qualquer dia, não só dentro do período).
        "clicaram_sem_conta": clicaram_sem_conta,
        "taxa_clique_sem_conta": _taxa(clicaram_sem_conta, total),
        "cadastraram_depois_de_clicar_sem_conta": EventoFunil.objects.filter(
            etapa=EventoFunil.CADASTRO, funil_id__in=clicaram_sem_conta_coorte.values("funil_id")
        ).count(),
        "cadastraram": cadastraram,
        "cadastraram_google": cadastros_coorte.filter(metodo="google").count(),
        "geraram_link": geraram_link,
        "taxa_cadastro": _taxa(cadastraram, total),
        "taxa_link": _taxa(geraram_link, total),
        "cadastros_periodo": cadastros_periodo.count(),
        "cadastros_periodo_google": cadastros_periodo.filter(metodo="google").count(),
    }


DIAS_PADRAO_CADASTROS_POR_DIA = 30
DIAS_MAXIMOS_CADASTROS_POR_DIA = 90


def obter_cadastros_por_dia(data_inicio=None, data_fim=None) -> list[dict]:
    """Uma linha por dia (mais recente primeiro): total de cadastros, pelo Google e pelo
    formulário. Sem período, os últimos 30 dias; períodos longos ficam com os 90 dias
    finais. Só tem dados desde a Fase 62 (início da medição do funil)."""
    fim = data_fim or timezone.localdate()
    inicio = data_inicio or fim - timedelta(days=DIAS_PADRAO_CADASTROS_POR_DIA - 1)
    inicio = max(inicio, fim - timedelta(days=DIAS_MAXIMOS_CADASTROS_POR_DIA - 1))

    por_dia = {
        linha["dia"]: linha
        for linha in EventoFunil.objects.filter(
            etapa=EventoFunil.CADASTRO, criado_em__date__gte=inicio, criado_em__date__lte=fim
        )
        .annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(total=Count("id"), google=Count("id", filter=Q(metodo="google")))
    }
    linhas = []
    dia = fim
    while dia >= inicio:
        linha = por_dia.get(dia, {"total": 0, "google": 0})
        linhas.append({
            "dia": dia,
            "total": linha["total"],
            "google": linha["google"],
            "formulario": linha["total"] - linha["google"],
        })
        dia -= timedelta(days=1)
    return linhas
