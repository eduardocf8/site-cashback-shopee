from django.conf import settings


def meta_pixel(request):
    """Deixa o ID do Meta Pixel disponível em todo template sem precisar passar no
    contexto de cada view - só usado por templates/_meta_pixel.html pra decidir se
    renderiza o script ou não (vazio = recurso desligado)."""
    return {"meta_pixel_id": settings.META_PIXEL_ID}
