import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.views.decorators.csrf import csrf_exempt

from instagram_bot.models import RegistroPublicacao

from . import instagram_api, services, webhook
from .forms import (
    AutomacaoComentarioForm,
    AutomacaoStoryForm,
    ContaInstagramForm,
    ProcessarComentarioManualForm,
)
from .models import (
    AutomacaoComentario,
    AutomacaoStory,
    ComentarioProcessado,
    ContaInstagramConectada,
    RespostaStoryProcessada,
)

ITENS_POR_PAGINA = 20
TIPO_POST = "post"
TIPO_STORY = "story"


def staff_required(view_func):
    """Só usuários com is_staff=True acessam essa área - login separado do login de
    clientes do site (mesmo backend de autenticação, telas diferentes)."""
    return user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url="automacao_login")(view_func)


class AutomacaoLoginView(auth_views.LoginView):
    template_name = "automacao_instagram/login.html"

    def get_default_redirect_url(self):
        return resolve_url("automacao_contas")

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.user.is_staff:
            logout(self.request)
            messages.error(self.request, "Essa conta não tem acesso à automação de comentários.")
            return redirect("automacao_login")
        return response


@staff_required
def contas_lista(request):
    contas = ContaInstagramConectada.objects.filter(usuario=request.user)

    if request.method == "POST":
        form = ContaInstagramForm(request.POST)
        if form.is_valid():
            conta = form.save(commit=False)
            conta.usuario = request.user
            conta.save()
            messages.success(request, "Conta conectada com sucesso!")
            return redirect("automacao_contas")
    else:
        form = ContaInstagramForm()

    return render(request, "automacao_instagram/contas.html", {"contas": contas, "form": form})


@staff_required
def conta_remover(request, pk):
    if request.method == "POST":
        conta = get_object_or_404(ContaInstagramConectada, pk=pk, usuario=request.user)
        conta.delete()
        messages.success(request, "Conta removida.")
    return redirect("automacao_contas")


@staff_required
def automacao_lista(request):
    automacoes = list(
        AutomacaoComentario.objects.filter(conta__usuario=request.user)
        .select_related("conta")
        .annotate(
            total_comentarios=Count("comentarios", distinct=True),
            respostas_enviadas=Count(
                "comentarios", filter=Q(comentarios__resposta_publica_enviada=True), distinct=True
            ),
            dms_enviadas=Count("comentarios", filter=Q(comentarios__dm_enviada=True), distinct=True),
            dms_respondidas=Count("comentarios", filter=Q(comentarios__dm_respondida=True), distinct=True),
        )
    )
    resumo = {
        "total": len(automacoes),
        "ativas": sum(1 for a in automacoes if a.ativa),
        "comentarios": sum(a.total_comentarios for a in automacoes),
        "dms_enviadas": sum(a.dms_enviadas for a in automacoes),
        "dms_respondidas": sum(a.dms_respondidas for a in automacoes),
    }

    automacoes_story = list(
        AutomacaoStory.objects.filter(conta__usuario=request.user)
        .select_related("conta")
        .annotate(
            total_respostas=Count("respostas", distinct=True),
            dms_enviadas=Count("respostas", filter=Q(respostas__dm_enviada=True), distinct=True),
        )
    )
    resumo_story = {
        "total": len(automacoes_story),
        "ativas": sum(1 for a in automacoes_story if a.ativa),
        "dms_enviadas": sum(a.dms_enviadas for a in automacoes_story),
    }

    return render(
        request, "automacao_instagram/automacao_lista.html",
        {
            "automacoes": automacoes, "resumo": resumo,
            "automacoes_story": automacoes_story, "resumo_story": resumo_story,
        },
    )


@staff_required
def automacao_alternar_ativa(request, pk):
    if request.method == "POST":
        automacao = get_object_or_404(AutomacaoComentario, pk=pk, conta__usuario=request.user)
        automacao.ativa = not automacao.ativa
        automacao.save(update_fields=["ativa"])
    return redirect("automacao_lista")


@staff_required
def automacao_story_alternar_ativa(request, pk):
    if request.method == "POST":
        automacao = get_object_or_404(AutomacaoStory, pk=pk, conta__usuario=request.user)
        automacao.ativa = not automacao.ativa
        automacao.save(update_fields=["ativa"])
    return redirect("automacao_lista")


