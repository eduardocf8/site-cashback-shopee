"""Instagram no painel: a conexão da conta (vale para o Estúdio Instagram e para as Automações), as
Automações do Instagram (módulo próprio: Standard responde comentários; Premium também stories e
DMs) e a publicação dos posts do Estúdio.

Até o lançamento (settings.APPFILIADO_LANCAMENTO_INSTAGRAM), só para a conta com a chave de teste
ligada; as outras recebem 404. As regras ficam em instagram_painel/ (conexao.py, webhook.py e publicar.py)."""

import json
import secrets

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from estudio.models import PostInstagram
from instagram_painel import api, conexao
from instagram_painel import publicar as P
from instagram_painel.models import Automacao, ContaInstagram, Disparo, ImagemPublicacao, Publicacao
from instagram_painel.webhook import na_fila, palavras, respondidas_no_mes
from licencas import planos as planos_do_app

from . import modulos as mod
from .views import _contexto
from .views_estudio import SLUG, _beta, exige

SLUG_AUTOMACOES = "automacoes_instagram"
_automacoes = exige(SLUG_AUTOMACOES)
_conexao = exige(SLUG_AUTOMACOES, SLUG)  # conectar o Instagram: serve a quem tem qualquer um dos dois
SESSAO_STATE = "instagram_state"
SESSAO_JANELA = "instagram_janela"  # o login abriu numa janela à parte: a volta fecha a janela
MAX_AUTOMACOES = 50


def _retorno_url() -> str:
    # Tem de ser igual ao cadastrado no app da Meta: monta pelo endereço fixo do painel.
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_instagram_retorno")


def _ig(conta) -> ContaInstagram | None:
    return ContaInstagram.objects.filter(conta=conta).first()


def _tem_automacoes(conta) -> bool:
    return mod.estado(mod.POR_SLUG[SLUG_AUTOMACOES], conta.modulos_liberados()) == "liberado"


def _pagina_da_conexao(conta) -> str:
    """Onde fica o cartão do Instagram conectado: nas Automações ou, só com o Estúdio, nas Publicações."""
    return reverse("painel_estudio_automacoes" if _tem_automacoes(conta) else "painel_estudio_publicacoes")


@_automacoes
def automacoes(request, conta):
    plano = planos_do_app.automacoes(conta)
    lista = []
    for a in Automacao.objects.filter(conta=conta):
        total = a.disparos.count()
        lista.append({"a": a, "total": total, "dms": a.disparos.filter(dm_ok=True).count(),
                      "palavras": ", ".join(palavras(a)).upper(), "fora_do_plano": a.gatilho not in plano["gatilhos"]})
    return render(request, "painel/estudio_automacoes.html", _contexto(
        request, SLUG_AUTOMACOES, ig=_ig(conta), plano=plano, lista=lista, respondidas=respondidas_no_mes(conta),
        fila=na_fila(conta), configurado=bool(api.app_id() and api.app_secret()),
    ))


@_conexao
def conectar(request, conta):
    if not (api.app_id() and api.app_secret()):
        messages.error(request, "A conexão com o Instagram ainda não está configurada.")
        return redirect(_pagina_da_conexao(conta))
    state = secrets.token_urlsafe(24)
    request.session[SESSAO_STATE] = state
    # "1": volta para a página do cartão do Instagram; "ficar": só fecha a janela (o editor confere sozinho).
    janela = request.GET.get("janela")
    request.session[SESSAO_JANELA] = janela if janela in ("1", "ficar") else ""
    return redirect(api.url_de_autorizacao(_retorno_url(), state))


def _voltar(request, conta):
    """Fim do login: na janela à parte, avisa a página do Appfiliado e fecha; senão, volta para ela."""
    janela = request.session.pop(SESSAO_JANELA, "")
    if janela:
        return render(request, "painel/instagram_retorno.html",
                      {"destino": _pagina_da_conexao(conta), "ficar": janela == "ficar"})
    return redirect(_pagina_da_conexao(conta))


@_conexao
def retorno(request, conta):
    state = request.session.pop(SESSAO_STATE, None)
    if request.GET.get("error"):
        messages.info(request, "A conexão com o Instagram foi cancelada.")
        return _voltar(request, conta)
    if not state or not secrets.compare_digest(state, request.GET.get("state", "")) or not request.GET.get("code"):
        messages.error(request, "Não deu para confirmar a conexão. Tente conectar de novo.")
        return _voltar(request, conta)
    codigo = request.GET["code"].split("#")[0]
    try:
        ig = conexao.conectar(conta, codigo, _retorno_url())
    except conexao.ErroConexao as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Instagram @{ig.username} conectado.")
    return _voltar(request, conta)


