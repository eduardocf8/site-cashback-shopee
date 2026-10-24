"""Lado do worker: mantém as conexões de WhatsApp das contas abertas, atende os
pedidos do painel (conectar, desconectar, atualizar grupos) e envia a fila.

Roda numa thread dentro do comando sincronizar_painel --loop (o mesmo Background
Worker do Render que busca os números da Shopee). Usa a biblioteca neonize (uma
versão em Python do whatsmeow, a mesma base de várias integrações de WhatsApp):
o servidor entra como mais um "aparelho conectado" do número, igual ao WhatsApp
Web. A sessão fica guardada no Postgres (tabelas whatsmeow_*), então sobrevive a
deploys e reinícios sem precisar ler o QR Code de novo.

Os avisos da biblioteca chegam em threads dela; eles só vão para uma fila, e quem
mexe no banco é sempre a thread do gerenciador."""

import base64
import io
import logging
import os
import queue
import re
import sys
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from atendimento import servico as atendimento

from . import copia, rede
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, OfertaRecebida
from .servico import registrar_evento

logger = logging.getLogger(__name__)

INTERVALO = 2  # segundos entre uma volta e outra
ESPERA_PARA_REABRIR = 30  # se a sessão parar sozinha, tenta de novo depois disso
DESISTE_DO_ENVIO = timedelta(minutes=10)  # mensagem presa na fila sem conexão
ESPACO_ENTRE_ENVIOS = 3  # segundos entre duas mensagens do mesmo número
ENVIO_TRAVADO_APOS = timedelta(minutes=3)  # "pegou para enviar" e nunca terminou
# Fotos das mensagens copiadas (modo copiar): arquivos temporários, apagados em 6 h.
PASTA_DAS_FOTOS = Path(tempfile.gettempdir()) / "appfiliado-fotos"


def _dentro_da_pasta_das_fotos(caminho: str) -> bool:
    try:
        return Path(caminho).resolve().is_relative_to(PASTA_DAS_FOTOS.resolve())
    except (OSError, ValueError):
        return False


