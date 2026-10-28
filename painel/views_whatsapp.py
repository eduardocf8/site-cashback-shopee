"""Tela do Bot de WhatsApp no painel (versão de teste: conectar pelo QR Code, ver
os grupos e mandar uma mensagem de teste). Quem fala com o WhatsApp é o worker -
aqui só se registram pedidos (ver bot_whatsapp/servico.py)."""

import hashlib
import logging
from datetime import date, timedelta
from urllib.parse import quote

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from bot_whatsapp import alertas, campanhas, servico
from bot_whatsapp.models import (
    AlertaDisparado, AlertaPreco, CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, EventoWhatsApp,
    MensagemAvulsa, OfertaRecebida, ProdutoAcompanhado,
)
from bot_whatsapp.ofertas import grupos_do_plano, intervalo_do_plano, montar_texto, ofertas_enviadas_hoje, ritmo_com_muitos_grupos
from licencas import planos

from . import modulos as mod
from .autenticacao import conta_logada, conta_requerida
from .forms import AlertaPrecoForm, CampanhaBotForm, ConfiguracaoOfertasForm, MensagemAvulsaForm
from .views import _contexto

logger = logging.getLogger(__name__)


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
        form=form, config=config, historico=historico, recebidas=recebidas, conexao=conexao, regras=regras, regras_premium=planos.BOT[True],
        grupos_fora_do_plano=max(0, len(config.grupos or []) - regras["grupos"]),
        ritmo=ritmo_com_muitos_grupos(config, regras),
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
            messages.success(request, "Ligado em modo simulação: as ofertas aparecem aqui, mas nada vai pro WhatsApp.",
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
        messages.error(request, "Dê um nome pra data. Ex: Aniversário da loja.")
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
            messages.success(request, "Modo campanha salvo. Vale na hora pras próximas ofertas da campanha.")
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


# --- Alerta de preço ----------------------------------------------------------------

PRODUTOS_POR_PAGINA = 10

def _alerta(conta) -> AlertaPreco:
    alerta, _ = AlertaPreco.objects.get_or_create(conta=conta)
    return alerta


def _acao_do_alerta(request, conta, alerta, regras_da_conta):
    """As ações da tela (menos salvar): devolve para onde voltar."""
    acao = request.POST.get("acao")
    voltar = reverse("painel_whatsapp_alertas")
    if acao in ("ligar", "pausar"):
        if acao == "ligar" and not conta.shopee_validado_em:
            messages.error(request, "Conecte sua conta da Shopee em Configurações antes de ligar.")
            return voltar
        alerta.ativo = acao == "ligar"
        alerta.proxima_conferencia_em = timezone.now() if alerta.ativo else alerta.proxima_conferencia_em
        alerta.save(update_fields=["ativo", "proxima_conferencia_em", "atualizado_em"])
        messages.success(request, "Alerta de preço ligado. A primeira conferência sai em instantes." if alerta.ativo
                         else "Alerta de preço pausado.")
    elif acao == "conferir":
        if alerta.ultima_conferencia_em and timezone.now() - alerta.ultima_conferencia_em < alertas.CONFERIR_AGORA_A_CADA:
            messages.info(request, "Os preços acabaram de ser conferidos. Tente de novo em alguns minutos.")
        else:
            alerta.pedido_conferir_em = timezone.now()
            alerta.save(update_fields=["pedido_conferir_em", "atualizado_em"])
            messages.success(request, "Conferindo os preços agora. Recarregue a página em um minuto.")
    elif acao == "remover":
        ProdutoAcompanhado.objects.filter(conta=conta, pk=request.POST.get("produto")).delete()
        messages.info(request, "Produto removido do alerta.")
        pagina = request.POST.get("pagina", "")
        voltar += f"?pagina={pagina}#produtos" if pagina.isdigit() and pagina != "1" else "#produtos"
    elif acao in ("adicionar_links", "adicionar_item"):
        busca = request.POST.get("q", "").strip()[:120]
        voltar += f"?q={quote(busca)}#vitrine" if acao == "adicionar_item" and busca else "#produtos"
        if not conta.shopee_configurada:
            messages.error(request, "Conecte sua conta da Shopee em Configurações para adicionar produtos.")
            return voltar
        try:
            if acao == "adicionar_item":
                produto, novo = alertas.adicionar_item(conta, request.POST.get("item_id", "")[:40])
                if novo:
                    messages.success(request, f"“{produto.nome[:60]}” entrou no alerta.")
                else:
                    messages.info(request, "Esse produto já está no alerta.")
            else:
                r = alertas.adicionar_links(conta, request.POST.get("links", "")[:5000])
                partes = []
                if r["adicionados"]:
                    partes.append(f"{len(r['adicionados'])} produto{'s' if len(r['adicionados']) > 1 else ''} adicionado{'s' if len(r['adicionados']) > 1 else ''}")
                if r["ja_tinha"]:
                    partes.append(f"{len(r['ja_tinha'])} já estava{'m' if len(r['ja_tinha']) > 1 else ''} no alerta")
                if partes:
                    messages.success(request, ". ".join(partes).capitalize() + ".")
                if r["erros"]:
                    messages.error(request, f"Não achei {len(r['erros'])} produto{'s' if len(r['erros']) > 1 else ''} na Shopee: "
                                            "confira se o link abre o produto e se ele tem comissão de afiliado.")
        except alertas.LimiteDoPlano as erro:
            messages.error(request, str(erro))
        except Exception:  # noqa: BLE001
            logger.exception("Alerta de preço: erro ao adicionar")
            messages.error(request, "A Shopee não respondeu agora. Tente de novo em instantes.")
    return voltar


@conta_requerida
def whatsapp_alertas(request):
    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    alerta = _alerta(conta)
    regras_da_conta = alertas.regras(conta)
    conexao = servico.conexao_da(conta)
    salvar = request.method == "POST" and request.POST.get("acao", "salvar") == "salvar"
    form = AlertaPrecoForm(request.POST if salvar else None, instance=alerta, regras=regras_da_conta)
    if request.method == "POST":
        if not salvar:
            return redirect(_acao_do_alerta(request, conta, alerta, regras_da_conta))
        if form.is_valid():
            form.save()
            messages.success(request, "Alerta de preço salvo.")
            return redirect("painel_whatsapp_alertas")
        messages.error(request, "Confira os campos marcados.")

    busca = " ".join(request.GET.get("q", "").split())[:120]
    resultados = alertas.buscar_na_vitrine(conta, busca) if busca else []
    erro_busca = ""
    todos = ProdutoAcompanhado.objects.filter(conta=conta)
    total = todos.count()
    pagina = Paginator(todos, PRODUTOS_POR_PAGINA).get_page(request.GET.get("pagina"))
    acompanhados = set(todos.values_list("item_id", flat=True))
    do_bot = []
    for envio in EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.OFERTA).exclude(item_id="").exclude(
            item_id__startswith="link:").order_by("-id")[:200]:
        if envio.item_id not in {d["item_id"] for d in do_bot}:
            do_bot.append({"item_id": envio.item_id, "nome": envio.produto, "imagem": envio.imagem_url,
                           "acompanhado": envio.item_id in acompanhados})
        if len(do_bot) >= 8:
            break
    disparados = list(AlertaDisparado.objects.filter(conta=conta)[:20])
    AlertaDisparado.objects.filter(conta=conta, visto=False).update(visto=True)  # quem abriu a tela já viu
    exemplo = alertas.montar_mensagem(alerta.modelo_mensagem, EXEMPLO_DE_PRODUTO["nome"], 129.9, 99.9, 23.1,
                                      "https://s.shopee.com.br/seu-link")
    return render(request, "painel/whatsapp_alertas.html", _contexto(
        request, "whatsapp",
        alerta=alerta, form=form, regras=regras_da_conta, pagina=pagina, total=total,
        paginas=pagina.paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        limite=regras_da_conta["alerta_produtos"], cheio=total >= regras_da_conta["alerta_produtos"],
        grupos_da_automacao=grupos_do_plano(_config_ofertas(conta)),
        busca=busca, resultados=[{**r, "acompanhado": r["item_id"] in acompanhados} for r in resultados or []],
        erro_busca=erro_busca, do_bot=do_bot, disparados=disparados, exemplo=exemplo,
        intervalo=alertas.intervalo_efetivo(alerta, regras_da_conta),
        whatsapp_conectado=conexao.estado == ConexaoWhatsApp.CONECTADO,
        shopee_conectada=bool(conta.shopee_validado_em),
    ))


