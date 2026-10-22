import json
import logging
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from django.conf import settings
from django.db.models import Sum

from links.shopee_client import buscar_oferta_por_item_id

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
        percentual_comissao_extra=_decimal_seguro(node.get("sellerCommissionRate")),
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


# Formatos de link de produto observados na Shopee: o mais antigo
# .../produto-exemplo-i.<shopId>.<itemId> (documentado em links/forms.py,
# LinkProdutoForm), .../product/<shopId>/<itemId> (ROADMAP.md, Fase 35) e
# .../opaanlp/<shopId>/<itemId> (destino embutido na página de links curtos
# s.shopee.com.br, ver _texto_da_pagina_normalizado).
PADRAO_ITEM_ID_NA_URL = re.compile(r"-i\.\d+\.(\d+)|/(?:product|opaanlp)/\d+/(\d+)")


def resolver_item_id_sem_rede(url: str) -> int | None:
    """Extrai o item_id de uma URL só pelo padrão de texto, sem seguir nenhum
    redirecionamento - rápido e sem chamada de rede, mas só funciona pra links que já
    vêm no formato resolvido (não links curtos). Usado quando resolver de verdade
    (_resolver_item_id, que pode levar até 10s pra links curtos - ver Fase 35) deixaria
    uma ação do usuário lenta demais (ver links/services.py::gerar_click e
    ROADMAP.md, Fase 41). Retorna None em vez de levantar erro - quem chama trata
    "não identificado" como um estado normal, não uma falha."""
    match = PADRAO_ITEM_ID_NA_URL.search(url.strip().strip("<>\"' "))
    if match:
        return int(match.group(1) or match.group(2))
    return None


# Endereços que o servidor aceita abrir para achar o produto (o próprio domínio ou um
# subdomínio dele - "s.shopee.com.br" sim, "shopee.com.br.golpe.com" não).
DOMINIOS_DA_SHOPEE = ("shopee.com.br", "shopee.com", "shp.ee", "shope.ee", "shoope.top")
MAXIMO_REDIRECIONAMENTOS = 6
MAXIMO_BYTES_DA_PAGINA = 1_000_000


