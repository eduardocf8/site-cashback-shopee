"""Medição do funil de quem chega sem conta (ROADMAP 13.11): quantos visitantes
esbarram no pedido de cadastro, quantos se cadastram (formulário ou Google) e quantos
geram o primeiro link depois. Decide se "converter sem cadastro" vale o esforço."""
import re
import secrets
from datetime import timedelta
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import EventoFunil

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


def _taxa(parte, total):
    return round(100 * parte / total, 1) if total else None


def obter_funil(data_inicio=None, data_fim=None) -> dict:
    """Coorte = visitantes cuja TENTATIVA caiu no período; as etapas seguintes contam
    mesmo se aconteceram depois do fim do período."""
    from pedidos.analytics import _no_periodo

    tentativas = _no_periodo(EventoFunil.objects.filter(etapa=EventoFunil.TENTATIVA), "criado_em", data_inicio, data_fim)
    ids = tentativas.values("funil_id")
    cadastros_coorte = EventoFunil.objects.filter(etapa=EventoFunil.CADASTRO, funil_id__in=ids)
    links_coorte = EventoFunil.objects.filter(etapa=EventoFunil.PRIMEIRO_LINK, funil_id__in=ids)

    total = tentativas.count()
    cadastraram = cadastros_coorte.count()
    geraram_link = links_coorte.count()
    cadastros_periodo = _no_periodo(EventoFunil.objects.filter(etapa=EventoFunil.CADASTRO), "criado_em", data_inicio, data_fim)
    return {
        "tentativas": total,
        "tentativas_por_origem": {
            origem: tentativas.filter(origem=origem).count()
            for origem in ("conversor", "ir_shopee", "oferta", "story")
        },
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
