import queue
import time

from playwright.sync_api import sync_playwright

from chrome_manager import iniciar_chrome
from config import *
from database import Database
from parser import gerar_id_mensagem, extrair_links_shopee
from processor import processar_mensagem
from whatsapp import WhatsApp
from afiliados import ConversorAfiliados


fila_mensagens = queue.Queue()

iniciar_chrome()

play = sync_playwright().start()

db = Database()
zap = WhatsApp(play, headless=HEADLESS)
conversor = ConversorAfiliados(play, headless=HEADLESS)

# Abre o grupo origem uma vez no inicio.
zap.preparar_monitoramento_origem(GRUPO_ORIGEM)


def marcar_historico_como_lido():
    mensagens_iniciais = zap.capturar_mensagens()

    print(f"Marcando {len(mensagens_iniciais)} mensagens visiveis como lidas...")

    for msg in mensagens_iniciais:
        if not msg.get("texto"):
            continue

        id_msg = gerar_id_mensagem(
            msg.get("autor"),
            msg.get("texto"),
            msg.get("link")
        )

        db.salvar(
            id_msg,
            msg.get("autor"),
            msg.get("texto"),
            msg.get("link")
        )

    print("Historico ignorado. Aguardando novas mensagens...")
    print()


def capturar_novas_mensagens():
    """Captura novas mensagens de oferta sem baixar imagens."""
    mensagens = zap.capturar_mensagens()

    for msg in mensagens:
        if not msg.get("texto"):
            continue

        id_msg = gerar_id_mensagem(
            msg.get("autor"),
            msg.get("texto"),
            msg.get("link")
        )

        if db.existe(id_msg):
            continue

        db.salvar(
            id_msg,
            msg.get("autor"),
            msg.get("texto"),
            msg.get("link")
        )

        links_shopee = extrair_links_shopee(msg.get("texto"))

        if not links_shopee:
            if msg.get("link"):
                print("Mensagem nova ignorada: link nao e Shopee.")
            else:
                print("Mensagem nova ignorada: sem link.")
            continue

        msg["link"] = links_shopee[0]
        msg["links_shopee"] = links_shopee
        fila_mensagens.put(msg)
        print("Mensagem nova com link Shopee adicionada a fila.")


def processar_fila():
    while not fila_mensagens.empty():
        msg = fila_mensagens.get()

        try:
            oferta = processar_mensagem(msg, conversor)

            if oferta is None:
                print("Mensagem ignorada: sem oferta valida.")
                continue

            print("=" * 60)
            print("OFERTA PROCESSADA")
            print()
            print("AUTOR:")
            print(oferta.autor)
            print()
            print("LINK ORIGINAL:")
            print(oferta.link_original)
            print()
            print("LINK AFILIADO:")
            print(oferta.link_afiliado)
            print()
            print("TEXTO FINAL:")
            print(oferta.texto_final)
            print("=" * 60)
            print()

            for grupo in GRUPOS_DESTINO:
                zap.enviar_texto(
                    grupo,
                    oferta.texto_final,
                    aguardar_previa=AGUARDAR_PREVIA_LINK,
                    timeout_previa_ms=TIMEOUT_PREVIA_LINK_MS
                )

            zap.preparar_monitoramento_origem(GRUPO_ORIGEM)
            print("Oferta enviada e bot voltou para o grupo de origem.")
            print()

        except Exception as e:
            print("Erro ao processar/enviar oferta:")
            print(e)

            try:
                zap.limpar_preview_se_aberto()
                zap.fechar_visualizador_midia()
                zap.preparar_monitoramento_origem(GRUPO_ORIGEM)
                print("Bot recuperado e voltou para o grupo de origem.")
            except Exception as erro_recuperacao:
                print("Erro ao tentar recuperar o bot:")
                print(erro_recuperacao)

        finally:
            fila_mensagens.task_done()


try:
    if not PROCESSAR_HISTORICO_AO_INICIAR and db.quantidade() == 0:
        marcar_historico_como_lido()
    else:
        print("Processando mensagens novas encontradas no historico visivel...")

    print("Monitorando mensagens...")
    print()

    while True:
        capturar_novas_mensagens()
        processar_fila()
        time.sleep(INTERVALO / 1000)

except KeyboardInterrupt:
    print("Bot interrompido pelo usuario.")

finally:
    db.fechar()
    zap.fechar()
    conversor.fechar()
    play.stop()
