"""Estúdio Instagram: conectar o Instagram do afiliado e as automações de resposta (Premium).

Em teste, como o resto do Estúdio: só para a conta com a chave ligada (as outras recebem 404).
As regras ficam em instagram_painel/ (conexao.py e webhook.py)."""

import json
import secrets

from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from estudio import afiliados as A
from estudio.models import PostInstagram
from instagram_painel import api, conexao
from instagram_painel.models import Automacao, AvisoRecebido, ContaInstagram
from instagram_painel.webhook import palavras

from .views import _contexto
from .views_estudio import SLUG, _beta

SESSAO_STATE = "instagram_state"
MAX_AUTOMACOES = 50


def _retorno_url() -> str:
    # Tem de ser igual ao cadastrado no app da Meta: monta pelo endereço fixo do painel.
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_instagram_retorno")


def _ig(conta) -> ContaInstagram | None:
    return ContaInstagram.objects.filter(conta=conta).first()


@_beta
def automacoes(request, conta):
    premium = A.eh_premium(conta)
    lista = []
    if premium:
        for a in Automacao.objects.filter(conta=conta):
            total = a.disparos.count()
            lista.append({"a": a, "total": total, "dms": a.disparos.filter(dm_ok=True).count(),
                          "palavras": ", ".join(palavras(a)).upper()})
    ig = _ig(conta)
    # Em teste: mostra se os avisos da Meta estão chegando (os desta conta e o último de qualquer conta).
    avisos = list(AvisoRecebido.objects.filter(ig_id=ig.ig_id)[:15]) if ig else []
    return render(request, "painel/estudio_automacoes.html", _contexto(
        request, SLUG, ig=ig, premium=premium, lista=lista, configurado=bool(api.app_id() and api.app_secret()),
        avisos=avisos, ultimo_aviso=AvisoRecebido.objects.first(),
    ))


@_beta
def conectar(request, conta):
    if not (api.app_id() and api.app_secret()):
        messages.error(request, "A conexão com o Instagram ainda não está configurada.")
        return redirect("painel_estudio_automacoes")
    state = secrets.token_urlsafe(24)
    request.session[SESSAO_STATE] = state
    return redirect(api.url_de_autorizacao(_retorno_url(), state))


@_beta
def retorno(request, conta):
    state = request.session.pop(SESSAO_STATE, None)
    if request.GET.get("error"):
        messages.info(request, "A conexão com o Instagram foi cancelada.")
        return redirect("painel_estudio_automacoes")
    if not state or not secrets.compare_digest(state, request.GET.get("state", "")) or not request.GET.get("code"):
        messages.error(request, "Não deu para confirmar a conexão. Tente conectar de novo.")
        return redirect("painel_estudio_automacoes")
    codigo = request.GET["code"].split("#")[0]
    try:
        ig = conexao.conectar(conta, codigo, _retorno_url())
    except conexao.ErroConexao as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Instagram @{ig.username} conectado.")
    return redirect("painel_estudio_automacoes")


@require_POST
@_beta
def desconectar(request, conta):
    conexao.desconectar(conta)
    messages.info(request, "Instagram desconectado. As automações foram pausadas.")
    return redirect("painel_estudio_automacoes")


@_beta
def midias(request, conta):
    """Posts (ou stories no ar) do Instagram conectado, para escolher na automação."""
    ig = _ig(conta)
    if not ig:
        return JsonResponse({"erro": "Conecte o seu Instagram primeiro."}, status=400)
    try:
        itens = api.stories_no_ar(ig.token) if request.GET.get("tipo") == "story" else api.posts_recentes(ig.token)
    except api.ErroInstagram as erro:
        return JsonResponse({"erro": f"O Instagram não respondeu ({erro})."}, status=502)
    return JsonResponse({"itens": [{
        "id": m.get("id"), "link": m.get("permalink", ""), "legenda": (m.get("caption") or "")[:120],
        "imagem": m.get("thumbnail_url") or m.get("media_url") or "", "data": m.get("timestamp", ""),
    } for m in itens]})


