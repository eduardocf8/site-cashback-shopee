"""Produtos da vitrine do Meu site e os links de afiliado (com o Sub ID do site).

- "bot": cada oferta que o bot de WhatsApp põe na fila entra no topo; o mesmo produto
  não duplica (volta para o topo) e só ficam as LIMITE mais recentes;
- "busca": o worker refaz a busca na Shopee de tempos em tempos (mesmos campos do bot);
- "manual": os links que a pessoa colou, na ordem dela.
Quem fala com a Shopee é o worker (comando sincronizar_painel); o site só lê o banco."""

import json
import logging
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from bot_whatsapp import copia, shopee_ofertas
from bot_whatsapp.categorias import CATEGORIAS_SHOPEE, produto_pertence_as_categorias
from bot_whatsapp.models import ConfiguracaoOfertas
from licencas import planos
from painel import cripto

from .models import CategoriaProdutoSite, ProdutoSite, SiteAfiliado

logger = logging.getLogger(__name__)

LIMITE = 100  # produtos por vitrine
REFAZER_BUSCA_APOS = timedelta(hours=3)
LINKS_POR_VOLTA = 30  # links de afiliado gerados por volta do worker
MAXIMO_MANUAIS = 60


# Categorias da vitrine: as principais da Shopee Brasil (nível 1, os mesmos nomes do app),
# guardadas pelo número (ex: "100630" = Beleza). Lista em meusite/data/categorias_shopee.json.
with open(Path(__file__).resolve().parent / "data" / "categorias_shopee.json", encoding="utf-8") as _arquivo:
    CATEGORIAS = {str(item["id"]): item["nome"] for item in json.load(_arquivo)}

# Quando a Shopee não manda a categoria: o nicho adivinhado pelo nome do produto (as listas
# de palavras do bot) vira a categoria da Shopee mais próxima.
NICHO_PARA_CATEGORIA = {
    "moda": "100017", "beleza": "100630", "casa": "100636", "eletronicos": "100013", "eletrodomesticos": "100010",
    "bebes": "100632", "brinquedos": "100639", "esporte": "100637", "automotivo": "100640", "pet": "100631",
    "papelaria": "100638", "saude": "100001", "joias": "100009", "ferramentas": "100636",
}


def opcoes_de_categoria() -> list[tuple[str, str]]:
    """(número, nome) das categorias, em ordem alfabética."""
    return sorted(CATEGORIAS.items(), key=lambda par: par[1])


def nome_curto_da_categoria(chave: str) -> str:
    if chave in CATEGORIAS:
        return CATEGORIAS[chave]
    # Produto guardado antes da troca (nicho pelo nome), até o worker atualizar.
    label = CATEGORIAS_SHOPEE.get(chave, {}).get("label", "")
    return label.split(" (")[0].split(" e ")[0].strip()


def categoria_do_produto(produto: dict) -> str:
    """A categoria que a Shopee manda; sem ela, a adivinhada pelo nome."""
    oficial = str(produto.get("categoria_id") or "")
    if oficial in CATEGORIAS:
        return oficial
    nome = produto.get("nome") or ""
    for nicho in CATEGORIAS_SHOPEE:
        if produto_pertence_as_categorias(nome, [nicho]):
            return NICHO_PARA_CATEGORIA.get(nicho, "")
    return ""


def _dados(produto: dict) -> dict:
    preco = Decimal(str(round(float(produto.get("preco") or 0), 2)))
    desconto = int(round(float(produto.get("desconto") or 0)))
    original = None
    if 0 < desconto < 100 and preco:
        original = (preco / (Decimal(100 - desconto) / 100)).quantize(Decimal("0.01"))
    return {
        "nome": (produto.get("nome") or "")[:300], "imagem_url": (produto.get("imagem") or "")[:500],
        "preco": preco, "preco_original": original, "desconto": max(0, min(desconto, 99)),
        "categoria": categoria_do_produto(produto),
        "link_produto": (produto.get("link") or "")[:500],
    }


