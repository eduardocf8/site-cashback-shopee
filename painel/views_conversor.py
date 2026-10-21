"""Tela do Conversor de links (todos os planos)."""

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bot_whatsapp import servico
from bot_whatsapp.models import ConexaoWhatsApp

from . import conversor
from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

CONVERSOES_POR_HORA = 60


def _bot(conta) -> dict:
    """Grupos para o botão "Enviar no grupo" (só com o bot liberado e conectado)."""
    if mod.estado(mod.POR_SLUG["whatsapp"], conta.modulos_liberados()) != "liberado":
        return {"liberado": False, "destinos": []}
    conexao = servico.conexao_da(conta)
    conectado = conexao.estado == ConexaoWhatsApp.CONECTADO
    return {"liberado": True, "conectado": conectado, "destinos": servico.destinos_possiveis(conexao) if conectado else []}


def _passou_do_limite(conta) -> bool:
    chave = f"conversor:{conta.pk}"
    cache.add(chave, 0, 3600)
    try:
        return cache.incr(chave) > CONVERSOES_POR_HORA
    except ValueError:  # a chave expirou entre o add e o incr
        cache.set(chave, 1, 3600)
        return False


@conta_requerida
def conversor_view(request):
    conta = conta_logada(request)
    dados = {
        "texto": "",
        "modo": request.session.get("conversor_modo", conversor.MODO_TEXTO),
        "sub_id": request.session.get("conversor_sub_id", ""),
    }
    resultado = None
    if request.method == "POST":
        dados = {
            "texto": request.POST.get("texto", "")[: conversor.MAXIMO_CARACTERES + 1],
            "modo": request.POST.get("modo") if request.POST.get("modo") in dict(conversor.MODOS) else conversor.MODO_TEXTO,
            "sub_id": request.POST.get("sub_id", "").strip()[:100],
        }
        request.session["conversor_modo"] = dados["modo"]
        request.session["conversor_sub_id"] = dados["sub_id"]
        if _passou_do_limite(conta):
            messages.error(request, f"Você já fez {CONVERSOES_POR_HORA} conversões nesta hora. Tente de novo daqui a pouco.")
        else:
            try:
                resultado = conversor.converter(conta, dados["texto"], dados["modo"], dados["sub_id"])
            except conversor.ErroConversor as erro:
                messages.error(request, str(erro))
    return render(request, "painel/conversor.html", _contexto(
        request, "conversor",
        dados=dados,
        modos=conversor.MODOS,
        resultado=resultado,
        maximo_links=conversor.MAXIMO_LINKS,
        sub_id_padrao=conversor.SUB_ID_PADRAO,
        shopee_conectada=conta.shopee_configurada,
        bot=_bot(conta),
    ))


@require_POST
@conta_requerida
def conversor_enviar(request):
    conta = conta_logada(request)
    if not _bot(conta)["liberado"]:
        return redirect("painel_conversor")
    envio, motivo = servico.enfileirar_envio(
        conta, destino=request.POST.get("destino", ""), texto=request.POST.get("texto", "")[:4000],
    )
    if envio:
        messages.success(request, f"Mensagem na fila para “{envio.destino_nome}”. Ela sai em alguns segundos.")
    else:
        messages.error(request, motivo)
    return redirect("painel_conversor")
