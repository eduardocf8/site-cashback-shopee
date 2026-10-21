"""Tela do Bot de WhatsApp no painel (versão de teste: conectar pelo QR Code, ver
os grupos e mandar uma mensagem de teste). Quem fala com o WhatsApp é o worker -
aqui só se registram pedidos (ver bot_whatsapp/servico.py)."""

import hashlib
from datetime import date, timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bot_whatsapp import campanhas, servico
from bot_whatsapp.models import CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, EventoWhatsApp, OfertaRecebida
from bot_whatsapp.ofertas import intervalo_do_plano, montar_texto, ofertas_enviadas_hoje
from licencas import planos

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .forms import CampanhaBotForm, ConfiguracaoOfertasForm
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
        formato=_config_ofertas(conta_logada(request)).formato_envio,  # o teste sai como as ofertas
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
        "campanha_hoje": campanhas.campanha_do_dia(CampanhaBot.objects.filter(conta=conta).first(), timezone.localdate()),
    }


ULTIMAS_OFERTAS = 10  # quantas aparecem em "Últimas ofertas enviadas"


def _versao_da_tela(conta, config) -> str:
    """Resume o que aparece nos cartões ao vivo da tela de ofertas (status, recebidas e
    enviadas). Quando muda, a tela busca esses cartões de novo sem recarregar a página."""
    partes = [
        config.ativo, config.modo, config.simulacao, config.ia_status, config.situacao, config.ultimo_erro, config.testando,
        config.ultimo_envio_em, config.proximo_envio_em, config.limite_diario,
        servico.conexao_da(conta).estado, bool(conta.shopee_validado_em),
        timezone.localdate(),
    ]
    partes += EnvioWhatsApp.objects.filter(
        conta=conta, origem__in=[EnvioWhatsApp.OFERTA, EnvioWhatsApp.CAMPANHA]).values_list("pk", "estado")[:ULTIMAS_OFERTAS]
    partes += OfertaRecebida.objects.filter(conta=conta).values_list("pk", "estado")[:15]
    return hashlib.sha1(repr(partes).encode()).hexdigest()[:16]


