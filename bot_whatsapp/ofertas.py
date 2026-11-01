"""Motor das ofertas automáticas: roda numa thread do worker (junto com o
gerenciador do WhatsApp) e, para cada conta com as ofertas ligadas, a cada
"intervalo" escolhe o próximo produto da busca na Shopee que passa nos filtros e
ainda não foi para os grupos nos últimos N dias, gera o link de afiliado e põe a
mensagem (foto + texto) na fila de envio de cada grupo. Quem envia é o gerenciador.

Regras herdadas do app de Windows: busca paginada continuando de onde parou
(volta à página 1 depois de 3 h), filtros de número aplicados no resultado,
mesmo texto (formatador). Novidades do painel: dias da semana, limite por dia e
"não repetir por N dias" (no app era para sempre)."""

import copy
import logging
import threading
import time
from datetime import timedelta

from django.db import close_old_connections
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from licencas import planos
from painel import cripto

from . import campanhas, copia, ia, shopee_ofertas
from .formatador import formatar_texto_oferta
from .models import CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, OfertaRecebida

logger = logging.getLogger(__name__)

INTERVALO_MOTOR = 5  # segundos entre uma conferência e outra
VALIDADE_DA_RECEBIDA = timedelta(hours=1)  # modo copiar: oferta mais velha que isso não sai
PAGINAS_POR_VEZ = 5  # páginas de 50 produtos procuradas de uma vez atrás de um produto novo
RECOMECAR_BUSCA_APOS = timedelta(hours=3)
ESPERA_SEM_PRODUTO = timedelta(minutes=30)
ESPERA_APOS_ERRO = timedelta(minutes=5)
VALIDADE_DO_CACHE = 60 * 60  # segundos
OFERTAS_NO_TESTE = 5
OFERTAS_POR_NICHO_NO_TESTE = 3
LINK_DE_EXEMPLO = "https://s.shopee.com.br/seu-link"
MARCADOR_DO_LINK = "{{LINK_DE_AFILIADO}}"


def credenciais(conta) -> tuple[str, str]:
    return conta.shopee_app_id, cripto.decifrar(conta.shopee_secret_cifrado)


def dentro_do_horario(config, quando) -> bool:
    """quando = horário local. Janela que passa da meia-noite (ex: 20h às 2h) vale."""
    if quando.weekday() not in (config.dias_semana or []):
        return False
    inicio, fim, agora = config.horario_inicio, config.horario_fim, quando.time()
    if inicio == fim:
        return True
    if inicio < fim:
        return inicio <= agora < fim
    return agora >= inicio or agora < fim


def _que_contam(envios, simulacao: bool):
    """Envios que contam para o limite do dia e para não repetir. As simulações só
    contam enquanto a simulação está ligada - ao desligar, nada fica bloqueado por elas."""
    envios = envios.exclude(estado=EnvioWhatsApp.ERRO)
    return envios if simulacao else envios.exclude(estado=EnvioWhatsApp.SIMULADO)


def ofertas_enviadas_hoje(conta, agora, simulacao: bool = False) -> int:
    """Quantos produtos diferentes já saíram hoje (o mesmo produto em vários grupos
    conta uma vez)."""
    inicio_do_dia = timezone.localtime(agora).replace(hour=0, minute=0, second=0, microsecond=0)
    envios = EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.OFERTA, criado_em__gte=inicio_do_dia)
    return _que_contam(envios, simulacao).values("item_id").distinct().count()


def regras_do_plano(config) -> dict:
    """Limites do plano da conta (licencas/planos.py), guardados na config durante a volta."""
    if not hasattr(config, "_regras_do_plano"):
        from licencas.models import MODULO_WHATSAPP

        liberados = config.conta.modulos_liberados()
        config._regras_do_plano = {**planos.bot(liberados), "liberado": MODULO_WHATSAPP in liberados}
    return config._regras_do_plano


def grupos_do_plano(config) -> list[dict]:
    """Os grupos escolhidos, até o máximo do plano (se o plano diminuiu, valem os primeiros)."""
    return [g for g in config.grupos if g.get("jid")][: regras_do_plano(config)["grupos"]]


def grupos_no_limite_de_hoje(config, agora) -> set:
    """Grupos que já receberam hoje o máximo de ofertas por grupo do plano."""
    inicio_do_dia = timezone.localtime(agora).replace(hour=0, minute=0, second=0, microsecond=0)
    envios = _que_contam(EnvioWhatsApp.objects.filter(
        conta=config.conta, origem=EnvioWhatsApp.OFERTA, criado_em__gte=inicio_do_dia,
    ), config.simulacao)
    limite = regras_do_plano(config)["ofertas_por_grupo_dia"]
    return {destino for destino, total in envios.values_list("destino").annotate(total=Count("id")) if total >= limite}


