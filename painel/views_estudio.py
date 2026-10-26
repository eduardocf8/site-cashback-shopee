"""Estúdio Instagram no painel: lista de posts, criar (link da Shopee, IA, modelo ou em branco),
editor, imagens e "Minha marca". As regras ficam em estudio/afiliados.py.

Em construção: só abre para a conta com "testa o Estúdio Instagram" ligado no admin. Para as
outras, todas as páginas daqui respondem 404, como se não existissem."""

import json
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST

from carrosseis.servicos import ErroGerador
from instagram_painel import api as ig_api
from instagram_painel.models import ContaInstagram
from estudio import afiliados as A
from estudio.marcas import CAMPOS_TEXTO, FORMATOS, LIMITES_LISTA, MARCAS
from estudio.models import FONTES_AFILIADO, TEMAS_AFILIADO, ImagemAfiliado, MarcaAfiliado, ModeloAfiliado, PostInstagram

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

SLUG = "estudio_instagram"
MAXIMO_JSON = 900_000  # slides + miniatura em base64


def exige(slug: str, *ou: str):
    """Conta logada, módulo visível (até o lançamento, só com o teste ligado; senão 404) e no plano
    (senão a tela de desbloquear do primeiro). Com `ou`, basta um dos módulos estar no plano."""
    def decorador(view):
        @wraps(view)
        @conta_requerida
        def interna(request, *args, **kwargs):
            conta = conta_logada(request)
            item = mod.POR_SLUG[slug]
            if not mod.ve_beta(item, conta):
                raise Http404
            liberados = conta.modulos_liberados()
            if not any(mod.estado(mod.POR_SLUG[s], liberados) == "liberado" for s in (slug, *ou)):
                if request.method != "GET":
                    return JsonResponse({"erro": f"{item['nome']} não está no seu plano."}, status=403)
                return render(request, "painel/modulo.html", _contexto(
                    request, slug, item={**item, "icone_path": mod.ICONES[item["icone"]]},
                    situacao=mod.estado(item, liberados)))
            return view(request, conta, *args, **kwargs)
        return interna
    return decorador


_beta = exige(SLUG)


def _do_dono(conta, pk) -> PostInstagram:
    return get_object_or_404(PostInstagram, pk=pk, conta=conta)


def _json(request) -> dict:
    if len(request.body) > MAXIMO_JSON:
        raise ValueError("Conteúdo grande demais.")
    dados = json.loads(request.body or b"{}")
    if not isinstance(dados, dict):
        raise ValueError("Formato inválido.")
    return dados


def _url_miniatura(post) -> str:
    if not post.miniatura:
        return ""
    return reverse("painel_estudio_miniatura", args=[post.pk]) + f"?v={int(post.atualizado_em.timestamp())}"


@_beta
def lista(request, conta):
    posts = PostInstagram.objects.filter(conta=conta).only("pk", "nome", "formato", "estado", "atualizado_em", "miniatura")[:60]
    cartoes = [{"post": p, "miniatura": _url_miniatura(p), "formato": FORMATOS[p.formato][0]} for p in posts]
    modelos = [{k: m[k] for k in ("codigo", "nome", "descricao", "formato")} | {"formato_nome": FORMATOS[m["formato"]][0], "meu": m.get("meu")}
               for m in A.modelos(conta)]
    return render(request, "painel/estudio.html", _contexto(
        request, SLUG, cartoes=cartoes, modelos=modelos, premium=A.eh_premium(conta), restantes=A.restantes(conta),
        shopee_ok=conta.shopee_configurada, ia_ligada=bool(settings.ANTHROPIC_API_KEY),
        formatos=[(k, v[0]) for k, v in FORMATOS.items()], previa_modelos=A.modelos(conta),
        previa_config={**_desenho(conta), "exemplo": static("estudio/exemplo-produto.jpg")},
        ig=ContaInstagram.objects.filter(conta=conta).first(), configurado=bool(ig_api.app_id() and ig_api.app_secret()),
    ))