# --- Mensagens avulsas --------------------------------------------------------------

DISPAROS_NA_TELA = 15


def _nichos_em_uso(config) -> list[tuple[str, str]]:
    from bot_whatsapp.ofertas import nichos_do_plano

    if not config or not config.por_nicho:
        return []
    return [(nicho["id"], f"{nicho['nome']} ({len(grupos)} grupo{'s' if len(grupos) > 1 else ''})")
            for nicho, grupos in nichos_do_plano(config)]


def _grupos_por_nicho(config) -> dict[str, str]:
    """Os nomes dos grupos de cada nicho, pra mostrar embaixo da escolha do nicho."""
    from bot_whatsapp.ofertas import nichos_do_plano

    if not config or not config.por_nicho:
        return {}
    return {nicho["id"]: ", ".join(g.get("nome") or g["jid"] for g in grupos) for nicho, grupos in nichos_do_plano(config)}


def _disparos(conta) -> list[dict]:
    """As últimas mensagens que saíram (ou não): um item por disparo, com a situação em cada grupo."""
    envios = (EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.MENSAGEM)
              .order_by("-disparo_em", "id")[:DISPAROS_NA_TELA * 20])
    disparos: dict[tuple, dict] = {}
    for envio in envios:
        chave = (envio.mensagem_id, envio.disparo_em)
        item = disparos.setdefault(chave, {"em": envio.disparo_em, "texto": envio.texto, "envios": []})
        item["envios"].append(envio)
    lista = list(disparos.values())[:DISPAROS_NA_TELA]
    for item in lista:
        estados = [e.estado for e in item["envios"]]
        item["enviados"] = estados.count(EnvioWhatsApp.ENVIADO)
        item["na_fila"] = estados.count(EnvioWhatsApp.PENDENTE)
        item["erros"] = [e for e in item["envios"] if e.estado == EnvioWhatsApp.ERRO]
    return lista


