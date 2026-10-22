"""Sincronização do catálogo de ofertas da cash-b (e, depois, do Radar do Appfiliado).

A Shopee limita cada busca da API de afiliados: o feed geral para em 56 páginas (só
~1.560 produtos diferentes, porque ele repete itens) e cada categoria em ~40 páginas
(~1.700 produtos). Somando o feed geral e as 27 categorias principais, a medição de
10/2026 (explorar_limite_catalogo --categorias) achou 47.674 produtos únicos.

Como funciona:
- Uma rodada por dia, a partir das HORA_DA_RODADA: as primeiras PAGINAS_DIARIAS de cada
  busca (os mais vendidos, onde o preço muda e importa mais). Uma vez por semana (ou se
  a última completa tem mais de 7 dias), a rodada completa: até PAGINAS_COMPLETA_CATEGORIA
  em cada categoria, para chegar perto de MAXIMO_OFERTAS produtos.
- Roda numa thread do worker (sincronizar_painel --loop), poucas páginas por vez, sem
  pressa - nada disso passa pelo site (que tem só 120s por requisição).
- Guarda e atualiza (não apaga tudo): cada produto que aparece numa busca ganha
  visto_em = agora e preço/comissão/vendas novos. No fim da rodada, saem os que não
  aparecem há DIAS_PARA_REMOVER dias (sem estoque ou sem comissão) e, se passar do teto,
  os menos vendidos.
- Os nomes curtos (Gemini) vêm aos poucos, dos mais vendidos para os menos (ver
  services.encurtar_nomes_pendentes); até lá, aparece o nome original."""

import logging
import threading
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from links.shopee_client import ShopeeAPIError, ShopeeConfigError, buscar_ofertas_produtos

from .models import BuscaCatalogo, CashbackMaximoCache, NomeCurtoCache, Oferta, SincronizacaoCatalogo

logger = logging.getLogger(__name__)

HORA_DA_RODADA = 3  # horário local em que começa a rodada do dia
DIA_DA_COMPLETA = 0  # segunda-feira
PAGINAS_DIARIAS = 10
PAGINAS_COMPLETA_CATEGORIA = 25  # ~1.100 produtos por categoria: ~30 mil no total
PAGINAS_COMPLETA_GERAL = 70  # o feed geral para sozinho em 56
POR_PAGINA = 50
PAGINAS_POR_VOLTA = 5
FALHAS_PARA_DESISTIR = 3
DIAS_PARA_REMOVER = 9  # a rodada completa é semanal: folga de 2 dias
MAXIMO_OFERTAS = 30000
INTERVALO_DA_THREAD = 15  # segundos entre uma volta e outra
NOMES_A_CADA = timedelta(minutes=10)
LOTES_DE_NOMES_POR_VEZ = 5  # 5 x 50 nomes a cada 10 minutos (respeita o limite por minuto do Gemini)

CAMPOS_ATUALIZADOS = [
    "nome", "imagem_url", "preco_min", "preco_max", "percentual_desconto", "percentual_comissao", "percentual_comissao_extra",
    "avaliacao",
    "vendas", "categoria_id", "categoria_nome", "loja_nome", "product_link", "visto_em", "nome_curto",
]


def credenciais_configuradas() -> bool:
    return bool(settings.SHOPEE_AFFILIATE_APP_ID and settings.SHOPEE_AFFILIATE_SECRET)


def estado() -> SincronizacaoCatalogo:
    obj, _ = SincronizacaoCatalogo.objects.get_or_create(pk=1)
    return obj


def garantir_buscas() -> None:
    """O feed geral + uma busca por categoria principal (as mesmas do filtro do site)."""
    from .services import carregar_categorias_nivel1

    categorias = carregar_categorias_nivel1()
    desejadas = {"geral": ("Feed geral", None)}
    desejadas.update({f"categoria:{c}": (n, c) for c, n in sorted(categorias.items(), key=lambda i: i[1])})
    BuscaCatalogo.objects.exclude(chave__in=desejadas).delete()
    for chave, (nome, categoria_id) in desejadas.items():
        BuscaCatalogo.objects.update_or_create(chave=chave, defaults={"nome": nome, "categoria_id": categoria_id})


