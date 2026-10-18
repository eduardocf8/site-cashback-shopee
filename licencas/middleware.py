from django.conf import settings
from django.http import HttpResponseNotFound

PREFIXO_PERMITIDO = "/licencas/"


class SoApiNoDominioAppfiliadoMiddleware:
    """Nos domínios de settings.APPFILIADO_API_HOSTS (ex: api.appfiliado.com.br), só a
    API de licenças responde. Sem isso, o mesmo servidor mostraria o site e o /admin/
    da cash-b num endereço do Appfiliado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APPFILIADO_API_HOSTS:
            host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
            if host in settings.APPFILIADO_API_HOSTS and not request.path.startswith(PREFIXO_PERMITIDO):
                return HttpResponseNotFound("Não encontrado.")
        return self.get_response(request)
