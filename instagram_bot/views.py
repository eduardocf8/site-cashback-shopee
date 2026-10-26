import requests
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from accounts.cliques_anonimos import salvar_click_anonimo
from accounts.funil import exigir_login_ou_pagina_de_escolha, registrar_primeiro_link
from links.models import Click
from links.services import gerar_click
from links.shopee_client import ShopeeAPIError, ShopeeConfigError, SubIdInvalidoError

from cashback_shopee.meta_capi import enviar_evento, gerar_event_id

from . import aprovacao
from .models import RegistroPublicacao


def aprovar_publicacao(request, token):
    """Página que o link de aprovar/rejeitar do e-mail abre - só texto simples, já
    que é aberta uma vez só e não precisa de nenhuma interação além do clique."""
    _registro, mensagem = aprovacao.processar_decisao(token)
    return HttpResponse(mensagem, content_type="text/plain; charset=utf-8")


@exigir_login_ou_pagina_de_escolha("story")
def ir_para_story_de_oferta(request, registro_id):
    """Link enviado por DM pra quem responde um story de oferta (ver
    automacao_instagram/webhook.py, modo "link do produto") - mesmo fluxo de
    clique/cashback rastreado que ofertas/views.py::ir_para_oferta usa (login dá
    cashback de verdade; sem login, página de escolha e clique anônimo - ROADMAP
    13.11), reimplementado aqui em vez de importado de lá pra não criar uma
    dependência de ofertas -> instagram_bot (é o contrário hoje) nem reusar uma
    função "privada" (_ir_com_click_ou_erro) de outro app."""
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

    # Só via Conversions API - ver o mesmo comentário em
    # ofertas/views.py::_ir_com_click_ou_erro (redireciona direto pro link da Shopee,
    # sem página nossa pra disparar o Pixel do navegador).
    enviar_evento("GerouLinkCashback", request, gerar_event_id(), {"tipo_click": click.tipo})
    registrar_primeiro_link(request)
    resposta = redirect(click.link_gerado)
    if not request.user.is_authenticated:
        # Clique anônimo (ROADMAP 13.11) - guarda no navegador pra ligar à conta se a
        # pessoa se cadastrar dentro de 7 dias (ver accounts/cliques_anonimos.py).
        # Aqui em particular, o navegador costuma ser o in-app do Instagram - ver
        # aviso condicional em links/views.py::continuar_sem_cadastro.
        salvar_click_anonimo(request, resposta, click.id.hex)
    return resposta
