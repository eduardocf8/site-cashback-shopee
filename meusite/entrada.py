"""Página pública do link de entrada nos grupos (bot_whatsapp/entrada.py): seunome.appfiliado.com.br/g/<slug>/.

Abre leve (sem nada do site da bio), registra a visita no pixel do Meta e, no botão, manda pro grupo
da vez. O clique passa por /g/<slug>/entrar/, que conta e redireciona: assim o link do anúncio nunca
muda, mesmo trocando de grupo."""

import re

from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from bot_whatsapp import entrada
from bot_whatsapp.models import GrupoMonitorado, LinkEntrada

from . import cores
from .models import SiteAfiliado

OFERTAS_NA_PAGINA = 4
FOTOS_NA_CAPA = 5
EMOJI_NA_FRENTE = re.compile(r"^([^\w\s]+)\s+(.+)$")


def _total_aproximado(total: int) -> int:
    """3.247 -> 3.200; 347 -> 340 (o "mais de" nunca passa do número de verdade)."""
    return total // 100 * 100 if total >= 1000 else total // 10 * 10


def montar(link: LinkEntrada, site: SiteAfiliado, previa: bool = False, foto_url: str = "", capa_url: str = "") -> dict:
    """Tudo o que a página do link mostra, no modelo e com os blocos que a pessoa escolheu.
    foto_url e capa_url mudam na prévia do painel (a página pública usa foto.jpg e capa.jpg)."""
    from .publico import produtos_da_vitrine

    situacao = entrada.situacao(link)
    vitrine = link.modelo == LinkEntrada.MODELO_VITRINE
    ofertas = []
    if vitrine or link.mostrar_ofertas or (link.mostrar_capa and not link.capa):
        ofertas = [p for p in produtos_da_vitrine(site)[:40] if p.imagem_url][: max(OFERTAS_NA_PAGINA, FOTOS_NA_CAPA)]
    total = 0
    if link.mostrar_total:
        total = sum(m or 0 for m in GrupoMonitorado.objects.filter(conta=link.conta, jid__in=link.grupos)
                    .values_list("membros", flat=True))
    da_vez = situacao["da_vez"]
    beneficios = []
    for linha in (link.beneficios or [])[:4]:
        achou = EMOJI_NA_FRENTE.match(str(linha).strip())
        beneficios.append({"icone": achou.group(1), "texto": achou.group(2)} if achou else {"icone": "✓", "texto": linha})
    capa_fotos = [p.imagem_url for p in ofertas[:FOTOS_NA_CAPA]] if link.mostrar_capa and not link.capa else []
    return {
        "link": link, "site": site, "previa": previa, "modelo": link.modelo,
        "fixo": link.modelo in (LinkEntrada.MODELO_BENEFICIOS, LinkEntrada.MODELO_VITRINE),  # botão preso embaixo
        "tema": cores.tema(link.cor or site.cor),
        "nome": link.nome_exibido or site.nome or "",
        "tem_foto": bool(link.foto or site.foto),
        "foto_url": foto_url or f"foto.jpg?v={link.foto_versao}-{site.foto_versao}",
        "capa_url": (capa_url or f"capa.jpg?v={link.capa_versao}") if link.mostrar_capa and link.capa else "",
        "capa_fotos": capa_fotos if len(capa_fotos) >= 3 else [],
        "selos": [s for s in (link.selos or [])[:3] if str(s).strip()] if link.mostrar_selos else [],
        "beneficios": beneficios if link.modelo == LinkEntrada.MODELO_BENEFICIOS else [],
        "ofertas": ofertas[:OFERTAS_NA_PAGINA] if vitrine or link.mostrar_ofertas else [],
        "total": _total_aproximado(total) if total >= 50 else 0,
        "vagas": {"nome": da_vez["nome"], "membros": da_vez["membros"], "limite": link.limite_por_grupo,
                  "porcento": da_vez["ocupacao"]} if link.mostrar_vagas and da_vez else None,
        "redes": site.lista_de_redes() if link.mostrar_redes else [],
        "tem_vaga": da_vez is not None,
    }


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
        **montar(link, site), "destino": "entrar/" + (f"?{consulta}" if consulta else ""),
    })


@never_cache
def entrar(request, slug, endereco=None):
    link, site = _link(request, slug, endereco)
    grupo = entrada.grupo_da_vez(link)
    if not grupo:
        return render(request, "meusite/entrada.html", {**montar(link, site), "tem_vaga": False, "destino": ""}, status=503)
    if not entrada.e_robo(request):
        entrada.contar(link, _campanha(request), grupo["jid"], clique=True)
    return redirect(grupo["convite"])


def capa(request, slug, endereco=None):
    link, _ = _link(request, slug, endereco)
    if not link.capa:
        raise Http404
    return HttpResponse(bytes(link.capa), content_type="image/jpeg")


def foto(request, slug, endereco=None):
    """A foto do link; sem ela, a do Meu site."""
    link, site = _link(request, slug, endereco)
    foto = link.foto or site.foto
    if not foto:
        raise Http404
    return HttpResponse(bytes(foto), content_type="image/jpeg")
