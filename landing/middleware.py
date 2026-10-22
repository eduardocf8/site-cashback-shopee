from django.conf import settings


class LandingDoAppfiliadoMiddleware:
    """appfiliado.com.br (e www.) mostra só a página de vendas do Appfiliado (landing/urls.py):
    nada da cash-b nem o /admin/ dela aparece nesse endereço."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APPFILIADO_LANDING_HOSTS:
            host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
            if host in settings.APPFILIADO_LANDING_HOSTS:
                request.urlconf = "landing.urls"
        return self.get_response(request)