@require_POST
@_conexao
def desconectar(request, conta):
    conexao.desconectar(conta)
    messages.info(request, "Instagram desconectado. As automações e as publicações agendadas ficam paradas até conectar de novo.")
    return redirect(_pagina_da_conexao(conta))


@_automacoes
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

    def __init__(self, *args, gatilhos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.gatilhos = gatilhos or [g for g, _ in Automacao.GATILHOS]

    def clean(self):
        d = super().clean()
        gatilho = d.get("gatilho")
        if gatilho and gatilho not in self.gatilhos:
            self.add_error("gatilho", "Responder stories e DMs é do plano Premium das Automações.")
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
    plano = planos_do_app.automacoes(conta)
    gatilhos = [{"valor": v, "nome": n, "livre": v in plano["gatilhos"]} for v, n in Automacao.GATILHOS]
    return _contexto(request, SLUG_AUTOMACOES, form=form, automacao=automacao, ig=_ig(conta), gatilhos=gatilhos, plano=plano,
                     disparos=automacao.disparos.all()[:50] if automacao else [])


@_automacoes
def automacao_nova(request, conta):
    gatilhos = planos_do_app.automacoes(conta)["gatilhos"]
    if request.method == "POST":
        form = AutomacaoForm(request.POST, gatilhos=gatilhos)
        if Automacao.objects.filter(conta=conta).count() >= MAX_AUTOMACOES:
            form.add_error(None, f"Você chegou a {MAX_AUTOMACOES} automações. Exclua alguma para criar outra.")
        elif form.is_valid():
            a = form.save(commit=False)
            a.conta = conta
            post = PostInstagram.objects.filter(conta=conta, pk=request.POST.get("post") or 0).first()
            a.post_estudio = post
            a.save()
            messages.success(request, f"Automação \"{a.nome}\" criada.")
            return redirect("painel_estudio_automacoes")
    else:
        inicial = {"gatilho": Automacao.COMENTARIO, "palavras": "QUERO", "ativa": True,
                   "respostas": "Te mandei na DM! 📩\nEnviei o link na sua DM 😉\nCorre na DM que já te mandei!",
                   "texto_dm": "Oi! Aqui está o link que você pediu:"}
        post = PostInstagram.objects.filter(conta=conta, pk=request.GET.get("post") or 0).first()
        if post:
            inicial.update(nome=post.nome[:100], link=(post.produto or {}).get("link", ""))
            if (post.produto or {}).get("nome"):
                inicial["texto_dm"] = f"Oi! Aqui está o link do {post.produto['nome'][:80]}:"
        form = AutomacaoForm(initial=inicial, gatilhos=gatilhos)
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form) | {
        "post_id": request.GET.get("post") or request.POST.get("post") or ""})


@_automacoes
def automacao(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    form = AutomacaoForm(request.POST or None, instance=a, gatilhos=planos_do_app.automacoes(conta)["gatilhos"])
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Automação \"{a.nome}\" salva.")
        return redirect("painel_estudio_automacoes")
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form, a))


