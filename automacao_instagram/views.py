from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render, resolve_url

from . import instagram_api
from .forms import AutomacaoComentarioForm, ContaInstagramForm
from .models import AutomacaoComentario, ComentarioProcessado, ContaInstagramConectada

ITENS_POR_PAGINA = 20


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
    automacoes = (
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
    return render(request, "automacao_instagram/automacao_lista.html", {"automacoes": automacoes})


@staff_required
def automacao_alternar_ativa(request, pk):
    if request.method == "POST":
        automacao = get_object_or_404(AutomacaoComentario, pk=pk, conta__usuario=request.user)
        automacao.ativa = not automacao.ativa
        automacao.save(update_fields=["ativa"])
    return redirect("automacao_lista")


@staff_required
def automacao_nova(request):
    contas = ContaInstagramConectada.objects.filter(usuario=request.user)
    if not contas.exists():
        messages.info(request, "Conecte uma conta do Instagram antes de criar uma automação.")
        return redirect("automacao_contas")

    conta_id = request.GET.get("conta") or request.POST.get("conta")
    if not conta_id:
        return render(request, "automacao_instagram/automacao_escolher_conta.html", {"contas": contas})
    conta = get_object_or_404(contas, pk=conta_id)

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

    return render(request, "automacao_instagram/automacao_editar.html", {"form": form, "automacao": automacao})


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
