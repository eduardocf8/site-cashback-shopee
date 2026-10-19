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

from . import shopee_ofertas
from .formatador import formatar_texto_oferta
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp

logger = logging.getLogger(__name__)

INTERVALO_MOTOR = 15  # segundos entre uma conferência e outra
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


def ofertas_enviadas_hoje(conta, agora) -> int:
    """Quantos produtos diferentes já saíram hoje (o mesmo produto em vários grupos
    conta uma vez)."""
    inicio_do_dia = timezone.localtime(agora).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        EnvioWhatsApp.objects.filter(conta=conta, origem=EnvioWhatsApp.OFERTA, criado_em__gte=inicio_do_dia)
        .exclude(estado=EnvioWhatsApp.ERRO).values("item_id").distinct().count()
    )


def grupos_que_ainda_nao_receberam(config, item_id: str, agora) -> list[dict]:
    desde = agora - timedelta(days=max(1, config.repetir_apos_dias))
    ja_receberam = set(
        EnvioWhatsApp.objects.filter(
            conta=config.conta, origem=EnvioWhatsApp.OFERTA, item_id=item_id, criado_em__gte=desde,
        ).exclude(estado=EnvioWhatsApp.ERRO).values_list("destino", flat=True)
    )
    return [g for g in config.grupos if g.get("jid") and g["jid"] not in ja_receberam]


def motivo_para_esperar(config, conexao, agora) -> str:
    """"" = pode enviar agora; senão, o motivo (aparece no painel)."""
    app_id, secret = credenciais(config.conta)
    if not config.conta.shopee_validado_em or not app_id or not secret:
        return "Conecte sua conta da Shopee em Configurações."
    if not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO:
        return "Esperando o WhatsApp conectar."
    if not config.grupos:
        return "Escolha pelo menos um grupo."
    if not dentro_do_horario(config, timezone.localtime(agora)):
        return "Fora do horário de envio."
    if config.limite_diario and ofertas_enviadas_hoje(config.conta, agora) >= config.limite_diario:
        return "Limite de ofertas de hoje atingido."
    return ""


def montar_texto(produto: dict, link: str, cupom: str = "") -> str:
    return formatar_texto_oferta(shopee_ofertas.texto_base(produto, cupom), link)


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

        produto, grupos = self.proximo_produto(config, agora)
        if not produto:
            config.situacao = "Nenhuma oferta nova com esses filtros agora. Tento de novo em 30 minutos."
            config.proximo_envio_em = agora + ESPERA_SEM_PRODUTO
            config.save(update_fields=["situacao", "proximo_envio_em", "pagina_atual", "pagina_em", "atualizado_em"])
            return

        app_id, secret = credenciais(config.conta)
        # Mesmo texto para todos os grupos; só o link muda quando cada grupo tem o seu
        # Sub ID (um link por combinação de Sub IDs).
        modelo = montar_texto(produto, MARCADOR_DO_LINK, config.cupom)
        links: dict[tuple, str] = {}
        envios = []
        for grupo in grupos:
            sub_ids = tuple(config.lista_sub_ids(grupo["jid"]))
            if sub_ids not in links:
                links[sub_ids] = shopee_ofertas.gerar_link_afiliado(app_id, secret, produto["link"], list(sub_ids))
            link = links[sub_ids]
            envios.append(EnvioWhatsApp(
                conta=config.conta, destino=grupo["jid"], destino_nome=grupo.get("nome", ""),
                texto=modelo.replace(MARCADOR_DO_LINK, link), imagem_url=produto["imagem"][:1000],
                origem=EnvioWhatsApp.OFERTA, item_id=produto["item_id"], produto=produto["nome"][:300],
                link_afiliado=link[:500],
            ))
        EnvioWhatsApp.objects.bulk_create(envios)
        config.ultimo_envio_em = agora
        config.proximo_envio_em = agora + timedelta(minutes=max(1, config.intervalo_minutos))
        config.situacao = ""
        config.ultimo_erro = ""
        config.save(update_fields=[
            "ultimo_envio_em", "proximo_envio_em", "situacao", "ultimo_erro", "pagina_atual", "pagina_em",
            "atualizado_em",
        ])

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
            config.save(update_fields=["teste_resultado", "teste_erro", "teste_em", "atualizado_em"])

    def testar(self, config, agora) -> list[dict]:
        """As próximas ofertas que sairiam com os filtros atuais (sem mexer na posição
        da busca e sem gerar link - o texto mostra um link de exemplo)."""
        app_id, secret = credenciais(config.conta)
        if not app_id or not secret:
            raise ValueError("Conecte sua conta da Shopee em Configurações.")
        achadas = []
        pagina = 1
        for _ in range(3):
            produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, config, pagina)
            for produto in produtos:
                if not shopee_ofertas.passa_nos_filtros(produto, config):
                    continue
                if config.grupos and not grupos_que_ainda_nao_receberam(config, produto["item_id"], agora):
                    continue
                achadas.append({
                    "nome": produto["nome"], "preco": produto["preco"], "comissao": produto["comissao"],
                    "desconto": produto["desconto"], "vendas": produto["vendas"], "avaliacao": produto["avaliacao"],
                    "imagem": produto["imagem"], "texto": montar_texto(produto, LINK_DE_EXEMPLO, config.cupom),
                })
                if len(achadas) >= OFERTAS_NO_TESTE:
                    return achadas
            if not tem_proxima:
                break
            pagina += 1
        return achadas


def iniciar_em_segundo_plano() -> Motor:
    motor = Motor()
    threading.Thread(target=motor.rodar, name="ofertas-motor", daemon=True).start()
    return motor
