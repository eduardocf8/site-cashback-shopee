"""Tela do Bot de WhatsApp no painel (versão de teste: conectar pelo QR Code, ver
os grupos e mandar uma mensagem de teste). Quem fala com o WhatsApp é o worker -
aqui só se registram pedidos (ver bot_whatsapp/servico.py)."""

import hashlib
from datetime import timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bot_whatsapp import servico
from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, EventoWhatsApp, OfertaRecebida
from bot_whatsapp.ofertas import ofertas_enviadas_hoje

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .forms import ConfiguracaoOfertasForm
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
        envios=EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.TESTE)[:8],
        destinos=servico.destinos_possiveis(conexao),
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
    voltar = request.POST.get("voltar", "")
    if voltar == reverse("painel_whatsapp_ofertas"):
        messages.info(request, "Buscando seus grupos e canais… Recarregue a página em alguns segundos.")
        return redirect(voltar)
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


# --- Ofertas automáticas (busca na Shopee) ---------------------------------------------

def _config_ofertas(conta) -> ConfiguracaoOfertas:
    config, _ = ConfiguracaoOfertas.objects.get_or_create(conta=conta)
    return config


def _resumo_ofertas(conta, config) -> dict:
    agora = timezone.now()
    conexao = servico.conexao_da(conta)
    return {
        "enviadas_hoje": ofertas_enviadas_hoje(conta, agora, config.simulacao),
        "whatsapp_conectado": conexao.estado == ConexaoWhatsApp.CONECTADO,
        "shopee_conectada": bool(conta.shopee_validado_em),
        "proximo_envio": config.proximo_envio_em if config.ativo and not config.situacao else None,
        "hoje_ymd": timezone.localtime(agora).strftime("%Y%m%d"),
    }


def _versao_da_tela(conta, config) -> str:
    """Resume o que aparece nos cartões ao vivo da tela de ofertas (status, recebidas e
    enviadas). Quando muda, a tela busca esses cartões de novo sem recarregar a página."""
    partes = [
        config.ativo, config.modo, config.simulacao, config.ia_status, config.situacao, config.ultimo_erro, config.testando,
        config.ultimo_envio_em, config.proximo_envio_em, config.limite_diario,
        servico.conexao_da(conta).estado, bool(conta.shopee_validado_em),
        timezone.localdate(),
    ]
    partes += EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.OFERTA).values_list("pk", "estado")[:20]
    partes += OfertaRecebida.objects.filter(conta=conta).values_list("pk", "estado")[:15]
    return hashlib.sha1(repr(partes).encode()).hexdigest()[:16]


@conta_requerida
def whatsapp_ofertas(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    config = _config_ofertas(conta)
    conexao = servico.conexao_da(conta)
    form = ConfiguracaoOfertasForm(request.POST or None, instance=config, grupos_disponiveis=conexao.grupos)
    if request.method == "POST":
        if form.is_valid():
            config = form.save()
            if "intervalo_minutos" in form.changed_data and config.ativo and config.ultimo_envio_em:
                # O intervalo novo já vale para a próxima oferta: conta a partir da última.
                config.proximo_envio_em = max(
                    timezone.now(), config.ultimo_envio_em + timedelta(minutes=config.intervalo_minutos),
                )
                config.save(update_fields=["proximo_envio_em", "atualizado_em"])
            messages.success(request, "Configurações das ofertas salvas.")
            return redirect("painel_whatsapp_ofertas")
        messages.error(request, "Confira os campos marcados.")
    historico = EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.OFERTA)[:20]
    recebidas = OfertaRecebida.objects.filter(conta=conta)[:15]
    return render(request, "painel/whatsapp_ofertas.html", _contexto(
        request, "whatsapp",
        form=form, config=config, historico=historico, recebidas=recebidas, conexao=conexao,
        versao=_versao_da_tela(conta, config),
        **_resumo_ofertas(conta, config),
    ))


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_ofertas_ligar(request):
    conta = conta_logada(request)
    config = _config_ofertas(conta)
    if not conta.shopee_validado_em:
        messages.error(request, "Conecte sua conta da Shopee em Configurações antes de ligar.")
    elif not config.grupos:
        messages.error(request, "Escolha pelo menos um grupo e salve antes de ligar.")
    elif config.modo == ConfiguracaoOfertas.MODO_COPIAR and not config.origens:
        messages.error(request, "Escolha de quais grupos ou canais copiar e salve antes de ligar.")
    else:
        config.ativo = True
        config.proximo_envio_em = timezone.now()
        config.situacao = ""
        config.save(update_fields=["ativo", "proximo_envio_em", "situacao", "atualizado_em"])
        if config.simulacao:
            messages.success(request, "Ligado em modo simulação: as ofertas aparecem aqui, mas nada vai para o WhatsApp.")
        else:
            messages.success(request, "Ofertas automáticas ligadas. A primeira sai em instantes, se estiver no horário.")
    return redirect("painel_whatsapp_ofertas")


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_ofertas_pausar(request):
    config = _config_ofertas(conta_logada(request))
    config.ativo = False
    config.save(update_fields=["ativo", "atualizado_em"])
    messages.info(request, "Ofertas automáticas pausadas.")
    return redirect("painel_whatsapp_ofertas")


@require_POST
@conta_requerida
@_so_liberado
def whatsapp_ofertas_testar(request):
    config = _config_ofertas(conta_logada(request))
    config.pedido_teste_em = timezone.now()
    config.save(update_fields=["pedido_teste_em", "atualizado_em"])
    return redirect(f"{reverse('painel_whatsapp_ofertas')}#teste")


@conta_requerida
def whatsapp_ofertas_estado(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return JsonResponse({}, status=403)
    config = _config_ofertas(conta)
    return JsonResponse({
        "testando": config.testando,
        "ativo": config.ativo,
        "situacao": config.situacao,
        "ultimo_envio": config.ultimo_envio_em.isoformat() if config.ultimo_envio_em else "",
        "versao": _versao_da_tela(conta, config),
    })
