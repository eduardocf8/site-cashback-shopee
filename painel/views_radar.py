"""Tela do Radar de ofertas (todos os planos). Os botões de cada produto dependem do
plano: copiar o link de afiliado (todos), mandar no grupo e acompanhar o preço (Bot de
WhatsApp) e gerar carrossel (Carrosséis). Fora do plano, o botão vem com cadeado."""

import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bot_whatsapp import alertas, servico, shopee_ofertas
from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp
from licencas.models import MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM, MODULO_WHATSAPP
from ofertas.services import eh_host_da_shopee

from . import radar
from .autenticacao import conta_logada, conta_requerida
from .views import _contexto

logger = logging.getLogger(__name__)


def _voltar(request) -> str:
    """Volta para a mesma busca do radar (só caminhos do próprio radar)."""
    voltar = request.POST.get("voltar", "")
    return voltar if voltar.startswith("/radar/") and "//" not in voltar else reverse("painel_radar")


def _liberados(conta) -> dict:
    liberados = set(conta.modulos_liberados())
    return {"bot": MODULO_WHATSAPP in liberados,
            "carrosseis": bool({MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM} & liberados)}


@conta_requerida
def radar_view(request):
    conta = conta_logada(request)
    filtros = radar.filtros_da_requisicao(request.GET)
    try:
        pagina = max(1, min(int(request.GET.get("pagina", 1)), radar.MAXIMO_PAGINAS))
    except ValueError:
        pagina = 1
    produtos, tem_proxima, erro = [], False, ""
    if conta.shopee_configurada:
        try:
            produtos, tem_proxima = radar.buscar(conta, filtros, pagina)
        except Exception:  # noqa: BLE001
            logger.warning("Radar: busca falhou", exc_info=True)
            erro = "A Shopee não respondeu agora. Tente de novo em instantes."
    pode = _liberados(conta)
    destinos = []
    if pode["bot"]:
        conexao = servico.conexao_da(conta)
        if conexao.estado == ConexaoWhatsApp.CONECTADO:
            destinos = servico.destinos_possiveis(conexao)
    from bot_whatsapp.categorias import opcoes_categoria

    return render(request, "painel/radar.html", _contexto(
        request, "radar",
        filtros=filtros, ordens=radar.ORDENS, categorias=opcoes_categoria(), produtos=produtos,
        pagina=pagina, tem_proxima=tem_proxima, erro=erro, pode=pode, destinos=destinos,
        acompanhados=set(conta.produtos_acompanhados.values_list("item_id", flat=True)) if pode["bot"] else set(),
        shopee_conectada=conta.shopee_configurada, aqui=request.get_full_path(),
    ))


@require_POST
@conta_requerida
def radar_link(request):
    """O link de afiliado de um produto (Sub ID "radar"), para o botão "Copiar link"."""
    conta = conta_logada(request)
    link = request.POST.get("link", "").strip()[:1000]
    if not conta.shopee_configurada or not eh_host_da_shopee(link):
        return JsonResponse({"erro": "Link inválido."}, status=400)
    from bot_whatsapp.ofertas import credenciais

    try:
        app_id, secret = credenciais(conta)
        return JsonResponse({"link": shopee_ofertas.gerar_link_afiliado(app_id, secret, link, [radar.SUB_ID])})
    except Exception:  # noqa: BLE001
        logger.warning("Radar: link de afiliado falhou", exc_info=True)
        return JsonResponse({"erro": "A Shopee não gerou o link agora. Tente de novo."}, status=502)


@require_POST
@conta_requerida
def radar_enviar(request):
    """Manda um produto num grupo pelo bot (mesmo texto e Sub IDs das ofertas automáticas)."""
    from bot_whatsapp.ofertas import MARCADOR_DO_LINK, enfileirar, montar_texto

    conta = conta_logada(request)
    if not _liberados(conta)["bot"]:
        return redirect(_voltar(request))
    conexao = servico.conexao_da(conta)
    grupo = next((g for g in servico.destinos_possiveis(conexao) if g.get("jid") == request.POST.get("destino")), None)
    if conexao.estado != ConexaoWhatsApp.CONECTADO or not grupo:
        messages.error(request, "Conecte o WhatsApp e escolha um dos seus grupos.")
        return redirect(_voltar(request))
    try:
        produto = alertas.produto_da_shopee(conta, request.POST.get("item_id", "")[:40])
        if not produto:
            raise ValueError("A Shopee não devolveu esse produto agora.")
        config, _ = ConfiguracaoOfertas.objects.get_or_create(conta=conta)
        enfileirar(config, [grupo], montar_texto(produto, MARCADOR_DO_LINK, config.cupom), produto["link"],
                   item_id=produto["item_id"], nome=produto["nome"], imagem_url=produto["imagem"], produto=produto,
                   origem=EnvioWhatsApp.OFERTA)
        estado = "simulada (o modo simulação está ligado)" if config.simulacao else "na fila. Sai em alguns segundos"
        messages.success(request, f"Oferta para “{grupo.get('nome', 'o grupo')}” {estado}.")
    except Exception as erro:  # noqa: BLE001
        logger.warning("Radar: envio para o grupo falhou", exc_info=True)
        messages.error(request, str(erro) if isinstance(erro, ValueError) else "Não deu para mandar agora. Tente de novo.")
    return redirect(_voltar(request))


@require_POST
@conta_requerida
def radar_acompanhar(request):
    conta = conta_logada(request)
    if not _liberados(conta)["bot"]:
        return redirect(_voltar(request))
    try:
        produto, novo = alertas.adicionar_item(conta, request.POST.get("item_id", "")[:40])
        if novo:
            messages.success(request, f"“{produto.nome[:60]}” entrou no alerta de preço.")
        else:
            messages.info(request, "Esse produto já está no alerta de preço.")
    except alertas.LimiteDoPlano as erro:
        messages.error(request, str(erro))
    except Exception:  # noqa: BLE001
        logger.warning("Radar: acompanhar falhou", exc_info=True)
        messages.error(request, "A Shopee não respondeu agora. Tente de novo em instantes.")
    return redirect(_voltar(request))
