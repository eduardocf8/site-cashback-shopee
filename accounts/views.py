from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from pedidos.models import Pedido
from saques.services import calcular_saldo_disponivel

from .forms import ChavePixForm, EditarPerfilForm, RegistroForm
from .tokens import enviar_email_verificacao, validar_token_verificacao

User = get_user_model()


def registrar(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            enviar_email_verificacao(usuario, request)
            login(request, usuario)
            return redirect("dashboard")
    else:
        form = RegistroForm()

    return render(request, "accounts/registrar.html", {"form": form})


def verificar_email(request, token):
    dados = validar_token_verificacao(token)
    if not dados:
        messages.error(request, "Esse link de verificação é inválido ou expirou.")
        return redirect("home")

    try:
        usuario = User.objects.get(pk=dados["user_id"])
    except User.DoesNotExist:
        messages.error(request, "Conta não encontrada.")
        return redirect("home")

    if usuario.email != dados["email"]:
        messages.error(request, "Esse link não é mais válido — o e-mail da conta mudou.")
        return redirect("home")

    if not usuario.email_verificado:
        usuario.email_verificado = True
        usuario.save(update_fields=["email_verificado"])

    messages.success(request, "E-mail verificado com sucesso!")
    return redirect("dashboard" if request.user.is_authenticated else "login")


@login_required
def reenviar_verificacao(request):
    if request.user.email_verificado:
        messages.info(request, "Seu e-mail já está verificado.")
    else:
        enviar_email_verificacao(request.user, request)
        messages.success(request, "Enviamos um novo link de verificação pro seu e-mail.")
    return redirect("dashboard")


@login_required
def dashboard(request):
    pedidos_usuario = Pedido.objects.filter(usuario=request.user)

    saldos = {chave: Decimal("0") for chave, _ in Pedido.STATUS_CHOICES}
    for linha in pedidos_usuario.values("status").annotate(total=Sum("valor_cashback")):
        saldos[linha["status"]] = linha["total"] or Decimal("0")

    contexto = {
        "saldo_pendente": saldos[Pedido.STATUS_PENDENTE],
        "saldo_validado": saldos[Pedido.STATUS_VALIDADO],
        "saldo_liberado": saldos[Pedido.STATUS_LIBERADO],
        "saldo_cancelado": saldos[Pedido.STATUS_CANCELADO],
        "saldo_disponivel": calcular_saldo_disponivel(request.user),
        "saque_valor_minimo": settings.SAQUE_VALOR_MINIMO,
        "clicks": request.user.clicks.all()[:30],
        "pedidos": pedidos_usuario.order_by("-data_compra")[:30],
        "saques": request.user.saques.all()[:20],
    }
    return render(request, "accounts/dashboard.html", contexto)


@login_required
def editar_chave_pix(request):
    if request.method == "POST":
        form = ChavePixForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Chave PIX atualizada com sucesso!")
            return redirect("dashboard")
    else:
        form = ChavePixForm(instance=request.user)

    return render(request, "accounts/chave_pix.html", {"form": form})


@login_required
def editar_perfil(request):
    if request.method == "POST":
        # Captura o e-mail antigo antes de validar o form: como o form usa
        # instance=request.user (mesmo objeto), form.is_valid() já escreve o
        # e-mail novo direto no request.user em memória.
        email_antigo = request.user.email
        form = EditarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            usuario = form.save(commit=False)
            email_mudou = usuario.email != email_antigo
            if email_mudou:
                usuario.email_verificado = False
            usuario.save()

            if email_mudou:
                enviar_email_verificacao(usuario, request)
                messages.success(
                    request,
                    "Dados atualizados! Como você mudou o e-mail, mandamos um novo link de "
                    "verificação pra ele.",
                )
            else:
                messages.success(request, "Dados atualizados com sucesso!")
            return redirect("dashboard")
    else:
        form = EditarPerfilForm(instance=request.user)

    return render(request, "accounts/editar_perfil.html", {"form": form})
