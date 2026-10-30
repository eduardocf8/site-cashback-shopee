"""Aba "Link de entrada" do Bot de WhatsApp (bot_whatsapp/entrada.py). Em construção: só aparece
para contas com a chave beta_link_entrada ligada no admin."""

import re

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from bot_whatsapp import entrada, grupos_novos, membros
from bot_whatsapp.models import ConviteGrupo, LinkEntrada
from bot_whatsapp.servico import conexao_da
from meusite import cores
from meusite import entrada as pagina_publica
from meusite.forms import PADRAO_ENDERECO, CapaForm, FotoForm
from meusite.models import CORES, ENDERECOS_RESERVADOS, PEDACOS_RESERVADOS, SiteAfiliado

from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

MAXIMO_LINKS = 10


def _conta_com_beta(request):
    conta = conta_logada(request)
    if not entrada.liberado(conta):
        raise Http404
    return conta


def url_publica(site: SiteAfiliado | None, link: LinkEntrada) -> str:
    if not site or not site.endereco:
        return ""
    if settings.APPFILIADO_SITES_DOMINIO:
        return f"https://{site.endereco}.{settings.APPFILIADO_SITES_DOMINIO}/{link.slug}/"
    return reverse("site_pagina", kwargs={"endereco": site.endereco}) + f"{link.slug}/"


def _erro_do_endereco(endereco: str) -> str:
    if not PADRAO_ENDERECO.match(endereco) or "--" in endereco:
        return "Use de 3 a 40 letras minúsculas, números ou hífen (sem acento nem espaço)."
    if endereco in ENDERECOS_RESERVADOS or any(p in endereco for p in PEDACOS_RESERVADOS):
        return "Esse endereço é reservado. Escolha outro."
    if SiteAfiliado.objects.filter(endereco=endereco).exists():
        return "Esse endereço já está em uso. Escolha outro."
    return ""


@conta_requerida
def entrada_lista(request):
    conta = _conta_com_beta(request)
    site = SiteAfiliado.objects.filter(conta=conta).first()
    acao = request.POST.get("acao") if request.method == "POST" else ""
    if acao == "endereco" and not (site and site.endereco):
        endereco = str(request.POST.get("endereco") or "").strip().lower()
        erro = _erro_do_endereco(endereco)
        if erro:
            messages.error(request, erro)
        else:
            site = site or SiteAfiliado(conta=conta, publicado=False)
            site.endereco = endereco
            site.save()
            messages.success(request, "Endereço salvo.")
        return redirect("painel_whatsapp_entrada")
    if acao == "novo":
        if not (site and site.endereco):
            messages.error(request, "Escolha o endereço primeiro.")
        elif conta.links_entrada.count() >= MAXIMO_LINKS:
            messages.error(request, f"Dá para ter até {MAXIMO_LINKS} links de entrada.")
        else:
            base = "grupo-vip"
            slug, n = base, 1
            while conta.links_entrada.filter(slug=slug).exists():
                n += 1
                slug = f"{base}-{n}"
            link = LinkEntrada.objects.create(conta=conta, slug=slug)
            return redirect("painel_whatsapp_entrada_link", pk=link.pk)
        return redirect("painel_whatsapp_entrada")
    links = []
    for link in conta.links_entrada.defer("foto"):
        estado = entrada.situacao(link)
        links.append({"link": link, "url": url_publica(site, link), "estado": estado,
                      "numeros": entrada.estatisticas(link)})
    return render(request, "painel/whatsapp_entrada.html", _contexto(
        request, "whatsapp", site=site, links=links, maximo=MAXIMO_LINKS,
        dominio=settings.APPFILIADO_SITES_DOMINIO or "appfiliado.com.br",
    ))


COR_DO_SITE, OUTRA_COR = "", "outra"


def _ler_aparencia(dados, link) -> list[str]:
    """Modelo, cor, textos e blocos da página (o que a prévia ao vivo também usa). Muda o link
    na memória; quem salva é quem chamou. Devolve os erros."""
    erros = []
    modelos = dict(LinkEntrada.MODELOS)
    link.modelo = dados.get("modelo") if dados.get("modelo") in modelos else link.modelo
    cor = str(dados.get("cor") or "")
    if cor == OUTRA_COR:
        cor = str(dados.get("cor_outra") or "").strip().upper()
        if not cores.valida(cor):
            erros.append("Escolha a outra cor no seletor.")
            cor = link.cor
    elif cor and cor not in dict(CORES):
        cor = link.cor
    link.cor = cor
    link.titulo = " ".join(str(dados.get("titulo") or "").split())[:80]
    if not link.titulo:
        erros.append("Escreva o título da página.")
    link.frase = " ".join(str(dados.get("frase") or "").split())[:200]
    link.texto_botao = " ".join(str(dados.get("texto_botao") or "").split())[:40] or "Entrar no grupo"
    link.nome_exibido = " ".join(str(dados.get("nome_exibido") or "").split())[:60]
    link.beneficios = [t for t in (" ".join(str(b).split())[:80] for b in dados.getlist("beneficios")[:4]) if t]
    link.selos = [t for t in (" ".join(str(b).split())[:30] for b in dados.getlist("selos")[:3]) if t]
    for campo in ("mostrar_selos", "mostrar_total", "mostrar_vagas", "mostrar_ofertas", "mostrar_redes", "mostrar_capa"):
        setattr(link, campo, dados.get(campo) == "on")
    return erros


