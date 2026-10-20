"""Meu site: o editor no painel (o site público está em meusite/publico.py)."""

import re
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from licencas import planos
from licencas.models import MODULO_WHATSAPP
from meusite.forms import BotaoForm, FotoForm, SiteForm
from meusite import vitrine
from meusite.models import ENDERECOS_RESERVADOS, BotaoSite, CliqueSite, ProdutoSite, SiteAfiliado

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

CAMPOS_DA_VITRINE = {"vitrine", "busca_tipo", "palavra_chave", "loja", "categorias", "ordenacao", "links_manuais"}


def _liberado(conta) -> bool:
    return mod.estado(mod.POR_SLUG["site"], conta.modulos_liberados()) == "liberado"


def endereco_sugerido(conta) -> str:
    """Do nome (ou do e-mail): "Bia Souza" -> "biasouza", sem repetir o de outra conta."""
    base = conta.nome or conta.email.split("@")[0]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "", base)[:30] or "meusite"
    if len(base) < 3:
        base = f"{base}site"
    sugestao, n = base, 2
    while sugestao in ENDERECOS_RESERVADOS or SiteAfiliado.objects.filter(endereco=sugestao).exists():
        sugestao, n = f"{base}{n}", n + 1
    return sugestao


def url_publica(site) -> str:
    if not site.endereco:
        return ""
    if settings.APPFILIADO_SITES_DOMINIO:
        return f"https://{site.endereco}.{settings.APPFILIADO_SITES_DOMINIO}"
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + f"/s/{site.endereco}/"


def resumo_dos_cliques(site, dias=30) -> dict:
    desde = timezone.localdate() - timedelta(days=dias - 1)
    cliques = CliqueSite.objects.filter(site=site, dia__gte=desde)
    por_tipo = dict(cliques.values_list("tipo").annotate(soma=Sum("total")).values_list("tipo", "soma"))
    por_botao = dict(cliques.filter(tipo=CliqueSite.BOTAO).values_list("alvo_id").annotate(soma=Sum("total"))
                     .values_list("alvo_id", "soma"))
    produtos = (cliques.filter(tipo=CliqueSite.PRODUTO).values("alvo_id", "alvo_nome")
                .annotate(soma=Sum("total")).order_by("-soma")[:5])
    return {
        "dias": dias,
        "visitas": por_tipo.get(CliqueSite.VISITA, 0),
        "botoes": por_tipo.get(CliqueSite.BOTAO, 0) + por_tipo.get(CliqueSite.REDE, 0),
        "produtos": por_tipo.get(CliqueSite.PRODUTO, 0),
        "conversor": por_tipo.get(CliqueSite.CONVERSOR, 0),
        "por_botao": por_botao,
        "top_produtos": list(produtos),
    }