def grupos_que_ainda_nao_receberam(config, item_id: str, agora, limite_do_dia: bool = True) -> list[dict]:
    desde = agora - timedelta(days=max(1, config.repetir_apos_dias))
    envios = EnvioWhatsApp.objects.filter(
        conta=config.conta, origem=EnvioWhatsApp.OFERTA, item_id=item_id, criado_em__gte=desde,
    )
    ja_receberam = set(_que_contam(envios, config.simulacao).values_list("destino", flat=True))
    cheios = grupos_no_limite_de_hoje(config, agora) if limite_do_dia else set()
    return [g for g in grupos_do_plano(config) if g["jid"] not in ja_receberam and g["jid"] not in cheios]


NICHO_TODOS = "todos"


def categorias_da_shopee() -> list[tuple[str, str]]:
    """As categorias principais da Shopee (id, nome), em ordem alfabética: são os nichos."""
    from ofertas.services import carregar_categorias_nivel1

    return sorted(((str(id_), nome) for id_, nome in carregar_categorias_nivel1().items()), key=lambda c: c[1])


def nome_do_nicho(nicho: str) -> str:
    if nicho == NICHO_TODOS:
        return "Todos"
    return dict(categorias_da_shopee()).get(nicho, nicho)


def nichos_do_plano(config) -> list[tuple[dict, list[dict]]]:
    """Envio por nicho: os nichos em uso ("todos" primeiro, depois as categorias em ordem
    alfabética), cada um com os seus grupos que cabem no plano. Grupo sem nicho = "todos"."""
    ordem = [NICHO_TODOS] + [id_ for id_, _ in categorias_da_shopee()]
    por_nicho: dict[str, list[dict]] = {}
    for grupo in grupos_do_plano(config):
        nicho = str((config.nichos or {}).get(grupo["jid"]) or NICHO_TODOS)
        por_nicho.setdefault(nicho if nicho in ordem else NICHO_TODOS, []).append(grupo)
    return [({"id": n, "nome": nome_do_nicho(n)}, por_nicho[n]) for n in ordem if n in por_nicho]


def config_do_nicho(config, nicho: dict, grupos: list[dict]):
    """Cópia da config, só na memória (nunca é salva), com a busca e os grupos do nicho: a
    categoria da Shopee dele (busca direto nela) ou, no "Todos", ofertas em geral. Filtros,
    mensagem, ritmo e IA continuam os da config."""
    do_nicho = copy.copy(config)
    do_nicho.tipo_busca = ConfiguracaoOfertas.BUSCA_GERAL
    do_nicho.palavra_chave, do_nicho.loja, do_nicho.categorias = "", "", []
    do_nicho.categoria_shopee = None if nicho["id"] == NICHO_TODOS else int(nicho["id"])
    do_nicho.grupos = grupos
    do_nicho.chave_do_cache = (config.conta_id, nicho["id"])
    onde_parou = (config.paginas_nichos or {}).get(nicho["id"]) or {}
    do_nicho.pagina_atual = int(onde_parou.get("pagina") or 1)
    do_nicho.pagina_em = parse_datetime(str(onde_parou.get("em") or ""))
    return do_nicho


# Uma mensagem por número a cada ~4 s: o gerenciador dá uma volta a cada 2 s e espera 3 s entre duas
# mensagens do mesmo número (gerenciador.INTERVALO e ESPACO_ENTRE_ENVIOS). Com 200 grupos, uma oferta
# leva uns 13 minutos para chegar em todos.
SEGUNDOS_POR_MENSAGEM = 4
# Com mais que isso na fila (uns 2 minutos de envio), a próxima oferta espera a fila andar.
LIMITE_DA_FILA = 30


