from django.conf import settings

from .meta_capi import COOKIE_CONSENTIMENTO, CONSENTIMENTO_ACEITO


def meta_pixel(request):
    """Deixa o ID do Meta Pixel disponível em todo template sem precisar passar no
    contexto de cada view - só usado por templates/_meta_pixel.html pra decidir se
    renderiza o script ou não (vazio = recurso desligado). O nome/valor do cookie de
    consentimento vêm do mesmo lugar que a CAPI lê (meta_capi.py), pra navegador e
    servidor nunca divergirem."""
    return {
        "meta_pixel_id": settings.META_PIXEL_ID,
        "cookie_consentimento": COOKIE_CONSENTIMENTO,
        "consentimento_aceito": CONSENTIMENTO_ACEITO,
    }