def endereco_do_banco() -> str:
    """Onde a biblioteca guarda a sessão: o mesmo Postgres do site em produção;
    em desenvolvimento (SQLite), um arquivo separado."""
    url = os.environ.get("WHATSAPP_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if url.startswith(("postgres://", "postgresql://")):
        return url
    return str(settings.BASE_DIR / "whatsapp_sessoes.sqlite3")


def propriedades_do_aparelho():
    """Como o servidor se apresenta ao WhatsApp. O bot não usa o histórico das
    conversas, então pede o mínimo possível: ao conectar um aparelho novo, o celular
    manda o histórico dos chats, e num número com muitos grupos isso passava dos
    512 MB do worker (o Render reiniciava). Só vale para conexões feitas depois
    desta mudança - quem já estava conectado precisa desconectar e ler o QR de novo."""
    from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import DeviceProps

    return DeviceProps(
        os="Appfiliado",
        platformType=DeviceProps.DESKTOP,
        requireFullSync=False,
        historySyncConfig=DeviceProps.HistorySyncConfig(
            fullSyncDaysLimit=1, fullSyncSizeMbLimit=1, storageQuotaMb=10, recentSyncDaysLimit=1,
        ),
    )


def _jid_texto(jid) -> str:
    return f"{jid.User}@{jid.Server}"


def _jid_de_texto(texto: str):
    from neonize.utils.jid import build_jid

    usuario, _, servidor = texto.partition("@")
    return build_jid(usuario, servidor)


class Sessao:
    """Uma conexão de WhatsApp de uma conta, rodando na sua própria thread."""

    def __init__(self, fila: queue.Queue, conta_id: int, jid_b64: str = "", novo: bool = False):
        from neonize.client import NewClient
        from neonize.events import (
            ConnectedEv,
            ConnectFailureEv,
            DisconnectedEv,
            KeepAliveRestoredEv,
            KeepAliveTimeoutEv,
            LoggedOutEv,
            MessageEv,
        )
        from neonize.proto.Neonize_pb2 import JID

        self.conta_id = conta_id
        self.fila = fila
        self.conectada = False
        self.thread = None
        # Modo copiar: grupos/canais cujas mensagens com link da Shopee interessam
        # (o gerenciador atualiza a cada 30 s a partir da configuração das ofertas).
        self.origens: set[str] = set()
        self.canais_ao_vivo: dict[str, float] = {}  # canal -> até quando vale o "ao vivo"
        jid = JID.FromString(base64.b64decode(jid_b64)) if (jid_b64 and not novo) else None
        # Sem jid é sempre um aparelho novo: senão a biblioteca retomaria a primeira
        # sessão guardada no banco, que pode ser de outra conta.
        self.cliente = NewClient(
            endereco_do_banco(),
            jid=jid,
            props=propriedades_do_aparelho(),
            uuid=f"appfiliado-{conta_id}",
            new_device=jid is None,
        )

        @self.cliente.qr
        def _qr(_cliente, dados: bytes):
            self.fila.put(("qr", conta_id, dados.decode(errors="ignore"), self))

        @self.cliente.event(ConnectedEv)
        def _conectou(_cliente, _ev):
            self.conectada = True
            self.fila.put(("conectou", conta_id, "", self))

        @self.cliente.event(DisconnectedEv)
        def _caiu(_cliente, _ev):
            self.conectada = False
            self.fila.put(("caiu", conta_id, "", self))

        @self.cliente.event(LoggedOutEv)
        def _deslogou(_cliente, ev):
            self.conectada = False
            self.fila.put(("deslogou", conta_id, str(ev.Reason), self))

        @self.cliente.event(ConnectFailureEv)
        def _falhou(_cliente, ev):
            self.fila.put(("falhou", conta_id, f"{ev.Reason} {ev.Message}".strip(), self))

        @self.cliente.event(KeepAliveTimeoutEv)
        def _instavel(_cliente, _ev):
            self.fila.put(("instavel", conta_id, "", self))

        @self.cliente.event(KeepAliveRestoredEv)
        def _estabilizou(_cliente, _ev):
            self.fila.put(("estabilizou", conta_id, "", self))

        @self.cliente.event(MessageEv)
        def _mensagem(_cliente, ev):
            # Chega aqui toda mensagem de todos os chats: filtra rápido e só manda para
            # a fila as dos grupos/canais de origem com link ou foto. As do próprio
            # número também valem (muita gente posta a oferta do mesmo chip): não há
            # risco de loop, porque origem e destino nunca são o mesmo grupo.
            if atendimento.deve_ouvir(conta_id, ev):  # conversa privada do número de vendas
                self.fila.put(("atendimento", conta_id, ev, self))
                return
            if not self.origens or _jid_texto(ev.Info.MessageSource.Chat) not in self.origens:
                return
            texto = copia.texto_da_mensagem(ev.Message)
            if copia.tem_algum_link(texto) or copia.tem_foto(ev.Message):
                self.fila.put(("mensagem", conta_id, ev, self))

    def iniciar(self):
        self.thread = threading.Thread(target=self._rodar, name=f"whatsapp-{self.conta_id}", daemon=True)
        self.thread.start()

    def _rodar(self):
        try:
            self.cliente.connect()  # só volta quando a sessão termina
        except Exception as erro:  # noqa: BLE001
            self.conectada = False
            self.fila.put(("terminou", self.conta_id, str(erro)[:300], self))
            return
        self.conectada = False
        self.fila.put(("terminou", self.conta_id, "", self))

    @property
    def viva(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def parar(self):
        try:
            self.cliente.stop()
        except Exception:  # noqa: BLE001
            logger.exception("WhatsApp: erro ao parar a sessão da conta %s", self.conta_id)


class Gerenciador:
    def __init__(self):
        self.fila: queue.Queue = queue.Queue()
        self.sessoes: dict[int, Sessao] = {}
        self.reabrir_em: dict[int, float] = {}
        self.ultimo_envio: dict[int, float] = {}
        self.proxima_atualizacao_das_origens = 0.0
        self.proxima_limpeza_de_fotos = 0.0

    # --- Ciclo -----------------------------------------------------------------

    def rodar(self):
        close_old_connections()
        self.retomar()
        while True:
            close_old_connections()
            try:
                self.uma_volta()
            except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
                logger.exception("WhatsApp: erro no gerenciador")
            time.sleep(INTERVALO)

    def uma_volta(self):
        self.tratar_avisos()
        self.atender_pedidos()
        self.reabrir_sessoes_paradas()
        self.atualizar_origens()
        self.enviar_pendentes()
        self.limpar_fotos_antigas()
        atendimento.uma_volta(self.sessoes)

    def retomar(self):
        """Ao ligar o worker (ex: depois de um deploy), reabre as sessões que
        estavam conectadas e cancela QR Codes que ficaram pela metade."""
        ConexaoWhatsApp.objects.filter(estado=ConexaoWhatsApp.AGUARDANDO_QR, pedido_conectar=False).update(
            estado=ConexaoWhatsApp.DESCONECTADO, qr_codigo="", erro="O QR Code expirou. Tente de novo.",
        )
        estados = [ConexaoWhatsApp.CONECTADO, ConexaoWhatsApp.RECONECTANDO]
        for conexao in ConexaoWhatsApp.objects.filter(estado__in=estados).exclude(jid=""):
            conexao.estado = ConexaoWhatsApp.RECONECTANDO
            conexao.save(update_fields=["estado", "atualizado_em"])
            registrar_evento(conexao.conta_id, "retomando", "Servidor reiniciado - reconectando a sessão salva.")
            self.abrir(conexao.conta_id, conexao.jid)

    def abrir(self, conta_id: int, jid_b64: str = "", novo: bool = False) -> Sessao:
        antiga = self.sessoes.pop(conta_id, None)
        if antiga:
            antiga.parar()
        sessao = Sessao(self.fila, conta_id, jid_b64, novo)
        self.sessoes[conta_id] = sessao
        self.proxima_atualizacao_das_origens = 0.0
        self.reabrir_em.pop(conta_id, None)
        sessao.iniciar()
        return sessao

    # --- Avisos da biblioteca ----------------------------------------------------

    def tratar_avisos(self):
        while True:
            try:
                tipo, conta_id, detalhe, origem = self.fila.get_nowait()
            except queue.Empty:
                return
            if self.sessoes.get(conta_id) is not origem:
                continue  # aviso de uma sessão que já foi trocada ou encerrada
            conexao = ConexaoWhatsApp.objects.filter(conta_id=conta_id).first()
            if conexao:
                getattr(self, f"_aviso_{tipo}")(conexao, detalhe)

    def _aviso_qr(self, conexao, codigo):
        if conexao.estado in (ConexaoWhatsApp.AGUARDANDO_QR, ConexaoWhatsApp.DESCONECTADO):
            conexao.estado = ConexaoWhatsApp.AGUARDANDO_QR
            conexao.qr_codigo = codigo
            conexao.qr_em = timezone.now()
            conexao.save(update_fields=["estado", "qr_codigo", "qr_em", "atualizado_em"])

    def _aviso_conectou(self, conexao, _detalhe):
        sessao = self.sessoes.get(conexao.conta_id)
        era = conexao.estado
        if sessao:
            try:
                eu = sessao.cliente.get_me()
                conexao.jid = base64.b64encode(eu.JID.SerializeToString()).decode()
                conexao.numero = eu.JID.User
                conexao.nome = eu.PushName or conexao.nome
            except Exception:  # noqa: BLE001
                logger.exception("WhatsApp: não consegui ler o número conectado da conta %s", conexao.conta_id)
        conexao.estado = ConexaoWhatsApp.CONECTADO
        conexao.conectado_em = timezone.now()
        conexao.qr_codigo = ""
        conexao.erro = ""
        conexao.pedido_grupos = True
        conexao.save()
        if era == ConexaoWhatsApp.RECONECTANDO:
            registrar_evento(conexao.conta_id, "reconectou", "Conexão de volta.")
        else:
            registrar_evento(conexao.conta_id, "conectou", f"Número {conexao.numero_formatado} conectado.")

    def _aviso_caiu(self, conexao, _detalhe):
        if conexao.estado == ConexaoWhatsApp.CONECTADO:
            conexao.estado = ConexaoWhatsApp.RECONECTANDO
            conexao.save(update_fields=["estado", "atualizado_em"])
            registrar_evento(conexao.conta_id, "caiu", "A conexão caiu - reconectando sozinho.")

    def _aviso_deslogou(self, conexao, detalhe):
        sessao = self.sessoes.pop(conexao.conta_id, None)
        if sessao:
            sessao.parar()
        self._limpar(conexao, erro="O WhatsApp desconectou este aparelho (pelo celular ou por segurança).")
        registrar_evento(conexao.conta_id, "deslogou", f"Aparelho desconectado pelo WhatsApp ({detalhe}).")

    def _aviso_falhou(self, conexao, detalhe):
        registrar_evento(conexao.conta_id, "falha", f"O WhatsApp recusou a conexão: {detalhe}")

    def _aviso_instavel(self, conexao, _detalhe):
        registrar_evento(conexao.conta_id, "instavel", "O WhatsApp parou de responder por alguns segundos.")

    def _aviso_atendimento(self, _conexao, ev):
        mensagem = copia.desembrulhar(ev.Message)
        midia = any(mensagem.HasField(c) for c in ("audioMessage", "imageMessage", "videoMessage", "stickerMessage",
                                                    "documentMessage", "ptvMessage"))
        atendimento.registrar(ev, copia.texto_da_mensagem(ev.Message).strip(), midia)

    def _aviso_mensagem(self, conexao, ev):
        """Guarda a oferta que chegou numa origem (o motor das ofertas repassa) e
        baixa a foto dela, se tiver."""
        chat = _jid_texto(ev.Info.MessageSource.Chat)
        config = ConfiguracaoOfertas.objects.filter(conta_id=conexao.conta_id).only("origens").first()
        nome = next((o.get("nome", "") for o in (config.origens if config else []) if o.get("jid") == chat), "")
        texto = copia.texto_da_mensagem(ev.Message)
        com_link_da_shopee = bool(copia.links_shopee(texto))
        defaults = {"origem": chat[:80], "origem_nome": nome[:200], "texto": texto}
        if not com_link_da_shopee:
            # Fica na lista (como ignorada) para a pessoa ver que o bot viu a mensagem.
            defaults.update(estado=OfertaRecebida.IGNORADA, processada_em=timezone.now(),
                            motivo="Sem link da Shopee na mensagem." if texto else "Foto sem texto (sem link da Shopee).")
        recebida, criada = OfertaRecebida.objects.get_or_create(
            conta_id=conexao.conta_id, mensagem_id=f"{chat}/{ev.Info.ID}"[:120], defaults=defaults,
        )
        if not criada or not com_link_da_shopee or not copia.tem_foto(ev.Message):
            return
        sessao = self.sessoes.get(conexao.conta_id)
        try:
            # Foto de grupo de terceiros: tamanho declarado limitado antes de baixar.
            tamanho = copia.desembrulhar(ev.Message).imageMessage.fileLength
            if tamanho and tamanho > rede.MAXIMO_BYTES:
                logger.warning("WhatsApp: foto grande demais na mensagem %s (%s bytes)", recebida.pk, tamanho)
                return
            dados = sessao.cliente.download_any(copia.desembrulhar(ev.Message))
            PASTA_DAS_FOTOS.mkdir(parents=True, exist_ok=True)
            caminho = PASTA_DAS_FOTOS / f"{conexao.conta_id}-{recebida.pk}.jpg"
            caminho.write_bytes(dados)
            recebida.imagem_arquivo = str(caminho)
            recebida.save(update_fields=["imagem_arquivo"])
        except Exception:  # noqa: BLE001 - sem a foto, o motor usa a foto do produto na API
            logger.exception("WhatsApp: não consegui baixar a foto da mensagem %s", recebida.pk)

    def atualizar_origens(self):
        """Quais grupos/canais cada sessão deve ouvir (modo copiar ligado)."""
        if time.monotonic() < self.proxima_atualizacao_das_origens:
            return
        self.proxima_atualizacao_das_origens = time.monotonic() + 30
        configs = {
            c.conta_id: c for c in ConfiguracaoOfertas.objects.filter(
                conta_id__in=list(self.sessoes), ativo=True, modo=ConfiguracaoOfertas.MODO_COPIAR,
            )
        }
        for conta_id, sessao in self.sessoes.items():
            config = configs.get(conta_id)
            sessao.origens = {o["jid"] for o in config.origens if o.get("jid")} if config else set()
            self._acompanhar_canais(sessao)

    def _acompanhar_canais(self, sessao):
        """Canais só mandam as postagens novas para quem pediu "atualizações ao vivo",
        e o pedido vale por um tempo: pede de novo antes de vencer."""
        if not sessao.conectada:
            return
        agora = time.monotonic()
        for jid in sessao.origens:
            if not jid.endswith("@newsletter") or sessao.canais_ao_vivo.get(jid, 0) > agora:
                continue
            try:
                duracao = sessao.cliente.newsletter_subscribe_live_updates(_jid_de_texto(jid))
                sessao.canais_ao_vivo[jid] = agora + max(60, int(duracao or 300) - 60)
            except Exception:  # noqa: BLE001 - tenta de novo daqui a 5 min
                logger.exception("WhatsApp: não deu para acompanhar o canal %s", jid)
                sessao.canais_ao_vivo[jid] = agora + 300

    def limpar_fotos_antigas(self):
        if time.monotonic() < self.proxima_limpeza_de_fotos:
            return
        self.proxima_limpeza_de_fotos = time.monotonic() + 600
        limite = time.time() - 6 * 3600
        for arquivo in PASTA_DAS_FOTOS.glob("*.jpg") if PASTA_DAS_FOTOS.exists() else []:
            try:
                if arquivo.stat().st_mtime < limite:
                    arquivo.unlink()
            except OSError:
                pass

    def _aviso_estabilizou(self, conexao, _detalhe):
        registrar_evento(conexao.conta_id, "estabilizou", "O WhatsApp voltou a responder.")

    def _aviso_terminou(self, conexao, detalhe):
        self.sessoes.pop(conexao.conta_id, None)
        if conexao.estado == ConexaoWhatsApp.AGUARDANDO_QR:
            conexao.estado = ConexaoWhatsApp.DESCONECTADO
            conexao.qr_codigo = ""
            conexao.erro = "O QR Code expirou. Tente de novo." if not detalhe else f"Não deu para conectar: {detalhe}"
            conexao.save()
        elif conexao.jid and conexao.estado in (ConexaoWhatsApp.CONECTADO, ConexaoWhatsApp.RECONECTANDO):
            conexao.estado = ConexaoWhatsApp.RECONECTANDO
            conexao.save(update_fields=["estado", "atualizado_em"])
            registrar_evento(conexao.conta_id, "parou", (detalhe or "A sessão parou.") + " Tentando de novo em 30 s.")
            self.reabrir_em[conexao.conta_id] = time.monotonic() + ESPERA_PARA_REABRIR

    # --- Pedidos do painel --------------------------------------------------------

    def atender_pedidos(self):
        for conexao in ConexaoWhatsApp.objects.filter(pedido_desconectar=True):
            self._desconectar(conexao)
        for conexao in ConexaoWhatsApp.objects.filter(pedido_conectar=True):
            conexao.pedido_conectar = False
            conexao.save(update_fields=["pedido_conectar", "atualizado_em"])
            registrar_evento(conexao.conta_id, "qr", "Gerando o QR Code.")
            self.abrir(conexao.conta_id, novo=True)
        for conexao in ConexaoWhatsApp.objects.filter(pedido_grupos=True, estado=ConexaoWhatsApp.CONECTADO):
            self._atualizar_grupos(conexao)

    def _desconectar(self, conexao):
        sessao = self.sessoes.pop(conexao.conta_id, None)
        if sessao:
            try:
                if sessao.conectada:
                    sessao.cliente.logout()  # some também da lista de aparelhos do celular
            except Exception:  # noqa: BLE001
                logger.exception("WhatsApp: erro no logout da conta %s", conexao.conta_id)
            sessao.parar()
        self._limpar(conexao)
        registrar_evento(conexao.conta_id, "desconectou", "Desconectado pelo painel.")

    def _limpar(self, conexao, erro: str = ""):
        conexao.estado = ConexaoWhatsApp.DESCONECTADO
        conexao.jid = ""
        conexao.qr_codigo = ""
        conexao.grupos = []
        conexao.pedido_desconectar = False
        conexao.pedido_grupos = False
        conexao.erro = erro
        conexao.save()
        self.reabrir_em.pop(conexao.conta_id, None)

    def _atualizar_grupos(self, conexao):
        sessao = self.sessoes.get(conexao.conta_id)
        if not sessao or not sessao.conectada:
            return
        try:
            grupos = sessao.cliente.get_joined_groups()
        except Exception as erro:  # noqa: BLE001
            logger.exception("WhatsApp: erro ao listar grupos da conta %s", conexao.conta_id)
            conexao.erro = f"Não deu para listar os grupos: {str(erro)[:200]}"
            conexao.pedido_grupos = False
            conexao.save(update_fields=["erro", "pedido_grupos", "atualizado_em"])
            return
        destinos = [
            {
                "jid": _jid_texto(grupo.JID),
                "nome": grupo.GroupName.Name or "(grupo sem nome)",
                "participantes": len(getattr(grupo, "Participants", []) or []),
                "tipo": "grupo",
            }
            for grupo in grupos
        ]
        destinos += self._canais(sessao, conexao.conta_id)
        conexao.grupos = sorted(destinos, key=lambda d: (d["tipo"] != "grupo", d["nome"].lower()))
        conexao.grupos_em = timezone.now()
        conexao.pedido_grupos = False
        conexao.save(update_fields=["grupos", "grupos_em", "pedido_grupos", "atualizado_em"])

    @staticmethod
    def _canais(sessao, conta_id) -> list[dict]:
        """Canais que o número segue; pode_postar = é dono ou administrador (só esses
        aceitam postagem). Se a lista de canais falhar, os grupos continuam valendo."""
        try:
            canais = sessao.cliente.get_subscribed_newletters()  # (sic) nome da biblioteca
        except Exception:  # noqa: BLE001
            logger.exception("WhatsApp: erro ao listar canais da conta %s", conta_id)
            return []
        destinos = []
        for canal in canais:
            papel = canal.ViewerMeta.DESCRIPTOR.fields_by_name["Role"].enum_type.values_by_number.get(canal.ViewerMeta.Role)
            destinos.append({
                "jid": _jid_texto(canal.ID),
                "nome": canal.ThreadMeta.Name.Text or "(canal sem nome)",
                "participantes": int(canal.ThreadMeta.SubscriberCount or 0),
                "tipo": "canal",
                # Seguidor não posta: o canal serve só de origem (modo copiar).
                "pode_postar": bool(papel and papel.name in ("OWNER", "ADMIN")),
            })
        return destinos

    def reabrir_sessoes_paradas(self):
        agora = time.monotonic()
        for conta_id, quando in list(self.reabrir_em.items()):
            if agora < quando:
                continue
            self.reabrir_em.pop(conta_id, None)
            conexao = ConexaoWhatsApp.objects.filter(conta_id=conta_id).exclude(jid="").first()
            if conexao and conexao.estado == ConexaoWhatsApp.RECONECTANDO:
                self.abrir(conta_id, conexao.jid)

    # --- Envio --------------------------------------------------------------------

    def enviar_pendentes(self):
        """No máximo uma mensagem por número a cada ESPACO_ENTRE_ENVIOS segundos
        (várias contas se revezam): uma oferta para 10 grupos não sai de rajada."""
        from neonize.utils.jid import build_jid

        agora = time.monotonic()
        ja_enviou_nesta_volta = set()
        # "enviado_em" preenchido com a mensagem ainda na fila = alguém já pegou para enviar
        # (ver o fim do laço). Se isso parou no meio (reinício do servidor), não manda de
        # novo: melhor perder uma do que repetir.
        EnvioWhatsApp.objects.filter(
            estado=EnvioWhatsApp.PENDENTE, enviado_em__lt=timezone.now() - ENVIO_TRAVADO_APOS,
        ).update(estado=EnvioWhatsApp.ERRO, erro="O envio foi interrompido (reinício do servidor). Não foi repetido, para não duplicar.")
        for envio in EnvioWhatsApp.objects.filter(
                estado=EnvioWhatsApp.PENDENTE, enviado_em__isnull=True).order_by("id")[:50]:
            if envio.conta_id in ja_enviou_nesta_volta:
                continue
            if agora - self.ultimo_envio.get(envio.conta_id, 0) < ESPACO_ENTRE_ENVIOS:
                continue
            sessao = self.sessoes.get(envio.conta_id)
            if not sessao or not sessao.conectada:
                if timezone.now() - envio.criado_em > DESISTE_DO_ENVIO:
                    envio.estado = EnvioWhatsApp.ERRO
                    envio.erro = "O WhatsApp estava desconectado."
                    envio.save(update_fields=["estado", "erro"])
                continue
            # Dois workers (o antigo e o novo, durante um deploy) podem olhar a mesma mensagem:
            # só quem conseguir marcar primeiro envia.
            if not EnvioWhatsApp.objects.filter(
                    pk=envio.pk, estado=EnvioWhatsApp.PENDENTE, enviado_em__isnull=True).update(enviado_em=timezone.now()):
                continue
            ja_enviou_nesta_volta.add(envio.conta_id)
            self.ultimo_envio[envio.conta_id] = agora
            usuario, _, servidor = envio.destino.partition("@")
            destino = build_jid(usuario, servidor or "g.us")
            try:
                # A foto vai sempre como bytes baixados aqui (com os limites de rede.py): um
                # texto solto nunca chega à biblioteca, que abriria arquivo local ou URL interna.
                foto = ler_foto(envio.imagem_arquivo) or (rede.baixar(envio.imagem_url) if envio.imagem_url else None)
                if envio.formato == "previa":
                    # Cartão grande do link (grupo e canal); sem foto separada.
                    sessao.cliente.send_message(
                        destino, mensagem_com_previa_grande(sessao.cliente, envio, foto, canal=servidor == "newsletter"),
                    )
                elif servidor == "newsletter":
                    # Canal: foto com legenda pede um envio especial que a biblioteca não
                    # tem; vai texto com prévia do link (título + foto pequena), como no app.
                    sessao.cliente.send_message(destino, mensagem_com_previa(envio, foto))
                elif foto and _imagem_aceitavel(foto):
                    sessao.cliente.send_image(destino, foto, caption=envio.texto or None)
                else:
                    sessao.cliente.send_message(destino, envio.texto)
            except Exception as erro:  # noqa: BLE001
                if "not connected" in str(erro).lower() and timezone.now() - envio.criado_em <= DESISTE_DO_ENVIO:
                    # A conexão caiu na hora (ex: este worker está sendo desligado num deploy):
                    # nada foi enviado. Devolve à fila para o outro worker, ou a próxima volta, tentar.
                    logger.warning("WhatsApp: sem conexão ao enviar a mensagem %s; volta pra fila", envio.pk)
                    EnvioWhatsApp.objects.filter(pk=envio.pk, estado=EnvioWhatsApp.PENDENTE).update(enviado_em=None)
                    continue
                logger.exception("WhatsApp: erro ao enviar a mensagem %s", envio.pk)
                envio.estado = EnvioWhatsApp.ERRO
                envio.erro = str(erro)[:500]
                envio.save(update_fields=["estado", "erro"])
                continue
            envio.estado = EnvioWhatsApp.ENVIADO
            envio.enviado_em = timezone.now()
            envio.save(update_fields=["estado", "enviado_em"])


LIMITE_DE_MEMORIA_GO = "200MiB"


def garantir_limite_de_memoria(argv: list[str]) -> None:
    """A parte em Go da biblioteca tem coleta de lixo própria e, sem limite, deixa a
    memória crescer até perto do teto da máquina (o Render reinicia o worker em 512
    MB). O Go só lê o GOMEMLIMIT do ambiente com que o processo nasceu - definir
    depois, de dentro do Python, não tem efeito. Então, se não veio definido, o
    processo se reinicia uma vez (exec) com ele. Quem já define no Render não passa
    por aqui."""
    if os.environ.get("GOMEMLIMIT"):
        return
    os.execve(sys.executable, [sys.executable, *argv], {**os.environ, "GOMEMLIMIT": LIMITE_DE_MEMORIA_GO})


URL_NO_TEXTO = re.compile(r"https?://\S+")


def _imagem_aceitavel(dados: bytes) -> bool:
    """A foto abre e não é uma "bomba" de pixels (a biblioteca do WhatsApp a decodifica)."""
    try:
        rede.abrir_imagem(dados)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp: foto recusada (não abre ou é grande demais)")
        return False


def ler_foto(caminho: str) -> bytes | None:
    """Só lê arquivo da pasta de fotos baixadas pelo próprio bot."""
    if not caminho or not _dentro_da_pasta_das_fotos(caminho):
        return None
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read()
    except OSError:
        return None  # o worker reiniciou e o arquivo temporário sumiu


def miniatura(url: str = "", dados: bytes | None = None, lado: int = 300, qualidade: int = 70) -> bytes | None:
    """Foto pequena (até `lado` px, JPEG) para a prévia do link; None se não der."""
    if not url and not dados:
        return None
    try:
        from PIL import Image

        if dados is None:
            dados = rede.baixar(url)
            if not dados:
                return None
        imagem = rede.abrir_imagem(dados).convert("RGB")
        imagem.thumbnail((lado, lado))
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=qualidade)
        return saida.getvalue()
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp: não consegui preparar a foto pra prévia: %s", (url or "arquivo")[:200])
        return None


def mensagem_com_previa(envio, foto: bytes | None = None):
    """Texto com a prévia do link montada aqui (título e foto do produto), sem
    depender de o WhatsApp abrir a página da Shopee."""
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ExtendedTextMessage, Message

    link = envio.link_afiliado or next(iter(URL_NO_TEXTO.findall(envio.texto)), "")
    if not link:
        return Message(conversation=envio.texto)
    previa = ExtendedTextMessage(
        text=envio.texto, matchedText=link, title=(envio.produto or "Oferta na Shopee")[:150],
        previewType=ExtendedTextMessage.PreviewType.NONE,
    )
    pequena = miniatura(dados=foto) if foto else miniatura(envio.imagem_url)
    if pequena:
        previa.JPEGThumbnail = pequena
    return Message(extendedTextMessage=previa)


LADO_MAXIMO_DA_PREVIA = 800  # px: a foto vai inteira, na proporção dela (o WhatsApp mostra o cartão grande)


def imagem_da_previa(dados: bytes) -> tuple[bytes, int, int] | None:
    """A foto do produto em JPEG, até 800 px no lado maior e sem cortar - como o
    WhatsApp Web faz ao colar um link. (bytes, largura, altura) ou None se não der."""
    try:
        from PIL import Image

        imagem = rede.abrir_imagem(dados)
        if imagem.mode in ("RGBA", "LA", "P"):  # fundo transparente vira branco
            imagem = imagem.convert("RGBA")
            fundo = Image.new("RGB", imagem.size, (255, 255, 255))
            fundo.paste(imagem, mask=imagem.split()[-1])
            imagem = fundo
        imagem = imagem.convert("RGB")
        imagem.thumbnail((LADO_MAXIMO_DA_PREVIA, LADO_MAXIMO_DA_PREVIA), Image.LANCZOS)
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=85, optimize=True)
        return saida.getvalue(), imagem.width, imagem.height
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp: não consegui preparar a imagem da prévia")
        return None


