"""Gerador de carrosséis no painel: a lista, o "cole o link" e o editor. A geração e as
regras do que pode ser salvo estão em carrosseis/servicos.py."""

import io
import json

from django import forms
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from carrosseis import servicos
from carrosseis.models import Carrossel

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

MAXIMO_JSON = 300_000  # bytes de um salvamento (um roteiro tem uns poucos KB)
FOTO_LADO, FOTO_MAXIMO_MB = 1080, 8


def _bloqueio(request, conta):
    item = mod.POR_SLUG["carrosseis"]
    situacao = mod.estado(item, conta.modulos_liberados())
    if situacao == "liberado":
        return None
    return render(request, "painel/modulo.html", _contexto(
        request, "carrosseis", item={**item, "icone_path": mod.ICONES["carrosseis"]}, situacao=situacao))


def _do_dono(request, pk):
    return get_object_or_404(Carrossel, pk=pk, conta=conta_logada(request))


def _json(request) -> dict:
    if len(request.body) > MAXIMO_JSON:
        raise ValueError("Conteúdo grande demais.")
    dados = json.loads(request.body or b"{}")
    if not isinstance(dados, dict):
        raise ValueError("Formato inválido.")
    return dados


@conta_requerida
def carrosseis(request):
    conta = conta_logada(request)
    bloqueio = _bloqueio(request, conta)
    if bloqueio:
        return bloqueio
    if request.method == "POST":
        try:
            carrossel = servicos.criar(conta, request.POST.get("link", ""))
        except servicos.ErroGerador as erro:
            messages.error(request, str(erro))
            return redirect("painel_carrosseis")
        return redirect("painel_carrossel", pk=carrossel.pk)
    lista = Carrossel.objects.filter(conta=conta).defer("foto_propria", "recorte")[:60]
    return render(request, "painel/carrosseis.html", _contexto(
        request, "carrosseis", carrosseis=lista, restantes=servicos.restantes(conta),
        premium=servicos.eh_premium(conta), shopee_ok=conta.shopee_configurada,
    ))


@conta_requerida
def carrossel(request, pk):
    conta = conta_logada(request)
    bloqueio = _bloqueio(request, conta)
    if bloqueio:
        return bloqueio
    c = _do_dono(request, pk)
    premium = servicos.eh_premium(conta)
    dados = {
        "id": c.pk, "produto": c.produto, "roteiros": c.roteiros, "originais": c.originais,
        "opcoes": servicos.limpar_opcoes(c.opcoes, premium), "legenda": c.legenda, "hashtags": c.hashtags,
        "premium": premium, "restantes": servicos.restantes(conta),
        "fotoPropria": reverse("painel_carrossel_foto", args=[c.pk]) + f"?v={int(c.atualizado_em.timestamp())}" if c.foto_propria else "",
        "recorte": reverse("painel_carrossel_recorte", args=[c.pk]) + f"?v={int(c.atualizado_em.timestamp())}" if c.recorte else "",
        "urls": {
            "salvar": reverse("painel_carrossel_salvar", args=[c.pk]),
            "reescrever": reverse("painel_carrossel_reescrever", args=[c.pk]),
            "foto": reverse("painel_carrossel_foto", args=[c.pk]),
            "recorte": reverse("painel_carrossel_recorte", args=[c.pk]),
            "padrao": reverse("painel_carrossel_padrao"),
        },
    }
    return render(request, "painel/carrossel_editor.html", _contexto(request, "carrosseis", c=c, dados=dados, premium=premium))


@require_POST
@conta_requerida
def salvar(request, pk):
    c = _do_dono(request, pk)
    if _bloqueio(request, c.conta):
        return JsonResponse({"erro": "O gerador de carrosséis não está no seu plano."}, status=403)
    try:
        servicos.salvar(c, _json(request))
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"ok": True})


@require_POST
@conta_requerida
def reescrever(request, pk):
    c = _do_dono(request, pk)
    try:
        dados = _json(request)
        slide = servicos.reescrever_slide(c, dados.get("slide"), dados.get("familia"))
    except (ValueError, servicos.ErroGerador) as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"slide": slide, "restantes": servicos.restantes(c.conta)})


@require_POST
@conta_requerida
def padrao(request):
    conta = conta_logada(request)
    if not servicos.eh_premium(conta):
        return JsonResponse({"erro": "Salvar um padrão é do plano Premium."}, status=403)
    try:
        servicos.salvar_padrao(conta, _json(request).get("opcoes"))
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=400)
    return JsonResponse({"ok": True})


