"""Resultados › Campanhas da Meta (anuncios/servico.py). Em construção: só para contas com a chave
beta_campanhas_meta ligada no admin."""

import json
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from anuncios import meta, servico
from anuncios.models import CampanhaMeta, ConexaoMeta

from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

SESSAO_STATE = "meta_ads_state"
SESSAO_JANELA = "meta_ads_janela"


def _conta_com_beta(request):
    conta = conta_logada(request)
    if not servico.liberado(conta):
        raise Http404
    return conta


def _retorno_url() -> str:
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_meta_retorno")


@conta_requerida
def campanhas(request):
    conta = _conta_com_beta(request)
    conexao = ConexaoMeta.objects.filter(conta=conta).first()
    if request.method == "POST" and conexao:
        return _acao(request, conexao)
    dias = request.GET.get("dias", "7")
    dias = int(dias) if dias in {str(d) for d, _ in servico.PERIODOS} else 7
    dados = servico.tela(conexao, dias) if conexao else None
    return render(request, "painel/campanhas_meta.html", _contexto(
        request, "resultados", conexao=conexao, dados=dados, periodos=servico.PERIODOS, configurado=meta.configurado(),
        contas=list(conexao.contas.all()) if conexao else [],
    ))


def _acao(request, conexao):
    acao = request.POST.get("acao", "")
    voltar = reverse("painel_campanhas_meta") + (f"?dias={request.POST['dias']}" if request.POST.get("dias", "").isdigit() else "")
    if acao == "atualizar":
        from django.utils import timezone

        conexao.pedido_em = timezone.now()
        conexao.save(update_fields=["pedido_em"])
        messages.info(request, "Buscando as campanhas na Meta. Os números aparecem em instantes.")
    elif acao == "imposto":
        try:
            valor = Decimal(str(request.POST.get("imposto", "")).replace(",", "."))
        except InvalidOperation:
            valor = Decimal(-1)
        if not Decimal(0) <= valor <= Decimal(50):
            messages.error(request, "O imposto vai de 0 a 50%.")
        else:
            conexao.imposto = valor.quantize(Decimal("0.01"))
            conexao.save(update_fields=["imposto"])
            messages.success(request, "Imposto salvo.")
    elif acao == "contas":
        marcadas = set(request.POST.getlist("contas"))
        for c in conexao.contas.all():
            c.acompanhar = c.account_id in marcadas
            c.save(update_fields=["acompanhar"])
        messages.success(request, "Contas de anúncios salvas.")
    elif acao == "sub_id":
        campanha = get_object_or_404(CampanhaMeta, pk=request.POST.get("campanha"), conta_anuncios__conexao=conexao)
        campanha.sub_id = "".join(ch for ch in str(request.POST.get("sub_id") or "") if ch.isalnum())[:120]
        campanha.save(update_fields=["sub_id"])
        messages.success(request, f"Sub ID da campanha {campanha.nome} salvo." if campanha.sub_id
                         else f"A campanha {campanha.nome} volta a usar o Sub ID com o mesmo nome dela.")
    return redirect(voltar)


@conta_requerida
def conectar(request):
    _conta_com_beta(request)
    if not meta.configurado():
        messages.error(request, "A conexão com a Meta ainda não está configurada.")
        return redirect("painel_campanhas_meta")
    state = secrets.token_urlsafe(24)
    request.session[SESSAO_STATE] = state
    request.session[SESSAO_JANELA] = request.GET.get("janela") == "1"
    return redirect(meta.url_de_login(_retorno_url(), state))


@conta_requerida
def retorno(request):
    conta = _conta_com_beta(request)
    state = request.session.pop(SESSAO_STATE, None)
    if request.GET.get("error"):
        messages.info(request, "A conexão com a Meta foi cancelada.")
    elif not state or not secrets.compare_digest(state, request.GET.get("state", "")) or not request.GET.get("code"):
        messages.error(request, "Não deu para confirmar a conexão. Tente conectar de novo.")
    else:
        try:
            conexao = servico.conectar(conta, request.GET["code"].split("#")[0], _retorno_url())
        except servico.ErroConexao as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Conta de anúncios conectada ({conexao.contas.count()} encontrada(s)). "
                                      "As campanhas aparecem em instantes.")
    if request.session.pop(SESSAO_JANELA, False):
        return render(request, "painel/meta_retorno.html", {"destino": reverse("painel_campanhas_meta")})
    return redirect("painel_campanhas_meta")


@require_POST
@conta_requerida
def desconectar(request):
    conta = _conta_com_beta(request)
    servico.desconectar(conta)
    messages.info(request, "Conta de anúncios desconectada. O acesso e os números das campanhas foram apagados.")
    return redirect("painel_campanhas_meta")


# --- avisos da Meta (sem login: quem chama é a Meta, a segurança é a assinatura) ------------------

@csrf_exempt
@require_POST
def desautorizar(request):
    """A pessoa tirou o Appfiliado Anúncios do Facebook dela: apaga a conexão."""
    dados = servico.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    servico.apagar_por_usuario(str(dados.get("user_id") or ""))
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def apagar_dados(request):
    """Pedido de exclusão de dados (exigido pela Meta): apaga e devolve onde acompanhar."""
    dados = servico.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    servico.apagar_por_usuario(str(dados.get("user_id") or ""))
    codigo = secrets.token_hex(8)
    url = settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_meta_dados_apagados", args=[codigo])
    return HttpResponse(json.dumps({"url": url, "confirmation_code": codigo}), content_type="application/json")


def dados_apagados(request, codigo):
    if not codigo.isalnum() or len(codigo) > 32:
        raise Http404
    return HttpResponse(f"Pedido {codigo}: os dados de anúncios da Meta ligados a esta conta foram apagados do Appfiliado.",
                        content_type="text/plain; charset=utf-8")
