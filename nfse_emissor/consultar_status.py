"""
consultar_status.py
-------------------
A emissão de NFS-e é assíncrona: você envia, a prefeitura processa, e só
depois a nota fica 'autorizada'. Este script relê o último CSV de resultado
e consulta o status atual de cada referência, mostrando quais autorizaram
e (quando a API devolver) os links de PDF/XML.

Uso:
    python consultar_status.py
"""

import csv
import glob
import os

import config
import provedor


def _ultimo_resultado() -> str:
    padrao = os.path.join(config.PASTA_SAIDA, "resultado_*.csv")
    arquivos = sorted(glob.glob(padrao))
    if not arquivos:
        raise FileNotFoundError(
            "Nenhum arquivo de resultado encontrado. Rode emitir_em_massa.py antes."
        )
    return arquivos[-1]


def main():
    caminho = _ultimo_resultado()
    print(f"Consultando status das notas de: {caminho}\n")

    with open(caminho, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    for linha in linhas:
        ref = linha["referencia"]
        try:
            r = provedor.consultar(ref)
            corpo = r["corpo"]
            status = corpo.get("status", "?") if isinstance(corpo, dict) else "?"
            print(f"{ref:30s} status={status}")

            # Quando autorizada, a Focus costuma devolver caminhos de PDF/XML.
            # Nomes de campo não confirmados na doc (ver provedor.py) —
            # ajuste esta lista se a API devolver chaves diferentes.
            if isinstance(corpo, dict):
                for chave in ("url", "caminho_xml_nota_fiscal",
                              "caminho_danfse", "url_danfse"):
                    if corpo.get(chave):
                        print(f"    {chave}: {corpo[chave]}")
        except provedor.ErroEmissao as e:
            print(f"{ref:30s} ERRO: {e}")


if __name__ == "__main__":
    main()