class FotoForm(forms.Form):
    foto = forms.ImageField()

    def clean_foto(self):
        from PIL import Image, ImageOps

        arquivo = self.cleaned_data["foto"]
        if arquivo.size > FOTO_MAXIMO_MB * 1024 * 1024:
            raise forms.ValidationError(f"A foto pode ter até {FOTO_MAXIMO_MB} MB.")
        aberta = Image.open(arquivo)
        if aberta.size[0] * aberta.size[1] > 30_000_000:  # "bomba" de pixels: estoura a memória ao abrir
            raise forms.ValidationError("Essa foto é grande demais. Use uma de até 30 megapixels.")
        imagem = ImageOps.exif_transpose(aberta).convert("RGB")
        imagem.thumbnail((FOTO_LADO, FOTO_LADO), Image.LANCZOS)
        saida = io.BytesIO()
        imagem.save(saida, "JPEG", quality=86, optimize=True)
        return saida.getvalue()


@conta_requerida
def foto(request, pk):
    """GET: a foto própria (mesmo endereço do painel, então o desenho no navegador pode
    exportar o PNG). POST: troca (premium). POST com remover=1: volta para a da Shopee."""
    c = get_object_or_404(Carrossel, pk=pk, conta=conta_logada(request))
    if request.method == "POST":
        if not servicos.eh_premium(c.conta):
            return JsonResponse({"erro": "Trocar a foto é do plano Premium."}, status=403)
        if request.POST.get("remover"):
            c.foto_propria = None
        else:
            form = FotoForm(request.POST, request.FILES)
            if not form.is_valid():
                erro = " ".join(e for erros in form.errors.values() for e in erros) or "Não consegui abrir essa imagem."
                return JsonResponse({"erro": erro}, status=400)
            c.foto_propria = form.cleaned_data["foto"]
        c.recorte = None  # o recorte era da foto anterior
        c.save(update_fields=["foto_propria", "recorte", "atualizado_em"])
        url = reverse("painel_carrossel_foto", args=[c.pk]) + f"?v={int(c.atualizado_em.timestamp())}" if c.foto_propria else ""
        return JsonResponse({"url": url})
    if not c.foto_propria:
        return HttpResponse(status=404)
    resposta = HttpResponse(bytes(c.foto_propria), content_type="image/jpeg")
    resposta["Cache-Control"] = "private, max-age=86400"
    return resposta


@require_POST
@conta_requerida
def apagar(request, pk):
    _do_dono(request, pk).delete()
    messages.info(request, "Carrossel apagado.")
    return redirect("painel_carrosseis")


RECORTE_MAXIMO_MB, RECORTE_LADO = 4, 1400


class RecorteForm(forms.Form):
    recorte = forms.ImageField()

    def clean_recorte(self):
        """PNG com transparência, feito no navegador. Reabre e regrava aqui: tira metadados e garante o formato."""
        from PIL import Image

        arquivo = self.cleaned_data["recorte"]
        if arquivo.size > RECORTE_MAXIMO_MB * 1024 * 1024:
            raise forms.ValidationError(f"O recorte pode ter até {RECORTE_MAXIMO_MB} MB.")
        aberta = Image.open(arquivo)
        if aberta.format != "PNG" or "A" not in aberta.getbands():
            raise forms.ValidationError("O recorte precisa ser um PNG com fundo transparente.")
        if aberta.size[0] * aberta.size[1] > 12_000_000:
            raise forms.ValidationError("O recorte é grande demais.")
        imagem = aberta.convert("RGBA")
        imagem.thumbnail((RECORTE_LADO, RECORTE_LADO), Image.LANCZOS)
        saida = io.BytesIO()
        imagem.save(saida, "PNG", optimize=True)
        return saida.getvalue()


@conta_requerida
def recorte(request, pk):
    """GET: o produto sem fundo (PNG). POST: guarda o que o navegador gerou (premium). POST com remover=1: apaga."""
    c = get_object_or_404(Carrossel, pk=pk, conta=conta_logada(request))
    if request.method == "POST":
        if not servicos.eh_premium(c.conta):
            return JsonResponse({"erro": "Remover o fundo da foto é do plano Premium."}, status=403)
        if request.POST.get("remover"):
            c.recorte = None
        else:
            form = RecorteForm(request.POST, request.FILES)
            if not form.is_valid():
                erro = " ".join(e for erros in form.errors.values() for e in erros) or "Não consegui abrir esse recorte."
                return JsonResponse({"erro": erro}, status=400)
            c.recorte = form.cleaned_data["recorte"]
        c.save(update_fields=["recorte", "atualizado_em"])
        url = reverse("painel_carrossel_recorte", args=[c.pk]) + f"?v={int(c.atualizado_em.timestamp())}" if c.recorte else ""
        return JsonResponse({"url": url})
    if not c.recorte:
        return HttpResponse(status=404)
    resposta = HttpResponse(bytes(c.recorte), content_type="image/png")
    resposta["Cache-Control"] = "private, max-age=86400"
    return resposta
