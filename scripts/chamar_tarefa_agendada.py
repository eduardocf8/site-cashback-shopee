#!/usr/bin/env python3
"""Chama um endereço de tarefa agendada do site (/tarefas/...).

Usado pelos Cron Jobs do Render em vez do agendador do GitHub Actions - o agendador
gratuito do GitHub atrasava demais (às vezes várias horas) pra esse repositório, ver
"Cron Jobs do Render" em marketing/instagram/README.md. Fica fora do Django de
propósito (só depende de TAREFAS_TOKEN e requests) - o Cron Job não precisa do resto
das variáveis de ambiente do app (banco, chaves de API etc.) só pra fazer 1 chamada
HTTP, então evita ter que configurar tudo isso de novo num serviço separado.

Uso: python3 scripts/chamar_tarefa_agendada.py /tarefas/executar/
"""
import os
import sys
import time

import requests

DOMINIO = "https://cash-b.com"
TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 15
TIMEOUT_SEGUNDOS = 300


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: chamar_tarefa_agendada.py <caminho, ex: /tarefas/executar/>", file=sys.stderr)
        sys.exit(2)

    token = os.environ.get("TAREFAS_TOKEN")
    if not token:
        print("TAREFAS_TOKEN não configurado nesse Cron Job.", file=sys.stderr)
        sys.exit(1)

    url = f"{DOMINIO}{sys.argv[1]}?token={token}"

    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
            resposta.raise_for_status()
            print(f"OK ({resposta.status_code}): {resposta.text[:500]}")
            return
        except requests.RequestException as erro:
            ultimo_erro = erro
            print(f"Tentativa {tentativa}/{TENTATIVAS} falhou: {erro}", file=sys.stderr)
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_SEGUNDOS)

    print(f"Todas as {TENTATIVAS} tentativas falharam: {ultimo_erro}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
