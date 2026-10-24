"""Liga o clique anônimo (ROADMAP 13.11, decisão de 24/10/2026) à conta quando a
pessoa se cadastra ou entra com o Google, pelo mesmo navegador, dentro da janela de
7 dias - ver accounts/funil.py (página de escolha) e accounts/views.py."""
from django.utils import timezone

from links.models import Click
from pedidos.models import Pedido

NOME_COOKIE = "cashb_clique_anonimo"
JANELA_DIAS = 7
# Teto de cliques guardados por navegador - evita um cookie enorme em quem navega
# muito sem se cadastrar; os mais antigos vão caindo fora da janela de qualquer jeito.
MAX_IDS_NO_COOKIE = 20
IDADE_MAXIMA_COOKIE_SEGUNDOS = JANELA_DIAS * 24 * 3600


def _ids_do_cookie(request) -> list[str]:
    # Cookie essencial (não precisa de consentimento) - serve só pra cash-b saber a
    # quem ligar o clique, não é compartilhado com terceiros nem usado pra
    # publicidade (ver paginas/templates/paginas/cookies.html). Assinado pra evitar
    # que alguém edite o valor na mão e tente ligar o clique anônimo de outra pessoa.
    bruto = request.get_signed_cookie(NOME_COOKIE, default="", salt=NOME_COOKIE)
    return [item for item in bruto.split(",") if item]


def salvar_click_anonimo(request, response, click_id_hex: str) -> None:
    """Acrescenta esse clique ao cookie do navegador - lido depois no cadastro/login
    pra ligar à conta nova (ver ligar_clicks_anonimos)."""
    ids = _ids_do_cookie(request)
    if click_id_hex not in ids:
        ids.append(click_id_hex)
    ids = ids[-MAX_IDS_NO_COOKIE:]
    response.set_signed_cookie(
        NOME_COOKIE, ",".join(ids), salt=NOME_COOKIE,
        max_age=IDADE_MAXIMA_COOKIE_SEGUNDOS, httponly=True, samesite="Lax",
    )


def ligar_clicks_anonimos(request, usuario) -> int:
    """Chamada assim que a pessoa cria conta ou entra com o Google (accounts/views.py):
    liga à conta todo clique anônimo do cookie desse navegador que ainda está sem
    usuário e dentro da janela de 7 dias. Os Pedidos que já existiam a partir desses
    cliques também passam a ter usuario preenchido (pra aparecer em "Meus pedidos" de
    cara); o valor_cashback deles é recalculado sozinho na próxima sincronização, que
    volta a computar o cashback normalmente agora que o clique tem usuário (ver
    pedidos/services.py::_montar_defaults). Retorna quantos cliques foram ligados."""
    ids = _ids_do_cookie(request)
    if not ids:
        return 0

    limite = timezone.now() - timezone.timedelta(days=JANELA_DIAS)
    clicks = list(Click.objects.filter(id__in=ids, usuario__isnull=True, criado_em__gte=limite))
    if not clicks:
        return 0

    for click in clicks:
        click.usuario = usuario
    Click.objects.bulk_update(clicks, ["usuario"])

    Pedido.objects.filter(click__in=clicks, usuario__isnull=True).update(usuario=usuario)
    return len(clicks)
