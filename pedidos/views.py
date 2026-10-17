from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import ReclamacaoPedidoForm
from .middleware import _previa_ligada
from .models import CampanhaCashback, ReclamacaoPedido
from .previa import CHAVE_SESSAO, DURACAO, pode_ver_previa
from .reclamacoes import ReclamacaoInvalida, abrir_reclamacao


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


@login_required
@require_http_methods(["GET", "POST"])
def compra_nao_apareceu(request):
    """Formulário de reclamação de compra não registrada + andamento das já enviadas."""
    if request.method == "POST":
        form = ReclamacaoPedidoForm(request.POST)
        if form.is_valid():
            try:
                reclamacao = abrir_reclamacao(
                    request.user,
                    form.cleaned_data["order_id"],
                    form.cleaned_data["data_compra"],
                    form.cleaned_data["produto"],
                )
            except ReclamacaoInvalida as erro:
                form.add_error(None, str(erro))
            else:
                if reclamacao.status == ReclamacaoPedido.STATUS_EM_ANALISE:
                    messages.success(
                        request,
                        "Encontramos esse pedido! Vamos conferir e, se estiver tudo certo, ele entra "
                        "na sua conta em poucos dias. Avisamos por e-mail.",
                    )
                else:
                    messages.success(
                        request,
                        "Recebemos seu aviso. Vamos procurar esse pedido nos próximos dias e te "
                        "avisamos por e-mail.",
                    )
                return redirect("compra_nao_apareceu")
    else:
        form = ReclamacaoPedidoForm()

    return render(
        request,
        "pedidos/compra_nao_apareceu.html",
        {"form": form, "reclamacoes": request.user.reclamacoes_pedido.all()[:20]},
    )
