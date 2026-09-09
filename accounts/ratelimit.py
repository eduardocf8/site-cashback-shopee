from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def _obter_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "desconhecido")


def _incrementar_contador(chave: str, janela_segundos: int) -> int:
    """Contador de janela fixa: a primeira chamada grava o TTL, as seguintes só
    incrementam (sem renovar o TTL) - a janela sempre termina janela_segundos depois
    da primeira tentativa, não da última."""
    if cache.add(chave, 1, janela_segundos):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:
        # a chave expirou entre o add() (que falhou, achando que já existia) e o
        # incr() - trata como se fosse a primeira tentativa da nova janela.
        cache.add(chave, 1, janela_segundos)
        return 1


def limitar_por_ip(nome: str, limite: int, janela_segundos: int):
    """Bloqueia (HTTP 429) depois de `limite` requisições do mesmo IP dentro de
    `janela_segundos`, pra telas sem login que disparam e-mail ou criam conta
    (cadastro, esqueci-senha, reenviar verificação) - django-axes só protege o login.

    Usa o cache padrão do Django (memória local do processo) em vez de uma biblioteca
    externa (django-ratelimit) só pra isso - é só um contador com TTL. Só funciona
    corretamente com 1 worker do gunicorn (é o caso hoje - ver README.md); com mais de
    um worker, cada processo teria seu próprio contador."""
    def decorador(view_func):
        @wraps(view_func)
        def view_com_limite(request, *args, **kwargs):
            chave = f"ratelimit:{nome}:{_obter_ip(request)}"
            if _incrementar_contador(chave, janela_segundos) > limite:
                return HttpResponse("Muitas tentativas. Tente de novo em alguns minutos.", status=429)
            return view_func(request, *args, **kwargs)
        return view_com_limite
    return decorador
