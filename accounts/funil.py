"""Medição do funil de quem chega sem conta (ROADMAP 13.11): quantos visitantes
esbarram no pedido de cadastro, quantos se cadastram (formulário ou Google) e quantos
geram o primeiro link depois. Decide se "converter sem cadastro" vale o esforço."""
import re
import secrets
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError

from .models import EventoFunil

SESSION_KEY_FUNIL = "funil_sem_conta_id"
# Prévias de link (WhatsApp, Facebook, Pinterest) e buscadores batem nessas URLs sem
# ser gente - contá-los inflaria as "tentativas".
PADRAO_ROBO = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|pinterest|headless", re.I)


def _eh_robo(request) -> bool:
    return bool(PADRAO_ROBO.search(request.META.get("HTTP_USER_AGENT", "")))


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
    _registrar(_funil_id(request, criar=True), EventoFunil.TENTATIVA, origem=origem)


def registrar_cadastro(request, metodo: str) -> None:
    """Todo cadastro novo entra - com ou sem tentativa antes (quem já chegou decidido)."""
    _registrar(_funil_id(request, criar=True), EventoFunil.CADASTRO, metodo=metodo)


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
