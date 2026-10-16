"""Prova social com números reais da cash-b (ROADMAP 13.8).

Cada frase só aparece quando o número passa de um mínimo configurável
(PROVA_SOCIAL_MIN_*): número pequeno ("R$ 50 já pagos") atrapalha mais do que
ajuda. Valores arredondados para baixo ("mais de 600"), nunca para cima.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Sum

from pedidos.models import Pedido
from saques.models import Saque

CHAVE_CACHE = "prova_social:frases"
CACHE_SEGUNDOS = 60 * 60


def _aproximado(numero) -> str:
    """"Mais de 600" para 674; "600" exato para 600 ("mais de 600" seria falso).
    Arredonda sempre para baixo: centenas abaixo de 10 mil, milhares acima."""
    numero = int(numero)
    passo = 1 if numero < 100 else 100 if numero < 10_000 else 1_000
    arredondado = numero // passo * passo
    texto = f"{arredondado:,}".replace(",", ".")
    return texto if arredondado == numero else f"Mais de {texto}"


def _calcular_frases() -> list[str]:
    frases = []

    usuarios = get_user_model().objects.filter(is_active=True, is_staff=False).count()
    if usuarios >= settings.PROVA_SOCIAL_MIN_USUARIOS:
        frases.append(f"{_aproximado(usuarios)} pessoas já se cadastraram")

    # Só pedidos vindos de um clique do site: os "fora do site" não geram cashback
    # pra ninguém (ver pedidos/analytics.py::obter_pedidos_filtrados).
    pedidos = Pedido.objects.filter(Pedido.filtro_do_site()).exclude(status=Pedido.STATUS_CANCELADO).count()
    if pedidos >= settings.PROVA_SOCIAL_MIN_PEDIDOS:
        frases.append(f"{_aproximado(pedidos)} compras com cashback")

    pago = Saque.objects.filter(status=Saque.STATUS_PAGO).aggregate(total=Sum("valor"))["total"] or Decimal("0")
    if pago >= settings.PROVA_SOCIAL_MIN_PAGO:
        texto = _aproximado(pago)
        texto = texto.replace("Mais de ", "Mais de R$ ") if texto.startswith("Mais de") else f"R$ {texto}"
        frases.append(f"{texto} já pagos via Pix")

    return frases


def frases_prova_social() -> list[str]:
    """Consulta o banco no máximo 1x por hora (cache), não a cada visita à home."""
    frases = cache.get(CHAVE_CACHE)
    if frases is None:
        frases = _calcular_frases()
        cache.set(CHAVE_CACHE, frases, CACHE_SEGUNDOS)
    return frases
