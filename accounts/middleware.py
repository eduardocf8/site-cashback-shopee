SESSION_KEY_ORIGEM = "origem_cadastro"
TAMANHO_ORIGEM = 50
TAMANHO_CAMPANHA = 100


class OrigemCadastroMiddleware:
    """Guarda na sessão o utm_source/utm_campaign da PRIMEIRA visita com UTM de quem
    ainda não tem conta, pra registrar() gravar no User. Primeiro toque, não último:
    quem chega por um Pin, navega e só volta pra se cadastrar dias depois pelo Google
    continua contando como Pinterest - é o canal que trouxe a pessoa que interessa.

    Sem isso o funil_cadastros não tinha como separar a coorte por canal (ver a
    ressalva no fim da saída dele)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origem = request.GET.get("utm_source", "").strip()
        if (
            origem
            and not request.user.is_authenticated
            and SESSION_KEY_ORIGEM not in request.session
        ):
            request.session[SESSION_KEY_ORIGEM] = {
                "origem": origem.lower()[:TAMANHO_ORIGEM],
                "campanha": request.GET.get("utm_campaign", "").strip()[:TAMANHO_CAMPANHA],
            }
        return self.get_response(request)
