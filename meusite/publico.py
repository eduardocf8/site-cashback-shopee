"""O site que o visitante vê (seunome.appfiliado.com.br ou <painel>/s/seunome/)."""

import logging
import threading

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.clickjacking import xframe_options_sameorigin

from bot_whatsapp import copia, shopee_ofertas
from licencas import planos
from licencas.models import MODULO_SITE
from ofertas.services import resolver_item_id_sem_rede

from . import vitrine
from .models import REDES, BotaoSite, CliqueSite, ProdutoSite, SiteAfiliado

logger = logging.getLogger(__name__)

CONVERSOES_POR_HORA = 20  # por visitante (IP), por site


def _site(request, endereco=None) -> SiteAfiliado:
    endereco = endereco or getattr(request, "site_endereco", "")
    site = SiteAfiliado.objects.select_related("conta").filter(endereco=endereco).first()
    previa = request.GET.get("previa") == "1" and _e_o_dono(request, site)
    if not site or not (previa or (site.publicado and MODULO_SITE in site.conta.modulos_liberados())):
        raise Http404("Site não encontrado.")
    return site


def _e_o_dono(request, site) -> bool:
    from painel.autenticacao import conta_logada

    conta = conta_logada(request)
    return bool(site and conta and conta.pk == site.conta_id)


def base_do_site(request, site) -> str:
    """Início dos links dentro do site: "/" no subdomínio, "/s/seunome/" pelo painel."""
    return "/" if getattr(request, "site_endereco", "") else f"/s/{site.endereco}/"


def contar(site, tipo, alvo_id=0, alvo_nome=""):
    hoje = timezone.localdate()
    registro, _ = CliqueSite.objects.get_or_create(
        site=site, dia=hoje, tipo=tipo, alvo_id=alvo_id, defaults={"alvo_nome": alvo_nome[:300]},
    )
    CliqueSite.objects.filter(pk=registro.pk).update(total=F("total") + 1)


def produtos_da_vitrine(site):
    if site.vitrine == SiteAfiliado.VITRINE_NENHUMA:
        return ProdutoSite.objects.none()
    if site.vitrine == SiteAfiliado.VITRINE_MANUAL and not planos.site_premium(site.conta):
        return ProdutoSite.objects.none()  # produtos escolhidos são do Premium (ex: o plano mudou)
    return site.produtos.filter(fonte=site.vitrine)[: vitrine.LIMITE]


@xframe_options_sameorigin  # a prévia do editor mostra o site num quadro, no próprio painel
def pagina(request, endereco=None):
    site = _site(request, endereco)
    previa = request.GET.get("previa") == "1"
    if not previa:
        contar(site, CliqueSite.VISITA)
    produtos = list(produtos_da_vitrine(site))
    regras = planos.site(site.conta)
    categorias = []
    for p in produtos:
        if p.categoria and p.categoria not in categorias:
            categorias.append(p.categoria)
    return render(request, "meusite/publico.html", {
        "site": site,
        "base": base_do_site(request, site),
        "botoes": site.botoes.all()[: regras["botoes"]],  # se o plano diminuiu, aparecem os primeiros
        "redes": site.lista_de_redes(),
        "produtos": produtos,
        "categorias": [(c, vitrine.nome_curto_da_categoria(c)) for c in categorias],
        "atualizado_em": max((p.posicao_em for p in produtos), default=None),
        "com_marca": not regras["premium"],
        "erro": request.GET.get("erro", ""),
        "previa": previa,
        # Na prévia do editor vão todos os ícones (escondidos os não preenchidos): o editor mostra
        # e esconde enquanto a pessoa digita, sem salvar.
        "todas_redes": [{"rede": rede, "nome": nome, "ativa": bool((site.redes or {}).get(rede))}
                        for rede, nome, _ in REDES] if previa else [],
        "hoje_ymd": timezone.localdate().strftime("%Y%m%d"),
        "url_appfiliado": settings.APPFILIADO_URL_PLANOS,
    })


