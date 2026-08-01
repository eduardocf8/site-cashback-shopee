from django.http import HttpResponse

from . import aprovacao


def aprovar_publicacao(request, token):
    """Página que o link de aprovar/rejeitar do e-mail abre - só texto simples, já
    que é aberta uma vez só e não precisa de nenhuma interação além do clique."""
    _registro, mensagem = aprovacao.processar_decisao(token)
    return HttpResponse(mensagem, content_type="text/plain; charset=utf-8")
