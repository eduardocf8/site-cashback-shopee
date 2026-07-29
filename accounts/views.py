from decimal import Decimal

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from pedidos.models import Pedido

from .forms import RegistroForm


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
        "clicks": request.user.clicks.all()[:30],
        "pedidos": pedidos_usuario.order_by("-data_compra")[:30],
    }
    return render(request, "accounts/dashboard.html", contexto)