@require_POST
@_automacoes
def automacao_ligar(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    a.ativa = not a.ativa
    a.save(update_fields=["ativa", "atualizada_em"])
    if request.POST.get("voltar") == "lista":
        return redirect("painel_estudio_automacoes")
    return redirect("painel_estudio_automacao", pk=a.pk)


@require_POST
@_automacoes
def automacao_excluir(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    a.delete()
    messages.info(request, f"Automação \"{a.nome}\" excluída.")
    return redirect("painel_estudio_automacoes")


@_automacoes
def historico(request, conta):
    """Todas as respostas das automações, das mais novas para as mais antigas."""
    automacoes_ = Automacao.objects.filter(conta=conta).order_by("nome")
    disparos = Disparo.objects.filter(automacao__conta=conta).select_related("automacao")
    escolhida = automacoes_.filter(pk=request.GET.get("automacao") or 0).first()
    if escolhida:
        disparos = disparos.filter(automacao=escolhida)
    pagina = Paginator(disparos, 50).get_page(request.GET.get("pagina"))
    return render(request, "painel/estudio_historico.html", _contexto(
        request, SLUG_AUTOMACOES, pagina=pagina, automacoes=automacoes_, escolhida=escolhida,
        total=disparos.count(), dms=disparos.filter(dm_ok=True).count(), respostas=disparos.filter(resposta_ok=True).count(),
    ))


# --- publicar no Instagram (todos os planos) -----------------------------------------------------

def _publicacao_json(p: Publicacao) -> dict:
    return {"id": p.pk, "tipo": p.get_tipo_display(), "estado": p.estado, "estado_nome": p.get_estado_display(),
            "quando": timezone.localtime(p.publicada_em or p.agendada_para).strftime("%d/%m/%Y %H:%M"),
            "link": p.permalink, "erro": p.erro, "agora": p.agora,
            "cancelar": reverse("painel_estudio_publicacao_cancelar", args=[p.pk]) if p.estado == Publicacao.PENDENTE else "",
            "tentar": reverse("painel_estudio_publicacao_tentar", args=[p.pk]) if p.estado == Publicacao.ERRO else ""}


@_beta
def publicar(request, conta, pk):
    """GET: a conta conectada e as publicações deste post. POST: as imagens (JPEG) e quando publicar."""
    post = get_object_or_404(PostInstagram, pk=pk, conta=conta)
    if request.method == "POST":
        try:
            quando = None if request.POST.get("quando") != "agendar" else P.quando_de(request.POST.get("data", ""))
            arquivos = [request.FILES[k] for k in sorted(request.FILES, key=lambda k: int(k.split("_")[-1]) if k.split("_")[-1].isdigit() else 99)
                        if k.startswith("imagem_")]
            pub = P.agendar(post, arquivos, quando)
        except P.ErroPublicacao as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        msg = ("Enviado! O post sai no seu Instagram em instantes." if quando is None
               else f"Agendado para {timezone.localtime(quando).strftime('%d/%m/%Y às %H:%M')}.")
        return JsonResponse({"ok": True, "mensagem": msg, "publicacao": _publicacao_json(pub)})
    ig = _ig(conta)
    return JsonResponse({
        "ig": {"username": ig.username, "foto": ig.foto} if ig else None,
        "conectar": reverse("painel_instagram_conectar") + "?janela=ficar" if api.app_id() and api.app_secret() else "",
        "tipo": P.tipo_do_post(post),
        "publicacoes": [_publicacao_json(p) for p in Publicacao.objects.filter(post=post).exclude(estado=Publicacao.CANCELADA)[:10]],
    })


@_beta
def publicacoes(request, conta):
    """Publicações agendadas e as mais recentes, de todos os posts."""
    agendadas = Publicacao.objects.filter(conta=conta, estado__in=[Publicacao.PENDENTE, Publicacao.PUBLICANDO]).order_by("agendada_para")
    feitas = Publicacao.objects.filter(conta=conta, estado__in=[Publicacao.PUBLICADA, Publicacao.ERRO]).order_by("-agendada_para")
    pagina = Paginator(feitas, 30).get_page(request.GET.get("pagina"))
    return render(request, "painel/estudio_publicacoes.html", _contexto(
        request, SLUG, agendadas=agendadas, pagina=pagina, ig=_ig(conta), configurado=bool(api.app_id() and api.app_secret())))


@require_POST
@_beta
def publicacao_cancelar(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    if P.cancelar(pub):
        msg = "Publicação cancelada."
    else:
        msg = "Essa publicação já saiu ou está saindo agora."
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"mensagem": msg})
    messages.info(request, msg)
    return redirect("painel_estudio_publicacoes")


@require_POST
@_beta
def publicacao_tentar(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    msg = ("Vamos tentar de novo. O post sai em instantes." if P.tentar_de_novo(pub)
           else "Não dá para tentar de novo essa publicação. Publique outra vez pelo editor.")
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"mensagem": msg})
    messages.info(request, msg)
    return redirect("painel_estudio_publicacoes")


@_beta
def publicacao_miniatura(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    if not pub.miniatura:
        raise Http404
    resposta = HttpResponse(bytes(pub.miniatura), content_type="image/jpeg")
    resposta["Cache-Control"] = "private, max-age=86400"
    return resposta


def midia_publica(request, token):
    """A imagem que a Meta baixa para publicar. Sem login: o token secreto é a chave, e só vale
    enquanto a publicação não saiu."""
    if len(token) > 64:
        raise Http404
    imagem = (ImagemPublicacao.objects.filter(token=token, publicacao__estado__in=[Publicacao.PENDENTE, Publicacao.PUBLICANDO])
              .only("dados").first())
    if not imagem:
        raise Http404
    resposta = HttpResponse(bytes(imagem.dados), content_type="image/jpeg")
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


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
