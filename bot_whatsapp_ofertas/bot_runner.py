import queue
import threading
import random
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QImage
from playwright.sync_api import sync_playwright

from afiliados import ConversorAfiliados
from browser_launch import (
    montar_kwargs_launch,
    aplicar_anti_deteccao_no_contexto,
)
from database import Database
from formatador import formatar_texto_oferta
from ia_revisor import RevisorIA
from oferta import Oferta
from parser import extrair_links_shopee, gerar_id_mensagem
from processor import processar_mensagem
from settings import APP_DIR
from whatsapp import WhatsApp

# Se o bot ficar mais tempo que isso sem rodar um ciclo Shopee (parado,
# desligado, fora do horario agendado etc.), a pagina salva e considerada
# "velha" demais: a lista de ofertas da Shopee muda com o tempo (vendas,
# comissoes, campanhas novas), entao comecamos de novo da pagina 1 em vez
# de continuar de um ponto que nao reflete mais a lista atual.
RENOVACAO_PAGINA_SHOPEE_SEGUNDOS = 3 * 60 * 60  # 3 horas


class BotRunner:
    def __init__(self, settings, on_log=None, on_status=None, on_stats=None):
        self.settings = settings
        self.on_log = on_log or (lambda text: None)
        self.on_status = on_status or (lambda text: None)
        self.on_stats = on_stats or (lambda stats: None)
        self.stop_event = threading.Event()
        self.thread = None
        self.runtime_lock = threading.Lock()
        self.play = None
        self.db = None
        self.zap = None
        self.conversor = None
        self.stats = {
            "processadas": 0,
            "enviadas": 0,
            "erros": 0,
        }

    def start(self):
        if self.is_running():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self._status("Parando bot... aguarde o fechamento seguro das janelas.")

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def _log(self, message=""):
        self.on_log(str(message))

    def _status(self, message):
        self.on_status(str(message))
        self._log(message)

    def _emit_stats(self):
        self.on_stats(dict(self.stats))

    def _run(self):
        fila_mensagens = queue.Queue()
        falhas_consecutivas = 0

        try:
            db_path = self._resolve_app_path(self.settings.database_path)
            profile_dir = self._resolve_app_path(self.settings.profile_dir)
            self.settings.profile_dir = str(profile_dir)

            while not self.stop_event.is_set():
                if not self._esta_no_horario_ativo():
                    if self.zap or self.db or self.play:
                        self._status("Fora do horario agendado. Pausando e fechando navegador...")
                        self._fechar_recursos_runtime()
                    self._status(self._mensagem_fora_do_horario())
                    self.stop_event.wait(60)
                    continue

                try:
                    if not self.zap or not self.db or not self.play:
                        self._inicializar_runtime(str(db_path))

                    if self._modo_shopee():
                        self._processar_ofertas_shopee(self.db, self.zap, self.conversor)
                        intervalo = max(5, int(self.settings.shopee_ofertas_intervalo_envio_segundos or 300))
                    else:
                        self._capturar_novas_mensagens(self.db, self.zap, fila_mensagens)
                        self._processar_fila(self.db, self.zap, self.conversor, fila_mensagens)
                        intervalo = self.settings.intervalo_ms / 1000

                    falhas_consecutivas = 0
                    self.stop_event.wait(intervalo)

                except Exception as e:
                    falhas_consecutivas += 1
                    self.stats["erros"] += 1
                    self._emit_stats()
                    self._log("Falha no monitoramento do bot:")
                    self._log(e)
                    self._log(traceback.format_exc())

                    if not self._deve_tentar_recuperar(falhas_consecutivas):
                        self._status(f"Erro no bot: {e}")
                        break

                    self._status(
                        "Tentando recuperar automaticamente "
                        f"({falhas_consecutivas}/{self.settings.recuperacao_max_tentativas})..."
                    )
                    self._fechar_recursos_runtime()
                    self.stop_event.wait(self.settings.recuperacao_intervalo_segundos)

            self._status("Bot parado.")

        except Exception as e:
            self.stats["erros"] += 1
            self._emit_stats()
            self._status(f"Erro no bot: {e}")
            self._log(traceback.format_exc())

        finally:
            self._fechar_recursos_runtime()
            self._status("Bot finalizado.")

    def _inicializar_runtime(self, db_path):
        self._status("Iniciando navegador e WhatsApp...")
        if self.settings.headless:
            self._log("Modo minimizado ativo: o Chrome sera aberto e minimizado automaticamente.")

        self.play = sync_playwright().start()
        self.db = Database(str(db_path))
        self.zap = WhatsApp(self.play, headless=self.settings.headless, app_config=self.settings)
        self.conversor = ConversorAfiliados(self.play, headless=self.settings.headless, app_config=self.settings)
        self.conversor.definir_logger(self._log)
        # O conversor usa um navegador de verdade (Chrome) proprio - SEPARADO
        # do navegador do WhatsApp Web - para resolver links curtos e baixar a
        # imagem do produto no Modo Grupo.
        navegador_shopee = self._abrir_navegador_shopee()
        if navegador_shopee:
            self.conversor.definir_contexto_navegador(navegador_shopee)

        if self._modo_shopee():
            self._status("Modo Shopee ativo. Buscando ofertas pela API...")
            return

        self._status("Preparando grupo de origem...")
        self.zap.preparar_monitoramento_origem(self.settings.grupo_origem)

        if not self.settings.processar_historico_ao_iniciar and self.db.quantidade() == 0:
            self._marcar_historico_como_lido(self.db, self.zap)
        else:
            self._log("Processando mensagens novas encontradas no historico visivel...")

        self._status("Monitorando mensagens...")

    def _modo_shopee(self):
        return getattr(self.settings, "modo_origem_ofertas", "whatsapp") == "shopee"

    def _abrir_navegador_shopee(self):
        """
        Abre o navegador (Google Chrome) usado pelo conversor para tarefas
        auxiliares da Shopee no Modo Grupo: resolver links curtos
        (s.shopee.com.br) e baixar a imagem do produto quando a API nao
        retorna. E um navegador separado do WhatsApp Web de proposito - ver
        comentario em _inicializar_runtime.

        Observacao: a captura de produtos de COLECAO nao usa mais este
        navegador; passou a ser feita pela API (por aproximacao), porque a
        Shopee bloqueia o scraping da pagina de colecao com captcha.
        """

        pasta_perfil_shopee = str(self._resolve_app_path("perfil_shopee_bot"))
        headless_visual = bool(self.settings.headless)
        try:
            navegador = self.play.chromium.launch_persistent_context(
                **montar_kwargs_launch(
                    user_data_dir=pasta_perfil_shopee,
                    channel="chrome",
                    headless_visual=headless_visual,
                )
            )
            aplicar_anti_deteccao_no_contexto(navegador)
        except Exception as e:
            self._log(f"Google Chrome de verdade falhou ao abrir o navegador da Shopee: {e}")
            try:
                navegador = self.play.chromium.launch_persistent_context(
                    **montar_kwargs_launch(
                        user_data_dir=pasta_perfil_shopee,
                        channel=None,
                        headless_visual=headless_visual,
                    )
                )
                aplicar_anti_deteccao_no_contexto(navegador)
            except Exception as e:
                self._log(f"Nao consegui abrir o navegador dedicado da Shopee: {e}")
                return None

        if self.settings.headless:
            try:
                for pagina in navegador.pages:
                    pagina.close()
            except Exception:
                pass

        return navegador

    def _deve_tentar_recuperar(self, falhas_consecutivas):
        if self.stop_event.is_set():
            return False
        if not self.settings.recuperacao_automatica:
            return False
        return falhas_consecutivas <= self.settings.recuperacao_max_tentativas

    def _esta_no_horario_ativo(self):
        if not self.settings.agendamento_ativo:
            return True

        inicio = self._parse_horario(self.settings.horario_inicio)
        fim = self._parse_horario(self.settings.horario_fim)
        if inicio is None or fim is None:
            return True

        agora = datetime.now().time()
        if inicio <= fim:
            return inicio <= agora < fim

        return agora >= inicio or agora < fim

    def _parse_horario(self, value):
        try:
            return datetime.strptime(value, "%H:%M").time()
        except Exception:
            return None

    def _mensagem_fora_do_horario(self):
        return (
            "Fora do horario agendado. "
            f"O bot voltara a monitorar entre {self.settings.horario_inicio} "
            f"e {self.settings.horario_fim}."
        )

    def _fechar_recursos_runtime(self):
        with self.runtime_lock:
            recursos = (
                ("WhatsApp", self.zap),
                ("Conversor Shopee", self.conversor),
                ("Banco de dados", self.db),
            )

            for nome, recurso in recursos:
                try:
                    if recurso:
                        recurso.fechar()
                except Exception as e:
                    self._log(f"Falha ao fechar {nome}: {e}")

            try:
                if self.play:
                    self.play.stop()
            except Exception as e:
                self._log(f"Falha ao fechar Playwright: {e}")

            self.zap = None
            self.conversor = None
            self.db = None
            self.play = None

    def _resolve_app_path(self, value):
        path = Path(value)
        if path.is_absolute():
            return path
        return APP_DIR / path

    def _marcar_historico_como_lido(self, db, zap):
        mensagens_iniciais = zap.capturar_mensagens()
        self._log(f"Marcando {len(mensagens_iniciais)} mensagens visiveis como lidas...")

        for msg in mensagens_iniciais:
            if not msg.get("texto"):
                continue

            id_msg = gerar_id_mensagem(
                msg.get("autor"),
                msg.get("texto"),
                msg.get("link"),
            )

            db.salvar(
                id_msg,
                msg.get("autor"),
                msg.get("texto"),
                msg.get("link"),
            )

        self._log("Historico ignorado. Aguardando novas mensagens...")

    def _capturar_novas_mensagens(self, db, zap, fila_mensagens):
        mensagens = zap.capturar_mensagens()

        for msg in mensagens:
            if self.stop_event.is_set():
                return

            if not msg.get("texto"):
                continue

            id_msg = gerar_id_mensagem(
                msg.get("autor"),
                msg.get("texto"),
                msg.get("link"),
            )

            if db.existe(id_msg):
                continue

            db.salvar(
                id_msg,
                msg.get("autor"),
                msg.get("texto"),
                msg.get("link"),
            )

            links_shopee = extrair_links_shopee(msg.get("texto"))

            if not links_shopee:
                if msg.get("link"):
                    self._log("Mensagem nova ignorada: link nao e Shopee.")
                else:
                    self._log("Mensagem nova ignorada: sem link.")
                continue

            msg["link"] = links_shopee[0]
            msg["links_shopee"] = links_shopee

            if self.settings.ignorar_links_ja_enviados:
                destinos_atuais = self.settings.normalized_destinos()
                link_repetido = next(
                    (
                        link for link in links_shopee
                        if db.link_ja_enviado_para_todos(link, destinos_atuais)
                    ),
                    None,
                )
                if link_repetido:
                    self._log("Oferta ignorada: link ja enviado anteriormente para todos os grupos de destino atuais.")
                    self._log(link_repetido)
                    continue

            fila_mensagens.put(msg)
            self._log("Mensagem nova com link Shopee adicionada a fila.")

    def _processar_fila(self, db, zap, conversor, fila_mensagens):
        revisor_ia = RevisorIA(self.settings, self._log)
        while not fila_mensagens.empty() and not self.stop_event.is_set():
            msg = fila_mensagens.get()
            imagem_fallback = None

            try:
                self._status("Convertendo link e formatando oferta...")
                oferta = processar_mensagem(msg, conversor)

                if oferta is None:
                    self._log("Mensagem ignorada: sem oferta valida.")
                    continue

                if self.settings.ia_revisao_ativa:
                    self._status("Revisando texto com IA...")
                    oferta.texto_final = revisor_ia.revisar_texto(
                        oferta.texto_final,
                        oferta.link_afiliado,
                    )

                self.stats["processadas"] += 1
                self._emit_stats()

                self._log("=" * 60)
                self._log("OFERTA PROCESSADA")
                self._log(f"LINK ORIGINAL: {oferta.link_original}")
                self._log(f"LINK AFILIADO: {oferta.link_afiliado}")
                self._log("TEXTO FINAL:")
                self._log(oferta.texto_final)
                self._log("=" * 60)

                # 1) O link do produto ja foi capturado na mensagem do grupo
                # origem (processar_mensagem/extrair_links_shopee, acima).
                # 2) Agora buscamos os dados do produto na API da Shopee, a
                # partir desse link, para baixar a imagem real do produto
                # (em vez de depender de uma imagem capturada da propria
                # mensagem do WhatsApp).
                self._status("Buscando imagem do produto na API Shopee...")
                try:
                    dados_produto, motivo = conversor.obter_oferta_por_link(oferta.link_original)
                except Exception as erro_produto:
                    dados_produto, motivo = None, "erro"
                    self._log(f"Nao consegui buscar dados do produto na API Shopee: {erro_produto}")

                if dados_produto:
                    imagem_fallback = self._baixar_imagem_produto_via_api(dados_produto)
                    if motivo == "pagina_produto":
                        self._log("Produto fora da base de ofertas da Shopee; imagem obtida direto da pagina do produto.")
                    elif motivo == "navegador":
                        self._log("Link bloqueava requisicao simples (checagem de navegador da Shopee); imagem obtida abrindo o link no navegador.")
                elif motivo == "sem_item_id":
                    self._log(
                        "Nao encontrei o itemId nesse link (formato de URL diferente do esperado); "
                        "envio sera so com a previa do link, sem imagem de fallback."
                    )
                else:
                    self._log(
                        "Nao consegui obter uma imagem para esse produto (nem pela API de ofertas, "
                        "nem pela pagina do produto); envio sera so com a previa do link."
                    )

                if self.settings.modo_simulacao:
                    self._status("Simulacao concluida. Oferta nao enviada.")
                    self._log("MODO SIMULACAO: envio no WhatsApp ignorado.")
                    self._log("MODO SIMULACAO: link nao gravado no historico de enviados.")
                else:
                    for grupo in self.settings.normalized_destinos():
                        if self.stop_event.is_set():
                            break

                        if (
                            self.settings.ignorar_links_ja_enviados
                            and db.link_ja_enviado(oferta.link_original, grupo)
                        ):
                            self._log(f"Oferta ja enviada anteriormente para {grupo}; pulando esse grupo.")
                            continue

                        self._status(f"Enviando oferta para {grupo}...")
                        # 3) Tenta carregar a previa da imagem pelo link; se
                        # nao conseguir, envia a imagem baixada da API.
                        tipo_envio = zap.enviar_texto_com_fallback_imagem(
                            grupo,
                            oferta.texto_final,
                            caminho_imagem=imagem_fallback,
                            aguardar_previa=self.settings.aguardar_previa_link,
                            timeout_previa_ms=self.settings.timeout_previa_link_ms,
                            tipo_destino=self.settings.destino_tipo,
                        )
                        if tipo_envio == "imagem":
                            self._log("Previa do link nao carregou. Imagem baixada da API Shopee enviada como fallback.")
                        elif tipo_envio == "preview":
                            self._log("Oferta enviada com previa do link com imagem.")
                        elif tipo_envio == "nao_enviado_sem_imagem":
                            self._log(
                                "Oferta nao enviada: a previa nao carregou imagem "
                                "e nao havia imagem da API para fallback."
                            )
                            continue
                        elif str(tipo_envio).startswith("nao_enviado_falha_imagem:"):
                            motivo = str(tipo_envio).split(":", 1)[1]
                            self._log(f"Oferta nao enviada: falha ao anexar imagem de fallback. Detalhe: {motivo}")
                            continue
                        else:
                            self._log("Oferta enviada somente com texto.")

                        self.stats["enviadas"] += 1
                        self._emit_stats()

                        if not self.stop_event.is_set() and not self.settings.modo_simulacao:
                            db.salvar_link_enviado(
                                oferta.link_original,
                                oferta.link_afiliado,
                                oferta.texto_final,
                                grupo,
                            )

                if not self._modo_shopee():
                    zap.preparar_monitoramento_origem(self.settings.grupo_origem)
                if self.settings.modo_simulacao:
                    self._status("Simulacao pronta. Monitorando origem...")
                else:
                    self._status("Oferta enviada. Monitorando origem...")

            except Exception as e:
                self.stats["erros"] += 1
                self._emit_stats()
                self._log("Erro ao processar/enviar oferta:")
                self._log(e)
                self._log(traceback.format_exc())

                try:
                    zap.limpar_preview_se_aberto()
                    zap.fechar_visualizador_midia()
                    if not self._modo_shopee():
                        zap.preparar_monitoramento_origem(self.settings.grupo_origem)
                        self._log("Bot recuperado e voltou para o grupo de origem.")
                except Exception as erro_recuperacao:
                    self._log("Erro ao tentar recuperar o bot:")
                    self._log(erro_recuperacao)

            finally:
                self._remover_imagem_temporaria(imagem_fallback)
                fila_mensagens.task_done()

    def _processar_ofertas_shopee(self, db, zap, conversor):
        quantidade = 10
        limite_busca = 50
        max_paginas_busca = 8
        intervalo = max(5, int(self.settings.shopee_ofertas_intervalo_envio_segundos or 300))
        self._status("Buscando ofertas na Shopee...")
        self._log("=" * 60)
        self._log("CICLO MODO SHOPEE")
        self._log(f"Quantidade por ciclo: {quantidade}")
        self._log(f"Candidatas por pagina: {limite_busca}")
        self._log(f"Paginas maximas para procurar ofertas novas: {max_paginas_busca}")
        self._log(f"Intervalo entre envios/buscas: {self._formatar_duracao(intervalo)}")

        link_colecao = str(getattr(self.settings, "shopee_ofertas_link_colecao", "") or "").strip()
        if link_colecao:
            resultado = self._buscar_ofertas_colecao_para_ciclo(db, conversor, quantidade, link_colecao)
        else:
            resultado = self._buscar_ofertas_shopee_para_ciclo(
                db,
                conversor,
                quantidade=quantidade,
                limite_por_pagina=limite_busca,
                max_paginas=max_paginas_busca,
            )
        ofertas = resultado.get("ofertas") or []
        total_recebido = resultado.get("total_recebido") or 0
        total_filtrado = resultado.get("total_filtrado") or 0
        self._log(f"Ofertas recebidas da API: {total_recebido}")
        self._log(f"Ofertas que passaram pelos filtros: {total_filtrado}")
        self._log(f"Ofertas candidatas para analise: {len(ofertas)}")

        if not ofertas:
            self._status("Nenhuma oferta Shopee passou pelos filtros atuais.")
            self._log("Resumo do ciclo: 0 enviadas, 0 ignoradas, 0 erros.")
            self._log(f"Proxima busca em aproximadamente {self._formatar_duracao(intervalo)}.")
            self._log("=" * 60)
            return

        revisor_ia = RevisorIA(self.settings, self._log)
        enviadas_no_ciclo = 0
        simuladas_no_ciclo = 0
        ignoradas_repetidas = int(resultado.get("ignoradas_repetidas") or 0)
        ignoradas_sem_link = 0
        erros_no_ciclo = 0

        for oferta_shopee in ofertas:
            if self.stop_event.is_set():
                break
            if enviadas_no_ciclo + simuladas_no_ciclo >= quantidade:
                break

            try:
                link_original = self._link_oferta_shopee(oferta_shopee)
                if not link_original:
                    ignoradas_sem_link += 1
                    self._log("Oferta Shopee ignorada: API nao retornou link do produto.")
                    continue

                if (
                    self.settings.shopee_ofertas_nao_repetir
                    and db.link_ja_enviado_para_todos(link_original, self.settings.normalized_destinos())
                ):
                    ignoradas_repetidas += 1
                    self._log("Oferta Shopee ignorada: produto/link ja enviado anteriormente para todos os grupos de destino atuais.")
                    self._log(link_original)
                    continue

                oferta = self._criar_oferta_shopee(oferta_shopee, conversor, link_original)
                if oferta is None:
                    ignoradas_sem_link += 1
                    continue

                if self.settings.ia_revisao_ativa:
                    self._status("Revisando oferta Shopee com IA...")
                    oferta.texto_final = revisor_ia.revisar_texto(
                        oferta.texto_final,
                        oferta.link_afiliado,
                    )

                self.stats["processadas"] += 1
                self._emit_stats()
                self._registrar_oferta_processada(oferta)

                if self.settings.modo_simulacao:
                    simuladas_no_ciclo += 1
                    self._status("Simulacao concluida. Oferta Shopee nao enviada.")
                    self._log("MODO SIMULACAO: envio no WhatsApp ignorado.")
                    continue

                if enviadas_no_ciclo > 0:
                    self._log(f"Aguardando {self._formatar_duracao(intervalo)} ate a proxima oferta nova.")
                    self.stop_event.wait(intervalo)
                    if self.stop_event.is_set():
                        break

                imagem_fallback = self._baixar_imagem_produto_via_api(oferta_shopee)
                oferta_enviada_whatsapp = False
                try:
                    for grupo in self.settings.normalized_destinos():
                        if self.stop_event.is_set():
                            break

                        if (
                            self.settings.shopee_ofertas_nao_repetir
                            and db.link_ja_enviado(link_original, grupo)
                        ):
                            self._log(f"Oferta ja enviada anteriormente para {grupo}; pulando esse grupo.")
                            continue

                        self._status(f"Enviando oferta Shopee para {grupo}...")
                        tipo_envio = zap.enviar_texto_com_fallback_imagem(
                            grupo,
                            oferta.texto_final,
                            caminho_imagem=imagem_fallback,
                            aguardar_previa=self.settings.aguardar_previa_link,
                            timeout_previa_ms=self.settings.timeout_previa_link_ms,
                            tipo_destino=self.settings.destino_tipo,
                        )
                        if tipo_envio == "imagem":
                            self._log("Previa do link nao carregou. Imagem da API Shopee enviada como fallback.")
                        elif tipo_envio == "preview":
                            self._log("Oferta enviada com previa do link com imagem.")
                        elif tipo_envio == "nao_enviado_sem_imagem":
                            self._log(
                                "Oferta Shopee nao enviada: a previa nao carregou imagem "
                                "e nao havia imagem valida da API para fallback."
                            )
                            continue
                        elif str(tipo_envio).startswith("nao_enviado_falha_imagem:"):
                            motivo = str(tipo_envio).split(":", 1)[1]
                            self._log(f"Oferta Shopee nao enviada: falha ao anexar imagem de fallback. Detalhe: {motivo}")
                            continue
                        elif tipo_envio == "texto_sem_imagem":
                            self._log("Oferta enviada somente com texto: previa sem imagem e API nao trouxe imagem utilizavel.")
                        else:
                            self._log("Oferta enviada somente com texto.")
                        oferta_enviada_whatsapp = True
                        self.stats["enviadas"] += 1
                        self._emit_stats()

                        if not self.stop_event.is_set():
                            db.salvar_link_enviado(
                                oferta.link_original,
                                oferta.link_afiliado,
                                oferta.texto_final,
                                grupo,
                            )
                finally:
                    self._remover_imagem_temporaria(imagem_fallback)
                if not self.stop_event.is_set() and oferta_enviada_whatsapp:
                    enviadas_no_ciclo += 1
                    self._status("Oferta Shopee enviada. Aguardando proxima busca...")
                elif not self.stop_event.is_set():
                    self._status("Oferta Shopee pulada por falta de imagem.")

            except Exception as e:
                erros_no_ciclo += 1
                self.stats["erros"] += 1
                self._emit_stats()
                self._log("Erro ao processar/enviar oferta Shopee:")
                self._log(e)
                self._log(traceback.format_exc())
                try:
                    zap.limpar_preview_se_aberto()
                    zap.fechar_visualizador_midia()
                except Exception:
                    pass

        if enviadas_no_ciclo == 0:
            self._status("Busca Shopee concluida sem novos envios.")
        self._log("RESUMO DO CICLO MODO SHOPEE")
        self._log(f"Enviadas: {enviadas_no_ciclo}")
        self._log(f"Simuladas: {simuladas_no_ciclo}")
        self._log(f"Ignoradas por repeticao: {ignoradas_repetidas}")
        self._log(f"Ignoradas sem link: {ignoradas_sem_link}")
        self._log(f"Erros no ciclo: {erros_no_ciclo}")
        self._log(f"Meta do ciclo: {quantidade}")
        self._log(f"Proxima busca em aproximadamente {self._formatar_duracao(intervalo)}.")
        self._log("=" * 60)

    def _buscar_ofertas_colecao_para_ciclo(self, db, conversor, quantidade, link_colecao):
        """
        APROXIMACAO VIA API (substitui o antigo scraping da pagina de colecao).

        Uma "colecao" da Shopee (/collections/NNN) e uma lista curada: o
        conteudo dela NAO corresponde a nenhum filtro da API - por isso nao
        existe endpoint oficial que devolva "os produtos da colecao X", e por
        isso o scraping era necessario. Como a Shopee passou a bloquear esse
        scraping com captcha, aproximamos a colecao usando o que a API oferece:

          - Se o link for de uma LOJA (tem shopId, ex.: /shop/123... ou
            .123.456 no fim), buscamos as ofertas daquela loja via API
            (listType/shopId) - fidelidade alta para colecoes de loja.
          - Caso contrario (colecao curada generica), NAO da para reproduzir
            pela API. Avisamos e caimos na busca normal da Shopee (que respeita
            os filtros de palavra-chave/categoria/loja configurados na aba
            "Modo Shopee"). O usuario deve usar esses filtros para aproximar a
            colecao.
        """

        shop_id = conversor.extrair_shop_id_de_link(link_colecao)

        if shop_id:
            self._log(
                f"Link de colecao identificado como LOJA (shopId={shop_id}). "
                "Buscando ofertas dessa loja pela API (aproximacao da colecao)."
            )
            return self._buscar_ofertas_shopee_para_ciclo(
                db,
                conversor,
                quantidade=quantidade,
                limite_por_pagina=50,
                max_paginas=int(getattr(self.settings, "shopee_ofertas_max_paginas_busca", 8) or 8),
                shop_id_forcado=str(shop_id),
            )

        self._log(
            "O link informado e uma colecao curada da Shopee (nao e loja/categoria). "
            "A API da Shopee nao permite listar os produtos exatos de uma colecao, "
            "entao vou buscar ofertas pela API usando os filtros da aba \"Modo Shopee\" "
            "(palavra-chave / loja / categoria). Ajuste esses filtros para aproximar a "
            "colecao que voce quer."
        )
        return self._buscar_ofertas_shopee_para_ciclo(
            db,
            conversor,
            quantidade=quantidade,
            limite_por_pagina=50,
            max_paginas=int(getattr(self.settings, "shopee_ofertas_max_paginas_busca", 8) or 8),
        )

    def _buscar_ofertas_shopee_para_ciclo(self, db, conversor, quantidade, limite_por_pagina, max_paginas, shop_id_forcado=None):
        candidatas = []
        vistos_no_ciclo = set()
        total_recebido = 0
        total_filtrado = 0
        ignoradas_repetidas = 0
        ultimo_resultado = {}

        pagina_inicial = max(1, int(getattr(self.settings, "shopee_ofertas_pagina_atual", 1) or 1))
        atualizada_em = str(getattr(self.settings, "shopee_ofertas_pagina_atualizada_em", "") or "")

        if pagina_inicial > 1 and atualizada_em:
            segundos_parado = None
            try:
                instante_anterior = datetime.fromisoformat(atualizada_em)
                segundos_parado = (datetime.now() - instante_anterior).total_seconds()
            except ValueError:
                pass

            if segundos_parado is None or segundos_parado > RENOVACAO_PAGINA_SHOPEE_SEGUNDOS:
                self._log(
                    f"Faz mais de {self._formatar_duracao(RENOVACAO_PAGINA_SHOPEE_SEGUNDOS)} desde a ultima "
                    "busca Shopee (bot ficou parado/pausado). A lista de ofertas ja deve ter mudado nesse "
                    "tempo, entao reiniciando a varredura da pagina 1."
                )
                pagina_inicial = 1

        pagina = pagina_inicial
        paginas_percorridas = 0
        sweep_reiniciado = False

        self._log(f"Continuando busca Shopee a partir da pagina {pagina_inicial} (memoria do ciclo anterior).")

        while (
            paginas_percorridas < max_paginas
            and not self.stop_event.is_set()
            and len(candidatas) < quantidade
        ):
            self._log(f"Consultando ofertas Shopee - pagina {pagina}...")
            resultado = conversor.buscar_ofertas_shopee(
                self.settings,
                limite=limite_por_pagina,
                pagina=pagina,
                shop_id_forcado=shop_id_forcado,
            )
            ultimo_resultado = resultado
            ofertas_pagina = resultado.get("ofertas") or []
            total_recebido += int(resultado.get("total_recebido") or 0)
            total_filtrado += int(resultado.get("total_filtrado") or 0)
            paginas_percorridas += 1

            if paginas_percorridas == 1:
                self._log_diagnostico_colecao_shopee(resultado)

            tem_mais_paginas = resultado.get("tem_mais_paginas")
            pagina_esgotada = len(ofertas_pagina) < limite_por_pagina or tem_mais_paginas is False

            if not ofertas_pagina:
                self._log(f"Pagina {pagina}: nenhuma oferta passou pelos filtros.")
                if pagina_esgotada:
                    self._log("Fim da lista da Shopee para esses filtros; reiniciando da pagina 1 no proximo ciclo.")
                    pagina = 1
                    sweep_reiniciado = True
                    break
                pagina += 1
                continue

            novas_na_pagina = 0
            for oferta in ofertas_pagina:
                link_original = self._link_oferta_shopee(oferta)
                if not link_original:
                    candidatas.append(oferta)
                    novas_na_pagina += 1
                elif link_original in vistos_no_ciclo:
                    ignoradas_repetidas += 1
                    continue
                elif (
                    self.settings.shopee_ofertas_nao_repetir
                    and db.link_ja_enviado_para_todos(link_original, self.settings.normalized_destinos())
                ):
                    ignoradas_repetidas += 1
                    continue
                else:
                    vistos_no_ciclo.add(link_original)
                    candidatas.append(oferta)
                    novas_na_pagina += 1

                if len(candidatas) >= quantidade:
                    break

            self._log(
                f"Pagina {pagina}: {novas_na_pagina} nova(s), "
                f"{ignoradas_repetidas} repetida(s) acumulada(s)."
            )

            if pagina_esgotada:
                self._log("Fim da lista da Shopee para esses filtros; reiniciando da pagina 1 no proximo ciclo.")
                pagina = 1
                sweep_reiniciado = True
                break

            pagina += 1

        # Guarda em qual pagina o bot parou e quando, para o proximo ciclo continuar
        # dali (em vez de sempre reconsultar as mesmas paginas iniciais - principal
        # causa de o bot so encontrar ofertas repetidas) e para sabermos, na proxima
        # vez que o bot rodar, se essa memoria ja "venceu" (ver RENOVACAO_PAGINA_SHOPEE_SEGUNDOS).
        proxima_pagina = 1 if sweep_reiniciado else pagina
        if paginas_percorridas:
            self.settings.shopee_ofertas_pagina_atual = proxima_pagina
            self.settings.shopee_ofertas_pagina_atualizada_em = datetime.now().isoformat()
            try:
                self.settings.save()
            except Exception as erro_salvar:
                self._log(f"Nao consegui salvar a pagina atual da busca Shopee: {erro_salvar}")

        # A API da Shopee nao tem um sortType nativo para "maior desconto";
        # quando essa ordenacao esta selecionada, reordenamos aqui com os
        # dados de desconto ja recebidos.
        if str(getattr(self.settings, "shopee_ofertas_ordenacao", "")) == "maior_desconto":
            candidatas.sort(key=lambda oferta: oferta.get("desconto") or 0, reverse=True)

        resultado_final = dict(ultimo_resultado)
        resultado_final.update(
            {
                "ofertas": candidatas[:quantidade],
                "total_recebido": total_recebido,
                "total_filtrado": total_filtrado,
                "ignoradas_repetidas": ignoradas_repetidas,
                "paginas_consultadas": paginas_percorridas,
            }
        )
        return resultado_final

    def _log_diagnostico_colecao_shopee(self, resultado):
        link_colecao = (resultado.get("colecao_link") or "").strip()
        if not link_colecao:
            return

        parametros = (resultado.get("parametros_usados") or "").strip()

        # A "colecao" nao e mais filtrada pela API (a Shopee descontinuou o
        # filtro DETAIL_COLLECTION). Este link e usado apenas para APROXIMAR a
        # busca: se for de loja, buscamos a loja; senao, vale a busca normal
        # com os filtros da aba "Modo Shopee".
        self._log("Diagnostico do link informado no campo de colecao:")
        self._log(f"Link informado: {link_colecao}")
        if "shopId" in parametros:
            self._log("Aproximacao: buscando ofertas pela LOJA identificada no link.")
        else:
            self._log(
                "Aproximacao: link nao e de loja; usando os filtros da aba \"Modo Shopee\" "
                "(palavra-chave / loja / categoria) para aproximar a colecao."
            )
        if parametros:
            self._log(f"Parametros aceitos na chamada: {parametros}")

    def _link_oferta_shopee(self, dados):
        return (dados.get("link") or "").strip()

    def _baixar_imagem_produto_via_api(self, dados):
        """
        Baixa a imagem de um produto a partir da URL retornada pela API da
        Shopee (campo "imagem" da oferta normalizada). Usada tanto no modo
        Shopee (API) quanto no modo Grupo do WhatsApp, quando buscamos os
        dados do produto na API a partir do link capturado no grupo origem.
        """
        url = (dados.get("imagem") or "").strip()
        if not url:
            self._log("Imagem da API Shopee ausente nesta oferta.")
            return None
        if url.startswith("//"):
            url = "https:" + url
        if not url.lower().startswith(("http://", "https://")):
            self._log(f"Imagem da oferta ignorada: URL invalida ({url[:120]}).")
            return None

        try:
            pasta_temp = self._resolve_app_path("imagens_temp")
            pasta_temp.mkdir(parents=True, exist_ok=True)
            caminho = pasta_temp / f"shopee_{int(time.time() * 1000)}.jpg"

            requisicao = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(requisicao, timeout=20) as resposta:
                conteudo = resposta.read()

            if not conteudo:
                self._log("Imagem da API Shopee ignorada: download retornou vazio.")
                return None

            imagem = QImage()
            if not imagem.loadFromData(conteudo):
                self._log("Imagem da API Shopee ignorada: nao consegui converter para JPG.")
                return None

            if not imagem.save(str(caminho), "JPG", 92):
                self._log("Imagem da API Shopee ignorada: falha ao salvar JPG temporario.")
                return None

            self._log("Imagem da API Shopee baixada e convertida para JPG para fallback.")
            return str(caminho)
        except Exception as erro:
            self._log(f"Nao consegui baixar imagem da API Shopee: {erro}")
            return None

    def _remover_imagem_temporaria(self, caminho):
        if not caminho:
            return
        try:
            arquivo = Path(caminho)
            if arquivo.exists():
                arquivo.unlink()
        except Exception:
            pass
    def _criar_oferta_shopee(self, dados, conversor, link_original=None):
        link_original = (link_original or self._link_oferta_shopee(dados)).strip()
        if not link_original:
            self._log("Oferta Shopee ignorada: API nao retornou link do produto.")
            return None

        link_afiliado = conversor.converter_link(link_original)
        texto_base = self._montar_texto_base_shopee(dados, link_original)
        texto_final = formatar_texto_oferta(texto_base, link_afiliado)

        return Oferta(
            autor="Shopee API",
            texto_original=texto_base,
            links=[link_original],
            link_original=link_original,
            link_afiliado=link_afiliado,
            texto_final=texto_final,
            tem_imagem=False,
            id_mensagem=dados.get("item_id") or link_original,
        )

    def _montar_texto_base_shopee(self, dados, link_original):
        linhas = []
        nome = (dados.get("nome") or "Oferta Shopee").strip()
        linhas.append(nome)

        vendas = int(dados.get("vendas") or 0)
        if vendas:
            linhas.append(f"Mais de {vendas} vendidos!")

        desconto = float(dados.get("desconto") or 0)
        if desconto:
            linhas.append(f"Desconto: {desconto:g}%")

        avaliacao = float(dados.get("avaliacao") or 0)
        if avaliacao:
            linhas.append(f"Avaliacao: {avaliacao:g}/5")

        preco_pix = float(dados.get("preco_pix") or 0)
        preco_parcelado = float(dados.get("preco_parcelado") or 0)
        preco = float(dados.get("preco") or 0)
        if preco_pix and preco_parcelado and abs(preco_pix - preco_parcelado) >= 0.01:
            linhas.append(f"Por: {self._formatar_moeda(preco_pix)} no Pix")
            linhas.append(f"Ou: {self._formatar_moeda(preco_parcelado)} parcelado")
        elif preco_pix:
            linhas.append(f"Por: {self._formatar_moeda(preco_pix)} no Pix")
        elif preco:
            linhas.append(f"Por: {self._formatar_moeda(preco)}")

        cupom = str(getattr(self.settings, "shopee_ofertas_cupom", "") or "").strip()
        if cupom:
            linhas.append(f"Cupom: {cupom}")

        linhas.append(link_original)
        return "\n".join(linhas)

    def _formatar_moeda(self, valor):
        texto = f"{float(valor or 0):,.2f}"
        texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {texto}"

    def _formatar_duracao(self, segundos):
        segundos = int(segundos or 0)
        if segundos < 60:
            return f"{segundos} segundo(s)"
        minutos, resto = divmod(segundos, 60)
        if resto == 0:
            return f"{minutos} minuto(s)"
        return f"{minutos} minuto(s) e {resto} segundo(s)"

    def _registrar_oferta_processada(self, oferta):
        self._log("=" * 60)
        self._log("OFERTA PROCESSADA")
        self._log(f"LINK ORIGINAL: {oferta.link_original}")
        self._log(f"LINK AFILIADO: {oferta.link_afiliado}")
        self._log("TEXTO FINAL:")
        self._log(oferta.texto_final)
        self._log("=" * 60)
