import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render

from ofertas.services import obter_cashback_maximo_anunciado

from .forms import ContatoForm

logger = logging.getLogger(__name__)


def termos_de_uso(request):
    return render(request, "paginas/termos.html")


def privacidade(request):
    return render(request, "paginas/privacidade.html")


def cookies(request):
    return render(request, "paginas/cookies.html")


def regras_cashback(request):
    contexto = {"saque_valor_minimo": settings.SAQUE_VALOR_MINIMO}
    return render(request, "paginas/regras_cashback.html", contexto)


def faq(request):
    return render(request, "paginas/faq.html")


def cashback_vale_a_pena(request):
    # Mesma fonte usada no "até X%" da home (obter_cashback_maximo_anunciado) - pra
    # nunca ter um número diferente prometido em duas páginas do mesmo site.
    cashback_maximo_anunciado = obter_cashback_maximo_anunciado()
    exemplo_compra = Decimal("100")
    exemplo_cashback = (exemplo_compra * cashback_maximo_anunciado / Decimal("100")).quantize(Decimal("0.01"))
    contexto = {
        "cashback_maximo_anunciado": cashback_maximo_anunciado,
        "exemplo_compra": exemplo_compra,
        "exemplo_cashback": exemplo_cashback,
    }
    return render(request, "paginas/cashback_vale_a_pena.html", contexto)


def e_confiavel(request):
    contexto = {"saque_valor_minimo": settings.SAQUE_VALOR_MINIMO}
    return render(request, "paginas/e_confiavel.html", contexto)


def checklist_cashback_confiavel(request):
    return render(request, "paginas/checklist_cashback_confiavel.html")


def contato(request):
    if request.method == "POST":
        form = ContatoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            corpo = f"Nome: {dados['nome']}\nE-mail: {dados['email']}\n\n{dados['mensagem']}"
            try:
                EmailMessage(
                    subject=f"[Fale conosco] {dados['assunto']}",
                    body=corpo,
                    to=["contato@cash-b.com"],
                    reply_to=[dados["email"]],
                ).send()
                messages.success(
                    request, "Mensagem enviada! A gente responde o quanto antes no seu e-mail."
                )
            except Exception:
                logger.exception("Falha ao enviar mensagem do Fale conosco")
                messages.error(
                    request,
                    "Não conseguimos enviar sua mensagem agora. Tenta de novo em alguns minutos "
                    "ou escreve direto pra contato@cash-b.com.",
                )
            return redirect("contato")
    else:
        form = ContatoForm()

    return render(request, "paginas/contato.html", {"form": form})