@require_POST
@_beta
def novo(request, conta):
    como = request.POST.get("como", "")
    try:
        post = A.criar(conta, como, link=request.POST.get("link", ""), pedido=request.POST.get("pedido", ""),
                       codigo_modelo=request.POST.get("modelo", ""), formato=request.POST.get("formato", ""))
    except (A.ErroEstudio, ErroGerador) as erro:
        messages.error(request, str(erro))
        return redirect("painel_estudio")
    return redirect("painel_estudio_editor", pk=post.pk)


def _desenho(conta) -> dict:
    """O que o desenho dos slides precisa: plano, cores, fontes e a Minha marca."""
    premium = A.eh_premium(conta)
    marca = MarcaAfiliado.objects.filter(conta=conta).first()
    fontes = "painel/carrossel/fontes/"
    return {
        "premium": premium, "temas": A.temas(conta),
        "marca_afiliado": {
            "arroba": marca.arroba if marca else "", "fonte": marca.fonte if marca else "moderna",
            "logo": reverse("painel_estudio_logo") + f"?v={int(marca.atualizada_em.timestamp())}" if marca and marca.logo else "",
        },
        "fontes": {"dm500": static(fontes + "dm-sans-latin-500-normal.woff2"), "dm800": static(fontes + "dm-sans-latin-800-normal.woff2"),
                   "sora": static(fontes + "sora-latin-800-normal.woff2"), "bebas": static(fontes + "bebas-neue-latin-400-normal.woff2"),
                   "playfair": static(fontes + "playfair-display-latin-900-normal.woff2"),
                   "instrument": static(fontes + "instrument-serif-latin-400-normal.woff2"),
                   "manrope": static(fontes + "manrope-latin-800-normal.woff2"), "mono": static(fontes + "jetbrains-mono.woff2")},
    }


def _config(conta, post) -> dict:
    m = MARCAS[A.MARCA]
    desenho = _desenho(conta)
    return {
        **desenho, "marca": A.MARCA, "nome": m["nome"], "modo": "completo" if desenho["premium"] else "simples",
        "formatos": {k: {"nome": n, "w": w, "h": h} for k, (n, w, h) in FORMATOS.items()},
        "tipos": {k: {"nome": n, "campos": c} for k, (n, c) in m["tipos"].items()},
        "cores": m["cores"], "artes": m["artes"], "tons": m["tons"], "icones": [], "prints": {},
        "produto": {k: post.produto.get(k) for k in ("nome", "imagem", "preco", "de", "desconto")} if post.produto else {},
        "urls": {"salvar": reverse("painel_estudio_salvar", args=[post.pk]), "ia": reverse("painel_estudio_ia", args=[post.pk]),
                 "imagens": reverse("painel_estudio_imagens"), "lista": reverse("painel_estudio"),
                 "modelo": reverse("painel_estudio_salvar_modelo", args=[post.pk]) if desenho["premium"] else ""},
        "ia_ligada": bool(settings.ANTHROPIC_API_KEY),
        "campos_texto": {k: list(v) for k, v in CAMPOS_TEXTO.items()}, "limites": LIMITES_LISTA, "max_slides": A.MAX_SLIDES,
    }


@_beta
def editor(request, conta, pk):
    post = _do_dono(conta, pk)
    premium = A.eh_premium(conta)
    projeto = {"id": post.pk, "nome": post.nome, "formato": post.formato, "tema": post.tema, "slides": post.slides, "legenda": post.legenda}
    temas = [(k, n) for k, n in TEMAS_AFILIADO if k != "marca" or "marca" in A.temas(conta)]
    r = A.restantes(conta)
    return render(request, "painel/estudio_editor.html", _contexto(
        request, SLUG, post=post, config=_config(conta, post), projeto=projeto, modelos=A.modelos(conta), premium=premium, temas=temas,
        restantes=f"Restam {r['geracoes']} de {r['limite']} criações com IA hoje.",
        tem_automacoes=mod.estado(mod.POR_SLUG["automacoes_instagram"], conta.modulos_liberados()) == "liberado",
    ))


