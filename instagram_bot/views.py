import json

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from links.models import Click
from links.services import gerar_click
from links.shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

from . import aprovacao, webhook
from .models import RegistroPublicacao


def aprovar_publicacao(request, token):
    """Página que o link de aprovar/rejeitar do e-mail abre - só texto simples, já
    que é aberta uma vez só e não precisa de nenhuma interação além do clique."""
    _registro, mensagem = aprovacao.processar_decisao(token)
    return HttpResponse(mensagem, content_type="text/plain; charset=utf-8")


@csrf_exempt
def webhook_instagram(request):
    """Endpoint que recebe os eventos de mensagem da Meta (ver webhook.py) - GET é o
    handshake de verificação feito uma vez ao cadastrar a URL no painel da Meta; POST
    é cada entrega de evento de verdade (mensagem recebida). Sem @login_required nem
    proteção de CSRF de propósito: quem chama isso é a Meta, não um usuário logado -
    a segurança aqui é a assinatura X-Hub-Signature-256 (ver webhook.verificar_assinatura)."""
    if request.method == "GET":
        if (
            request.GET.get("hub.mode") == "subscribe"
            and settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
            and request.GET.get("hub.verify_token") == settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
        ):
            return HttpResponse(request.GET.get("hub.challenge", ""))
        return HttpResponseForbidden()

    if not webhook.verificar_assinatura(request.body, request.headers.get("X-Hub-Signature-256")):
        return HttpResponseForbidden()

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return HttpResponseBadRequest()

    webhook.processar_evento_webhook(payload, request)
    return HttpResponse("EVENT_RECEIVED")


@login_required
def ir_para_story_de_oferta(request, registro_id):
    """Link enviado por DM pra quem responde um story de oferta (ver webhook.py) -
    mesmo fluxo de clique/cashback rastreado que ofertas/views.py::ir_para_oferta usa
    (login exigido pra creditar o cashback à pessoa certa), reimplementado aqui em vez
    de importado de lá pra não criar uma dependência de ofertas -> instagram_bot (é o
    contrário hoje) nem reusar uma função "privada" (_ir_com_click_ou_erro) de outro app."""
    registro = get_object_or_404(RegistroPublicacao, pk=registro_id)
    if not registro.link_produto_original:
        messages.error(request, "Esse link não está mais disponível.")
        return redirect("home")

    try:
        click = gerar_click(
            request.user, Click.TIPO_STORY_DM, registro.link_produto_original,
            item_id_alvo=registro.oferta_item_id,
        )
    except ShopeeConfigError as erro:
        messages.error(request, str(erro))
        return redirect("home")
    except SubIdInvalidoError as erro:
        messages.error(request, str(erro))
        return redirect("home")
    except ShopeeAPIError as erro:
        messages.error(request, f"A Shopee recusou o pedido: {erro}")
        return redirect("home")
    except requests.RequestException:
        messages.error(request, "Não foi possível abrir essa oferta agora. Tenta de novo em instantes.")
        return redirect("home")

    return redirect(click.link_gerado)