def _salvar(request, conta, link) -> list[str]:
    """Lê o formulário do link. Devolve os erros (vazio = salvou)."""
    erros = []
    dados = request.POST
    slug = str(dados.get("slug") or "").strip().lower()
    if not entrada.PADRAO_SLUG.match(slug) or "--" in slug:
        erros.append("O endereço do link usa só letras minúsculas, números e hífen (até 40).")
    elif slug in entrada.SLUGS_RESERVADOS:
        erros.append("Esse endereço é usado por outra página do seu site. Escolha outro.")
    elif conta.links_entrada.filter(slug=slug).exclude(pk=link.pk).exists():
        erros.append("Você já tem um link com esse endereço.")
    pixel = re.sub(r"\D", "", str(dados.get("pixel_id") or ""))
    if dados.get("pixel_id", "").strip() and not 5 <= len(pixel) <= 20:
        erros.append("O ID do pixel do Meta é só números (em Gerenciador de Eventos > Fontes de dados).")
    try:
        limite = int(dados.get("limite_por_grupo") or 1000)
    except ValueError:
        limite = 0
    if not 50 <= limite <= membros.LIMITE_DO_WHATSAPP:
        erros.append(f"O limite por grupo vai de 50 a {membros.LIMITE_DO_WHATSAPP} pessoas.")
    admins, invalidos = grupos_novos.ler_numeros(dados.get("admins_dos_novos", ""))
    if invalidos:
        erros.append(f"Não entendi {', '.join(invalidos)} nos administradores. Use DDD e número, como (11) 98888-7777.")
    erros += _ler_aparencia(dados, link)
    if erros:
        link.refresh_from_db()  # nada fica pela metade
        return erros
    link.slug, link.pixel_id, link.limite_por_grupo = slug, pixel, limite
    link.redirecionar = dados.get("redirecionar") == "on"
    link.ativo = dados.get("ativo") == "on"
    link.criar_sozinho = dados.get("criar_sozinho") == "on"
    link.admins_dos_novos = admins[: grupos_novos.MAXIMO_ADMINS]
    link.save()
    entrada.salvar_grupos(link, dados.getlist("grupos"), conexao_da(conta))
    return []


def _trocar_foto(request, link, acao) -> None:
    """Foto própria do link (mesmo recorte do Meu site; sem ela, a página usa a foto do Meu site)
    e a capa (2 por 1; sem ela, a capa usa fotos das ofertas)."""
    if acao in ("capa", "remover_capa"):
        _trocar_capa(request, link, acao)
        return
    if acao == "remover_foto":
        link.foto, link.foto_versao = None, link.foto_versao + 1
        link.save(update_fields=["foto", "foto_versao", "atualizado_em"])
        messages.success(request, "A página voltou a usar a foto do Meu site.")
        return
    form = FotoForm(request.POST, request.FILES)
    if form.is_valid():
        link.foto, link.foto_versao = form.cleaned_data["foto"], link.foto_versao + 1
        link.save(update_fields=["foto", "foto_versao", "atualizado_em"])
        messages.success(request, "Foto trocada.")
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros)
                       or "Não consegui abrir essa imagem. Use JPG ou PNG.")


def _trocar_capa(request, link, acao) -> None:
    if acao == "remover_capa":
        link.capa, link.capa_versao = None, link.capa_versao + 1
        link.save(update_fields=["capa", "capa_versao", "atualizado_em"])
        messages.success(request, "Capa tirada. Com a capa ligada, ela usa fotos das ofertas.")
        return
    form = CapaForm(request.POST, request.FILES)
    if form.is_valid():
        link.capa, link.capa_versao, link.mostrar_capa = form.cleaned_data["foto"], link.capa_versao + 1, True
        link.save(update_fields=["capa", "capa_versao", "mostrar_capa", "atualizado_em"])
        messages.success(request, "Capa trocada.")
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros)
                       or "Não consegui abrir essa imagem. Use JPG ou PNG.")


