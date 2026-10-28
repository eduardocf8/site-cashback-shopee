"""Página pública do link de entrada nos grupos (bot_whatsapp/entrada.py): seunome.appfiliado.com.br/g/<slug>/.

Abre leve (sem nada do site da bio), registra a visita no pixel do Meta e, no botão, manda pro grupo
da vez. O clique passa por /g/<slug>/entrar/, que conta e redireciona: assim o link do anúncio nunca
muda, mesmo trocando de grupo."""

from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from bot_whatsapp import entrada
from bot_whatsapp.models import LinkEntrada

from .models import SiteAfiliado


def _link(request, slug, endereco=None) -> tuple[LinkEntrada, SiteAfiliado]:
    endereco = endereco or getattr(request, "site_endereco", "")
    site = SiteAfiliado.objects.select_related("conta").filter(endereco=endereco).first()
    link = LinkEntrada.objects.filter(conta=site.conta, slug=slug, ativo=True).first() if site else None
    if not link or not entrada.liberado(site.conta):
        raise Http404("Link não encontrado.")
    return link, site


def _campanha(request) -> str:
    return str(request.GET.get("utm_campaign") or "").strip()[:80]


@never_cache
def pagina(request, slug, endereco=None):
    link, site = _link(request, slug, endereco)
    if request.method == "GET" and not entrada.e_robo(request):
        entrada.contar(link, _campanha(request))
    consulta = request.META.get("QUERY_STRING", "")
    return render(request, "meusite/entrada.html", {
        "link": link, "site": site, "tem_vaga": entrada.grupo_da_vez(link) is not None,
        "destino": "entrar/" + (f"?{consulta}" if consulta else ""),
    })


@never_cache
def entrar(request, slug, endereco=None):
    link, site = _link(request, slug, endereco)
    grupo = entrada.grupo_da_vez(link)
    if not grupo:
        return render(request, "meusite/entrada.html", {"link": link, "site": site, "tem_vaga": False, "destino": ""},
                      status=503)
    if not entrada.e_robo(request):
        entrada.contar(link, _campanha(request), grupo["jid"], clique=True)
    return redirect(grupo["convite"])


def foto(request, slug, endereco=None):
    """A foto do link; sem ela, a do Meu site."""
    link, site = _link(request, slug, endereco)
    foto = link.foto or site.foto
    if not foto:
        raise Http404
    return HttpResponse(bytes(foto), content_type="image/jpeg")