def iniciar_rodada_se_preciso(atual: SincronizacaoCatalogo, agora) -> bool:
    """Começa a rodada de hoje (depois das HORA_DA_RODADA; a primeira de todas começa na hora)."""
    local = timezone.localtime(agora)
    hoje = local.date()
    if atual.rodada == hoje or (atual.rodada is not None and local.hour < HORA_DA_RODADA):
        return False
    completa = (hoje.weekday() == DIA_DA_COMPLETA or atual.ultima_completa is None
                or (hoje - atual.ultima_completa).days >= 7)
    garantir_buscas()
    BuscaCatalogo.objects.filter(categoria_id__isnull=True).update(
        limite_paginas=PAGINAS_COMPLETA_GERAL if completa else PAGINAS_DIARIAS)
    BuscaCatalogo.objects.filter(categoria_id__isnull=False).update(
        limite_paginas=PAGINAS_COMPLETA_CATEGORIA if completa else PAGINAS_DIARIAS)
    BuscaCatalogo.objects.update(pagina=1, terminada=False, falhas=0, produtos=0, ultimo_erro="")
    atual.rodada, atual.completa, atual.iniciada_em, atual.finalizada_em = hoje, completa, agora, None
    atual.paginas_lidas = atual.produtos_vistos = atual.removidos = 0
    atual.ultimo_erro = ""
    atual.save()
    logger.info("[catálogo] rodada %s começou (%s)", hoje, "completa" if completa else "diária")
    return True


def guardar_pagina(nodes: list[dict], agora, categoria_padrao: int | None = None) -> int:
    """Cria os produtos novos e atualiza os que já existem. Devolve quantos vieram."""
    from .services import _montar_oferta, carregar_categorias_nivel1

    categorias = carregar_categorias_nivel1()
    vindas: dict[int, Oferta] = {}
    for node in nodes:
        if not node.get("itemId") or not node.get("productName"):
            continue
        oferta = _montar_oferta(node, categorias)
        if not oferta.categoria_id and categoria_padrao:
            oferta.categoria_id, oferta.categoria_nome = categoria_padrao, categorias.get(categoria_padrao, "")
        oferta.visto_em = agora
        vindas[oferta.item_id] = oferta
    if not vindas:
        return 0
    existentes = {o.item_id: o for o in Oferta.objects.filter(item_id__in=vindas)}
    cache = {c.item_id: c for c in NomeCurtoCache.objects.filter(item_id__in=vindas)}
    criar, atualizar = [], []
    for item_id, nova in vindas.items():
        guardado = cache.get(item_id)
        nome_curto = guardado.nome_curto if guardado and guardado.nome_original == nova.nome else nova.nome
        atual = existentes.get(item_id)
        if atual is None:
            nova.nome_curto = nome_curto
            criar.append(nova)
            continue
        if atual.nome != nova.nome:
            atual.nome_curto = nome_curto  # nome mudou: o curto antigo não serve mais
        for campo in CAMPOS_ATUALIZADOS:
            if campo != "nome_curto":
                setattr(atual, campo, getattr(nova, campo))
        atualizar.append(atual)
    with transaction.atomic():
        Oferta.objects.bulk_create(criar, batch_size=200, ignore_conflicts=True)
        Oferta.objects.bulk_update(atualizar, CAMPOS_ATUALIZADOS, batch_size=200)
    return len(vindas)


def finalizar_rodada(atual: SincronizacaoCatalogo, agora) -> None:
    """Tira quem sumiu, respeita o teto e recalcula o "até X%" da home."""
    removidos = 0
    deu_tudo_certo = not BuscaCatalogo.objects.filter(falhas__gte=FALHAS_PARA_DESISTIR).exists()
    if deu_tudo_certo:  # com a Shopee fora do ar, ninguém some por engano
        vencidas = Oferta.objects.filter(visto_em__lt=agora - timedelta(days=DIAS_PARA_REMOVER))
        if atual.completa:
            vencidas = vencidas | Oferta.objects.filter(visto_em__isnull=True)  # sobras da sincronização antiga
        removidos += vencidas.delete()[0]
    excesso = Oferta.objects.count() - MAXIMO_OFERTAS
    if excesso > 0:
        menos_vendidas = list(Oferta.objects.order_by("vendas", "id").values_list("id", flat=True)[:excesso])
        removidos += Oferta.objects.filter(id__in=menos_vendidas).delete()[0]
    atualizar_cashback_maximo()
    atual.finalizada_em, atual.removidos = agora, removidos
    if atual.completa:
        atual.ultima_completa = atual.rodada
    atual.save()
    logger.info("[catálogo] rodada %s terminou: %s páginas, %s produtos vistos, %s removidos, %s no site",
                atual.rodada, atual.paginas_lidas, atual.produtos_vistos, removidos, Oferta.objects.count())


