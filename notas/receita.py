"""Dados públicos de um CNPJ (Receita Federal) para preencher o cadastro sozinho.

Usa a BrasilAPI e, se ela falhar, a Minha Receita (mesmo formato, dados abertos da Receita).
Nenhuma das duas pede chave."""

import logging
import re

import requests

logger = logging.getLogger(__name__)

FONTES = ["https://brasilapi.com.br/api/cnpj/v1/{}", "https://minhareceita.org/{}"]


class ErroReceita(Exception):
    pass


class ReceitaFora(ErroReceita):
    """As duas fontes falharam agora (não é que o CNPJ não exista): tentar de novo depois."""


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def cnpj_valido(cnpj: str) -> bool:
    cnpj = so_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d) * p for d, p in zip(cnpj[:tamanho], pesos))
        digito = 0 if soma % 11 < 2 else 11 - soma % 11
        if int(cnpj[tamanho]) != digito:
            return False
    return True


def consultar(cnpj: str) -> dict:
    cnpj = so_digitos(cnpj)
    if not cnpj_valido(cnpj):
        raise ErroReceita("Esse CNPJ não é válido. Confira os números.")
    ultimo_erro = None
    for fonte in FONTES:
        try:
            r = requests.get(fonte.format(cnpj), timeout=12, headers={"User-Agent": "Appfiliado"})
        except requests.RequestException as erro:
            ultimo_erro = erro
            continue
        if r.status_code == 404:
            raise ErroReceita("Não achei esse CNPJ na Receita Federal.")
        if r.status_code != 200:
            ultimo_erro = r.status_code
            continue
        try:
            d = r.json()
        except ValueError:
            continue
        mei = bool(d.get("opcao_pelo_mei"))
        tipo = (d.get("descricao_tipo_de_logradouro") or "").strip()
        rua = (d.get("logradouro") or "").strip()
        return {
            "endereco": {
                "municipio_ibge": str(d.get("codigo_municipio_ibge") or "")[:7],
                "cep": so_digitos(d.get("cep"))[:8],
                "logradouro": f"{tipo} {rua}".strip() if rua and not rua.upper().startswith(tipo.upper()) else rua,
                "numero": (d.get("numero") or "").strip(),
                "complemento": " ".join((d.get("complemento") or "").split()),
                "bairro": (d.get("bairro") or "").strip(),
            },
            "cnpj": cnpj,
            "razao_social": (d.get("razao_social") or "").strip()[:150],
            "municipio_ibge": str(d.get("codigo_municipio_ibge") or "")[:7],
            "municipio_nome": (d.get("municipio") or "").title()[:80],
            "uf": (d.get("uf") or "")[:2],
            "regime": "mei" if mei else ("simples" if d.get("opcao_pelo_simples") else ""),
            "ativa": (d.get("descricao_situacao_cadastral") or "").upper() == "ATIVA",
        }
    logger.warning("Notas: consulta de CNPJ falhou nas duas fontes (%s).", ultimo_erro)
    raise ReceitaFora("Não consegui consultar a Receita agora. Tente de novo em alguns minutos.")


def endereco(cnpj: str) -> dict:
    """Endereço do CNPJ (Receita), guardado no banco por 180 dias."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import CadastroCNPJ

    cnpj = so_digitos(cnpj)
    guardado = CadastroCNPJ.objects.filter(cnpj=cnpj, consultado_em__gte=timezone.now() - timedelta(days=180)).first()
    if guardado is None:
        guardado, _ = CadastroCNPJ.objects.update_or_create(cnpj=cnpj, defaults={"dados": consultar(cnpj)})
    return guardado.dados.get("endereco") or {}
