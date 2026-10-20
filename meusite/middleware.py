from django.conf import settings
from django.http import HttpResponseNotFound

from .models import ENDERECOS_RESERVADOS


class SiteDoAfiliadoMiddleware:
    """seunome.appfiliado.com.br -> o site daquela conta (meusite/urls_publico.py). Os
    domínios do painel e da API continuam com os middlewares deles."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        dominio = settings.APPFILIADO_SITES_DOMINIO
        if dominio:
            host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
            sufixo = "." + dominio
            do_dominio = host == dominio or host.endswith(sufixo)
            if (do_dominio and host not in settings.APPFILIADO_PAINEL_HOSTS
                    and host not in settings.APPFILIADO_API_HOSTS):
                endereco = host[: -len(sufixo)] if host.endswith(sufixo) else ""
                if endereco and "." not in endereco and endereco not in ENDERECOS_RESERVADOS:
                    request.urlconf = "meusite.urls_publico"
                    request.site_endereco = endereco
                else:
                    # www., admin., a.b., o domínio puro...: nada de cair no site da cash-b
                    # (nem no /admin/ dela) com o nome do Appfiliado no endereço.
                    return HttpResponseNotFound("Página não encontrada.", content_type="text/plain; charset=utf-8")
        return self.get_response(request)
