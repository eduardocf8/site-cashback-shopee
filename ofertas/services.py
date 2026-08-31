import json
import logging
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from links.shopee_client import buscar_oferta_por_item_id, buscar_ofertas_produtos

from . import gemini_client
from .gemini_client import GeminiAPIError, GeminiConfigError
from .models import CashbackMaximoCache, NomeCurtoCache, Oferta, OfertaDestaqueManual, OfertaManual

logger = logging.getLogger(__name__)

CAMINHO_CATEGORIAS_NIVEL1 = Path(__file__).resolve().parent / "data" / "shopee_categorias_nivel1.json"
TAMANHO_LOTE_GEMINI = 50
# O plano gratuito do Gemini libera só 15 requisições/minuto, e qualquer requisição HTTP
# nesse site tem 120s de orçamento antes do gunicorn matar o worker (--timeout 120, ver
# README.md) - por isso processa só alguns lotes por execução em vez do catálogo inteiro
# de uma vez. O NomeCurtoCache é permanente, então o que sobrar fica pendente e é
# retomado sozinho na próxima chamada, sem perder progresso.
# Isso roda numa tarefa agendada separada da sincronização com a Shopee (ver
# encurtar_nomes_pendentes/executar_encurtamento_nomes) - a busca na Shopee sozinha já
# usa boa parte do orçamento de 120s, então enfileirar o Gemini atrás dela nessa mesma
# requisição estourava o timeout quase toda vez.
LIMITE_LOTES_POR_EXECUCAO = 10
PAUSA_ENTRE_LOTES_SEGUNDOS = 4.5

_categorias_nivel1_cache: dict[int, str] | None = None


def carregar_categorias_nivel1() -> dict[int, str]:
    global _categorias_nivel1_cache
    if _categorias_nivel1_cache is None:
        with open(CAMINHO_CATEGORIAS_NIVEL1, encoding="utf-8") as f:
            lista = json.load(f)
        _categorias_nivel1_cache = {item["id"]: item["nome"] for item in lista}
    return _categorias_nivel1_cache


def _decimal_seguro(valor, padrao=Decimal("0")):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        return padrao


def _montar_oferta(node: dict, categorias_nivel1: dict[int, str]) -> Oferta:
    categoria_ids = node.get("productCatIds") or []
    categoria_id = categoria_ids[0] if categoria_ids else 0
    avaliacao_bruta = node.get("ratingStar")
    avaliacao = _decimal_seguro(avaliacao_bruta) if avaliacao_bruta else None

    nome = (node.get("productName") or "")[:255]
    return Oferta(
        item_id=node["itemId"],
        nome=nome,
        nome_curto=nome,  # melhorado depois por encurtar_nomes_pendentes(), numa tarefa separada
        imagem_url=node.get("imageUrl") or "",
        preco_min=_decimal_seguro(node.get("priceMin")),
        preco_max=_decimal_seguro(node.get("priceMax")),
        percentual_desconto=int(node.get("priceDiscountRate") or 0),
        percentual_comissao=_decimal_seguro(node.get("commissionRate")),
        avaliacao=avaliacao,
        vendas=int(node.get("sales") or 0),
        categoria_id=categoria_id,
        categoria_nome=categorias_nivel1.get(categoria_id, ""),
        loja_nome=(node.get("shopName") or "")[:255],
        product_link=node.get("productLink") or "",
    )


class LinkProdutoInvalidoError(Exception):
    """A URL não é reconhecível como link de produto da Shopee, ou não deu pra abri-la
    (ver buscar_oferta_por_link)."""


class SemComissaoError(LinkProdutoInvalidoError):
    """O link é de um produto de verdade da Shopee, mas ela não retornou nenhuma oferta
    pra esse item_id - ou seja, não tem comissão de afiliado ativa nesse momento, então
    não há cashback possível pra essa compra. Subclasse de LinkProdutoInvalidoError pra
    quem já trata esse tipo de erro genericamente continuar funcionando sem mudança."""