@staff_required
def automacao_nova(request):
    """1ª etapa: escolher o tipo (post ou story) - cada um puxa só o que faz sentido
    pra ele (posts pra um, stories ativos agora pro outro). 2ª etapa: escolher a
    conta. 3ª: escolher o item específico e configurar a regra - ver
    _automacao_nova_post/_automacao_nova_story."""
    contas = ContaInstagramConectada.objects.filter(usuario=request.user)
    if not contas.exists():
        messages.info(request, "Conecte uma conta do Instagram antes de criar uma automação.")
        return redirect("automacao_contas")

    tipo = request.GET.get("tipo") or request.POST.get("tipo")
    if tipo not in (TIPO_POST, TIPO_STORY):
        return render(request, "automacao_instagram/automacao_escolher_tipo.html")

    conta_id = request.GET.get("conta") or request.POST.get("conta")
    if not conta_id:
        return render(
            request, "automacao_instagram/automacao_escolher_conta.html", {"contas": contas, "tipo": tipo}
        )
    conta = get_object_or_404(contas, pk=conta_id)

    if tipo == TIPO_STORY:
        return _automacao_nova_story(request, conta)
    return _automacao_nova_post(request, conta)


def _automacao_nova_post(request, conta):
    try:
        midias = instagram_api.listar_midias_recentes(conta.instagram_business_account_id, conta.access_token)
    except instagram_api.InstagramAPIError as erro:
        messages.error(request, f"Não deu pra buscar os posts dessa conta: {erro}")
        midias = []

    if request.method == "POST":
        form = AutomacaoComentarioForm(request.POST)
        post_selecionado = request.POST.get("post_selecionado", "")
        if not post_selecionado:
            messages.error(request, "Selecione o post que vai receber a automação.")
        elif form.is_valid():
            media_id, _, permalink = post_selecionado.partition("|")
            automacao = form.save(commit=False)
            automacao.conta = conta
            automacao.instagram_media_id = media_id
            automacao.link_post = permalink
            automacao.save()
            messages.success(request, "Automação criada com sucesso!")
            return redirect("automacao_lista")
    else:
        form = AutomacaoComentarioForm()

    return render(
        request, "automacao_instagram/automacao_form.html",
        {"form": form, "conta": conta, "midias": midias},
    )


def _automacao_nova_story(request, conta):
    try:
        stories = instagram_api.listar_stories_recentes(conta.instagram_business_account_id, conta.access_token)
    except instagram_api.InstagramAPIError as erro:
        messages.error(request, f"Não deu pra buscar os stories dessa conta: {erro}")
        stories = []

    ids_com_link = set(
        RegistroPublicacao.objects.filter(instagram_media_id__in=[s["id"] for s in stories])
        .exclude(link_produto_original="")
        .values_list("instagram_media_id", flat=True)
    )
    for story in stories:
        story["tem_link_produto"] = story["id"] in ids_com_link

    if request.method == "POST":
        form = AutomacaoStoryForm(request.POST)
        story_selecionado = request.POST.get("story_selecionado", "")
        if not story_selecionado:
            messages.error(request, "Selecione o story que vai receber a automação.")
        elif form.is_valid():
            if (
                form.cleaned_data["modo_resposta"] == AutomacaoStory.MODO_LINK_PRODUTO
                and story_selecionado not in ids_com_link
            ):
                form.add_error(
                    None,
                    "Esse story não tem um link de produto detectado - escolha \"mensagem "
                    "personalizada\" ou um story publicado pelo bot de ofertas.",
                )
            else:
                story_escolhido = next((s for s in stories if s["id"] == story_selecionado), None)
                automacao = form.save(commit=False)
                automacao.conta = conta
                automacao.instagram_story_media_id = story_selecionado
                automacao.story_permalink = (story_escolhido or {}).get("permalink", "")
                automacao.save()
                messages.success(request, "Automação criada com sucesso!")
                return redirect("automacao_lista")
    else:
        form = AutomacaoStoryForm()

    return render(
        request, "automacao_instagram/automacao_form_story.html",
        {"form": form, "conta": conta, "stories": stories},
    )