def _guardar(site, fonte: str, produto: dict, quando) -> ProdutoSite | None:
    item_id = str(produto.get("item_id") or "")
    if not item_id or not produto.get("link"):
        return None
    existente = ProdutoSite.objects.filter(site=site, fonte=fonte, item_id=item_id).first()
    dados = _dados(produto)
    escolhida = CategoriaProdutoSite.objects.filter(site=site, item_id=item_id).values_list("categoria", flat=True).first()
    if escolhida is not None:  # a pessoa corrigiu a categoria deste produto
        dados["categoria"] = escolhida
    if existente:
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        existente.posicao_em = quando
        existente.save()
        return existente
    return ProdutoSite.objects.create(site=site, fonte=fonte, item_id=item_id, posicao_em=quando, **dados)


def _cortar(site, fonte: str, limite: int = LIMITE):
    sobra = ProdutoSite.objects.filter(site=site, fonte=fonte).order_by("-posicao_em", "-id").values_list("id", flat=True)[limite:]
    ProdutoSite.objects.filter(id__in=list(sobra)).delete()


def registrar_do_bot(conta, produto: dict | None, quando=None):
    """Chamado quando o bot põe uma oferta na fila (fora da simulação)."""
    if not produto:
        return
    site = SiteAfiliado.objects.filter(conta=conta, vitrine=SiteAfiliado.VITRINE_BOT).first()
    if not site:
        return
    try:
        with transaction.atomic():
            if _guardar(site, SiteAfiliado.VITRINE_BOT, produto, quando or timezone.now()):
                _cortar(site, SiteAfiliado.VITRINE_BOT)
    except Exception:  # noqa: BLE001 - a vitrine nunca pode atrapalhar o envio da oferta
        logger.exception("Meu site: não deu para pôr a oferta na vitrine da conta %s", conta.pk)


def _credenciais(site) -> tuple[str, str]:
    return site.conta.shopee_app_id, cripto.decifrar(site.conta.shopee_secret_cifrado)


def atualizar_busca(site, agora):
    app_id, secret = _credenciais(site)
    # Mesma busca do bot (sem os filtros de número): uma configuração do bot só em memória.
    config = ConfiguracaoOfertas(
        tipo_busca=site.busca_tipo, palavra_chave=site.palavra_chave, loja=site.loja,
        categorias=site.categorias, ordenacao=site.ordenacao, comissao_minima=0, desconto_minimo=0,
        preco_minimo=None, preco_maximo=None, vendas_minimas=0, avaliacao_minima=None,
    )
    achados = []
    for pagina in (1, 2):
        produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, config, pagina)
        achados += [p for p in produtos if shopee_ofertas.passa_nos_filtros(p, config)]
        if not tem_proxima or len(achados) >= LIMITE:
            break
    with transaction.atomic():
        vistos = set()
        for i, produto in enumerate(achados[:LIMITE]):
            if _guardar(site, SiteAfiliado.VITRINE_BUSCA, produto, agora - timedelta(seconds=i)):
                vistos.add(str(produto["item_id"]))
        ProdutoSite.objects.filter(site=site, fonte=SiteAfiliado.VITRINE_BUSCA).exclude(item_id__in=vistos).delete()


def links_manuais(site) -> list[str]:
    return [l.strip() for l in (site.links_manuais or "").splitlines() if l.strip()][:MAXIMO_MANUAIS]


def atualizar_manuais(site, agora):
    app_id, secret = _credenciais(site)
    vistos, problemas = set(), []
    for i, link in enumerate(links_manuais(site)):
        links = copia.links_shopee(link)
        item_id = copia.identificar_produto(links[0]) if links else ""
        produto = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id) if item_id else None
        if not produto:
            problemas.append(link[:60])
            continue
        if _guardar(site, SiteAfiliado.VITRINE_MANUAL, produto, agora - timedelta(seconds=i)):
            vistos.add(str(produto["item_id"]))
    ProdutoSite.objects.filter(site=site, fonte=SiteAfiliado.VITRINE_MANUAL).exclude(item_id__in=vistos).delete()
    if problemas:
        raise ValueError(f"Não achei {len(problemas)} produto(s) na Shopee: {', '.join(problemas[:3])}")


def link_do_site(site, link_produto: str, vitrine: bool = False) -> str:
    """Link de afiliado do site. A vitrine pode ter um Sub ID próprio (vazio = o do conversor)."""
    app_id, secret = _credenciais(site)
    sub_id = (site.sub_id_vitrine or site.sub_id) if vitrine else site.sub_id
    sub_ids = [sub_id] if sub_id else []
    return shopee_ofertas.gerar_link_afiliado(app_id, secret, link_produto, sub_ids)