# Padrão dos links de produto da Shopee: .../produto-exemplo-i.<shopId>.<itemId> -
# mesmo padrão documentado em links/forms.py (LinkProdutoForm).
PADRAO_ITEM_ID_NA_URL = re.compile(r"-i\.\d+\.(\d+)")


def _resolver_item_id(url: str) -> int:
    """Extrai o item_id de um link de produto da Shopee. Se for link curto (shp.ee,
    s.shopee.com.br), o padrão -i.<shopId>.<itemId> só aparece depois do
    redirecionamento, então segue ele primeiro - com um User-Agent de navegador de
    verdade, porque o padrão do requests (python-requests/x.x) pode receber uma
    página diferente da Shopee (ex: aviso pra abrir o app em vez do produto). Se a URL
    final ainda não tiver o padrão (ex: caiu numa página intermediária de
    abrir-app/landing em vez do produto direto), procura o mesmo padrão no HTML da
    página - o link real do produto costuma aparecer em algum lugar do conteúdo
    mesmo quando a URL do navegador não muda."""
    match = PADRAO_ITEM_ID_NA_URL.search(url)
    if match:
        return int(match.group(1))

    cabecalhos = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
        )
    }
    try:
        resposta = requests.get(url, allow_redirects=True, timeout=10, headers=cabecalhos)
    except requests.RequestException as erro:
        raise LinkProdutoInvalidoError(f"Não consegui abrir o link {url}: {erro}") from erro

    match = PADRAO_ITEM_ID_NA_URL.search(resposta.url) or PADRAO_ITEM_ID_NA_URL.search(resposta.text)
    if not match:
        raise LinkProdutoInvalidoError(
            f"Não consegui identificar o produto a partir do link {url} "
            f"(redirecionou pra {resposta.url}, mas não achei o padrão -i.<loja>.<item> "
            "nem na URL final nem no conteúdo da página - talvez esse link precise ser "
            "aberto no navegador/app pra chegar na página do produto)."
        )
    return int(match.group(1))


def buscar_oferta_por_link(url: str) -> Oferta:
    """Busca os dados de UM produto específico na Shopee a partir do link (usado pra
    postar uma oferta escolhida na mão, fora do calendário automático - ver
    instagram_bot/services.py, publicar_story_oferta_especifica). Não salva no banco -
    é só um Oferta em memória, pros mesmos geradores de imagem que já usam Oferta."""
    # Tira espaço e o embrulho de "<...>" / aspas que aparece quando cola o link de
    # algum app que formata como link (WhatsApp, Markdown) - sem isso, requests.get dá
    # "No connection adapters were found for '<https://...>'" em vez de abrir a URL.
    url = url.strip().strip("<>\"' ")
    item_id = _resolver_item_id(url)
    node = buscar_oferta_por_item_id(item_id)
    if node is None:
        raise SemComissaoError(
            f"A Shopee não oferece comissão de afiliado nesse produto agora (item_id={item_id}), "
            "portanto não há cashback."
        )
    return _montar_oferta(node, carregar_categorias_nivel1())


