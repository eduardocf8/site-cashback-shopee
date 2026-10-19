"""Motor das ofertas automáticas: roda numa thread do worker (junto com o
gerenciador do WhatsApp) e, para cada conta com as ofertas ligadas, a cada
"intervalo" escolhe o próximo produto da busca na Shopee que passa nos filtros e
ainda não foi para os grupos nos últimos N dias, gera o link de afiliado e põe a
mensagem (foto + texto) na fila de envio de cada grupo. Quem envia é o gerenciador.

Regras herdadas do app de Windows: busca paginada continuando de onde parou
(volta à página 1 depois de 3 h), filtros de número aplicados no resultado,
mesmo texto (formatador). Novidades do painel: dias da semana, limite por dia e
"não repetir por N dias" (no app era para sempre)."""

import logging
import threading
import time
from datetime import timedelta

from django.db import close_old_connections
from django.utils import timezone

from painel import cripto

from . import copia, ia, shopee_ofertas
from .formatador import formatar_texto_oferta
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, OfertaRecebida

logger = logging.getLogger(__name__)

INTERVALO_MOTOR = 5  # segundos entre uma conferência e outra
VALIDADE_DA_RECEBIDA = timedelta(hours=1)  # modo copiar: oferta mais velha que isso não sai
PAGINAS_POR_VEZ = 5  # páginas de 50 produtos procuradas de uma vez atrás de um produto novo
RECOMECAR_BUSCA_APOS = timedelta(hours=3)
ESPERA_SEM_PRODUTO = timedelta(minutes=30)
ESPERA_APOS_ERRO = timedelta(minutes=5)
VALIDADE_DO_CACHE = 60 * 60  # segundos
OFERTAS_NO_TESTE = 5
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


def grupos_que_ainda_nao_receberam(config, item_id: str, agora) -> list[dict]:
    desde = agora - timedelta(days=max(1, config.repetir_apos_dias))
    envios = EnvioWhatsApp.objects.filter(
        conta=config.conta, origem=EnvioWhatsApp.OFERTA, item_id=item_id, criado_em__gte=desde,
    )
    ja_receberam = set(_que_contam(envios, config.simulacao).values_list("destino", flat=True))
    return [g for g in config.grupos if g.get("jid") and g["jid"] not in ja_receberam]


def motivo_para_esperar(config, conexao, agora) -> str:
    """"" = pode enviar agora; senão, o motivo (aparece no painel)."""
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
    if not dentro_do_horario(config, timezone.localtime(agora)):
        return "Fora do horário de envio."
    if config.limite_diario and ofertas_enviadas_hoje(config.conta, agora, config.simulacao) >= config.limite_diario:
        return "Limite de ofertas de hoje atingido."
    return ""


def montar_texto(produto: dict, link: str, cupom: str = "") -> str:
    return formatar_texto_oferta(shopee_ofertas.texto_base(produto, cupom), link)


CAMPOS_DA_IA = ["ia_dia", "ia_revisoes_no_dia", "ia_status"]


