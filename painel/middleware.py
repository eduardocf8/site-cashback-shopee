from django.conf import settings


class DominioDoPainelMiddleware:
    """Nos domínios de settings.APPFILIADO_PAINEL_HOSTS (app.appfiliado.com.br),
    troca as URLs do site inteiro pelas do painel (painel/urls_dominio.py) -
    assim o painel mora na raiz do domínio e nada da cash-b (páginas, /admin/)
    aparece num endereço do Appfiliado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APPFILIADO_PAINEL_HOSTS:
            host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
            if host in settings.APPFILIADO_PAINEL_HOSTS:
                request.urlconf = "painel.urls_dominio"
        return self.get_response(request)