def eh_host_da_shopee(url: str) -> bool:
    """O link é mesmo da Shopee? Confere o host de verdade (sem usuário/senha no endereço,
    só http/https, domínio igual ou subdomínio de um da lista)."""
    try:
        partes = urlsplit(str(url or "").strip())
        host = (partes.hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    if partes.scheme.lower() not in ("http", "https") or partes.username is not None or "@" in partes.netloc:
        return False
    return any(host == d or host.endswith("." + d) for d in DOMINIOS_DA_SHOPEE)


def _abrir_pagina_da_shopee(url: str, timeout: float, cabecalhos: dict) -> tuple[str, str, int, int]:
    """Segue os redirecionamentos um por um, só enquanto continuam na Shopee, com tempo
    total e tamanho da página limitados. Devolve (URL final, texto, status, saltos).
    Um redirecionamento para fora da Shopee não é aberto: a URL dele vira a final (o
    item_id às vezes já está nela)."""
    limite = time.monotonic() + timeout
    atual, saltos = url, 0
    sessao = requests.Session()  # guarda os cookies entre um redirecionamento e outro, como o navegador
    while True:
        restante = limite - time.monotonic()
        if restante <= 0:
            raise requests.Timeout("tempo total esgotado")
        with sessao.get(atual, allow_redirects=False, timeout=min(restante, timeout), headers=cabecalhos,
                        stream=True) as resposta:
            destino = resposta.headers.get("Location") if resposta.is_redirect else None
            if destino and saltos < MAXIMO_REDIRECIONAMENTOS:
                proxima = urljoin(atual, destino)
                if not eh_host_da_shopee(proxima):
                    return proxima, "", resposta.status_code, saltos + 1
                atual, saltos = proxima, saltos + 1
                continue
            pedacos, total = [], 0
            for pedaco in resposta.iter_content(chunk_size=16384):
                pedacos.append(pedaco)
                total += len(pedaco)
                if total >= MAXIMO_BYTES_DA_PAGINA or time.monotonic() > limite:
                    break
            texto = b"".join(pedacos)[:MAXIMO_BYTES_DA_PAGINA].decode(resposta.encoding or "utf-8", errors="replace")
            return atual, texto, resposta.status_code, saltos


def _texto_da_pagina_normalizado(html: str) -> str:
    """O link curto (s.shopee.com.br, br.shp.ee) responde 200 sem redirecionamento HTTP:
    é uma página que redireciona via JavaScript, com o endereço do produto embutido -
    mas escrito com as barras escapadas de JSON ("https:\\/\\/shopee.com.br\\/product\\/1\\/2")
    e também em codificação de URL ("navigate_url=https%3A%2F%2Fshopee.com.br%2Fproduct..."),
    formas que o PADRAO_ITEM_ID_NA_URL não reconhece. Desfaz as duas antes de procurar."""
    return unquote(html.replace("\\/", "/"))


def _resolver_item_id(url: str, timeout: int = 10) -> int:
    """Extrai o item_id de um link de produto da Shopee. Se for link curto (shp.ee,
    s.shopee.com.br), o padrão -i.<shopId>.<itemId> só aparece depois do
    redirecionamento, então segue ele primeiro - com um User-Agent de navegador de
    verdade, porque o padrão do requests (python-requests/x.x) pode receber uma
    página diferente da Shopee (ex: aviso pra abrir o app em vez do produto). Se a URL
    final ainda não tiver o padrão (ex: caiu numa página intermediária de
    abrir-app/landing em vez do produto direto), procura o mesmo padrão no HTML da
    página - o link real do produto costuma aparecer em algum lugar do conteúdo
    mesmo quando a URL do navegador não muda.

    Chegou a existir um fallback via navegador headless (Browserless) pra links que
    dependem de JavaScript pra redirecionar - removido depois de confirmar em produção
    que a Shopee bloqueia esse tipo de navegador como tráfego suspeito nesse domínio de
    rastreamento (100% de bloqueio nos testes reais, não um caso raro que valesse a
    complexidade extra) - ver ROADMAP.md, Fase 37."""
    match = PADRAO_ITEM_ID_NA_URL.search(url)
    if match:
        return int(match.group(1) or match.group(2))

    # Além do User-Agent, alguns headers que um navegador de verdade sempre manda e o
    # requests não - sem eles, o link curto às vezes nem chega a redirecionar de
    # verdade (a "URL final" volta idêntica à original, como se a Shopee estivesse
    # tratando o pedido como não-navegador). Não tem garantia de que isso resolve -
    # pode ser um bloqueio mais forte (fingerprint de TLS/HTTP, JS obrigatório) que
    # nenhum header sozinho contorna.
    cabecalhos = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }
    if not eh_host_da_shopee(url):
        # Só abre endereço da própria Shopee: o link vem de visitante, de mensagem de grupo
        # de terceiros ou do afiliado - nunca deixa o servidor buscar outro endereço (SSRF).
        raise LinkProdutoInvalidoError(f"O link {url} não é da Shopee.")
    try:
        url_final, texto, status, saltos = _abrir_pagina_da_shopee(url, timeout, cabecalhos)
    except requests.RequestException as erro:
        raise LinkProdutoInvalidoError(f"Não consegui abrir o link {url}: {erro}") from erro

    match = PADRAO_ITEM_ID_NA_URL.search(url_final) or PADRAO_ITEM_ID_NA_URL.search(
        _texto_da_pagina_normalizado(texto)
    )
    if not match:
        raise LinkProdutoInvalidoError(
            f"Não consegui identificar o produto a partir do link {url} "
            f"(redirecionou pra {url_final} [status={status}, "
            f"{saltos} redirecionamento(s) seguido(s)], mas não achei "
            "nenhum padrão de link de produto da Shopee (-i.<loja>.<item> ou "
            "/product/<loja>/<item>) nem na URL final nem no conteúdo da página - talvez "
            "esse link precise ser aberto no navegador/app pra chegar na página do produto)."
        )
    return int(match.group(1) or match.group(2))


def resolver_item_id_com_rede(url: str, timeout: int = 10) -> int | None:
    """Como resolver_item_id_sem_rede, mas segue redirecionamento quando precisa
    (pode levar até 10s pra link curto) - só chame isso FORA do ciclo de requisição
    de um usuário. Usado pela tarefa agendada que tenta resolver, aos poucos, o
    item_id_alvo dos cliques que a resolução rápida não conseguiu (ver
    links/services.py::resolver_item_id_alvo_pendentes e ROADMAP.md, Fase 41/42).
    Retorna None em vez de levantar erro - "não identificado" é um resultado normal
    aqui, não uma falha."""
    try:
        return _resolver_item_id(url.strip().strip("<>\"' "), timeout=timeout)
    except LinkProdutoInvalidoError:
        return None


def buscar_oferta_por_link(url: str) -> Oferta:
    """Busca os dados de UM produto específico na Shopee a partir do link (usado pra
    postar uma oferta escolhida na mão, fora do calendário automático - ver
    instagram_bot/services.py, publicar_story_oferta_especifica - e pra mostrar o
    cashback real ao converter um link no site, ver links/views.py). Não salva no
    banco - é só um Oferta em memória, pros mesmos geradores de imagem que já usam
    Oferta."""
    # Tira espaço e o embrulho de "<...>" / aspas que aparece quando cola o link de
    # algum app que formata como link (WhatsApp, Markdown) - sem isso, requests.get dá
    # "No connection adapters were found for '<https://...>'" em vez de abrir a URL.
    url = url.strip().strip("<>\"' ")
    return buscar_oferta_por_item(_resolver_item_id(url))