@conta_requerida
def whatsapp_mensagens(request):
    from bot_whatsapp import mensagens

    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    regras = planos.bot(conta)
    conexao = servico.conexao_da(conta)
    config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
    editando = None
    pk = request.POST.get("pk") or request.GET.get("editar")
    if pk and str(pk).isdigit():
        editando = MensagemAvulsa.objects.filter(conta=conta, pk=pk).first()
    agendadas = MensagemAvulsa.objects.filter(conta=conta, proxima_em__isnull=False)
    acao = request.POST.get("acao", "") if request.method == "POST" else ""

    if acao in ("pausar", "retomar", "excluir") and editando:
        if acao == "excluir":
            editando.delete()
            messages.info(request, "Mensagem excluída.")
        else:
            editando.pausada = acao == "pausar"
            if not editando.pausada and editando.proxima_em and editando.proxima_em < timezone.now():
                # Ficou pausada e passou da hora: a semanal vai pra próxima; a agendada sai agora.
                editando.proxima_em = mensagens.calcular_proxima(editando, timezone.now()) or timezone.now()
            editando.save(update_fields=["pausada", "proxima_em", "atualizada_em"])
            messages.info(request, "Mensagem pausada." if editando.pausada else "Mensagem retomada.")
        return redirect("painel_whatsapp_mensagens")

    destinos = servico.destinos_possiveis(conexao)
    form = MensagemAvulsaForm(request.POST if acao == "salvar" else None, request.FILES if acao == "salvar" else None,
                              instance=editando or MensagemAvulsa(conta=conta), conta=conta, destinos=destinos,
                              nichos=_nichos_em_uso(config), regras=regras)
    if acao == "salvar":
        cheio = not editando and agendadas.count() >= regras["mensagens_agendadas"]
        if cheio:
            messages.error(request, f"Você já tem {regras['mensagens_agendadas']} mensagens agendadas, o máximo do seu "
                                    "plano. Exclua alguma para criar outra.")
        elif form.is_valid():
            mensagem = form.save()
            if not mensagens.destinos(mensagem, config, conexao):
                messages.warning(request, "Mensagem salva, mas ainda não tem nenhum grupo para receber: escolha os grupos "
                                          "na Automação ou marque “Escolher os grupos”.")
            elif mensagem.quando == MensagemAvulsa.QUANDO_AGORA:
                aviso = "" if conexao.estado == ConexaoWhatsApp.CONECTADO else (
                    " Seu WhatsApp está desconectado: ela sai assim que reconectar (em até 1 hora).")
                messages.success(request, "Mensagem enviada pra fila: sai em instantes." + aviso)
            else:
                messages.success(request, f"Mensagem agendada: {mensagens.descrever_quando(mensagem).lower()}.")
            return redirect("painel_whatsapp_mensagens")
        else:
            messages.error(request, "Confira os campos marcados.")

    lista = []
    for m in agendadas.order_by("pausada", "proxima_em"):
        grupos = mensagens.destinos(m, config, conexao)
        lista.append({"m": m, "quando": mensagens.descrever_quando(m), "total_grupos": len(grupos),
                      "pra_quem": {"todos": "Todos os grupos do bot", "nicho": f"Nicho: {m.nicho}",
                                   "grupos": "Grupos escolhidos"}.get(m.destino, "")})
    nomes_nicho = dict(_nichos_em_uso(config))
    for item in lista:
        if item["m"].destino == MensagemAvulsa.DESTINO_NICHO:
            item["pra_quem"] = "Nicho " + nomes_nicho.get(item["m"].nicho, "que não está mais em uso").split(" (")[0]
    return render(request, "painel/whatsapp_mensagens.html", _contexto(
        request, "whatsapp", form=form, editando=editando, agendadas=lista, disparos=_disparos(conta),
        conexao=conexao, regras=regras, maximo=regras["mensagens_agendadas"], grupos_por_nicho=_grupos_por_nicho(config),
        tem_grupos_no_bot=bool(config and config.grupos),
    ))


