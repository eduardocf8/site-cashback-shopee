"""Radar de ofertas (menu, todos os planos): os produtos da API de afiliados da Shopee
por mais vendidos, maior comissão ou maior desconto, com filtros. Cada página do radar
é uma página da API (50 produtos) já filtrada; a busca fica guardada 15 minutos."""

import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.cache import cache

from bot_whatsapp import shopee_ofertas
from bot_whatsapp.categorias import opcoes_categoria
from bot_whatsapp.models import ConfiguracaoOfertas

ORDENS = [("mais_vendidos", "Mais vendidos"), ("maior_comissao", "Maior comissão"), ("maior_desconto", "Maior desconto")]
VALIDADE_DO_CACHE = 15 * 60
SUB_ID = "radar"
# Cada busca da API tem o seu próprio fim (o "hasNextPage" da Shopee diz quando acabou):
# medido em 10/2026, o feed geral para em 56 páginas (1.572 produtos diferentes, porque ele
# repete itens) e cada palavra-chave em 40. Este teto é só de segurança.
MAXIMO_PAGINAS = 200


def _numero(texto, minimo=0, maximo=None):
    texto = str(texto or "").strip().replace("R$", "").replace(" ", "")
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    if valor < minimo or (maximo is not None and valor > maximo):
        return None
    return valor


def filtros_da_requisicao(dados) -> dict:
    categorias = {c for c, _ in opcoes_categoria()}
    ordem = dados.get("ordem") if dados.get("ordem") in dict(ORDENS) else "mais_vendidos"
    categoria = dados.get("categoria") if dados.get("categoria") in categorias else ""
    return {
        "palavra": " ".join(str(dados.get("palavra", "")).split())[:80],
        "ordem": ordem,
        "categoria": categoria,
        "preco_min": _numero(dados.get("preco_min")),
        "preco_max": _numero(dados.get("preco_max")),
        "comissao_min": _numero(dados.get("comissao_min"), 0, 100),
        "desconto_min": _numero(dados.get("desconto_min"), 0, 100),
        "avaliacao_min": _numero(dados.get("avaliacao_min"), 0, 5),
        "so_extra": dados.get("so_extra") in ("1", "on", "true"),
    }


def _busca(filtros) -> ConfiguracaoOfertas:
    """Uma configuração de busca (não salva) para reaproveitar a busca e os filtros do bot."""
    if filtros["palavra"]:
        tipo = ConfiguracaoOfertas.BUSCA_PALAVRA
    elif filtros["categoria"]:
        tipo = ConfiguracaoOfertas.BUSCA_CATEGORIA
    else:
        tipo = ConfiguracaoOfertas.BUSCA_GERAL
    return ConfiguracaoOfertas(
        tipo_busca=tipo, palavra_chave=filtros["palavra"], categorias=[filtros["categoria"]] if filtros["categoria"] else [],
        ordenacao=filtros["ordem"], comissao_minima=int(filtros["comissao_min"] or 0),
        desconto_minimo=int(filtros["desconto_min"] or 0), preco_minimo=filtros["preco_min"],
        preco_maximo=filtros["preco_max"], avaliacao_minima=filtros["avaliacao_min"], vendas_minimas=0,
    )


def buscar(conta, filtros, pagina: int) -> tuple[list[dict], bool]:
    """(produtos que passam nos filtros, tem próxima página). Levanta o erro da Shopee."""
    from bot_whatsapp.ofertas import credenciais

    pagina = max(1, min(int(pagina or 1), MAXIMO_PAGINAS))
    chave = "radar:%s:%s" % (conta.pk, hashlib.sha1(
        json.dumps({**filtros, "pagina": pagina}, default=str, sort_keys=True).encode()).hexdigest()[:20])
    guardado = cache.get(chave)
    if guardado is not None:
        return guardado
    app_id, secret = credenciais(conta)
    busca = _busca(filtros)
    produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, busca, pagina)
    produtos = [p for p in produtos if shopee_ofertas.passa_nos_filtros(p, busca)
                and (not filtros["so_extra"] or p.get("comissao_extra", 0) > 0)]
    for p in produtos:
        p["ganho"] = round(p["preco"] * p["comissao"] / 100, 2)  # comissão estimada por venda
    resultado = (produtos, tem_proxima and pagina < MAXIMO_PAGINAS)
    cache.set(chave, resultado, VALIDADE_DO_CACHE)
    return resultado
