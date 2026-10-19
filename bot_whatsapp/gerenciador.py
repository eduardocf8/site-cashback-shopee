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
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import ConexaoWhatsApp, EnvioWhatsApp
from .servico import registrar_evento

logger = logging.getLogger(__name__)

INTERVALO = 2  # segundos entre uma volta e outra
ESPERA_PARA_REABRIR = 30  # se a sessão parar sozinha, tenta de novo depois disso
DESISTE_DO_ENVIO = timedelta(minutes=10)  # mensagem presa na fila sem conexão
ESPACO_ENTRE_ENVIOS = 3  # segundos entre duas mensagens do mesmo número


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
        )
        from neonize.proto.Neonize_pb2 import JID

        self.conta_id = conta_id
        self.fila = fila
        self.conectada = False
        self.thread = None
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
        self.enviar_pendentes()

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
        destinos += self._canais_onde_pode_postar(sessao, conexao.conta_id)
        conexao.grupos = sorted(destinos, key=lambda d: (d["tipo"] != "grupo", d["nome"].lower()))
        conexao.grupos_em = timezone.now()
        conexao.pedido_grupos = False
        conexao.save(update_fields=["grupos", "grupos_em", "pedido_grupos", "atualizado_em"])

    @staticmethod
    def _canais_onde_pode_postar(sessao, conta_id) -> list[dict]:
        """Canais em que o número é dono ou administrador (só esses aceitam postagem).
        Se a lista de canais falhar, os grupos continuam valendo."""
        try:
            canais = sessao.cliente.get_subscribed_newletters()  # (sic) nome da biblioteca
        except Exception:  # noqa: BLE001
            logger.exception("WhatsApp: erro ao listar canais da conta %s", conta_id)
            return []
        destinos = []
        for canal in canais:
            papel = canal.ViewerMeta.DESCRIPTOR.fields_by_name["Role"].enum_type.values_by_number.get(canal.ViewerMeta.Role)
            if not papel or papel.name not in ("OWNER", "ADMIN"):
                continue
            destinos.append({
                "jid": _jid_texto(canal.ID),
                "nome": canal.ThreadMeta.Name.Text or "(canal sem nome)",
                "participantes": int(canal.ThreadMeta.SubscriberCount or 0),
                "tipo": "canal",
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
        for envio in EnvioWhatsApp.objects.filter(estado=EnvioWhatsApp.PENDENTE).order_by("id")[:50]:
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
            ja_enviou_nesta_volta.add(envio.conta_id)
            self.ultimo_envio[envio.conta_id] = agora
            usuario, _, servidor = envio.destino.partition("@")
            destino = build_jid(usuario, servidor or "g.us")
            try:
                if servidor == "newsletter":
                    # Canal: foto com legenda pede um envio especial que a biblioteca não
                    # tem; vai texto com prévia do link (título + foto pequena), como no app.
                    sessao.cliente.send_message(destino, mensagem_com_previa(envio))
                elif envio.imagem_url:
                    sessao.cliente.send_image(destino, envio.imagem_url, caption=envio.texto or None)
                else:
                    sessao.cliente.send_message(destino, envio.texto)
            except Exception as erro:  # noqa: BLE001
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


def miniatura(url: str) -> bytes | None:
    """Foto pequena (até 300 px, JPEG) para a prévia do link; None se não der."""
    if not url:
        return None
    try:
        import requests
        from PIL import Image

        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        imagem = Image.open(io.BytesIO(resposta.content)).convert("RGB")
        imagem.thumbnail((300, 300))
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=70)
        return saida.getvalue()
    except Exception:  # noqa: BLE001
        logger.warning("WhatsApp: não consegui baixar a foto para a prévia: %s", url[:200])
        return None


def mensagem_com_previa(envio):
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
    foto = miniatura(envio.imagem_url)
    if foto:
        previa.JPEGThumbnail = foto
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