def atualizar_cashback_maximo() -> None:
    """O maior % de cashback do catálogo (o de maior comissão com preço) - sempre grava, para
    a data "ofertas atualizadas às…" da página de ofertas acompanhar a rodada."""
    maior = Oferta.objects.filter(preco_min__gt=0, percentual_comissao__gt=0).order_by("-percentual_comissao").first()
    if maior:
        CashbackMaximoCache.atualizar(maior.percentual_cashback)


def avancar(agora=None, paginas: int = PAGINAS_POR_VOLTA) -> SincronizacaoCatalogo:
    """Uma volta: começa a rodada do dia se for a hora e lê até `paginas` páginas."""
    agora = agora or timezone.now()
    atual = estado()
    if not credenciais_configuradas():
        mensagem = "Sem SHOPEE_AFFILIATE_APP_ID/SECRET neste serviço: a sincronização do catálogo está parada."
        if atual.ultimo_erro != mensagem:
            atual.ultimo_erro = mensagem
            atual.save(update_fields=["ultimo_erro"])
        return atual
    iniciar_rodada_se_preciso(atual, agora)
    if atual.finalizada_em or atual.rodada is None:
        return atual
    for _ in range(paginas):
        busca = BuscaCatalogo.objects.filter(terminada=False).first()
        if busca is None:
            finalizar_rodada(atual, agora)
            return atual
        try:
            resultado = buscar_ofertas_produtos(busca.pagina, POR_PAGINA, categoria=busca.categoria_id)
        except (ShopeeAPIError, ShopeeConfigError, requests.RequestException, KeyError) as erro:
            busca.falhas += 1
            busca.ultimo_erro = f"Página {busca.pagina}: {erro}"[:300]
            busca.terminada = busca.falhas >= FALHAS_PARA_DESISTIR
            busca.save()
            atual.ultimo_erro = f"{busca.nome}: {busca.ultimo_erro}"[:500]
            atual.save(update_fields=["ultimo_erro"])
            logger.warning("[catálogo] %s", atual.ultimo_erro)
            return atual  # tenta de novo na próxima volta
        vieram = guardar_pagina(resultado.get("nodes") or [], agora, categoria_padrao=busca.categoria_id)
        busca.produtos += vieram
        busca.pagina += 1
        busca.terminada = not (resultado.get("pageInfo") or {}).get("hasNextPage") or busca.pagina > busca.limite_paginas
        busca.save()
        atual.paginas_lidas += 1
        atual.produtos_vistos += vieram
        atual.save(update_fields=["paginas_lidas", "produtos_vistos"])
    return atual


class Motor:
    def __init__(self):
        self.proximos_nomes = 0.0

    def rodar(self):
        while True:
            close_old_connections()
            try:
                self.uma_volta()
            except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
                logger.exception("[catálogo] erro na sincronização")
            time.sleep(INTERVALO_DA_THREAD)

    def uma_volta(self):
        avancar()
        if settings.GEMINI_API_KEY and time.monotonic() >= self.proximos_nomes:
            from .services import encurtar_nomes_pendentes

            self.proximos_nomes = time.monotonic() + NOMES_A_CADA.total_seconds()
            encurtar_nomes_pendentes(limite_lotes=LOTES_DE_NOMES_POR_VEZ)


def iniciar_em_segundo_plano() -> Motor:
    motor = Motor()
    threading.Thread(target=motor.rodar, name="catalogo-ofertas", daemon=True).start()
    return motor
