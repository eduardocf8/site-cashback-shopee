"""
provedor.py
-----------
Camada que fala com a API do provedor (ex.: Focus NFe).

Isolei tudo que é específico do provedor aqui. Se um dia você trocar de
provedor, em teoria só este arquivo muda; o resto do projeto continua igual.

IMPORTANTE: os nomes exatos dos campos JSON (montar_payload) e os endpoints
precisam bater com a documentação atual da API que você contratar. Os que
estão aqui são baseados no que a busca pela doc pública da Focus indicou,
mas o acesso direto a doc.focusnfe.com.br NÃO estava disponível neste
ambiente para confirmar campo a campo. CONFIRME antes de ir para produção:
    https://doc.focusnfe.com.br/reference/emitir_dps_nacional

Pontos que precisam de confirmação manual na doc:
  - Endpoint exato de emissão/consulta da NFS-e Nacional (usamos "v2/nfsen"
    abaixo, distinto do endpoint legado "v2/nfse" usado no padrão municipal
    antigo — no modelo Nacional você envia uma DPS e o ambiente nacional
    emite a NFS-e a partir dela).
  - Nomes e obrigatoriedade dos campos de Reforma Tributária (CTN/NBS/
    cClassTrib/cIndOp) em config.SERVICO.
  - Comportamento de idempotência nativo da API ao reenviar a mesma "ref"
    (por isso este módulo faz uma checagem defensiva antes de emitir —
    ver `emitir()`).

Instale a dependência antes de rodar:
    pip install requests
"""

import time
from decimal import Decimal

import requests

import config


# Endpoint de NFS-e Nacional. CONFIRMAR na doc antes de produção (ver módulo).
ENDPOINT_NFSE = "/v2/nfsen"

# Status que indicam que a nota já existe/está em curso para aquela
# referência e, portanto, NÃO deve ser reenviada. Lista best-effort — ajuste
# conforme os valores reais devolvidos pela API (visto em pesquisa:
# "processando_autorizacao", "autorizado", "cancelado").
STATUS_JA_PROCESSADOS = {"processando_autorizacao", "autorizado", "cancelado"}


class ErroEmissao(Exception):
    """Falha ao emitir uma nota."""


def montar_payload(registro: dict) -> dict:
    """Converte um registro de comissão no JSON que a API espera.

    ---- ESTE É O PONTO MAIS SENSÍVEL DO PROJETO ----
    A estrutura abaixo é um MODELO. Os campos, nomes e obrigatoriedade da
    NFS-e Nacional variam. Ajuste conforme a doc do provedor + orientação
    do contador (código de serviço, ISS, retenção, CTN, NBS etc.).
    """
    valor = registro["valor"]
    aliquota = Decimal(str(config.SERVICO["aliquota_iss"]))
    valor_iss = (valor * aliquota).quantize(Decimal("0.01"))

    doc = registro["tomador_documento"]
    tomador = {"razao_social": registro["tomador_nome"]}
    if len(doc) == 14:
        tomador["cnpj"] = doc
    else:
        tomador["cpf"] = doc
    if registro["tomador_email"]:
        tomador["email"] = registro["tomador_email"]

    payload = {
        "data_emissao": time.strftime("%Y-%m-%d"),
        "prestador": {
            "cnpj": config.PRESTADOR["cnpj"],
            "inscricao_municipal": config.PRESTADOR["inscricao_municipal"],
            "codigo_municipio": config.PRESTADOR["codigo_municipio"],
        },
        "tomador": tomador,
        "servico": {
            "aliquota": float(aliquota),
            "discriminacao": registro["descricao"],
            "iss_retido": config.SERVICO["iss_retido"],
            "item_lista_servico": config.SERVICO["codigo_servico_lc116"],
            "codigo_cnae": config.SERVICO["cnae"],
            "codigo_municipio": config.PRESTADOR["codigo_municipio"],
            "valor_servicos": float(valor),
            "valor_iss": float(valor_iss),

            # Campos exigidos pela NFS-e Nacional / Reforma Tributária.
            # NOME E OBRIGATORIEDADE NÃO CONFIRMADOS NA DOC — ver aviso no
            # topo do arquivo antes de emitir em produção.
            "codigo_tributacao_nacional": config.SERVICO["codigo_tributacao_nacional"],
            "codigo_nbs": config.SERVICO["codigo_nbs"],
        },
    }
    return payload


def _ja_emitida(referencia: str) -> dict | None:
    """Checagem defensiva de idempotência.

    Não confiamos apenas no comportamento nativo da API para a mesma "ref"
    (não confirmado na doc). Antes de emitir, consultamos a referência: se
    ela já existe com um status que indica processamento em curso ou
    concluído, não reenviamos e devolvemos o resultado da consulta.

    Se a consulta falhar por rede, não bloqueia a emissão (deixa a tentativa
    de POST seguir; melhor tentar emitir do que travar o lote inteiro por
    uma falha transitória de GET).
    """
    try:
        existente = consultar(referencia)
    except ErroEmissao:
        return None

    if existente["http_status"] == 200:
        corpo = existente["corpo"]
        status_atual = corpo.get("status") if isinstance(corpo, dict) else None
        if status_atual in STATUS_JA_PROCESSADOS:
            return existente
    return None


def emitir(referencia: str, registro: dict) -> dict:
    """Envia uma nota para emissão.

    'referencia' é um identificador único SEU para essa nota (idempotência).
    Use algo estável, como f"comissao-{ano}{mes}-{linha}", para poder
    reconsultar/reenviar sem duplicar.

    Antes de emitir, verifica defensivamente se essa referência já foi
    processada (ver `_ja_emitida`), para não depender só do comportamento
    nativo (não confirmado) da API para "ref" repetida.

    Retorna o dict de resposta da API. Levanta ErroEmissao em falha de rede.
    """
    ja_existe = _ja_emitida(referencia)
    if ja_existe is not None:
        return {**ja_existe, "ja_existia": True}

    url = f"{config.BASE_URL}{ENDPOINT_NFSE}?ref={referencia}"
    payload = montar_payload(registro)

    try:
        resp = requests.post(
            url,
            json=payload,
            auth=(config.PROVIDER_TOKEN, ""),  # Focus usa token como usuário, senha vazia
            timeout=30,
        )
    except requests.RequestException as e:
        raise ErroEmissao(f"Falha de rede ao emitir '{referencia}': {e}")

    # A API costuma responder 202 (aceito, processando de forma assíncrona)
    # ou 4xx com o motivo da rejeição. Tratamos ambos como resultado.
    try:
        corpo = resp.json()
    except ValueError:
        corpo = {"resposta_bruta": resp.text}

    return {
        "referencia": referencia,
        "http_status": resp.status_code,
        "corpo": corpo,
        "ja_existia": False,
    }


def consultar(referencia: str) -> dict:
    """Consulta o status de uma nota já enviada, pela sua referência.

    Útil porque a emissão é assíncrona: você envia, a prefeitura processa,
    e depois você consulta para saber se autorizou e pegar o link do PDF/XML.
    """
    url = f"{config.BASE_URL}{ENDPOINT_NFSE}/{referencia}"
    try:
        resp = requests.get(
            url,
            auth=(config.PROVIDER_TOKEN, ""),
            timeout=30,
        )
    except requests.RequestException as e:
        raise ErroEmissao(f"Falha de rede ao consultar '{referencia}': {e}")

    try:
        corpo = resp.json()
    except ValueError:
        corpo = {"resposta_bruta": resp.text}

    return {"referencia": referencia, "http_status": resp.status_code, "corpo": corpo}