@conta_requerida
def whatsapp_mensagem_foto(request, pk):
    from django.http import Http404, HttpResponse

    foto = MensagemAvulsa.objects.filter(conta=conta_logada(request), pk=pk).values_list("foto", flat=True).first()
    if not foto:
        raise Http404
    return HttpResponse(bytes(foto), content_type="image/jpeg")


# --- Membros dos grupos -----------------------------------------------------------------

def _grafico_de_membros(serie: list[dict], desde) -> dict | None:
    """Linha dos membros somados nos últimos 30 dias (só dos dias desde que começou a monitorar)."""
    pontos = [p for p in serie if desde and p["dia"] >= timezone.localtime(desde).date()]
    if len(pontos) < 2:
        return None
    valores = [p["membros"] for p in pontos]
    menor, maior = min(valores), max(valores)
    faixa = (maior - menor) or 1
    largura, altura, margem = 600, 160, 8
    coordenadas = []
    for i, valor in enumerate(valores):
        x = round(margem + i * (largura - 2 * margem) / (len(valores) - 1), 1)
        y = round(altura - margem - (valor - menor) * (altura - 2 * margem) / faixa, 1)
        coordenadas.append(f"{x},{y}")
    return {"pontos": " ".join(coordenadas), "largura": largura, "altura": altura, "menor": menor, "maior": maior,
            "inicio": pontos[0]["dia"], "fim": pontos[-1]["dia"]}


GRUPOS_POR_PAGINA = 10
ORDENS_DE_MEMBROS = [
    ("membros", "Mais membros"), ("var_24h", "Mais cresceram em 24 h"), ("var_7d", "Mais cresceram em 7 dias"),
    ("perda_7d", "Mais perderam em 7 dias"), ("lotacao", "Mais cheios"), ("comissao", "Maior comissão do mês"),
    ("nome", "Nome (A a Z)"),
]


def _grupos_filtrados(linhas: list[dict], busca: str, ordem: str) -> list[dict]:
    """A busca pelo nome (sem acento e maiúscula) e a ordem escolhida. Quem não tem o número
    (ex: variação de 7 dias antes de completar 7 dias) vai pro fim."""
    import unicodedata

    def sem_acento(texto):
        return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()

    if busca:
        termo = sem_acento(busca)
        linhas = [linha for linha in linhas if termo in sem_acento(linha["grupo"].nome)]
    if ordem == "nome":
        return sorted(linhas, key=lambda linha: sem_acento(linha["grupo"].nome))
    campo, sinal = {"perda_7d": ("var_7d", 1)}.get(ordem, (ordem, -1))
    return sorted(linhas, key=lambda linha: (linha[campo] is None, sinal * (linha[campo] or 0)))


