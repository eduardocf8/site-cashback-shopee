import logging
import threading
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

from pedidos.models import Pedido
from saques.services import calcular_saldo_disponivel

from .forms import ChavePixForm, RegistroForm

logger = logging.getLogger(__name__)


def _enviar_email_reset_senha(form, opts):
    try:
        form.save(**opts)
    except Exception:
        logger.exception("Falha ao enviar e-mail de redefinição de senha")


class PasswordResetView(auth_views.PasswordResetView):
    """Manda o e-mail de redefinição de senha numa thread separada.

    O envio via SMTP pode levar vários segundos (conexão + handshake TLS
    com o servidor externo); sem isso, o usuário fica esperando a página
    responder até o e-mail terminar de ser enviado. Qualquer falha no
    envio é registrada nos logs em vez de desaparecer silenciosamente.
    """

    def form_valid(self, form):
        opts = {
            "use_https": self.request.is_secure(),
            "token_generator": self.token_generator,
            "from_email": self.from_email,
            "email_template_name": self.email_template_name,
            "subject_template_name": self.subject_template_name,
            "request": self.request,
            "html_email_template_name": self.html_email_template_name,
            "extra_email_context": self.extra_email_context,
        }
        threading.Thread(target=_enviar_email_reset_senha, args=(form, opts), daemon=True).start()
        return HttpResponseRedirect(self.get_success_url())


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