@require_POST
@_beta
def salvar(request, conta, pk):
    post = _do_dono(conta, pk)
    try:
        A.salvar(post, _json(request))
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"id": post.pk, "slides": post.slides, "tema": post.tema})


@require_POST
@_beta
def ia(request, conta, pk):
    post = _do_dono(conta, pk)
    try:
        return JsonResponse(A.ajustar_com_ia(post, _json(request)))
    except (ValueError, A.ErroEstudio) as erro:
        return JsonResponse({"erro": str(erro)}, status=400)


@require_POST
@_beta
def salvar_modelo(request, conta, pk):
    """Guarda o post (já salvo) como modelo. Premium."""
    post = _do_dono(conta, pk)
    try:
        m = A.salvar_como_modelo(post, _json(request).get("nome"))
    except (ValueError, A.ErroEstudio) as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"codigo": f"meu-{m.pk}", "nome": m.nome})


@require_POST
@_beta
def apagar_modelo(request, conta, pk):
    get_object_or_404(ModeloAfiliado, pk=pk, conta=conta).delete()
    messages.info(request, "Modelo apagado.")
    return redirect("painel_estudio")


@require_POST
@_beta
def apagar(request, conta, pk):
    _do_dono(conta, pk).delete()
    messages.info(request, "Post apagado.")
    return redirect("painel_estudio")


@require_POST
@_beta
def duplicar(request, conta, pk):
    copia = A.duplicar(_do_dono(conta, pk))
    return redirect("painel_estudio_editor", pk=copia.pk)


def _bytes(dados, tipo):
    resposta = HttpResponse(bytes(dados), content_type=tipo)
    resposta["Cache-Control"] = "private, max-age=86400"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@_beta
def miniatura(request, conta, pk):
    post = _do_dono(conta, pk)
    if not post.miniatura:
        raise Http404
    return _bytes(post.miniatura, "image/jpeg")


@_beta
def imagens(request, conta):
    """GET: as imagens enviadas. POST: envia uma (foto de produto ou fundo)."""
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return JsonResponse({"erro": "Escolha uma imagem."}, status=400)
        try:
            A.guardar_imagem(conta, arquivo)
        except A.ErroEstudio as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
    lista_ = ImagemAfiliado.objects.filter(conta=conta).only("pk", "nome")[:A.MAX_IMAGENS]
    return JsonResponse({"imagens": [{"id": i.pk, "url": reverse("painel_estudio_imagem", args=[i.pk]), "nome": i.nome} for i in lista_]})


@_beta
def imagem(request, conta, pk):
    """GET: a imagem. POST: apaga."""
    im = get_object_or_404(ImagemAfiliado, pk=pk, conta=conta)
    if request.method == "POST":
        im.delete()
        return JsonResponse({"ok": True})
    return _bytes(im.dados, im.tipo)


@_beta
def minha_marca(request, conta):
    premium = A.eh_premium(conta)
    marca = MarcaAfiliado.objects.filter(conta=conta).first() or MarcaAfiliado(conta=conta)
    if request.method == "POST":
        try:
            A.salvar_marca(conta, request.POST, logo=request.FILES.get("logo"), tirar_logo=bool(request.POST.get("tirar_logo")))
        except A.ErroEstudio as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Sua marca foi salva.")
        return redirect("painel_estudio_marca")
    return render(request, "painel/estudio_marca.html", _contexto(
        request, SLUG, marca=marca, premium=premium, fontes=FONTES_AFILIADO,
        logo=reverse("painel_estudio_logo") + f"?v={int(marca.atualizada_em.timestamp())}" if marca.pk and marca.logo else "",
    ))


@_beta
def logo(request, conta):
    marca = MarcaAfiliado.objects.filter(conta=conta).first()
    if not marca or not marca.logo:
        raise Http404
    return _bytes(marca.logo, "image/png")
