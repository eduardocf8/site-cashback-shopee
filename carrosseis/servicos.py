"""Gerador de carrosséis: do link da Shopee ao carrossel salvo, e o que pode ser salvo
depois, conforme o plano (Standard ou Premium)."""

import re

from django.db.models import F
from django.utils import timezone

from bot_whatsapp import copia, shopee_ofertas
from bot_whatsapp.ofertas import credenciais
from licencas import planos
from licencas.models import MODULO_CARROSSEIS_PREMIUM
from links.shopee_client import ShopeeAPIError

from . import ia
from . import roteiro as R
from .models import Carrossel, PadraoCarrossel, UsoCarrossel

SUB_ID = "instagram"
# Limites por dia de cada plano: licencas/planos.py (Standard 3 gerações; Premium 10 e as reescritas).
REESCRITAS_POR_DIA = planos.CARROSSEIS[True]["reescritas"]
MODELOS = {
    R.PADRAO: ["destaque", "editorial", "promo", "neon", "polaroid", "bento"],
    R.PREMIUM: ["vitrine", "anotado", "etiqueta", "ficha"],
}
TEMAS = ["verde", "laranja", "rosa", "azul", "preto"]
FONTES = ["modelo", "moderna", "geometrica", "impacto", "elegante", "serifa"]
COR = re.compile(r"^#[0-9a-fA-F]{6}$")
ARROBA = re.compile(r"^@[A-Za-z0-9._]{1,30}$")


class ErroGerador(Exception):
    """Mensagem pronta para mostrar à pessoa."""


def eh_premium(conta) -> bool:
    return MODULO_CARROSSEIS_PREMIUM in conta.modulos_liberados()


def familia_do_modelo(modelo: str) -> str:
    return R.PREMIUM if modelo in MODELOS[R.PREMIUM] else R.PADRAO


# --- limite diário --------------------------------------------------------------------

def uso_de_hoje(conta) -> UsoCarrossel:
    uso, _ = UsoCarrossel.objects.get_or_create(conta=conta, dia=timezone.localdate())
    return uso


def restantes(conta) -> dict:
    uso = uso_de_hoje(conta)
    limite = planos.carrosseis(conta)["geracoes"]
    return {"geracoes": max(0, limite - uso.geracoes), "limite": limite,
            "reescritas": max(0, REESCRITAS_POR_DIA - uso.reescritas)}


def _consumir(conta, campo: str, limite: int) -> None:
    """Conta um uso, sem passar do limite nem com dois cliques ao mesmo tempo."""
    uso = uso_de_hoje(conta)
    atualizados = UsoCarrossel.objects.filter(pk=uso.pk, **{f"{campo}__lt": limite}).update(**{campo: F(campo) + 1})
    if not atualizados:
        raise ErroGerador("Você chegou ao limite de hoje. Amanhã libera de novo.")


# --- produto pelo link ----------------------------------------------------------------

def produto_do_link(conta, texto: str) -> dict:
    """Dados do produto e o link de afiliado (Sub ID "instagram"), com as credenciais da
    Shopee da própria conta. Levanta ErroGerador com o motivo."""
    if not conta.shopee_configurada:
        raise ErroGerador("Conecte sua conta de afiliado da Shopee em Configurações para gerar carrosséis.")
    links = copia.links_shopee(texto)
    if not links:
        raise ErroGerador("Cole um link de produto da Shopee (shopee.com.br ou s.shopee.com.br).")
    from accounts.ratelimit import _incrementar_contador

    # O limite do dia só conta carrossel gerado; abrir o link (até 10 s) tem limite próprio.
    if _incrementar_contador(f"carrosseis:link:{conta.pk}", 3600) > 40:
        raise ErroGerador("Muitas tentativas em pouco tempo. Espere alguns minutos e tente de novo.")
    link = links[0]
    item_id = copia.identificar_produto(link)
    if not item_id:
        raise ErroGerador("Não consegui achar o produto nesse link. Abra o produto na Shopee e copie o link de novo.")
    app_id, secret = credenciais(conta)
    try:
        achado = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id)
    except ShopeeAPIError as erro:
        raise ErroGerador(f"A Shopee não respondeu ({str(erro)[:120]}). Tente de novo em instantes.") from erro
    if not achado:
        raise ErroGerador("A Shopee não liberou esse produto para afiliados agora (sem comissão). Tente outro produto.")
    try:
        link_afiliado = shopee_ofertas.gerar_link_afiliado(app_id, secret, achado["link"], [SUB_ID])
    except ShopeeAPIError as erro:
        raise ErroGerador(f"Não consegui gerar o seu link de afiliado ({str(erro)[:120]}).") from erro
    preco, desconto = float(achado["preco"] or 0), float(achado["desconto"] or 0)
    # A Shopee só manda o preço atual e o % de desconto; o preço antigo sai da conta.
    de = round(preco / (1 - desconto / 100), 2) if 5 <= desconto < 95 else 0
    return {
        "nome": achado["nome"][:200], "preco": preco, "de": de, "desconto": round(desconto) if de else 0,
        "nota": round(float(achado["avaliacao"] or 0), 1), "vendas": int(achado["vendas"] or 0),
        "imagem": achado["imagem"], "loja": achado["loja"][:100], "link": link_afiliado, "item_id": item_id,
        "link_original": link[:600],
    }


# --- criar e salvar -------------------------------------------------------------------

