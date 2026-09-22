import os
import socket
import subprocess
import time


PORTA_CHROME = 9222

PASTA_PERFIL_CHROME = r"C:\ChromeBot"
PERFIL_CHROME = "Default"


def chrome_debug_aberto():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        sock.connect(("127.0.0.1", PORTA_CHROME))
        return True
    except:
        return False
    finally:
        sock.close()


def encontrar_chrome():
    caminhos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]

    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho

    raise Exception("Não encontrei o Google Chrome instalado.")


def iniciar_chrome():
    if chrome_debug_aberto():
        print("Chrome da Shopee já está aberto.")
        return

    chrome = encontrar_chrome()

    print("Abrindo Chrome da Shopee com perfil real...")

    subprocess.Popen([
        chrome,
        f"--remote-debugging-port={PORTA_CHROME}",
        f"--user-data-dir={PASTA_PERFIL_CHROME}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        "https://affiliate.shopee.com.br/offer/custom_link"
    ])

    for _ in range(40):
        if chrome_debug_aberto():
            print("Chrome da Shopee pronto.")
            return

        time.sleep(1)

    raise Exception("Não consegui iniciar o Chrome com depuração remota.")