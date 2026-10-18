"""Tela do Bot de WhatsApp no painel (versão de teste: conectar pelo QR Code, ver
os grupos e mandar uma mensagem de teste). Quem fala com o WhatsApp é o worker -
aqui só se registram pedidos (ver bot_whatsapp/servico.py)."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bot_whatsapp import servico
from bot_whatsapp.models import ConexaoWhatsApp, EnvioWhatsApp, EventoWhatsApp

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto


def _liberado(conta) -> bool:
    return mod.estado(mod.POR_SLUG["whatsapp"], conta.modulos_liberados()) == "liberado"


def _bloqueado(request):
    item = {**mod.POR_SLUG["whatsapp"], "icone_path": mod.ICONES["whatsapp"]}
    return render(request, "painel/modulo.html", _contexto(request, "whatsapp", item=item, situacao="bloqueado"))


@conta_requerida
def whatsapp(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    conexao = servico.conexao_da(conta)
    return render(request, "painel/whatsapp.html", _contexto(
        request, "whatsapp",
        conexao=conexao,
        tela=servico.estado_para_tela(conta),
        envios=EnvioWhatsApp.objects.filter(conta=conta)[:8],
        eventos=EventoWhatsApp.objects.filter(conta=conta)[:15],
        ConexaoWhatsApp=ConexaoWhatsApp,
    ))


@conta_requerida
def whatsapp_estado(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return JsonResponse({"estado": "bloqueado"}, status=403)
    return JsonResponse(servico.estado_para_tela(conta))


def _so_liberado(view):
    def interna(request, *args, **kwargs):
        if not _liberado(conta_logada(request)):
            return redirect("painel_whatsapp")
        return view(request, *args, **kwargs)
    return interna


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_conectar(request):
    servico.pedir_conexao(conta_logada(request))
    return redirect("painel_whatsapp")


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_desconectar(request):
    servico.pedir_desconexao(conta_logada(request))
    messages.info(request, "Desconectando o WhatsApp… Em alguns segundos ele some da lista de aparelhos do celular.")
    return redirect("painel_whatsapp")


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_grupos(request):
    servico.pedir_grupos(conta_logada(request))
    return redirect("painel_whatsapp")


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_enviar(request):
    envio, motivo = servico.enfileirar_envio(
        conta_logada(request),
        destino=request.POST.get("destino", ""),
        texto=request.POST.get("texto", "")[:4000],
        imagem_url=request.POST.get("imagem_url", "").strip()[:1000],
    )
    if envio:
        messages.success(request, f"Mensagem na fila para “{envio.destino_nome}”. Ela sai em alguns segundos.")
    else:
        messages.error(request, motivo)
    return redirect("painel_whatsapp")
