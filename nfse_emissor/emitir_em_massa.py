"""
emitir_em_massa.py
------------------
Script principal. Lê o CSV de comissões e dispara a emissão de uma NFS-e
por linha, com pausa entre chamadas, log de tudo e possibilidade de
reprocessar só o que falhou.

COMO USAR (fluxo recomendado):
  1) pip install requests
  2) Preencha config.py e valide os parâmetros fiscais com seu contador.
  3) Deixe USAR_PRODUCAO = False (homologação) e rode com POUCAS linhas:
         python emitir_em_massa.py
  4) Confira o resultado em notas_emitidas/resultado_YYYYMMDD_HHMMSS.csv
  5) Só depois de tudo certo, mude para produção.

O script é IDEMPOTENTE por referência: cada linha vira uma referência única
tipo "comissao-202608-2". Reenviar o script com o mesmo CSV/competência não
duplica a nota — antes de emitir, `provedor.emitir()` consulta a referência
e pula o envio se ela já estiver em processamento/autorizada (ver
provedor.py). Isso não depende só do comportamento nativo da API para "ref"
repetida, que ainda não foi confirmado na documentação.
"""

import csv
import os
import time

import config
import leitor_comissoes
import provedor


# Segundos de pausa entre uma emissão e outra. Evita estourar limites de taxa
# da API e dá fôlego ao Portal Nacional (que pode ficar instável).
PAUSA_ENTRE_EMISSOES = 1.0


def _competencia() -> str:
    """Retorna o mês de referência, ex. '202608'. Usado na referência da nota."""
    return time.strftime("%Y%m")


def _referencia(registro: dict) -> str:
    return f"comissao-{_competencia()}-{registro['linha_origem']}"


def _garantir_pasta_saida():
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)


def _sucesso(resultado: dict) -> bool:
    """Define o que consideramos 'aceito' pela API.

    Focus: 202 = enviado para processamento (assíncrono). 200 também conta
    quando a referência já existia (ver provedor._ja_emitida). Ajuste se
    necessário.
    """
    return resultado["http_status"] in (200, 201, 202)


def emitir_lote(registros: list) -> list:
    """Emite cada registro e devolve uma lista de resultados."""
    _garantir_pasta_saida()
    resultados = []
    total = len(registros)

    for idx, registro in enumerate(registros, start=1):
        ref = _referencia(registro)
        print(f"[{idx}/{total}] emitindo {ref} "
              f"(tomador {registro['tomador_nome']}, "
              f"R$ {registro['valor']})... ", end="", flush=True)

        try:
            resultado = provedor.emitir(ref, registro)
            ok = _sucesso(resultado)
            if resultado.get("ja_existia"):
                print("JÁ EMITIDA (pulada)")
            else:
                print("OK" if ok else f"REJEITADO ({resultado['http_status']})")
        except provedor.ErroEmissao as e:
            resultado = {"referencia": ref, "http_status": None,
                         "corpo": {"erro": str(e)}, "ja_existia": False}
            ok = False
            print(f"ERRO DE REDE")

        resultados.append({
            "referencia": ref,
            "linha_origem": registro["linha_origem"],
            "tomador": registro["tomador_nome"],
            "documento": registro["tomador_documento"],
            "valor": str(registro["valor"]),
            "sucesso": ok,
            "ja_existia": resultado.get("ja_existia", False),
            "http_status": resultado["http_status"],
            "detalhe": str(resultado["corpo"]),
        })

        time.sleep(PAUSA_ENTRE_EMISSOES)

    return resultados


def salvar_resultado(resultados: list) -> str:
    carimbo = time.strftime("%Y%m%d_%H%M%S")
    caminho = os.path.join(config.PASTA_SAIDA, f"resultado_{carimbo}.csv")
    campos = ["referencia", "linha_origem", "tomador", "documento",
              "valor", "sucesso", "ja_existia", "http_status", "detalhe"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(resultados)
    return caminho


def resumo(resultados: list):
    ok = sum(1 for r in resultados if r["sucesso"])
    falhas = len(resultados) - ok
    ja_existiam = sum(1 for r in resultados if r["ja_existia"])
    print("\n" + "=" * 50)
    print(f"Total processado : {len(resultados)}")
    print(f"Aceitas          : {ok}")
    print(f"  (já existiam)  : {ja_existiam}")
    print(f"Falhas/rejeições : {falhas}")
    if falhas:
        print("\nRevise as linhas com falha no CSV de resultado antes de reenviar.")
    print("=" * 50)


def main():
    print(f"Ambiente: {'PRODUÇÃO' if config.USAR_PRODUCAO else 'HOMOLOGAÇÃO (teste)'}")
    print(f"Lendo {config.ARQUIVO_ENTRADA}...\n")

    registros = leitor_comissoes.ler()
    if not registros:
        print("Nenhum registro válido para emitir. Encerrando.")
        return

    # Trava de segurança: confirma antes de disparar em massa
    print(f"\n{len(registros)} nota(s) serão emitidas.")
    if config.USAR_PRODUCAO:
        confirma = input("Você está em PRODUÇÃO. Digite 'EMITIR' para confirmar: ")
        if confirma.strip() != "EMITIR":
            print("Cancelado.")
            return

    resultados = emitir_lote(registros)
    caminho = salvar_resultado(resultados)
    resumo(resultados)
    print(f"\nResultado salvo em: {caminho}")
    print("Use consultar_status.py depois para checar a autorização e baixar PDFs/XMLs.")


if __name__ == "__main__":
    main()