@conta_requerida
def entrada_capa(request, pk):
    conta = _conta_com_beta(request)
    link = get_object_or_404(LinkEntrada, pk=pk, conta=conta)
    if not link.capa:
        raise Http404
    return HttpResponse(bytes(link.capa), content_type="image/jpeg")


@conta_requerida
@xframe_options_sameorigin
def entrada_previa(request, pk):
    """A página do link como fica, para a prévia ao vivo do painel. Com os campos do formulário
    na URL, mostra o que a pessoa está editando (sem salvar)."""
    conta = _conta_com_beta(request)
    link = get_object_or_404(LinkEntrada, pk=pk, conta=conta)
    site = SiteAfiliado.objects.filter(conta=conta).first() or SiteAfiliado(conta=conta)
    if "modelo" in request.GET:
        _ler_aparencia(request.GET, link)
        link.titulo = link.titulo or "Título da página"
    base = reverse("painel_whatsapp_entrada_link", args=[link.pk])
    return render(request, "meusite/entrada.html", pagina_publica.montar(
        link, site, previa=True, foto_url=f"{base}foto.jpg?v={link.foto_versao}-{site.foto_versao}",
        capa_url=f"{base}capa.jpg?v={link.capa_versao}"))


@conta_requerida
def entrada_foto(request, pk):
    """A foto que a página do link mostra (a dele ou a do Meu site), para a prévia no painel."""
    conta = _conta_com_beta(request)
    link = get_object_or_404(LinkEntrada, pk=pk, conta=conta)
    site = SiteAfiliado.objects.filter(conta=conta).first()
    foto = link.foto or (site.foto if site else None)
    if not foto:
        raise Http404
    return HttpResponse(bytes(foto), content_type="image/jpeg")


@conta_requerida
def entrada_link(request, pk):
    conta = _conta_com_beta(request)
    link = get_object_or_404(LinkEntrada, pk=pk, conta=conta)
    site = SiteAfiliado.objects.filter(conta=conta).first()
    conexao = conexao_da(conta)
    erros = []
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "excluir":
            link.delete()
            messages.info(request, "Link de entrada excluído.")
            return redirect("painel_whatsapp_entrada")
        if acao == "convite":
            jid, texto = request.POST.get("jid", ""), str(request.POST.get("convite") or "").strip()
            convite = ConviteGrupo.objects.filter(conta=conta, jid=jid, jid__in=link.grupos).first()
            if convite and texto and not texto.startswith("https://chat.whatsapp.com/"):
                messages.error(request, "Cole o link de convite do grupo, que começa com https://chat.whatsapp.com/")
            elif convite:
                convite.link, convite.manual, convite.erro = texto, bool(texto), ""
                convite.lido_em = None if not texto else convite.lido_em
                convite.save()
                messages.success(request, "Link de convite salvo." if texto else "O Appfiliado volta a ler o link sozinho.")
            return redirect(reverse("painel_whatsapp_entrada_link", args=[link.pk]) + "#grupos-do-link")
        if acao in ("foto", "remover_foto", "capa", "remover_capa"):
            _trocar_foto(request, link, acao)
            return redirect(reverse("painel_whatsapp_entrada_link", args=[link.pk]) + "#titulo-pagina")
        erros = _salvar(request, conta, link)
        if not erros:
            messages.success(request, "Link de entrada salvo.")
            return redirect("painel_whatsapp_entrada_link", pk=link.pk)
        for erro in erros:
            messages.error(request, erro)
    possiveis = sorted(membros.grupos_possiveis(conexao), key=lambda g: entrada.ordem_natural(str(g.get("nome", ""))))
    estado = entrada.situacao(link)
    return render(request, "painel/whatsapp_entrada_link.html", _contexto(
        request, "whatsapp", link=link, site=site, url=url_publica(site, link), estado=estado,
        numeros=entrada.estatisticas(link), possiveis=possiveis, escolhidos=set(link.grupos),
        admins=", ".join(grupos_novos._telefone(n) for n in link.admins_dos_novos or []),
        nomes={g["jid"]: g["nome"] for g in estado["grupos"]}, folga=entrada.FOLGA,
        limite_do_whatsapp=membros.LIMITE_DO_WHATSAPP, conexao=conexao,
        cores=CORES, cor_do_site=(site.cor if site else "") or "#E8541E", modelos=LinkEntrada.MODELOS,
        cor_outra=link.cor if link.cor and link.cor not in dict(CORES) else "",
        beneficios=(link.beneficios + [""] * 4)[:4], selos=(link.selos + [""] * 3)[:3],
        url_previa=reverse("painel_whatsapp_entrada_previa", args=[link.pk]),
    ))
