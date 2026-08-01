from django.conf import settings
from django.shortcuts import render


def termos_de_uso(request):
    return render(request, "paginas/termos.html")


def privacidade(request):
    return render(request, "paginas/privacidade.html")


def cookies(request):
    return render(request, "paginas/cookies.html")


def regras_cashback(request):
    contexto = {
        "percentual_repasse": settings.SHOPEE_CASHBACK_PERCENTUAL,
        "saque_valor_minimo": settings.SAQUE_VALOR_MINIMO,
    }
    return render(request, "paginas/regras_cashback.html", contexto)