def mensagem_com_previa_grande(cliente, envio, foto: bytes | None = None, canal: bool = False):
    """Texto com prévia grande do link: a foto do produto (inteira, na proporção dela) vai
    como miniatura de alta qualidade, como faz o WhatsApp ao colar um link. Grupo e canal
    guardam essa imagem de jeitos diferentes (a do grupo é criptografada, a do canal não);
    se o envio da imagem falhar, vai a miniatura dentro da própria mensagem. Se faltar a
    foto, cai na prévia pequena - a oferta sai de qualquer jeito."""
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ExtendedTextMessage, Message
    from neonize.utils.enum import MediaType

    link = envio.link_afiliado or next(iter(URL_NO_TEXTO.findall(envio.texto)), "")
    if not link:
        return Message(conversation=envio.texto)
    dados = foto
    if not dados and envio.imagem_url:
        dados = rede.baixar(envio.imagem_url)
        if not dados:
            logger.warning("WhatsApp: não consegui baixar a foto pra prévia grande: %s", envio.imagem_url[:200])
    pronta = imagem_da_previa(dados) if dados else None
    if not pronta:
        return mensagem_com_previa(envio, foto)
    imagem, largura, altura = pronta
    previa = ExtendedTextMessage(
        text=envio.texto, matchedText=link, title=(envio.produto or "Oferta na Shopee")[:150],
        previewType=ExtendedTextMessage.PreviewType.NONE,
        JPEGThumbnail=miniatura(dados=imagem) or b"", thumbnailWidth=largura, thumbnailHeight=altura,
    )
    try:
        if canal:
            enviada = cliente.upload_newsletter(imagem, MediaType.MediaLinkThumbnail)
            previa.MergeFrom(ExtendedTextMessage(thumbnailDirectPath=enviada.DirectPath, thumbnailSHA256=enviada.FileSHA256))
        else:
            enviada = cliente.upload(imagem, MediaType.MediaLinkThumbnail)
            previa.MergeFrom(ExtendedTextMessage(
                thumbnailDirectPath=enviada.DirectPath, thumbnailSHA256=enviada.FileSHA256,
                thumbnailEncSHA256=enviada.FileEncSHA256, mediaKey=enviada.MediaKey, mediaKeyTimestamp=int(time.time()),
            ))
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp: não consegui enviar a imagem da prévia grande; vai a miniatura")
        previa.JPEGThumbnail = miniatura(dados=imagem, lado=600, qualidade=80) or previa.JPEGThumbnail
    return Message(extendedTextMessage=previa)


def iniciar_em_segundo_plano():
    """Chamado pelo sincronizar_painel --loop. Se a biblioteca não carregar (ex:
    falta algo no servidor), avisa no log e deixa o resto do worker funcionando."""
    # O limite de memória da parte em Go (GOMEMLIMIT) é definido pelo
    # sincronizar_painel antes de o processo começar - ver garantir_limite_de_memoria.
    try:
        import neonize.client  # noqa: F401
    except Exception:  # noqa: BLE001
        logger.exception("WhatsApp: a biblioteca neonize não carregou - o bot de WhatsApp fica desligado.")
        return None
    logging.getLogger("whatsmeow").setLevel(logging.WARNING)
    gerenciador = Gerenciador()
    thread = threading.Thread(target=gerenciador.rodar, name="whatsapp-gerenciador", daemon=True)
    thread.start()
    from .ofertas import iniciar_em_segundo_plano as iniciar_motor_de_ofertas

    iniciar_motor_de_ofertas()
    return gerenciador