def minutos_por_rodada(quantos_grupos: int) -> int:
    """Quanto tempo uma oferta leva para chegar em todos os grupos (arredondado pra cima)."""
    return -(-quantos_grupos * SEGUNDOS_POR_MENSAGEM // 60)


def ritmo_com_muitos_grupos(config, regras) -> dict | None:
    """Pra tela: com muitos grupos, quanto tempo cada oferta leva para chegar em todos e quantas
    cabem por dia em cada grupo no horário de envio. None quando são poucos grupos (não muda nada)."""
    grupos = min(len([g for g in config.grupos or [] if g.get("jid")]), regras["grupos"])
    rodada = minutos_por_rodada(grupos)
    if rodada < 2:
        return None
    inicio, fim = config.horario_inicio, config.horario_fim
    janela = (fim.hour * 60 + fim.minute) - (inicio.hour * 60 + inicio.minute)
    janela = 24 * 60 if janela == 0 else janela % (24 * 60)
    por_dia = janela // max(rodada, intervalo_do_plano(config) if config.modo != ConfiguracaoOfertas.MODO_COPIAR else 0, 1)
    return {"grupos": grupos, "minutos": rodada, "por_dia": min(por_dia, regras["ofertas_por_grupo_dia"]),
            "limitado": por_dia < regras["ofertas_por_grupo_dia"]}


def mensagens_na_fila(conta) -> int:
    """Mensagens desta conta que ainda não saíram (ofertas, página da campanha, avulsas)."""
    return EnvioWhatsApp.objects.filter(conta=conta, estado=EnvioWhatsApp.PENDENTE).count()


def intervalo_do_plano(config) -> int:
    """Minutos até a próxima oferta: o escolhido, mas nunca menos que o mínimo do plano
    (copiando de outros grupos, 0 = repassa assim que chegar)."""
    if config.modo == ConfiguracaoOfertas.MODO_COPIAR:
        return config.intervalo_minutos
    return max(1, config.intervalo_minutos, regras_do_plano(config)["intervalo_minimo"])


def motivo_para_esperar(config, conexao, agora) -> str:
    """"" = pode enviar agora; senão, o motivo (aparece no painel)."""
    if not regras_do_plano(config)["liberado"]:
        # Assinatura cancelada, reembolsada ou vencida: o bot para (o plano Standard não é de graça).
        return "O Bot de WhatsApp não está no seu plano. Renove a assinatura pras ofertas voltarem."
    app_id, secret = credenciais(config.conta)
    if not config.conta.shopee_validado_em or not app_id or not secret:
        return "Conecte sua conta da Shopee em Configurações."
    precisa_do_whatsapp = not config.simulacao or config.modo == ConfiguracaoOfertas.MODO_COPIAR
    if precisa_do_whatsapp and (not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO):
        # na simulação buscando na Shopee nada vai para o WhatsApp; copiando, ele precisa
        # estar conectado para receber as mensagens das origens
        return "Esperando o WhatsApp conectar."
    if not config.grupos:
        return "Escolha pelo menos um grupo."
    regras = regras_do_plano(config)
    if config.modo == ConfiguracaoOfertas.MODO_COPIAR and not regras["copiar"]:
        return "Copiar ofertas de outros grupos é do plano Premium. Troque pra busca na Shopee ou faça o upgrade."
    if config.por_nicho:
        if not regras["nicho"]:
            return "O envio por nicho é do plano Premium. Troque para “Mesmas ofertas para todos” ou faça o upgrade."
    escolhidos = {g["jid"] for g in grupos_do_plano(config)}
    if escolhidos and escolhidos <= grupos_no_limite_de_hoje(config, agora):
        return f"Todos os grupos já receberam as {regras['ofertas_por_grupo_dia']} ofertas de hoje (limite do plano por grupo)."
    if not dentro_do_horario(config, timezone.localtime(agora)):
        return "Fora do horário de envio."
    # Ritmo automático: com muitos grupos, a oferta anterior pode ainda estar saindo. A próxima
    # espera a fila esvaziar, senão a fila só cresceria (e o número mandaria mensagens sem parar).
    na_fila = mensagens_na_fila(config.conta)
    if na_fila > LIMITE_DA_FILA:
        return f"Enviando a oferta anterior: faltam {na_fila} mensage{'ns' if na_fila > 1 else 'm'}. A próxima sai depois."
    if config.limite_diario and ofertas_enviadas_hoje(config.conta, agora, config.simulacao) >= config.limite_diario:
        return "Limite de ofertas de hoje atingido."
    return ""


def aplicar_campanha(config, campanha, agora) -> dict | None:
    """Dia de campanha (bot_whatsapp/campanhas.py): troca, só na memória, os valores da
    Automação pelos da campanha. A config nunca é salva com eles: o motor só salva campos
    de controle (próxima vez, página da busca, status), sempre com update_fields.
    Devolve a data da campanha de hoje (ou None) e guarda em config.campanha_hoje."""
    hoje = campanhas.campanha_do_dia(campanha, timezone.localtime(agora).date())
    config.campanha_hoje, config.campanha = hoje, campanha if hoje else None
    if not hoje:
        return None
    if campanha.intervalo_minutos:
        config.intervalo_minutos = campanha.intervalo_minutos
    if campanha.limite_diario:
        config.limite_diario = campanha.limite_diario
    config.horario_inicio, config.horario_fim = campanha.horario_inicio, campanha.horario_fim
    config.dias_semana = list(range(7))  # a data vale mesmo num dia da semana desligado na Automação
    if campanha.palavra_chave.strip():
        config.tipo_busca, config.palavra_chave = ConfiguracaoOfertas.BUSCA_PALAVRA, campanha.palavra_chave.strip()
    if campanha.comissao_minima is not None:
        config.comissao_minima = campanha.comissao_minima
    if campanha.desconto_minimo is not None:
        config.desconto_minimo = campanha.desconto_minimo
    if campanha.mensagem_ativa and campanha.cupom.strip():
        config.cupom = campanha.cupom.strip()
    return hoje


def frase_da_campanha(config) -> str:
    campanha = getattr(config, "campanha", None)
    return campanha.frase_abertura if campanha and campanha.mensagem_ativa else ""


def montar_texto(produto: dict, link: str, cupom: str = "") -> str:
    return formatar_texto_oferta(shopee_ofertas.texto_base(produto, cupom), link)


CAMPOS_DA_IA = ["ia_dia", "ia_revisoes_no_dia", "ia_status"]


def revisar_com_ia(config, modelo: str, agora) -> tuple[str, bool]:
    """O texto revisado pela IA (se ligada e dentro do limite do dia) ou o original.
    Atualiza o status e a contagem na config (quem chama salva CAMPOS_DA_IA)."""
    if not config.ia_ativa or not regras_do_plano(config)["ia"]:  # a revisão com IA é do Premium
        return modelo, False
    hoje = timezone.localtime(agora).date()
    if config.ia_dia != hoje:
        config.ia_dia, config.ia_revisoes_no_dia = hoje, 0
    if config.ia_revisoes_no_dia >= ia.MAXIMO_POR_DIA:
        config.ia_status = f"Limite de {ia.MAXIMO_POR_DIA} revisões com IA de hoje atingido - foi o texto original."
        return modelo, False
    texto, revisado, config.ia_status = ia.revisar(modelo, config.ia_tipo, MARCADOR_DO_LINK)
    config.ia_revisoes_no_dia += 1
    return texto, revisado


def enfileirar(config, grupos, modelo: str, link_origem: str, *, item_id: str, nome: str,
               imagem_url: str = "", imagem_arquivo: str = "", revisado_ia: bool = False,
               produto: dict | None = None, origem: str = EnvioWhatsApp.OFERTA, formato: str = ""):
    """Põe a oferta na fila de cada grupo. O texto é o mesmo para todos; só o link
    muda quando um grupo tem Sub ID próprio (um link por combinação de Sub IDs). Com a
    simulação ligada, fica registrada como "Simulado" e não vai para o WhatsApp."""
    # Com a IA ligada e o texto original indo, guarda o motivo em cada envio.
    ia_motivo = config.ia_status[:300] if (config.ia_ativa and regras_do_plano(config)["ia"] and not revisado_ia) else ""
    app_id, secret = credenciais(config.conta)
    links: dict[tuple, str] = {}
    envios = []
    for grupo in grupos:
        sub_ids = tuple(config.lista_sub_ids(grupo["jid"]))
        if sub_ids not in links:
            links[sub_ids] = shopee_ofertas.gerar_link_afiliado(app_id, secret, link_origem, list(sub_ids), "bot")
        link = links[sub_ids]
        envios.append(EnvioWhatsApp(
            conta=config.conta, destino=grupo["jid"], destino_nome=grupo.get("nome", ""),
            texto=modelo.replace(MARCADOR_DO_LINK, link), imagem_url=(imagem_url or "")[:1000],
            imagem_arquivo=imagem_arquivo, origem=origem, item_id=item_id,
            produto=(nome or "")[:300], link_afiliado=link[:500], revisado_ia=revisado_ia, ia_motivo=ia_motivo,
            formato=formato or config.formato_envio,
            estado=EnvioWhatsApp.SIMULADO if config.simulacao else EnvioWhatsApp.PENDENTE,
        ))
    EnvioWhatsApp.objects.bulk_create(envios)
    if not config.simulacao and origem == EnvioWhatsApp.OFERTA:
        # Meu site com a vitrine "últimas ofertas do bot": a oferta entra no topo.
        from meusite.vitrine import registrar_do_bot

        registrar_do_bot(config.conta, produto)


class Motor:
    def __init__(self):
        # conta_id -> {"chave": chave da busca, "produtos": [...], "em": monotonic}
        self.cache: dict[int, dict] = {}

    def rodar(self):
        while True:
            close_old_connections()
            try:
                self.uma_volta()
            except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
                logger.exception("Ofertas: erro no motor")
            time.sleep(INTERVALO_MOTOR)

    def uma_volta(self, agora=None):
        agora = agora or timezone.now()
        self.atender_testes(agora)
        configs = list(ConfiguracaoOfertas.objects.filter(ativo=True).select_related("conta"))
        modos_campanha = {c.conta_id: c for c in CampanhaBot.objects.filter(
            ativo=True, conta_id__in=[config.conta_id for config in configs])}
        for config in configs:
            aplicar_campanha(config, modos_campanha.get(config.conta_id), agora)
            if config.proximo_envio_em and config.proximo_envio_em > agora and not self._campanha_antecipa(config, agora):
                continue
            try:
                self.enviar_proxima(config, agora)
            except Exception as erro:  # noqa: BLE001
                logger.exception("Ofertas: erro na conta %s", config.conta_id)
                config.ultimo_erro = str(erro)[:500]
                config.situacao = "Deu erro ao buscar a próxima oferta - tentando de novo em 5 minutos."
                config.proximo_envio_em = agora + ESPERA_APOS_ERRO
                config.save(update_fields=["ultimo_erro", "situacao", "proximo_envio_em", "atualizado_em"])

    @staticmethod
    def _campanha_antecipa(config, agora) -> bool:
        """No dia da campanha, o intervalo dela vale na hora: a próxima vez (marcada com o
        intervalo de antes) não precisa ser esperada se o da campanha já passou. Só depois de
        um envio normal: depois de um erro ou de "nenhuma oferta nova" (situação preenchida),
        a espera marcada vale, senão o motor buscaria na Shopee a cada volta."""
        return bool(config.campanha_hoje and config.ultimo_envio_em and not config.situacao
                    and config.ultimo_envio_em + timedelta(minutes=intervalo_do_plano(config)) <= agora)

    def talvez_enviar_pagina_da_campanha(self, config, agora, antes: int | None = None):
        """A cada N ofertas do dia de campanha, manda a página da campanha (com o link de
        afiliado de cada grupo). Um erro aqui não atrapalha as ofertas. antes = quantas
        tinham saído antes desta vez (por nicho saem várias de uma vez)."""
        campanha = getattr(config, "campanha", None)
        if not (campanha and campanha.pagina_ativa and campanha.link_campanha):
            return
        a_cada = max(3, campanha.link_campanha_a_cada or 10)
        agora_sao = ofertas_enviadas_hoje(config.conta, agora, config.simulacao)
        if antes is None:
            antes = agora_sao - 1
        if agora_sao // a_cada <= max(0, antes) // a_cada:
            return
        texto = campanhas.texto_da_pagina(config.campanha_hoje["nome"], campanha.titulo_pagina, campanha.texto_pagina,
                                         campanha.cupom, MARCADOR_DO_LINK)
        try:
            enfileirar(config, grupos_do_plano(config), texto, campanha.link_campanha, item_id="",
                       nome=f"Página da campanha: {config.campanha_hoje['nome']}", origem=EnvioWhatsApp.CAMPANHA,
                       formato=ConfiguracaoOfertas.FORMATO_PREVIA)
        except Exception:  # noqa: BLE001
            logger.warning("Ofertas: não deu para mandar a página da campanha da conta %s", config.conta_id, exc_info=True)

    # --- Envio -------------------------------------------------------------------

    def enviar_proxima(self, config, agora):
        conexao = ConexaoWhatsApp.objects.filter(conta=config.conta).first()
        motivo = motivo_para_esperar(config, conexao, agora)
        if motivo:
            if config.situacao != motivo:
                config.situacao = motivo
                config.save(update_fields=["situacao", "atualizado_em"])
            return

        if config.modo == ConfiguracaoOfertas.MODO_COPIAR:
            self.repassar_proxima(config, agora)
            return
        if config.por_nicho:
            self.enviar_por_nicho(config, agora)
            return

        produto, grupos = self.proximo_produto(config, agora)
        if not produto:
            if not self._reservar_a_vez(config, agora + ESPERA_SEM_PRODUTO):
                return  # outro processo mexeu na vez enquanto este buscava (ele já enfileirou algo)
            config.situacao = "Nenhuma oferta nova com esses filtros agora. Tento de novo em 30 minutos."
            config.save(update_fields=["situacao", "proximo_envio_em", "pagina_atual", "pagina_em", "atualizado_em"])
            return

        proximo = agora + timedelta(minutes=intervalo_do_plano(config))
        if not self._reservar_a_vez(config, proximo):
            return  # outro processo (ex: o worker antigo, num deploy) já pegou esta vez
        modelo, revisado = revisar_com_ia(config, montar_texto(produto, MARCADOR_DO_LINK, config.cupom), agora)
        modelo = campanhas.com_abertura(modelo, frase_da_campanha(config))  # depois da IA: a frase não muda
        enfileirar(
            config, grupos, modelo, produto["link"],
            item_id=produto["item_id"], nome=produto["nome"], imagem_url=produto["imagem"], revisado_ia=revisado,
            produto=produto,
        )
        self.talvez_enviar_pagina_da_campanha(config, agora)
        config.ultimo_envio_em = agora
        config.proximo_envio_em = proximo
        config.situacao = ""
        config.ultimo_erro = ""
        config.save(update_fields=[
            "ultimo_envio_em", "proximo_envio_em", "situacao", "ultimo_erro", "pagina_atual", "pagina_em",
            "atualizado_em", *CAMPOS_DA_IA,
        ])

    def enviar_por_nicho(self, config, agora):
        """Uma oferta por nicho a cada intervalo, cada uma para os grupos do seu nicho."""
        nichos = nichos_do_plano(config)
        restam = None
        antes = ofertas_enviadas_hoje(config.conta, agora, config.simulacao)
        if config.limite_diario:
            restam = config.limite_diario - antes
        escolhidas, paginas = [], {}
        for nicho, grupos in nichos:
            if restam is not None and len(escolhidas) >= restam:
                break
            do_nicho = config_do_nicho(config, nicho, grupos)
            produto, destinos = self.proximo_produto(do_nicho, agora)
            paginas[nicho["id"]] = {"pagina": do_nicho.pagina_atual,
                                    "em": do_nicho.pagina_em.isoformat() if do_nicho.pagina_em else ""}
            if produto:
                escolhidas.append((nicho, produto, destinos))
        # Guarda onde a busca de cada nicho parou (e esquece a dos nichos que ninguém usa mais).
        config.paginas_nichos = paginas
        if not escolhidas:
            if not self._reservar_a_vez(config, agora + ESPERA_SEM_PRODUTO):
                return
            config.situacao = "Nenhuma oferta nova nos nichos com esses filtros agora. Tento de novo em 30 minutos."
            config.save(update_fields=["situacao", "proximo_envio_em", "paginas_nichos", "atualizado_em"])
            return

        proximo = agora + timedelta(minutes=intervalo_do_plano(config))
        if not self._reservar_a_vez(config, proximo):
            return
        erros = []
        for nicho, produto, destinos in escolhidas:
            try:  # um nicho com problema (ex: link que não gerou) não segura os outros
                modelo, revisado = revisar_com_ia(config, montar_texto(produto, MARCADOR_DO_LINK, config.cupom), agora)
                modelo = campanhas.com_abertura(modelo, frase_da_campanha(config))
                enfileirar(
                    config, destinos, modelo, produto["link"],
                    item_id=produto["item_id"], nome=produto["nome"], imagem_url=produto["imagem"],
                    revisado_ia=revisado, produto=produto,
                )
            except Exception as erro:  # noqa: BLE001
                logger.exception("Ofertas: erro no nicho %s da conta %s", nicho.get("nome"), config.conta_id)
                erros.append(f"{nicho.get('nome') or 'nicho'}: {str(erro)[:200]}")
        if len(erros) == len(escolhidas):
            raise RuntimeError("; ".join(erros))
        self.talvez_enviar_pagina_da_campanha(config, agora, antes)
        config.ultimo_envio_em = agora
        config.situacao = ""
        config.ultimo_erro = "; ".join(erros)[:500]
        config.save(update_fields=[
            "ultimo_envio_em", "proximo_envio_em", "situacao", "ultimo_erro", "paginas_nichos",
            "atualizado_em", *CAMPOS_DA_IA,
        ])

    @staticmethod
    def _reservar_a_vez(config, proximo) -> bool:
        """Só um processo leva esta vez de enviar. Durante um deploy o worker antigo e o
        novo rodam juntos por um tempo e os dois enxergam "já passou da hora": sem isso,
        os dois montariam a mesma oferta. Vale quem conseguir trocar o horário da próxima
        vez (do valor que leu para o novo) primeiro."""
        mesma_vez = ConfiguracaoOfertas.objects.filter(pk=config.pk)
        if config.proximo_envio_em:
            mesma_vez = mesma_vez.filter(proximo_envio_em=config.proximo_envio_em)
        else:
            mesma_vez = mesma_vez.filter(proximo_envio_em__isnull=True)
        if not mesma_vez.update(proximo_envio_em=proximo):
            return False
        config.proximo_envio_em = proximo
        return True

    def repassar_proxima(self, config, agora):
        """Modo copiar: repassa a próxima mensagem que chegou nos grupos/canais de origem."""
        pendentes = OfertaRecebida.objects.filter(conta=config.conta, estado=OfertaRecebida.PENDENTE)
        pendentes.filter(recebida_em__lt=agora - VALIDADE_DA_RECEBIDA).update(
            estado=OfertaRecebida.IGNORADA, processada_em=agora,
            motivo="Chegou há mais de 1 hora (fora do horário, limite do dia ou fila cheia).",
        )
        recebida = pendentes.filter(processada_em__isnull=True).order_by("id").first()
        # Só um processo repassa esta mensagem (ver _reservar_a_vez): quem marcar primeiro.
        if recebida and not pendentes.filter(pk=recebida.pk, processada_em__isnull=True).update(processada_em=agora):
            return
        if not recebida:
            aguardando = "Esperando ofertas nos grupos e canais de origem."
            if config.situacao != aguardando:
                config.situacao = aguardando
                config.save(update_fields=["situacao", "atualizado_em"])
            return

        app_id, secret = credenciais(config.conta)
        try:
            oferta = copia.preparar(app_id, secret, recebida.texto)
            chave = copia.chave_do_produto(oferta["item_id"], oferta["link_origem"])
            produto = oferta["produto"] or {}
            nome = produto.get("nome") or recebida.texto.strip().splitlines()[0][:300]
            recebida.item_id, recebida.produto = chave, nome[:300]
            grupos = grupos_que_ainda_nao_receberam(config, chave, agora)
            if not grupos:
                self._fechar(recebida, OfertaRecebida.IGNORADA, agora,
                             f"Já foi para todos os grupos nos últimos {config.repetir_apos_dias} dias.")
                return
            modelo, revisado = revisar_com_ia(config, formatar_texto_oferta(oferta["texto_base"], MARCADOR_DO_LINK), agora)
            modelo = campanhas.com_abertura(modelo, frase_da_campanha(config))
            enfileirar(
                config, grupos, modelo, oferta["link_origem"],
                item_id=chave, nome=nome,
                imagem_url="" if recebida.imagem_arquivo else produto.get("imagem", ""),
                imagem_arquivo=recebida.imagem_arquivo, revisado_ia=revisado, produto=oferta["produto"],
            )
        except Exception as erro:  # noqa: BLE001 - uma mensagem ruim não trava a fila
            logger.exception("Ofertas: erro ao repassar a mensagem %s", recebida.pk)
            self._fechar(recebida, OfertaRecebida.ERRO, agora, str(erro))
            config.ultimo_erro = f"Não deu para repassar uma oferta: {str(erro)[:300]}"
            config.save(update_fields=["ultimo_erro", "atualizado_em"])
            return

        self._fechar(recebida, OfertaRecebida.ENVIADA, agora,
                     "Simulação: não foi enviada de verdade." if config.simulacao else "")
        self.talvez_enviar_pagina_da_campanha(config, agora)
        config.ultimo_envio_em = agora
        config.proximo_envio_em = agora + timedelta(minutes=intervalo_do_plano(config))
        config.situacao = ""
        config.ultimo_erro = ""
        config.save(update_fields=[
            "ultimo_envio_em", "proximo_envio_em", "situacao", "ultimo_erro", "atualizado_em", *CAMPOS_DA_IA,
        ])

    @staticmethod
    def _fechar(recebida, estado, agora, motivo):
        recebida.estado, recebida.motivo, recebida.processada_em = estado, motivo[:300], agora
        recebida.save(update_fields=["estado", "motivo", "processada_em", "item_id", "produto"])

    def proximo_produto(self, config, agora) -> tuple[dict | None, list[dict]]:
        """O próximo produto que passa nos filtros e ainda não foi para algum dos
        grupos, e para quais grupos ele vai."""
        chave_do_cache = getattr(config, "chave_do_cache", config.conta_id)  # por nicho: uma busca por nicho
        cache = self.cache.get(chave_do_cache)
        if (not cache or cache["chave"] != config.chave_da_busca()
                or time.monotonic() - cache["em"] > VALIDADE_DO_CACHE):
            busca_mudou = bool(cache) and cache["chave"] != config.chave_da_busca()  # ex: começou ou acabou a campanha
            cache = {"chave": config.chave_da_busca(), "produtos": [], "em": time.monotonic()}
            self.cache[chave_do_cache] = cache
            if busca_mudou or not config.pagina_em or agora - config.pagina_em > RECOMECAR_BUSCA_APOS:
                config.pagina_atual = 1

        app_id, secret = credenciais(config.conta)
        paginas_lidas = 0
        while True:
            while cache["produtos"]:
                produto = cache["produtos"].pop(0)
                grupos = grupos_que_ainda_nao_receberam(config, produto["item_id"], agora)
                if grupos:
                    return produto, grupos
            if paginas_lidas >= PAGINAS_POR_VEZ:
                return None, []
            produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, config, config.pagina_atual)
            paginas_lidas += 1
            cache["produtos"] = [p for p in produtos if shopee_ofertas.passa_nos_filtros(p, config)]
            config.pagina_atual = config.pagina_atual + 1 if tem_proxima else 1
            config.pagina_em = agora
            if not tem_proxima and not cache["produtos"]:
                return None, []  # acabou a lista e não sobrou nada novo

    # --- "Testar busca" -------------------------------------------------------------

    def atender_testes(self, agora):
        for config in ConfiguracaoOfertas.objects.filter(pedido_teste_em__isnull=False).select_related("conta"):
            if not config.testando:
                continue
            config.teste_resultado, config.teste_erro = [], ""
            try:
                config.teste_resultado = self.testar(config, agora)
            except Exception as erro:  # noqa: BLE001
                logger.exception("Ofertas: erro no teste da conta %s", config.conta_id)
                config.teste_erro = str(erro)[:500]
            config.teste_em = timezone.now()
            config.save(update_fields=["teste_resultado", "teste_erro", "teste_em", "atualizado_em", *CAMPOS_DA_IA])

    def testar(self, config, agora) -> list[dict]:
        """As próximas ofertas que sairiam com os filtros atuais (sem mexer na posição
        da busca e sem gerar link - o texto mostra um link de exemplo). Por nicho: as
        primeiras de cada nicho, cada uma marcada com o nome dele (um nicho sem oferta
        vira uma linha com o motivo)."""
        app_id, secret = credenciais(config.conta)
        if not app_id or not secret:
            raise ValueError("Conecte sua conta da Shopee em Configurações.")
        if not config.por_nicho:
            return self._testar_busca(config, agora, OFERTAS_NO_TESTE)
        if not regras_do_plano(config)["nicho"]:
            raise ValueError("O envio por nicho é do plano Premium. Troque para “Mesmas ofertas para todos” ou faça o upgrade.")
        nichos = nichos_do_plano(config)
        if not nichos:
            raise ValueError("Escolha pelo menos um grupo e salve antes de testar.")
        resultado = []
        for nicho, grupos in nichos:
            do_nicho = config_do_nicho(config, nicho, grupos)
            try:
                achadas = self._testar_busca(do_nicho, agora, OFERTAS_POR_NICHO_NO_TESTE, revisar=not resultado)
            except ValueError as erro:
                achadas = [{"erro": str(erro)}]
            finally:
                for campo in CAMPOS_DA_IA:  # a IA conta na config de verdade
                    setattr(config, campo, getattr(do_nicho, campo))
            resultado += [{**a, "nicho": nicho.get("nome", "")} for a in achadas]
        return resultado

    def _testar_busca(self, config, agora, quantas: int, revisar: bool = True) -> list[dict]:
        app_id, secret = credenciais(config.conta)
        achadas = []
        recebidos = barrados_pelos_filtros = ja_enviados = 0
        pagina = 1
        for _ in range(3):
            produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, config, pagina)
            recebidos += len(produtos)
            for produto in produtos:
                if not shopee_ofertas.passa_nos_filtros(produto, config):
                    barrados_pelos_filtros += 1
                    continue
                if config.grupos and not grupos_que_ainda_nao_receberam(config, produto["item_id"], agora, limite_do_dia=False):
                    ja_enviados += 1
                    continue
                texto, revisado = montar_texto(produto, MARCADOR_DO_LINK, config.cupom), False
                if not achadas and revisar:  # a IA revisa só a primeira, para mostrar como fica
                    texto, revisado = revisar_com_ia(config, texto, agora)
                achadas.append({
                    "nome": produto["nome"], "preco": produto["preco"], "comissao": produto["comissao"],
                    "desconto": produto["desconto"], "vendas": produto["vendas"], "avaliacao": produto["avaliacao"],
                    "imagem": produto["imagem"], "texto": texto.replace(MARCADOR_DO_LINK, LINK_DE_EXEMPLO),
                    "revisado_ia": revisado,
                    # o que a IA fez com a primeira (aparece embaixo dela no "Teste da busca")
                    "ia_status": config.ia_status if (config.ia_ativa and regras_do_plano(config)["ia"]
                                                      and not achadas and revisar) else "",
                })
                if len(achadas) >= quantas:
                    return achadas
            if not tem_proxima:
                break
            pagina += 1
        if not achadas:
            # O motivo aparece no painel no lugar da lista.
            if not recebidos:
                raise ValueError("A Shopee não devolveu nenhum produto para essa busca. Confira a palavra-chave ou a loja.")
            raise ValueError(
                f"A Shopee devolveu {recebidos} produtos, mas nenhum serve agora: {barrados_pelos_filtros} "
                f"barrados pelos filtros e {ja_enviados} já enviados para os grupos nos últimos "
                f"{config.repetir_apos_dias} dias. Tente afrouxar algum filtro."
            )
        return achadas


def iniciar_em_segundo_plano() -> Motor:
    motor = Motor()
    threading.Thread(target=motor.rodar, name="ofertas-motor", daemon=True).start()
    return motor