def _aplicar_nomes_curtos(ofertas: list[Oferta]) -> None:
    """Preenche oferta.nome_curto pra cada oferta. Reaproveita o NomeCurtoCache (que
    sobrevive entre sincronizações, diferente de Oferta - ver models.py) pra só chamar o
    Gemini nos itens novos ou com nome mudado desde a última vez. nome_curto nunca fica
    vazio: cai pro nome original se o Gemini falhar ou não estiver configurado."""
    cache_por_item_id = {
        c.item_id: c for c in NomeCurtoCache.objects.filter(item_id__in=[o.item_id for o in ofertas])
    }

    pendentes = []
    for oferta in ofertas:
        cache = cache_por_item_id.get(oferta.item_id)
        if cache and cache.nome_original == oferta.nome:
            oferta.nome_curto = cache.nome_curto
        else:
            oferta.nome_curto = oferta.nome  # fallback, sobrescrito abaixo se o lote der certo
            pendentes.append(oferta)

    lotes = [pendentes[i : i + TAMANHO_LOTE_GEMINI] for i in range(0, len(pendentes), TAMANHO_LOTE_GEMINI)]
    lotes_a_processar = lotes[:LIMITE_LOTES_POR_EXECUCAO]
    if len(lotes) > len(lotes_a_processar):
        logger.info(
            "[ofertas] %s produto(s) sem nome_curto ficam pra próxima sincronização (limite de %s lote(s) por execução)",
            sum(len(lote) for lote in lotes[LIMITE_LOTES_POR_EXECUCAO:]), LIMITE_LOTES_POR_EXECUCAO,
        )

    cache_pra_salvar = []
    for indice, lote in enumerate(lotes_a_processar):
        if indice > 0:
            time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)  # respeita o limite de requisições/minuto do plano gratuito
        try:
            nomes_curtos = gemini_client.encurtar_nomes([oferta.nome for oferta in lote])
        except GeminiConfigError as erro:
            logger.warning("[ofertas] Gemini não configurado, pulando o resto do encurtamento: %s", erro)
            break
        except (GeminiAPIError, requests.RequestException) as erro:
            logger.warning("[ofertas] falha ao encurtar lote de %s nome(s) via Gemini: %s", len(lote), erro)
            continue
        for oferta, nome_curto in zip(lote, nomes_curtos):
            oferta.nome_curto = nome_curto or oferta.nome
            cache_pra_salvar.append(
                NomeCurtoCache(item_id=oferta.item_id, nome_original=oferta.nome, nome_curto=oferta.nome_curto)
            )

    if cache_pra_salvar:
        NomeCurtoCache.objects.bulk_create(
            cache_pra_salvar,
            update_conflicts=True,
            update_fields=["nome_original", "nome_curto", "atualizado_em"],
            unique_fields=["item_id"],
        )


def encurtar_nomes_pendentes() -> dict:
    """Melhora, aos poucos, o nome_curto das ofertas que ainda estão iguais ao nome
    original (ou seja, ainda não passaram pelo Gemini com sucesso). Chamado por uma
    tarefa agendada própria (ver cashback_shopee/views.py e tarefas-diarias.yml),
    separada da sincronização com a Shopee, pra ter os 120s de orçamento só pra si."""
    ofertas = list(Oferta.objects.all())
    _aplicar_nomes_curtos(ofertas)
    Oferta.objects.bulk_update(ofertas, ["nome_curto"], batch_size=200)
    return {"total_ofertas": len(ofertas)}


def sincronizar_ofertas(limite_por_pagina: int = 50, max_paginas: int = 40) -> dict:
    """Busca as ofertas de produtos (productOfferV2, listType ALL) e substitui a lista atual.

    Full-replace (não incremental): uma "oferta" é só uma foto do que a Shopee está
    oferecendo hoje, sem status a preservar entre sincronizações (diferente de Pedido/Saque).
    """
    categorias_nivel1 = carregar_categorias_nivel1()

    ofertas_novas = []
    pagina = 1
    while pagina <= max_paginas:
        resultado = buscar_ofertas_produtos(pagina, limite_por_pagina)
        for node in resultado["nodes"]:
            ofertas_novas.append(_montar_oferta(node, categorias_nivel1))
        if not resultado["pageInfo"].get("hasNextPage"):
            break
        pagina += 1

    # Dedup por item_id (a Shopee pode repetir um item entre páginas se o feed
    # for atualizado no meio da sincronização).
    por_item_id = {oferta.item_id: oferta for oferta in ofertas_novas}

    with transaction.atomic():
        Oferta.objects.all().delete()
        Oferta.objects.bulk_create(por_item_id.values(), batch_size=200)

    _atualizar_cashback_maximo(por_item_id.values())

    return {"total": len(por_item_id), "paginas_percorridas": pagina}


def obter_cashback_maximo_anunciado() -> Decimal:
    """Maior % de cashback real pra anunciar na home ("até X%") - vem do
    CashbackMaximoCache (calculado na última sincronização de ofertas). Se ainda não
    houve nenhuma sincronização (instalação nova), cai pro piso configurado manualmente
    em CASHBACK_MAXIMO_ANUNCIADO."""
    cache = CashbackMaximoCache.obter()
    if cache and cache.percentual_maximo:
        return cache.percentual_maximo
    return Decimal(str(settings.CASHBACK_MAXIMO_ANUNCIADO))


