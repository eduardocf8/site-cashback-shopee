from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from pedidos.models import Pedido
from saques.services import calcular_saldo_disponivel

from .forms import ChavePixForm, RegistroForm


def registrar(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect("dashboard")
    else:
        form = RegistroForm()

    return render(request, "accounts/registrar.html", {"form": form})


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