@conta_requerida
def meu_site(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        item = {**mod.POR_SLUG["site"], "icone_path": mod.ICONES["site"]}
        situacao = mod.estado(mod.POR_SLUG["site"], conta.modulos_liberados())
        return render(request, "painel/modulo.html", _contexto(request, "site", item=item, situacao=situacao))
    site, criado = SiteAfiliado.objects.get_or_create(conta=conta)
    tem_bot = MODULO_WHATSAPP in conta.modulos_liberados()
    if criado or not site.endereco:
        site.endereco = endereco_sugerido(conta)
        site.nome = site.nome or conta.nome or ""
        if not tem_bot:
            site.vitrine = SiteAfiliado.VITRINE_BUSCA
            site.pedido_vitrine_em = timezone.now()
        site.save()

    regras = planos.site(conta)
    form = SiteForm(instance=site, tem_bot=tem_bot, regras=regras)
    acao = request.POST.get("acao", "") if request.method == "POST" else ""
    if acao == "salvar":
        form = SiteForm(request.POST, instance=site, tem_bot=tem_bot, regras=regras)
        if form.is_valid():
            site = form.save(commit=False)
            if CAMPOS_DA_VITRINE & set(form.changed_data) and site.vitrine not in (
                    SiteAfiliado.VITRINE_BOT, SiteAfiliado.VITRINE_NENHUMA):
                site.pedido_vitrine_em = timezone.now()  # o worker refaz a vitrine em instantes
            site.save()
            if {"sub_id", "sub_id_vitrine"} & set(form.changed_data):
                # Sub ID novo: os links prontos dos produtos saem e são gerados de novo (o clique gera na hora).
                site.produtos.update(link_afiliado="")
            messages.success(request, "Site salvo.")
            return redirect("painel_meu_site")
        messages.error(request, "Confira os campos marcados.")
    elif acao:
        return _acao(request, site, acao, regras)

    botoes = list(site.botoes.all())
    cliques = resumo_dos_cliques(site)
    for b in botoes:
        b.cliques_30 = cliques["por_botao"].get(b.pk, 0)
    produtos = site.produtos.filter(fonte=site.vitrine)
    return render(request, "painel/meu_site.html", _contexto(
        request, "site",
        site=site, form=form, form_botao=BotaoForm(), botoes=botoes, maximo_botoes=regras["botoes"], regras=regras,
        url_publica=url_publica(site), url_previa=f"/s/{site.endereco}/?previa=1",
        cliques=cliques, total_produtos=produtos.count(), tem_bot=tem_bot,
        produtos_vitrine=list(produtos[:vitrine.LIMITE]),
        opcoes_categoria=vitrine.opcoes_de_categoria(),
        sem_marca=regras["premium"],
        dominio_sites=settings.APPFILIADO_SITES_DOMINIO,
        prefixo_sem_dominio=settings.APPFILIADO_PAINEL_URL.split("://")[-1].rstrip("/") + "/s/",
    ))


def _acao(request, site, acao, regras):
    voltar = redirect("painel_meu_site")
    if acao == "foto":
        form = FotoForm(request.POST, request.FILES)
        if form.is_valid():
            site.foto = form.cleaned_data["foto"]
            site.foto_versao += 1
            site.save(update_fields=["foto", "foto_versao", "atualizado_em"])
            messages.success(request, "Foto trocada.")
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros)
                           or "Não consegui abrir essa imagem. Use JPG ou PNG.")
        return voltar
    if acao == "remover_foto":
        site.foto, site.foto_versao = None, site.foto_versao + 1
        site.save(update_fields=["foto", "foto_versao", "atualizado_em"])
        return voltar
    if acao == "botao_novo":
        form = BotaoForm(request.POST)
        if site.botoes.count() >= regras["botoes"]:
            extra = "" if regras["premium"] else f" No plano Premium são até {planos.SITE[True]['botoes']}."
            messages.error(request, f"No seu plano dá para ter até {regras['botoes']} botões.{extra}")
        elif form.is_valid():
            botao = form.save(commit=False)
            botao.site = site
            botao.ordem = (site.botoes.order_by("-ordem").values_list("ordem", flat=True).first() or 0) + 1
            botao.save()
            messages.success(request, "Botão adicionado.")
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
        return redirect("/meu-site/#botoes")
    botao = BotaoSite.objects.filter(site=site, pk=request.POST.get("botao")).first()
    if not botao:
        return voltar
    if acao == "botao_editar":
        form = BotaoForm(request.POST, instance=botao)
        if form.is_valid():
            form.save()
            messages.success(request, "Botão salvo.")
        else:
            messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    elif acao == "botao_apagar":
        botao.delete()
        messages.info(request, "Botão apagado.")
    elif acao in ("botao_subir", "botao_descer"):
        lista = list(site.botoes.all())
        i = lista.index(botao)
        j = i - 1 if acao == "botao_subir" else i + 1
        if 0 <= j < len(lista):
            lista[i], lista[j] = lista[j], lista[i]
            for ordem, b in enumerate(lista, start=1):
                BotaoSite.objects.filter(pk=b.pk).update(ordem=ordem)
    return redirect("/meu-site/#botoes")


@conta_requerida
@require_POST
def categoria_produto(request, pk):
    """Troca a categoria de um produto da vitrine (a lista do editor chama aqui sem recarregar)."""
    site = get_object_or_404(SiteAfiliado, conta=conta_logada(request))
    produto = get_object_or_404(ProdutoSite, site=site, pk=pk)
    categoria = vitrine.escolher_categoria(site, produto, request.POST.get("categoria", ""))
    return JsonResponse({"ok": True, "categoria": categoria})