class AutomacaoForm(forms.ModelForm):
    class Meta:
        model = Automacao
        fields = ["nome", "gatilho", "midia_id", "midia_link", "midia_imagem", "midia_legenda", "palavras",
                  "responder_comentario", "respostas", "enviar_dm", "texto_dm", "link", "ativa"]
        widgets = {f: forms.HiddenInput for f in ("midia_id", "midia_link", "midia_imagem", "midia_legenda")}

    def clean(self):
        d = super().clean()
        gatilho = d.get("gatilho")
        if gatilho == Automacao.DIRETO and not (d.get("palavras") or "").strip():
            self.add_error("palavras", "Para DM, escolha pelo menos uma palavra (senão a automação responderia toda DM).")
        if gatilho != Automacao.COMENTARIO:
            d["responder_comentario"] = False
        if not d.get("responder_comentario") and not d.get("enviar_dm"):
            raise forms.ValidationError("Escolha pelo menos uma resposta: a do comentário ou a DM.")
        if d.get("responder_comentario") and not (d.get("respostas") or "").strip():
            self.add_error("respostas", "Escreva pelo menos uma resposta para o comentário.")
        if d.get("enviar_dm") and not (d.get("texto_dm") or "").strip():
            self.add_error("texto_dm", "Escreva o texto da DM.")
        for campo in ("midia_link", "midia_imagem"):
            if d.get(campo) and not str(d[campo]).startswith("https://"):
                d[campo] = ""
        return d


def _form_contexto(request, conta, form, automacao=None):
    return _contexto(request, SLUG, form=form, automacao=automacao, ig=_ig(conta),
                     disparos=automacao.disparos.all()[:50] if automacao else [])


def _so_premium(request, conta):
    if not A.eh_premium(conta):
        messages.info(request, "As automações de resposta são do plano Premium.")
        return redirect("painel_estudio_automacoes")
    return None


@_beta
def automacao_nova(request, conta):
    if (r := _so_premium(request, conta)):
        return r
    if request.method == "POST":
        form = AutomacaoForm(request.POST)
        if Automacao.objects.filter(conta=conta).count() >= MAX_AUTOMACOES:
            form.add_error(None, f"Você chegou a {MAX_AUTOMACOES} automações. Apague alguma para criar outra.")
        elif form.is_valid():
            a = form.save(commit=False)
            a.conta = conta
            post = PostInstagram.objects.filter(conta=conta, pk=request.POST.get("post") or 0).first()
            a.post_estudio = post
            a.save()
            messages.success(request, "Automação criada.")
            return redirect("painel_estudio_automacao", pk=a.pk)
    else:
        inicial = {"gatilho": Automacao.COMENTARIO, "palavras": "QUERO", "ativa": True,
                   "respostas": "Te mandei na DM! 📩\nEnviei o link na sua DM 😉\nCorre na DM que já te mandei!",
                   "texto_dm": "Oi! Aqui está o link que você pediu:"}
        post = PostInstagram.objects.filter(conta=conta, pk=request.GET.get("post") or 0).first()
        if post:
            inicial.update(nome=post.nome[:100], link=(post.produto or {}).get("link", ""))
            if (post.produto or {}).get("nome"):
                inicial["texto_dm"] = f"Oi! Aqui está o link do {post.produto['nome'][:80]}:"
        form = AutomacaoForm(initial=inicial)
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form) | {
        "post_id": request.GET.get("post") or request.POST.get("post") or ""})


@_beta
def automacao(request, conta, pk):
    if (r := _so_premium(request, conta)):
        return r
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    form = AutomacaoForm(request.POST or None, instance=a)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Automação salva.")
        return redirect("painel_estudio_automacao", pk=a.pk)
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form, a))


@require_POST
@_beta
def automacao_ligar(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    a.ativa = not a.ativa
    a.save(update_fields=["ativa", "atualizada_em"])
    if request.POST.get("voltar") == "lista":
        return redirect("painel_estudio_automacoes")
    return redirect("painel_estudio_automacao", pk=a.pk)


@require_POST
@_beta
def automacao_apagar(request, conta, pk):
    get_object_or_404(Automacao, pk=pk, conta=conta).delete()
    messages.info(request, "Automação apagada.")
    return redirect("painel_estudio_automacoes")


# --- avisos da Meta (sem login: quem chama é a Meta, a segurança é a assinatura) ------------------

@csrf_exempt
@require_POST
def desautorizar(request):
    """A pessoa tirou o Appfiliado do Instagram dela: apaga a conexão."""
    dados = conexao.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    conexao.apagar_por_usuario(str(dados.get("user_id") or ""))
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def apagar_dados(request):
    """Pedido de exclusão de dados (exigido pela Meta): apaga e devolve onde acompanhar."""
    dados = conexao.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    conexao.apagar_por_usuario(str(dados.get("user_id") or ""))
    codigo = secrets.token_hex(8)
    url = settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_instagram_dados_apagados", args=[codigo])
    return HttpResponse(json.dumps({"url": url, "confirmation_code": codigo}), content_type="application/json")


def dados_apagados(request, codigo):
    if not codigo.isalnum() or len(codigo) > 32:
        raise Http404
    return HttpResponse(f"Pedido {codigo}: os dados do Instagram ligados a esta conta foram apagados do Appfiliado.",
                        content_type="text/plain; charset=utf-8")