def _atualizar_cashback_maximo(ofertas) -> None:
    """Recalcula o maior % de cashback anunciado na home a partir das ofertas
    recém-sincronizadas. Chamado uma vez por sincronização, não por request - ver
    CashbackMaximoCache."""
    percentuais = [
        oferta.percentual_cashback for oferta in ofertas if oferta.preco_min and oferta.percentual_comissao
    ]
    if not percentuais:
        return
    CashbackMaximoCache.atualizar(max(percentuais))


def normalizar_nome_produto(nome: str) -> str:
    """minúsculas e sem acento, pra comparar nome de produto ignorando esse tipo de
    diferença (usado pra não repetir o "mesmo" produto vindo de lojas diferentes -
    ver selecionar_top_ofertas_sem_duplicar)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def selecionar_top_ofertas_sem_duplicar(quantidade: int) -> list[Oferta]:
    """As ofertas mais vendidas (Oferta.Meta.ordering = -vendas), sem repetir produto.

    A Shopee pode anunciar o mesmo produto genérico (ex: "Percarbonato de sódio") em
    lojas diferentes, cada uma com seu próprio item_id - sincronizar_ofertas só remove
    duplicado por item_id, então sem essa checagem o mesmo produto pode aparecer mais
    de uma vez no mesmo story/post."""
    selecionadas = []
    nomes_vistos = set()
    for oferta in Oferta.objects.all():
        nome_normalizado = normalizar_nome_produto(oferta.nome)
        if nome_normalizado in nomes_vistos:
            continue
        nomes_vistos.add(nome_normalizado)
        selecionadas.append(oferta)
        if len(selecionadas) >= quantidade:
            break
    return selecionadas


def selecionar_carrossel_home(quantidade_carrossel: int) -> tuple[object | None, list]:
    """Oferta destaque (hero "Oferta do dia") + lista pro carrossel "Ofertas em alta" da home.

    O carrossel prioriza as ofertas manuais cadastradas no admin (as mais recentes
    primeiro - ver OfertaManual.Meta.ordering), completando as vagas restantes com as
    mais vendidas do catálogo sincronizado. Sem limite de ofertas manuais: se houver
    mais do que `quantidade_carrossel`, todas aparecem mesmo assim (o carrossel cresce
    em vez de descartar alguma).

    A oferta destaque normalmente também vem do catálogo sincronizado (a mais vendida),
    mas um OfertaDestaqueManual cadastrado no admin (ver página dedicada em
    OfertaDestaqueManualAdmin) a substitui - nesse caso nenhuma vaga extra do catálogo
    precisa ser reservada pra ela, sobrando uma vaga a mais pro carrossel.
    """
    destaque_manual = OfertaDestaqueManual.objects.first()
    ofertas_manuais_carrossel = list(OfertaManual.objects.all())
    vagas_organicas = max(quantidade_carrossel - len(ofertas_manuais_carrossel), 0)
    quantidade_a_buscar = vagas_organicas if destaque_manual else 1 + vagas_organicas
    top_organicas = selecionar_top_ofertas_sem_duplicar(quantidade_a_buscar)

    if destaque_manual:
        oferta_destaque = destaque_manual
        ofertas_em_alta = ofertas_manuais_carrossel + top_organicas
    else:
        oferta_destaque = top_organicas[0] if top_organicas else None
        ofertas_em_alta = ofertas_manuais_carrossel + top_organicas[1:]
    return oferta_destaque, ofertas_em_alta


def categorias_mais_vendidas(quantidade: int) -> list[dict]:
    """[{"categoria_id":.., "categoria_nome":.., "vendas_total":..}, ...], as
    `quantidade` categorias (nível 1) com mais vendas somadas entre as ofertas
    sincronizadas agora."""
    return list(
        Oferta.objects.values("categoria_id", "categoria_nome")
        .annotate(vendas_total=Sum("vendas"))
        .order_by("-vendas_total")[:quantidade]
    )