@staff_required
def automacao_editar(request, pk):
    automacao = get_object_or_404(AutomacaoComentario, pk=pk, conta__usuario=request.user)

    if request.method == "POST":
        form = AutomacaoComentarioForm(request.POST, instance=automacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Automação atualizada.")
            return redirect("automacao_lista")
    else:
        form = AutomacaoComentarioForm(instance=automacao)

    return render(
        request, "automacao_instagram/automacao_editar.html",
        {"form": form, "automacao": automacao, "form_manual": ProcessarComentarioManualForm()},
    )


@staff_required
def automacao_processar_manual(request, pk):
    automacao = get_object_or_404(AutomacaoComentario, pk=pk, conta__usuario=request.user)
    if request.method == "POST":
        form = ProcessarComentarioManualForm(request.POST)
        if form.is_valid():
            try:
                registro = services.processar_comentario_manual(
                    automacao,
                    form.cleaned_data["instagram_comment_id"],
                    form.cleaned_data["texto_comentario"],
                    form.cleaned_data["autor_username"],
                )
            except ValueError as erro:
                messages.error(request, str(erro))
            else:
                partes = []
                if registro.resposta_publica_enviada:
                    partes.append("resposta pública enviada")
                elif registro.resposta_publica_erro:
                    partes.append(f"erro na resposta pública: {registro.resposta_publica_erro}")
                if registro.dm_enviada:
                    partes.append("DM enviada")
                elif registro.dm_erro:
                    partes.append(f"erro na DM: {registro.dm_erro}")
                messages.success(request, "Comentário processado - " + ("; ".join(partes) if partes else "nada a enviar."))
        else:
            messages.error(request, "Preencha o ID e o texto do comentário.")
    return redirect("automacao_editar", pk=pk)


@staff_required
def automacao_story_editar(request, pk):
    automacao = get_object_or_404(AutomacaoStory, pk=pk, conta__usuario=request.user)

    if request.method == "POST":
        form = AutomacaoStoryForm(request.POST, instance=automacao)
        if form.is_valid():
            if (
                form.cleaned_data["modo_resposta"] == AutomacaoStory.MODO_LINK_PRODUTO
                and not RegistroPublicacao.objects.filter(
                    instagram_media_id=automacao.instagram_story_media_id,
                ).exclude(link_produto_original="").exists()
            ):
                form.add_error(
                    None, "Esse story não tem um link de produto detectado - escolha \"mensagem personalizada\"."
                )
            else:
                form.save()
                messages.success(request, "Automação atualizada.")
                return redirect("automacao_lista")
    else:
        form = AutomacaoStoryForm(instance=automacao)

    return render(
        request, "automacao_instagram/automacao_story_editar.html", {"form": form, "automacao": automacao}
    )


@staff_required
def historico(request):
    comentarios = ComentarioProcessado.objects.filter(automacao__conta__usuario=request.user).select_related(
        "automacao"
    )

    automacao_id = request.GET.get("automacao", "")
    if automacao_id:
        comentarios = comentarios.filter(automacao_id=automacao_id)

    pagina = Paginator(comentarios, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))
    automacoes = AutomacaoComentario.objects.filter(conta__usuario=request.user)

    return render(
        request, "automacao_instagram/historico.html",
        {"comentarios": pagina, "automacoes": automacoes, "filtro_automacao": automacao_id},
    )


@staff_required
def historico_story(request):
    respostas = RespostaStoryProcessada.objects.filter(automacao__conta__usuario=request.user).select_related(
        "automacao"
    )

    automacao_id = request.GET.get("automacao", "")
    if automacao_id:
        respostas = respostas.filter(automacao_id=automacao_id)

    pagina = Paginator(respostas, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))
    automacoes = AutomacaoStory.objects.filter(conta__usuario=request.user)

    return render(
        request, "automacao_instagram/historico_story.html",
        {"respostas": pagina, "automacoes": automacoes, "filtro_automacao": automacao_id},
    )


@csrf_exempt
def webhook_instagram(request):
    """Endpoint que recebe os eventos de mensagem da Meta (ver webhook.py) - GET é o
    handshake de verificação feito uma vez ao cadastrar a URL no painel da Meta; POST
    é cada entrega de evento de verdade (mensagem recebida). Sem @staff_required nem
    proteção de CSRF de propósito: quem chama isso é a Meta, não um usuário logado - a
    segurança aqui é a assinatura X-Hub-Signature-256 (ver webhook.verificar_assinatura)."""
    if request.method == "GET":
        if (
            request.GET.get("hub.mode") == "subscribe"
            and settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
            and request.GET.get("hub.verify_token") == settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
        ):
            return HttpResponse(request.GET.get("hub.challenge", ""))
        return HttpResponseForbidden()

    if not webhook.verificar_assinatura(request.body, request.headers.get("X-Hub-Signature-256")):
        return HttpResponseForbidden()

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return HttpResponseBadRequest()

    webhook.processar_evento_webhook(payload, request)
    return HttpResponse("EVENT_RECEIVED")