@conta_requerida
def whatsapp_membros(request):
    from urllib.parse import quote

    from bot_whatsapp import grupos_novos, membros
    from bot_whatsapp.models import GrupoMonitorado, PedidoGrupo

    conta = conta_logada(request)
    if not _liberado(conta):
        return _bloqueado(request)
    conexao = servico.conexao_da(conta)
    if request.method == "POST" and request.POST.get("acao") == "criar_grupo":
        pedido, motivo = grupos_novos.pedir(
            conta, request.POST.get("nome"), request.POST.get("base", ""), request.POST.get("copiar") == "on",
            request.POST.get("so_admins") == "on", request.POST.get("administradores", ""),
            request.POST.get("incluir") == "on",
        )
        if not pedido:
            messages.error(request, motivo)
            return redirect(reverse("painel_whatsapp_membros") + f"?criar={quote(request.POST.get('base', '') or '1')}#criar")
        messages.success(request, f"Criando o grupo “{pedido.nome}”. Em até 1 minuto ele aparece aqui com o link de convite.")
        return redirect(reverse("painel_whatsapp_membros") + "#criados")
    if request.method == "POST":
        jids = request.POST.getlist("grupos")
        if len(set(jids)) > membros.MAXIMO_GRUPOS:
            messages.error(request, f"Dá para acompanhar até {membros.MAXIMO_GRUPOS} grupos.")
            return redirect(reverse("painel_whatsapp_membros") + "?escolher=1")
        quantos = membros.escolher(conta, jids, conexao)
        if quantos:
            messages.success(request, f"Pronto! {quantos} grupo{'s' if quantos > 1 else ''} sendo acompanhado"
                                      f"{'s' if quantos > 1 else ''}. A primeira leitura sai em até 1 minuto.")
        else:
            messages.info(request, "Nenhum grupo sendo acompanhado.")
        return redirect("painel_whatsapp_membros")
    dados = membros.painel(conta)
    busca = str(request.GET.get("busca") or "").strip()[:80]
    ordens = [o for o in ORDENS_DE_MEMBROS if o[0] != "comissao" or dados["tem_comissao"]]
    ordem = request.GET.get("ordem") if request.GET.get("ordem") in dict(ordens) else "membros"
    pagina = Paginator(_grupos_filtrados(dados["linhas"], busca, ordem), GRUPOS_POR_PAGINA).get_page(request.GET.get("pagina"))
    escolhidos = set(GrupoMonitorado.objects.filter(conta=conta).values_list("jid", flat=True))
    criar = None
    if request.GET.get("criar"):
        nomes = {g.get("jid"): g.get("nome", "") for g in conexao.grupos or []}
        base = request.GET["criar"] if request.GET["criar"] in nomes else ""
        criar = {"base": base, "nome": grupos_novos.proximo_nome(nomes.get(base, ""), grupos_novos.nomes_em_uso(conta, conexao)) if base else "",
                 "admins": grupos_novos.ultimos_admins(conta), "feitos_hoje": grupos_novos.criados_hoje(conta),
                 "por_dia": grupos_novos.POR_DIA, "bases": sorted(membros.grupos_possiveis(conexao), key=lambda g: str(g.get("nome", "")).lower())}
    possiveis = sorted(membros.grupos_possiveis(conexao), key=lambda g: (g["jid"] not in escolhidos, str(g.get("nome", "")).lower()))
    return render(request, "painel/whatsapp_membros.html", _contexto(
        request, "whatsapp", conexao=conexao, dados=dados, possiveis=possiveis, escolhidos=escolhidos,
        escolhendo=(request.GET.get("escolher") == "1" or not dados["quantos"]) and not criar,
        grafico=_grafico_de_membros(dados["serie"], dados["monitorando_desde"]),
        limite_do_whatsapp=membros.LIMITE_DO_WHATSAPP,
        pagina=pagina, paginas=pagina.paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        busca=busca, ordem=ordem, ordens=ordens, por_pagina=GRUPOS_POR_PAGINA,
        criar=criar, pedidos=PedidoGrupo.objects.filter(conta=conta)[:5],
    ))
