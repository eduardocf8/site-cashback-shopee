from django.utils import timezone
from django.utils.cache import add_never_cache_headers, patch_vary_headers
from django.utils.dateparse import parse_datetime

from .models import CampanhaCashback
from .previa import CAMINHOS, CHAVE_SESSAO, _campanha_previa, pode_ver_previa


def _previa_ligada(request) -> bool:
    ate = parse_datetime(request.session.get(CHAVE_SESSAO) or "")
    return bool(ate and timezone.is_aware(ate) and ate > timezone.now())


def campanha_para_previa(request):
    """A campanha a mostrar em prévia nesta requisição, ou None. Ver pedidos/previa.py: todas as
    travas são conferidas aqui, a cada requisição, da mais barata para a mais cara."""
    if request.method not in ("GET", "HEAD") or request.path not in CAMINHOS:
        return None
    if not pode_ver_previa(getattr(request, "user", None)):
        return None
    if not _previa_ligada(request):
        return None
    return CampanhaCashback.proxima_para_previa()


class PreviaCampanhaMiddleware:
    """Liga a prévia da campanha para o superusuário que a ativou. Vem DEPOIS do middleware de
    autenticação (precisa do usuário e da sessão)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        campanha = campanha_para_previa(request)
        if campanha is None:
            return self.get_response(request)

        token = _campanha_previa.set(campanha)
        try:
            # O template é renderizado aqui dentro, enquanto a prévia está ligada.
            resposta = self.get_response(request)
        finally:
            _campanha_previa.reset(token)

        add_never_cache_headers(resposta)
        resposta["Cache-Control"] = "private, no-store"
        patch_vary_headers(resposta, ("Cookie",))
        return resposta