def revisar_com_ia(config, modelo: str, agora) -> tuple[str, bool]:
    """O texto revisado pela IA (se ligada e dentro do limite do dia) ou o original.
    Atualiza o status e a contagem na config (quem chama salva CAMPOS_DA_IA)."""
    if not config.ia_ativa:
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
               produto: dict | None = None):
    # Com a IA ligada e o texto original indo, guarda o motivo em cada envio.
    ia_motivo = config.ia_status[:300] if (config.ia_ativa and not revisado_ia) else ""
    """Põe a oferta na fila de cada grupo. O texto é o mesmo para todos; só o link
    muda quando um grupo tem Sub ID próprio (um link por combinação de Sub IDs). Com a
    simulação ligada, fica registrada como "Simulado" e não vai para o WhatsApp."""
    app_id, secret = credenciais(config.conta)
    links: dict[tuple, str] = {}
    envios = []
    for grupo in grupos:
        sub_ids = tuple(config.lista_sub_ids(grupo["jid"]))
        if sub_ids not in links:
            links[sub_ids] = shopee_ofertas.gerar_link_afiliado(app_id, secret, link_origem, list(sub_ids))
        link = links[sub_ids]
        envios.append(EnvioWhatsApp(
            conta=config.conta, destino=grupo["jid"], destino_nome=grupo.get("nome", ""),
            texto=modelo.replace(MARCADOR_DO_LINK, link), imagem_url=(imagem_url or "")[:1000],
            imagem_arquivo=imagem_arquivo, origem=EnvioWhatsApp.OFERTA, item_id=item_id,
            produto=(nome or "")[:300], link_afiliado=link[:500], revisado_ia=revisado_ia, ia_motivo=ia_motivo,
            formato=config.formato_envio,
            estado=EnvioWhatsApp.SIMULADO if config.simulacao else EnvioWhatsApp.PENDENTE,
        ))
    EnvioWhatsApp.objects.bulk_create(envios)
    if not config.simulacao:
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
        configs = ConfiguracaoOfertas.objects.filter(ativo=True).select_related("conta")
        for config in configs:
            if config.proximo_envio_em and config.proximo_envio_em > agora:
                continue
            try:
                self.enviar_proxima(config, agora)
            except Exception as erro:  # noqa: BLE001
                logger.exception("Ofertas: erro na conta %s", config.conta_id)
                config.ultimo_erro = str(erro)[:500]
                config.situacao = "Deu erro ao buscar a próxima oferta - tentando de novo em 5 minutos."
                config.proximo_envio_em = agora + ESPERA_APOS_ERRO
                config.save(update_fields=["ultimo_erro", "situacao", "proximo_envio_em", "atualizado_em"])

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

        produto, grupos = self.proximo_produto(config, agora)
        if not produto:
            if not self._reservar_a_vez(config, agora + ESPERA_SEM_PRODUTO):
                return  # outro processo mexeu na vez enquanto este buscava (ele já enfileirou algo)
            config.situacao = "Nenhuma oferta nova com esses filtros agora. Tento de novo em 30 minutos."
            config.save(update_fields=["situacao", "proximo_envio_em", "pagina_atual", "pagina_em", "atualizado_em"])
            return

        proximo = agora + timedelta(minutes=max(1, config.intervalo_minutos))
        if not self._reservar_a_vez(config, proximo):
            return  # outro processo (ex: o worker antigo, num deploy) já pegou esta vez
        modelo, revisado = revisar_com_ia(config, montar_texto(produto, MARCADOR_DO_LINK, config.cupom), agora)
        enfileirar(
            config, grupos, modelo, produto["link"],
            item_id=produto["item_id"], nome=produto["nome"], imagem_url=produto["imagem"], revisado_ia=revisado,
            produto=produto,
        )
        config.ultimo_envio_em = agora
        config.proximo_envio_em = proximo
        config.situacao = ""
        config.ultimo_erro = ""
        config.save(update_fields=[
            "ultimo_envio_em", "proximo_envio_em", "situacao", "ultimo_erro", "pagina_atual", "pagina_em",
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
        config.ultimo_envio_em = agora
        config.proximo_envio_em = agora + timedelta(minutes=config.intervalo_minutos)
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
        cache = self.cache.get(config.conta_id)
        if (not cache or cache["chave"] != config.chave_da_busca()
                or time.monotonic() - cache["em"] > VALIDADE_DO_CACHE):
            cache = {"chave": config.chave_da_busca(), "produtos": [], "em": time.monotonic()}
            self.cache[config.conta_id] = cache
            if not config.pagina_em or agora - config.pagina_em > RECOMECAR_BUSCA_APOS:
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
        da busca e sem gerar link - o texto mostra um link de exemplo)."""
        app_id, secret = credenciais(config.conta)
        if not app_id or not secret:
            raise ValueError("Conecte sua conta da Shopee em Configurações.")
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
                if config.grupos and not grupos_que_ainda_nao_receberam(config, produto["item_id"], agora):
                    ja_enviados += 1
                    continue
                texto, revisado = montar_texto(produto, MARCADOR_DO_LINK, config.cupom), False
                if not achadas:  # a IA revisa só a primeira, para mostrar como fica
                    texto, revisado = revisar_com_ia(config, texto, agora)
                achadas.append({
                    "nome": produto["nome"], "preco": produto["preco"], "comissao": produto["comissao"],
                    "desconto": produto["desconto"], "vendas": produto["vendas"], "avaliacao": produto["avaliacao"],
                    "imagem": produto["imagem"], "texto": texto.replace(MARCADOR_DO_LINK, LINK_DE_EXEMPLO),
                    "revisado_ia": revisado,
                    # o que a IA fez com a primeira (aparece embaixo dela no "Teste da busca")
                    "ia_status": config.ia_status if (config.ia_ativa and not achadas) else "",
                })
                if len(achadas) >= OFERTAS_NO_TESTE:
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
