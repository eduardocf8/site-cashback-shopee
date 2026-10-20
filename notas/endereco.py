"""Endereço do vendedor (tomador) a partir do relatório da Shopee.

O relatório traz o endereço em texto corrido, no formato
    "Rua X, 123, Complemento - Bairro, Cidade - Estado, 01234567"
É o mesmo endereço que outros emissores usam. A base pública da Receita não serve como fonte
principal: esconde rua e número dos MEIs e às vezes tem um CEP antigo, que o governo recusa
(E0240). O código do município vem da lista oficial do IBGE (pelo nome da cidade) ou, se a
cidade não estiver nela, do CEP (BrasilAPI e, se falhar, ViaCEP)."""

import json
import logging
import re
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import requests

from .receita import ReceitaFora, so_digitos

logger = logging.getLogger(__name__)

ESTADOS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}
_SEM_ACENTO = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
                            "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
FONTES_CEP = ["https://brasilapi.com.br/api/cep/v2/{}", "https://viacep.com.br/ws/{}/json/"]
DIAS_GUARDADO = 180


def _chave_cidade(nome: str) -> str:
    nome = (nome or "").translate(_SEM_ACENTO).lower().replace("'", " ").replace("-", " ").replace("`", " ")
    return " ".join(nome.split())


@lru_cache(maxsize=1)
def _municipios() -> dict:
    """{UF: {nome normalizado: código IBGE}}, da lista oficial do IBGE (municipios_ibge.json)."""
    with open(Path(__file__).with_name("municipios_ibge.json"), encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    return {uf: {_chave_cidade(nome): codigo for nome, codigo in cidades.items()} for uf, cidades in dados.items()}


def municipio(cidade: str, uf: str) -> str:
    """Código IBGE do município pelo nome e UF ("" se não achar)."""
    return _municipios().get((uf or "").upper(), {}).get(_chave_cidade(cidade), "")


def _limpo(texto: str) -> str:
    return " ".join((texto or "").split()).strip(" ,-")


def _uf(estado: str) -> str:
    estado = _limpo(estado)
    if re.fullmatch(r"[A-Za-z]{2}", estado):
        return estado.upper()
    return ESTADOS.get(estado.translate(_SEM_ACENTO).lower(), "")


def ler_do_relatorio(texto: str) -> dict | None:
    """Separa o endereço do relatório. None se não der para ler (endereço estrangeiro, sem CEP...)."""
    texto = " ".join((texto or "").split())
    achado = re.fullmatch(r"(?P<resto>.+),\s*(?P<cep>\d{5}-?\d{3})", texto)
    if not achado:
        return None
    cep, resto = so_digitos(achado["cep"]), achado["resto"]
    if "," not in resto:
        return None
    resto, cidade_estado = resto.rsplit(",", 1)
    cidade, _, estado = cidade_estado.rpartition(" - ")
    if " - " in resto:
        resto, bairro = resto.rsplit(" - ", 1)
    else:
        bairro = ""
    partes = [p.strip() for p in resto.split(",", 2)] + ["", ""]
    logradouro, numero, complemento = partes[0], partes[1], partes[2]
    if not logradouro:
        return None
    return {
        "logradouro": _limpo(logradouro), "numero": _limpo(numero), "complemento": _limpo(complemento),
        "bairro": _limpo(bairro), "cidade": _limpo(cidade), "uf": _uf(estado), "cep": cep,
    }


def _consultar_cep(cep: str) -> dict:
    """{"municipio_ibge", "uf", "cidade", "bairro", "logradouro"} ou {} se o CEP não existe.
    ReceitaFora se as duas fontes falharam agora."""
    nao_existe = 0
    for fonte in FONTES_CEP:
        try:
            r = requests.get(fonte.format(cep), timeout=10, headers={"User-Agent": "Appfiliado"})
        except requests.RequestException:
            continue
        if r.status_code in (400, 404):
            nao_existe += 1
            continue
        if r.status_code != 200:
            continue
        try:
            d = r.json()
        except ValueError:
            continue
        if d.get("erro"):  # ViaCEP responde 200 com {"erro": true}
            nao_existe += 1
            continue
        ibge = d.get("ibge")
        ibge = ibge.get("city") if isinstance(ibge, dict) else ibge
        if not ibge:
            continue
        return {"municipio_ibge": str(ibge)[:7], "uf": (d.get("state") or d.get("uf") or "")[:2],
                "cidade": d.get("city") or d.get("localidade") or "",
                "bairro": d.get("neighborhood") or d.get("bairro") or "",
                "logradouro": d.get("street") or d.get("logradouro") or ""}
    if nao_existe == len(FONTES_CEP):
        return {}
    raise ReceitaFora("Não consegui consultar o CEP agora. Tento de novo em alguns minutos.")


def cep(numero: str) -> dict:
    """Dados do CEP, guardados no banco por 180 dias ({} = CEP não existe)."""
    from django.utils import timezone

    from .models import CEPConsultado

    numero = so_digitos(numero)
    if len(numero) != 8:
        return {}
    guardado = CEPConsultado.objects.filter(
        cep=numero, consultado_em__gte=timezone.now() - timedelta(days=DIAS_GUARDADO)).first()
    if guardado is None:
        guardado, _ = CEPConsultado.objects.update_or_create(cep=numero, defaults={"dados": _consultar_cep(numero)})
    return guardado.dados


def completo(end: dict | None) -> bool:
    return bool(end and len(end.get("municipio_ibge", "")) == 7 and len(end.get("cep", "")) == 8
                and end.get("logradouro"))


def do_relatorio(texto: str, conferir_cep: bool = False) -> dict | None:
    """Endereço do relatório pronto para a nota, ou None se não der.

    O município sai da lista do IBGE pelo nome da cidade (sem consulta nenhuma). Só consulta o
    CEP se a cidade não estiver na lista ou se conferir_cep (quando o governo já recusou o CEP).
    ReceitaFora se a consulta do CEP falhou agora."""
    lido = ler_do_relatorio(texto)
    if not lido:
        return None
    codigo, dados = "" if conferir_cep else municipio(lido["cidade"], lido["uf"]), {}
    if not codigo:
        dados = cep(lido["cep"])
        if not dados:
            return None  # CEP não existe: o governo recusaria (E0240)
        codigo = dados["municipio_ibge"]
    return {
        "municipio_ibge": codigo, "cep": lido["cep"],
        "logradouro": lido["logradouro"] or dados.get("logradouro", ""),
        "numero": lido["numero"] or "S/N", "complemento": lido["complemento"],
        "bairro": lido["bairro"] or dados.get("bairro") or "-",
    }