def gerar_links_pendentes():
    pendentes = (ProdutoSite.objects.filter(link_afiliado="", site__conta__shopee_validado_em__isnull=False)
                 .select_related("site__conta")[:LINKS_POR_VOLTA])
    for produto in pendentes:
        try:
            produto.link_afiliado = link_do_site(produto.site, produto.link_produto, vitrine=True)[:500]
            produto.save(update_fields=["link_afiliado"])
        except Exception:  # noqa: BLE001 - o clique gera na hora
            logger.exception("Meu site: link do produto %s", produto.pk)


def uma_volta(agora=None) -> list[str]:
    """Chamado pelo worker a cada volta."""
    agora = agora or timezone.now()
    logs = []
    sites = SiteAfiliado.objects.filter(conta__shopee_validado_em__isnull=False).exclude(
        vitrine__in=[SiteAfiliado.VITRINE_BOT, SiteAfiliado.VITRINE_NENHUMA],
    ).select_related("conta")
    for site in sites:
        vencida = site.vitrine == SiteAfiliado.VITRINE_BUSCA and (
            not site.vitrine_atualizada_em or agora - site.vitrine_atualizada_em > REFAZER_BUSCA_APOS
        )
        if not (site.vitrine_pedida or vencida):
            continue
        site.vitrine_erro = ""
        try:
            if site.vitrine == SiteAfiliado.VITRINE_BUSCA:
                atualizar_busca(site, agora)
            elif not planos.site_premium(site.conta):
                raise ValueError("A vitrine com os produtos que você escolher é do plano Premium.")
            else:
                atualizar_manuais(site, agora)
            logs.append(f"Meu site: vitrine de {site.endereco} atualizada")
        except Exception as erro:  # noqa: BLE001
            logger.exception("Meu site: vitrine do site %s", site.pk)
            site.vitrine_erro = str(erro)[:500]
        site.vitrine_atualizada_em = agora
        site.save(update_fields=["vitrine_erro", "vitrine_atualizada_em", "atualizado_em"])
    gerar_links_pendentes()
    atualizar_categorias_antigas()
    return logs


CATEGORIAS_POR_VOLTA = 20


def atualizar_categorias_antigas(limite: int = CATEGORIAS_POR_VOLTA) -> int:
    """Produtos guardados quando a categoria saía só do nome: busca a categoria da Shopee de
    cada um (aos poucos, algumas por volta do worker). Os que a pessoa corrigiu não mudam."""
    antigos = (ProdutoSite.objects.exclude(categoria="").exclude(categoria__in=list(CATEGORIAS))
               .filter(site__conta__shopee_validado_em__isnull=False).select_related("site__conta")[:limite])
    feitos = 0
    for produto in antigos:
        site = produto.site
        if CategoriaProdutoSite.objects.filter(site=site, item_id=produto.item_id).exists():
            continue
        try:
            app_id, secret = _credenciais(site)
            achado = shopee_ofertas.buscar_produto_por_item(app_id, secret, produto.item_id)
        except Exception as erro:  # noqa: BLE001 - fica com a categoria mais próxima (sem tentar de novo a cada volta)
            logger.warning("Meu site: categoria do produto %s na Shopee: %s", produto.pk, erro)
            achado = None
        oficial = str((achado or {}).get("categoria_id") or "")
        nova = oficial if oficial in CATEGORIAS else NICHO_PARA_CATEGORIA.get(produto.categoria, "")
        ProdutoSite.objects.filter(pk=produto.pk).update(categoria=nova)
        feitos += 1
    return feitos


def escolher_categoria(site, produto: ProdutoSite, categoria: str) -> str:
    """Guarda a categoria escolhida para o produto (vale também nas próximas atualizações)."""
    categoria = categoria if categoria in CATEGORIAS else ""
    CategoriaProdutoSite.objects.update_or_create(site=site, item_id=produto.item_id, defaults={"categoria": categoria})
    ProdutoSite.objects.filter(site=site, item_id=produto.item_id).update(categoria=categoria)
    return categoria