def buscar_oferta_por_item(item_id: int) -> Oferta:
    """Como buscar_oferta_por_link, a partir do item_id já conhecido - usado também
    pela estimativa ao vivo do conversor (links/views.py::cashback_estimado), que só
    aceita links com o item_id na própria URL, sem seguir redirecionamento."""
    node = buscar_oferta_por_item_id(item_id)
    if node is None:
        raise SemComissaoError(
            f"A Shopee não oferece comissão de afiliado nesse produto agora (item_id={item_id}), "
            "portanto não há cashback."
        )
    return _montar_oferta(node, carregar_categorias_nivel1())


def _aplicar_nomes_curtos(ofertas: list[Oferta], limite_lotes: int | None = None) -> None:
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
    limite_lotes = limite_lotes or LIMITE_LOTES_POR_EXECUCAO
    lotes_a_processar = lotes[:limite_lotes]
    if len(lotes) > len(lotes_a_processar):
        logger.info(
            "[ofertas] %s produto(s) sem nome_curto ficam pra próxima vez (limite de %s lote(s) por execução)",
            sum(len(lote) for lote in lotes[limite_lotes:]), limite_lotes,
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


def encurtar_nomes_pendentes(limite_lotes: int = LIMITE_LOTES_POR_EXECUCAO) -> dict:
    """Melhora, aos poucos, o nome_curto das ofertas que ainda estão iguais ao nome
    original, das mais vendidas para as menos (são elas que aparecem primeiro no site).
    Quem já passou pelo Gemini com esse mesmo nome (NomeCurtoCache) não entra de novo.
    Chamado pela thread do catálogo no worker (ofertas/catalogo.py) e pela tarefa
    agendada do site (cashback_shopee/views.py), que tem os 120s só para si."""
    from django.db.models import Exists, F, OuterRef

    ja_tem = NomeCurtoCache.objects.filter(item_id=OuterRef("item_id"), nome_original=OuterRef("nome"))
    pendentes = list(
        Oferta.objects.filter(nome_curto=F("nome")).exclude(Exists(ja_tem))
        .order_by("-vendas")[: limite_lotes * TAMANHO_LOTE_GEMINI]
    )
    if pendentes:
        _aplicar_nomes_curtos(pendentes, limite_lotes=limite_lotes)
        Oferta.objects.bulk_update(pendentes, ["nome_curto"], batch_size=200)
    return {"pendentes_nesta_vez": len(pendentes)}


# A sincronização do catálogo (guardar e atualizar, por categoria, no worker) fica em
# ofertas/catalogo.py. A antiga sincronizar_ofertas() apagava e recriava tudo a cada dia,
# só com o feed geral (~1.560 produtos), dentro da requisição do site.


def obter_cashback_maximo_anunciado() -> Decimal:
    """Maior % de cashback real pra anunciar na home ("até X%") - vem do
    CashbackMaximoCache (calculado na última sincronização de ofertas). Se ainda não
    houve nenhuma sincronização (instalação nova), cai pro piso configurado manualmente
    em CASHBACK_MAXIMO_ANUNCIADO."""
    cache = CashbackMaximoCache.obter()
    if cache and cache.percentual_maximo:
        return cache.percentual_maximo
    return Decimal(str(settings.CASHBACK_MAXIMO_ANUNCIADO))


def normalizar_nome_produto(nome: str) -> str:
    """minúsculas e sem acento, pra comparar nome de produto ignorando esse tipo de
    diferença (usado pra não repetir o "mesmo" produto vindo de lojas diferentes -
    ver selecionar_top_ofertas_sem_duplicar)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def selecionar_top_ofertas_sem_duplicar(quantidade: int) -> list[Oferta]:
    """As ofertas mais vendidas (Oferta.Meta.ordering = -vendas), sem repetir produto.

    A Shopee pode anunciar o mesmo produto genérico (ex: "Percarbonato de sódio") em
    lojas diferentes, cada uma com seu próprio item_id - a sincronização do catálogo só remove
    duplicado por item_id, então sem essa checagem o mesmo produto pode aparecer mais
    de uma vez no mesmo story/post."""
    selecionadas = []
    nomes_vistos = set()
    # Só os mais vendidos (a lista é ordenada por -vendas): com dezenas de milhares de
    # produtos, percorrer o catálogo todo a cada visita à home carregaria tudo na memória.
    for oferta in Oferta.objects.all()[: max(quantidade * 50, 500)]:
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
