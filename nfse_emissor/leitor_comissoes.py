"""
leitor_comissoes.py
--------------------
Lê o relatório de comissões (CSV) e devolve uma lista de dicionários, um por
nota a emitir. Faz validações básicas para evitar disparar emissão com dado
faltando ou inválido.

FORMATO ESPERADO DO CSV (cabeçalho na primeira linha):
    tomador_cnpj_cpf,tomador_nome,tomador_email,valor_comissao,descricao

- tomador_cnpj_cpf : CNPJ (14 díg.) ou CPF (11 díg.) do vendedor, só números
- tomador_nome     : razão social / nome do vendedor
- tomador_email    : e-mail para envio da nota (pode ficar vazio)
- valor_comissao   : valor da comissão extra, ex. 12.34  (use ponto decimal)
- descricao        : opcional; se vazio, usa a descrição padrão do config

NOTA: este formato ainda é o do esqueleto (comissoes_exemplo.csv), não o
relatório real exportado pela Shopee. Ajuste os nomes das colunas assim que
tiver um exemplo real do relatório da Shopee.
"""

import csv
import os
from decimal import Decimal, InvalidOperation

import config


class LinhaInvalida(Exception):
    """Erro de validação em uma linha do CSV."""


def _so_digitos(texto: str) -> str:
    return "".join(c for c in (texto or "") if c.isdigit())


def _cpf_valido(cpf: str) -> bool:
    if len(set(cpf)) == 1:  # todos os dígitos iguais (000..., 111...)
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * ((tamanho + 1) - i) for i in range(tamanho))
        dv = (soma * 10) % 11
        dv = 0 if dv == 10 else dv
        if dv != int(cpf[tamanho]):
            return False
    return True


def _cnpj_valido(cnpj: str) -> bool:
    if len(set(cnpj)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(pos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(cnpj[pos]):
            return False
    return True


def _validar_documento(doc: str, linha_num: int) -> str:
    doc = _so_digitos(doc)
    if len(doc) not in (11, 14):
        raise LinhaInvalida(
            f"Linha {linha_num}: documento do tomador deve ter 11 (CPF) ou "
            f"14 (CNPJ) dígitos; recebido '{doc}' ({len(doc)} dígitos)."
        )
    if len(doc) == 11 and not _cpf_valido(doc):
        raise LinhaInvalida(
            f"Linha {linha_num}: CPF '{doc}' é inválido (dígito verificador)."
        )
    if len(doc) == 14 and not _cnpj_valido(doc):
        raise LinhaInvalida(
            f"Linha {linha_num}: CNPJ '{doc}' é inválido (dígito verificador)."
        )
    return doc


def _validar_valor(valor_str: str, linha_num: int) -> Decimal:
    # aceita "12,34" ou "12.34"
    valor_str = (valor_str or "").strip().replace(",", ".")
    try:
        valor = Decimal(valor_str)
    except (InvalidOperation, AttributeError):
        raise LinhaInvalida(
            f"Linha {linha_num}: valor '{valor_str}' não é um número válido."
        )
    if valor <= 0:
        raise LinhaInvalida(
            f"Linha {linha_num}: valor da comissão deve ser maior que zero."
        )
    return valor


def ler(caminho: str = None) -> list:
    """Lê o CSV e retorna lista de dicts prontos para emissão.

    Levanta FileNotFoundError se o arquivo não existir.
    Linhas inválidas são coletadas e reportadas juntas ao final,
    para você corrigir tudo de uma vez em vez de descobrir de uma em uma.
    """
    caminho = caminho or config.ARQUIVO_ENTRADA
    if not os.path.exists(caminho):
        raise FileNotFoundError(
            f"Arquivo de entrada '{caminho}' não encontrado. "
            f"Exporte o relatório da Shopee e salve com esse nome."
        )

    registros = []
    erros = []

    with open(caminho, newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        for i, linha in enumerate(leitor, start=2):  # start=2: linha 1 é o cabeçalho
            try:
                doc = _validar_documento(linha.get("tomador_cnpj_cpf", ""), i)
                valor = _validar_valor(linha.get("valor_comissao", ""), i)
                nome = (linha.get("tomador_nome") or "").strip()
                if not nome:
                    raise LinhaInvalida(f"Linha {i}: nome do tomador vazio.")

                descricao = (linha.get("descricao") or "").strip()
                if not descricao:
                    descricao = config.SERVICO["descricao_padrao"]

                registros.append({
                    "linha_origem": i,
                    "tomador_documento": doc,
                    "tomador_nome": nome,
                    "tomador_email": (linha.get("tomador_email") or "").strip(),
                    "valor": valor,
                    "descricao": descricao,
                })
            except LinhaInvalida as e:
                erros.append(str(e))

    if erros:
        print("⚠️  Foram encontrados problemas no CSV:")
        for e in erros:
            print("   -", e)
        print(f"\n{len(erros)} linha(s) com erro NÃO serão emitidas. "
              f"{len(registros)} linha(s) OK.")

    return registros