@conta_requerida
def whatsapp_ofertas(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    config = _config_ofertas(conta)
    conexao = servico.conexao_da(conta)
    regras = planos.bot(conta)
    form = ConfiguracaoOfertasForm(request.POST or None, instance=config, grupos_disponiveis=conexao.grupos, regras=regras)
    if request.method == "POST":
        if form.is_valid():
            config = form.save()
            if "intervalo_minutos" in form.changed_data and config.ativo and config.ultimo_envio_em:
                # O intervalo novo já vale para a próxima oferta: conta a partir da última.
                config.proximo_envio_em = max(
                    timezone.now(), config.ultimo_envio_em + timedelta(minutes=intervalo_do_plano(config)),
                )
                config.save(update_fields=["proximo_envio_em", "atualizado_em"])
            messages.success(request, "Configurações das ofertas salvas.")
            return redirect("painel_whatsapp_ofertas")
        messages.error(request, "Confira os campos marcados.")
    historico = EnvioWhatsApp.objects.filter(
        conta=conta, origem__in=[EnvioWhatsApp.OFERTA, EnvioWhatsApp.CAMPANHA])[:ULTIMAS_OFERTAS]
    recebidas = OfertaRecebida.objects.filter(conta=conta)[:15]
    return render(request, "painel/whatsapp_ofertas.html", _contexto(
        request, "whatsapp",
        form=form, config=config, historico=historico, recebidas=recebidas, conexao=conexao, regras=regras,
        grupos_fora_do_plano=max(0, len(config.grupos or []) - regras["grupos"]),
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
        # Somem sozinhas quando a primeira oferta sair (ofertas.js).
        if config.simulacao:
            messages.success(request, "Ligado em modo simulação: as ofertas aparecem aqui, mas nada vai para o WhatsApp.",
                             extra_tags="some-ao-enviar")
        else:
            messages.success(request, "Ofertas automáticas ligadas. A primeira sai em instantes.", extra_tags="some-ao-enviar")
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


# --- Modo campanha ------------------------------------------------------------------

MAXIMO_DATAS_PROPRIAS = 20
EXEMPLO_DE_PRODUTO = {"nome": "Fone Bluetooth com cancelamento de ruído", "vendas": "10mil", "desconto": 62,
                      "avaliacao": 4.8, "preco": 49.9}


def _campanha(conta) -> CampanhaBot:
    campanha, _ = CampanhaBot.objects.get_or_create(conta=conta)
    return campanha


def _previa(campanha, config) -> str:
    """Uma oferta de exemplo como sai no dia da campanha."""
    if not campanha.mensagem_ativa:
        return montar_texto(EXEMPLO_DE_PRODUTO, "https://s.shopee.com.br/seu-link", config.cupom)
    texto = montar_texto(EXEMPLO_DE_PRODUTO, "https://s.shopee.com.br/seu-link", campanha.cupom or config.cupom)
    return campanhas.com_abertura(texto, campanha.frase_abertura)


def _previa_da_pagina(campanha, proxima) -> str:
    nome = proxima["nome"] if proxima else "11.11"
    return campanhas.texto_da_pagina(nome, campanha.titulo_pagina, campanha.texto_pagina, campanha.cupom,
                                     "https://s.shopee.com.br/sua-pagina")


def _adicionar_data(request, campanha, hoje) -> None:
    nome = " ".join(request.POST.get("nome", "").split())[:60]
    try:
        dia = date.fromisoformat(request.POST.get("data", ""))
    except ValueError:
        messages.error(request, "Escolha o dia da data.")
        return
    if not nome:
        messages.error(request, "Dê um nome para a data. Ex: Aniversário da loja.")
    elif dia < hoje or dia > hoje + timedelta(days=365):
        messages.error(request, "Escolha um dia entre hoje e os próximos 12 meses.")
    elif len(campanha.datas_proprias or []) >= MAXIMO_DATAS_PROPRIAS:
        messages.error(request, f"Dá para ter até {MAXIMO_DATAS_PROPRIAS} datas próprias.")
    else:
        anual = request.POST.get("anual") == "1"
        proprias = [p for p in campanha.datas_proprias or [] if p.get("data") != dia.isoformat()]
        proprias.append({"data": dia.isoformat(), "nome": nome, "anual": anual})
        campanha.datas_proprias = sorted(proprias, key=lambda p: p["data"])
        campanha.save(update_fields=["datas_proprias", "atualizado_em"])
        messages.success(request, f"“{nome}” incluída em {dia:%d/%m}.")


def _marcar_data(request, campanha, hoje):
    """Liga ou desliga uma data da Shopee na hora (a tela chama ao marcar a caixa)."""
    chave = request.POST.get("chave", "")
    datas = {d["chave"]: d["nome"] for d in campanhas.datas_do_ano(hoje.year)}
    if chave not in datas:
        return JsonResponse({"erro": "Data desconhecida."}, status=400)
    ligada = request.POST.get("ligada") == "1"
    atuais = [c for c in campanha.datas_ligadas or [] if c != chave]
    campanha.datas_ligadas = atuais + [chave] if ligada else atuais
    campanha.save(update_fields=["datas_ligadas", "atualizado_em"])
    proxima = campanhas.proxima_ligada(campanha, hoje)
    return JsonResponse({
        "texto": f"{datas[chave]} {'ligada' if ligada else 'desligada'} no modo campanha.",
        "proxima": f"{proxima['nome']}, {proxima['data']:%d/%m} ({campanhas.quando(proxima['faltam'])})" if proxima else "",
    })


@conta_requerida
def whatsapp_campanhas(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    campanha = _campanha(conta)
    config = _config_ofertas(conta)
    hoje = timezone.localdate()
    vigentes = campanhas.sem_datas_passadas(campanha.datas_proprias, hoje)
    if vigentes != (campanha.datas_proprias or []):  # as que já passaram somem sozinhas
        campanha.datas_proprias = vigentes
        campanha.save(update_fields=["datas_proprias", "atualizado_em"])
    regras = planos.bot(conta)
    datas = campanhas.proximas_datas(campanha, hoje)
    acao = request.POST.get("acao", "salvar")
    form = CampanhaBotForm(request.POST if request.method == "POST" and acao == "salvar" else None, instance=campanha, datas=datas, regras=regras)
    if request.method == "POST":
        if acao in ("ligar", "desligar"):
            campanha.ativo = acao == "ligar"
            campanha.save(update_fields=["ativo", "atualizado_em"])
            messages.success(request, "Modo campanha ligado." if campanha.ativo else "Modo campanha desligado.")
            return redirect("painel_whatsapp_campanhas")
        if acao == "marcar_data":
            return _marcar_data(request, campanha, hoje)
        if acao == "adicionar_data":
            _adicionar_data(request, campanha, hoje)
            return redirect(f"{reverse('painel_whatsapp_campanhas')}#datas")
        if acao == "remover_data":
            campanha.datas_proprias = [p for p in campanha.datas_proprias or [] if p.get("data") != request.POST.get("data")]
            campanha.save(update_fields=["datas_proprias", "atualizado_em"])
            messages.info(request, "Data removida.")
            return redirect(f"{reverse('painel_whatsapp_campanhas')}#datas")
        if form.is_valid():
            form.save()
            messages.success(request, "Modo campanha salvo. Vale na hora para as próximas ofertas da campanha.")
            return redirect("painel_whatsapp_campanhas")
        messages.error(request, "Confira os campos marcados.")
    hoje_campanha = campanhas.campanha_do_dia(campanha, hoje)
    proxima = campanhas.proxima_ligada(campanha, hoje)
    return render(request, "painel/whatsapp_campanhas.html", _contexto(
        request, "whatsapp",
        campanha=campanha, config=config, form=form, regras=regras,
        datas=campanhas.proximas_datas(campanha, hoje),
        hoje_campanha=hoje_campanha, proxima=proxima,
        quando=campanhas.quando(proxima["faltam"]) if proxima else "",
        previa=_previa(campanha, config),
        previa_pagina=_previa_da_pagina(campanha, hoje_campanha or proxima),
    ))
