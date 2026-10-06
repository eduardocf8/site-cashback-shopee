from datetime import timedelta

from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .middleware import _previa_ligada
from .models import CampanhaCashback
from .previa import CHAVE_SESSAO, DURACAO, pode_ver_previa


@require_http_methods(["GET", "POST"])
def previa_campanha(request):
    """Liga/desliga a prévia da campanha, só para o superusuário logado (ver pedidos/previa.py).

    Para qualquer outra pessoa - anônima, usuário comum, até staff que não seja superusuário - a
    página responde 404, igual a uma que não existe: nem a existência da tela é revelada."""
    if not pode_ver_previa(request.user):
        raise Http404()

    if request.method == "POST":
        if request.POST.get("acao") == "ligar" and CampanhaCashback.proxima_para_previa():
            request.session[CHAVE_SESSAO] = (timezone.now() + DURACAO).isoformat()
        else:
            request.session.pop(CHAVE_SESSAO, None)
        return redirect("previa_campanha")

    resposta = render(
        request,
        "previa_campanha.html",
        {
            "campanha": CampanhaCashback.proxima_para_previa(),
            "ligada": _previa_ligada(request),
            "horas": int(DURACAO / timedelta(hours=1)),
        },
    )
    resposta["Cache-Control"] = "private, no-store"
    return resposta