def opcoes_iniciais(conta) -> dict:
    premium = eh_premium(conta)
    opcoes = {"modelo": "vitrine" if premium else "destaque", "tema": "verde", "cor": "", "fonte": "modelo",
              "usarRecorte": True, "mostraNota": True, "mostraDe": True, "mostraArrasta": True, "arroba": ""}
    padrao = PadraoCarrossel.objects.filter(conta=conta).first() if premium else None
    if padrao:
        opcoes.update(padrao.opcoes)
    return limpar_opcoes(opcoes, premium)


def criar(conta, texto_link: str) -> Carrossel:
    """Busca o produto (sem gastar o limite se o link não servir), conta o uso e gera."""
    premium = eh_premium(conta)
    limite = planos.carrosseis(conta)["geracoes"]
    if restantes(conta)["geracoes"] <= 0:
        extra = "" if premium else f" No plano Premium são {planos.CARROSSEIS[True]['geracoes']} por dia."
        raise ErroGerador(f"Você já gerou os {limite} carrosséis de hoje. Amanhã libera de novo.{extra}")
    produto = produto_do_link(conta, texto_link)
    _consumir(conta, "geracoes", limite)
    roteiros, _ = ia.gerar(produto)
    originais = {f: {str(s["_id"]): s for s in roteiros[f]} for f in (R.PADRAO, R.PREMIUM)}
    return Carrossel.objects.create(
        conta=conta, item_id=produto.pop("item_id"), link_original=produto.pop("link_original"), produto=produto,
        roteiros={f: roteiros[f] for f in (R.PADRAO, R.PREMIUM)}, originais=originais,
        opcoes=opcoes_iniciais(conta), legenda=roteiros["legenda"], hashtags=roteiros["hashtags"],
    )


def limpar_opcoes(opcoes: dict, premium: bool) -> dict:
    """O que a pessoa pode escolher, conforme o plano. Valor estranho volta ao padrão."""
    opcoes = opcoes if isinstance(opcoes, dict) else {}
    modelos = MODELOS[R.PADRAO] + (MODELOS[R.PREMIUM] if premium else [])
    limpo = {
        "modelo": opcoes.get("modelo") if opcoes.get("modelo") in modelos else ("vitrine" if premium else "destaque"),
        "tema": opcoes.get("tema") if opcoes.get("tema") in TEMAS else "verde",
        "arroba": opcoes["arroba"] if isinstance(opcoes.get("arroba"), str) and ARROBA.match(opcoes["arroba"]) else "",
        "cor": "", "fonte": "modelo", "usarRecorte": True, "mostraNota": True, "mostraDe": True, "mostraArrasta": True,
    }
    if premium:
        limpo["cor"] = opcoes["cor"] if isinstance(opcoes.get("cor"), str) and COR.match(opcoes["cor"]) else ""
        limpo["fonte"] = opcoes.get("fonte") if opcoes.get("fonte") in FONTES else "modelo"
        for chave in ("usarRecorte", "mostraNota", "mostraDe", "mostraArrasta"):
            limpo[chave] = opcoes.get(chave) is not False
    return limpo


def salvar(carrossel: Carrossel, dados: dict) -> None:
    """Grava o que veio do editor. Levanta ValueError se o roteiro não serve."""
    premium = eh_premium(carrossel.conta)
    roteiros = dict(carrossel.roteiros)
    enviados = dados.get("roteiros") if isinstance(dados.get("roteiros"), dict) else {}
    for familia in (R.PADRAO, R.PREMIUM):
        if familia not in enviados or (familia == R.PREMIUM and not premium):
            continue
        slides = R.limpar_roteiro(enviados[familia], familia, premium)
        if not premium:
            # Standard: dá para editar, reordenar e remover, mas não duplicar nem criar slide.
            origens = [s.get("_orig") for s in slides]
            if len(slides) > len(carrossel.originais.get(familia, {})) or len(set(origens)) != len(origens) \
                    or any(str(o) not in carrossel.originais.get(familia, {}) for o in origens):
                raise ValueError("Adicionar ou duplicar slides é do plano Premium.")
        roteiros[familia] = slides
    carrossel.roteiros = roteiros
    carrossel.opcoes = limpar_opcoes(dados.get("opcoes"), premium)
    carrossel.legenda = R.CONTROLE.sub("", str(dados.get("legenda", carrossel.legenda)))[:2200]
    carrossel.hashtags = " ".join(re.findall(r"#[\wÀ-ÿ]+", str(dados.get("hashtags", carrossel.hashtags))))[:300]
    carrossel.save(update_fields=["roteiros", "opcoes", "legenda", "hashtags", "atualizado_em"])


def salvar_padrao(conta, opcoes: dict) -> None:
    limpo = limpar_opcoes(opcoes, premium=True)
    PadraoCarrossel.objects.update_or_create(conta=conta, defaults={"opcoes": limpo})


def reescrever_slide(carrossel: Carrossel, slide: dict, familia: str) -> dict:
    conta = carrossel.conta
    if not eh_premium(conta):
        raise ErroGerador("A IA reescrevendo slides é do plano Premium.")
    if familia not in (R.PADRAO, R.PREMIUM):
        raise ErroGerador("Slide inválido.")
    limpo = R.limpar_slide(slide, familia, premium=True)
    if not limpo:
        raise ErroGerador("Slide inválido.")
    _consumir(conta, "reescritas", REESCRITAS_POR_DIA)
    try:
        return ia.reescrever(carrossel.produto, limpo, familia)
    except (ia.gemini.ErroDaIA, ValueError, TypeError) as erro:
        UsoCarrossel.objects.filter(conta=conta, dia=timezone.localdate()).update(reescritas=F("reescritas") - 1)
        raise ErroGerador("A IA não conseguiu reescrever agora. Tente de novo em instantes.") from erro
