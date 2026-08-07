from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.formats import number_format

from .services import ChavePixNaoConfiguradaError, ValorAbaixoDoMinimoError, solicitar_saque


@login_required
def pedir_saque(request):
    if request.method == "POST":
        if not request.user.email_verificado:
            messages.error(request, "Confirme seu e-mail antes de solicitar um saque.")
            return redirect("dashboard")
        try:
            saque = solicitar_saque(request.user)
            valor_formatado = number_format(saque.valor, decimal_pos=2)
            messages.success(
                request,
                f"Saque de R$ {valor_formatado} solicitado! Assim que for aprovado, o PIX cai na sua chave cadastrada.",
            )
        except ChavePixNaoConfiguradaError as erro:
            messages.error(request, str(erro))
        except ValorAbaixoDoMinimoError as erro:
            messages.error(request, str(erro))

    return redirect("dashboard")