def ir_botao(request, botao_id, endereco=None):
    site = _site(request, endereco)
    # Só os botões que aparecem no site (os primeiros do plano): um botão escondido depois de o
    # plano diminuir não continua funcionando pelo endereço direto.
    visiveis = list(site.botoes.values_list("pk", flat=True)[: planos.site(site.conta)["botoes"]])
    botao = BotaoSite.objects.filter(site=site, pk=botao_id, pk__in=visiveis).first()
    if not botao:
        raise Http404
    contar(site, CliqueSite.BOTAO, botao.pk, botao.texto)
    return redirect(botao.url)


def ir_rede(request, rede, endereco=None):
    from .models import REDES

    site = _site(request, endereco)
    nomes = [r for r, _, _ in REDES]
    url = (site.redes or {}).get(rede)
    if rede not in nomes or not url:
        raise Http404
    contar(site, CliqueSite.REDE, nomes.index(rede) + 1, rede)
    return redirect(url)


def ir_produto(request, produto_id, endereco=None):
    site = _site(request, endereco)
    produto = ProdutoSite.objects.filter(site=site, pk=produto_id).first()
    if not produto:
        raise Http404
    contar(site, CliqueSite.PRODUTO, produto.pk, produto.nome)
    if not produto.link_afiliado:
        try:
            produto.link_afiliado = vitrine.link_do_site(site, produto.link_produto, vitrine=True)[:500]
            produto.save(update_fields=["link_afiliado"])
        except Exception:  # noqa: BLE001 - na pior hipótese, vai para o produto sem o link
            logger.exception("Meu site: link na hora do produto %s", produto.pk)
            return redirect(produto.link_produto)
    return redirect(produto.link_afiliado)


def _ip(request) -> str:
    from accounts.ratelimit import _obter_ip

    return _obter_ip(request)  # o IP real (o começo do X-Forwarded-For o visitante inventa)


# No máximo 2 visitantes por vez abrindo link curto na Shopee (pode levar alguns segundos):
# o servidor tem poucos atendimentos ao mesmo tempo e eles não podem ficar todos presos nisso.
_ABRINDO_LINK = threading.BoundedSemaphore(2)


def _identificar_sem_travar(link: str) -> str:
    rapido = resolver_item_id_sem_rede(link)
    if rapido:
        return str(rapido)
    if not _ABRINDO_LINK.acquire(blocking=False):
        return ""  # ocupado: vai com o link como veio (o link de afiliado sai do mesmo jeito)
    try:
        return copia.identificar_produto(link)
    finally:
        _ABRINDO_LINK.release()


def converter(request, endereco=None):
    """O visitante colou um link da Shopee: vai para a Shopee pelo link do dono do site."""
    site = _site(request, endereco)
    base = base_do_site(request, site)
    if not site.mostrar_conversor:
        raise Http404
    links = copia.links_shopee(request.GET.get("link", ""))
    if not links:
        return redirect(f"{base}?erro=link#conversor")
    chave = f"meusite-conv:{site.pk}:{_ip(request)}"
    if cache.get(chave, 0) >= CONVERSOES_POR_HORA:
        return redirect(f"{base}?erro=limite#conversor")
    cache.set(chave, cache.get(chave, 0) + 1, 3600)
    contar(site, CliqueSite.CONVERSOR)
    try:
        # Do link limpo do produto (sem o rastreio de quem divulgou); sem ele, do original.
        item_id = _identificar_sem_travar(links[0])
        produto = None
        if item_id:
            app_id, secret = vitrine._credenciais(site)
            produto = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id)
        return redirect(vitrine.link_do_site(site, (produto or {}).get("link") or links[0]))
    except Exception:  # noqa: BLE001
        logger.exception("Meu site: conversor do site %s", site.pk)
        return redirect(f"{base}?erro=falhou#conversor")


@cache_control(public=True, max_age=86400)
def foto(request, endereco=None):
    site = _site(request, endereco)
    if not site.foto:
        raise Http404
    return HttpResponse(bytes(site.foto), content_type="image/jpeg")


def nao_encontrado(request, exception=None):
    return render(request, "meusite/nao_encontrado.html", status=404)
