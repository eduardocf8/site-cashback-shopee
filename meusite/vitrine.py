"""Produtos da vitrine do Meu site e os links de afiliado (com o Sub ID do site).

- "bot": cada oferta que o bot de WhatsApp põe na fila entra no topo; o mesmo produto
  não duplica (volta para o topo) e só ficam as mais recentes, até o limite do plano;
- "busca": o worker refaz a busca na Shopee de tempos em tempos (mesmos campos do bot), com as
  categorias equilibradas (veja atualizar_busca);
- "manual": os links que a pessoa colou, na ordem dela (buscados aos poucos, MANUAIS_POR_VOLTA por volta).
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

REFAZER_BUSCA_APOS = timedelta(hours=3)
TETO_POR_CATEGORIA = 15  # "Ofertas em geral": no máximo 15% da vitrine de cada categoria...
PAGINAS_POR_VAGA = 3  # ...procurando até 3x mais produtos que as vagas para completar
MAXIMO_DE_PAGINAS = 40  # páginas de 50 numa busca (1.000 vagas)
MANUAIS_POR_VOLTA = 50  # links escolhidos buscados na Shopee por volta do worker
LINKS_POR_VOLTA = 30  # links de afiliado gerados por volta do worker


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


def limite_de_ofertas(site) -> int:
    """Quantos produtos a vitrine mostra no plano da conta."""
    regras = planos.site(site.conta)
    return regras["escolhidos"] if site.vitrine == SiteAfiliado.VITRINE_MANUAL else regras["ofertas"]


def _cortar(site, fonte: str, limite: int):
    """Passou do limite: sai a mais antiga da categoria com mais produtos (e não a mais antiga de
    todas), para a vitrine não virar uma categoria só quando o bot manda muito de uma."""
    produtos = list(ProdutoSite.objects.filter(site=site, fonte=fonte).order_by("posicao_em", "id").values_list("id", "categoria"))
    excesso = len(produtos) - limite
    if excesso <= 0:
        return
    por_categoria = {}
    for pk, categoria in produtos:  # do mais antigo para o mais novo
        por_categoria.setdefault(categoria, []).append(pk)
    saem = []
    for _ in range(excesso):
        maior = max(por_categoria.values(), key=len)
        saem.append(maior.pop(0))
    ProdutoSite.objects.filter(id__in=saem).delete()


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
                _cortar(site, SiteAfiliado.VITRINE_BOT, planos.site(conta)["ofertas"])
    except Exception:  # noqa: BLE001 - a vitrine nunca pode atrapalhar o envio da oferta
        logger.exception("Meu site: não deu para pôr a oferta na vitrine da conta %s", conta.pk)


def _credenciais(site) -> tuple[str, str]:
    return site.conta.shopee_app_id, cripto.decifrar(site.conta.shopee_secret_cifrado)


# Categorias do bot (busca "Categorias") -> categorias principais da Shopee onde buscar cada uma.
# filtrar_nome: a categoria da Shopee é mais larga que a do bot (ex: Ferramentas dentro de Casa),
# então confere também o nome. Sem categoria na Shopee (Alimentos): busca geral filtrada pelo nome.
NICHO_NA_SHOPEE = {
    "moda": {"ids": ["100017", "100011", "100532", "100012", "100016", "100533"]},
    "beleza": {"ids": ["100630"]},
    "casa": {"ids": ["100636"]},
    "eletronicos": {"ids": ["100013", "100644", "100535", "100635"]},
    "eletrodomesticos": {"ids": ["100010"]},
    "bebes": {"ids": ["100632", "100633"]},
    "brinquedos": {"ids": ["100639"]},
    "esporte": {"ids": ["100637"]},
    "automotivo": {"ids": ["100640", "100641"]},
    "pet": {"ids": ["100631"]},
    "papelaria": {"ids": ["100638"]},
    "saude": {"ids": ["100001"]},
    "joias": {"ids": ["100009", "100534"]},
    "ferramentas": {"ids": ["100636"], "filtrar_nome": True},
    "alimentos": {"ids": [], "filtrar_nome": True},
}


def _config_da_busca(site, categoria_shopee=None) -> ConfiguracaoOfertas:
    """Mesma busca do bot (sem os filtros de número): uma configuração do bot só em memória."""
    config = ConfiguracaoOfertas(
        tipo_busca=site.busca_tipo, palavra_chave=site.palavra_chave, loja=site.loja,
        categorias=site.categorias, ordenacao=site.ordenacao, comissao_minima=0, desconto_minimo=0,
        preco_minimo=None, preco_maximo=None, vendas_minimas=0, avaliacao_minima=None,
    )
    if categoria_shopee:  # já é a categoria da Shopee: sem o filtro pelo nome das categorias do bot
        config.tipo_busca, config.categoria_shopee = ConfiguracaoOfertas.BUSCA_GERAL, categoria_shopee
    return config


def _paginas(app_id, secret, config, paginas, filtro=None):
    """Os produtos das páginas, uma de cada vez, até acabar (para quem precisa de mais)."""
    for pagina in range(1, paginas + 1):
        produtos, tem_proxima = shopee_ofertas.buscar_produtos(app_id, secret, config, pagina)
        yield [p for p in produtos if shopee_ofertas.passa_nos_filtros(p, config) and (not filtro or filtro(p))]
        if not tem_proxima:
            return


def _paginas_para(vagas: int, folga: int = 1) -> int:
    return min(MAXIMO_DE_PAGINAS, -(-vagas * folga // shopee_ofertas.POR_PAGINA))


def _busca_geral(site, app_id, secret, limite: int) -> list[dict]:
    """Uma busca só (geral, palavra-chave ou loja), na ordem da Shopee. Em "Ofertas em geral",
    no máximo TETO_POR_CATEGORIA% das vagas para cada categoria: os mais vendidos se concentram
    em poucas categorias e a vitrine ficava com 40 de uma e 1 de outra. Se não der para
    completar, o que passou do teto entra no fim."""
    config = _config_da_busca(site)
    equilibrar = site.busca_tipo == SiteAfiliado.BUSCA_GERAL
    teto = max(1, limite * TETO_POR_CATEGORIA // 100)
    escolhidos, sobra, por_categoria, vistos = [], [], {}, set()
    for produtos in _paginas(app_id, secret, config, _paginas_para(limite, PAGINAS_POR_VAGA if equilibrar else 1)):
        for p in produtos:
            if str(p["item_id"]) in vistos:
                continue
            vistos.add(str(p["item_id"]))
            categoria = categoria_do_produto(p)
            if equilibrar and por_categoria.get(categoria, 0) >= teto:
                sobra.append(p)
                continue
            por_categoria[categoria] = por_categoria.get(categoria, 0) + 1
            escolhidos.append(p)
        if len(escolhidos) >= limite:
            break
    return (escolhidos + sobra)[:limite]


def _busca_por_categoria(site, app_id, secret, limite: int) -> list[dict]:
    """Busca "Categorias": cada categoria escolhida é buscada na própria categoria da Shopee e
    as vagas são divididas por igual, intercaladas (uma de cada). Se uma categoria tiver
    menos, as outras completam."""
    nichos = [n for n in dict.fromkeys(site.categorias or []) if n in NICHO_NA_SHOPEE] or list(site.categorias or [])
    if not nichos:
        return _busca_geral(site, app_id, secret, limite)
    cota = -(-limite // len(nichos))  # arredonda para cima
    quantos = cota + cota // 2  # a folga cobre a categoria que tiver menos
    listas = []
    for nicho in nichos:
        regra = NICHO_NA_SHOPEE.get(nicho, {"ids": [], "filtrar_nome": True})
        filtro = (lambda p, n=nicho: produto_pertence_as_categorias(p["nome"], [n])) if regra.get("filtrar_nome") else None
        paginas = _paginas_para(quantos // max(1, len(regra["ids"])), 2 if filtro else 1) + 1
        fontes = [_paginas(app_id, secret, _config_da_busca(site, cid), paginas, filtro) for cid in regra["ids"]]
        if not fontes:  # sem categoria na Shopee: busca geral filtrada pelo nome
            geral = _config_da_busca(site)
            geral.tipo_busca, geral.categorias = ConfiguracaoOfertas.BUSCA_CATEGORIA, [nicho]
            fontes = [_paginas(app_id, secret, geral, _paginas_para(quantos, 4))]
        listas.append(_intercalar(_ate(fontes, quantos)))
    vistos, saida = set(), []
    for p in _intercalar(listas):
        if str(p["item_id"]) not in vistos:
            vistos.add(str(p["item_id"]))
            saida.append(p)
    return saida[:limite]


def _ate(fontes, quantos: int) -> list[list[dict]]:
    """Lê as fontes (geradores de páginas) aos poucos, todas por igual, até juntar quantos."""
    listas, ativas = [[] for _ in fontes], list(range(len(fontes)))
    while ativas and sum(len(lista) for lista in listas) < quantos:
        for i in list(ativas):
            pagina = next(fontes[i], None)
            if pagina is None:
                ativas.remove(i)
            else:
                listas[i] += pagina
    return listas


def _intercalar(listas: list[list[dict]]) -> list[dict]:
    """[[a1, a2], [b1]] -> [a1, b1, a2]."""
    saida = []
    for i in range(max((len(lista) for lista in listas), default=0)):
        saida += [lista[i] for lista in listas if i < len(lista)]
    return saida


def atualizar_busca(site, agora):
    app_id, secret = _credenciais(site)
    limite = limite_de_ofertas(site)
    if site.busca_tipo == SiteAfiliado.BUSCA_CATEGORIA:
        achados = _busca_por_categoria(site, app_id, secret, limite)
    else:
        achados = _busca_geral(site, app_id, secret, limite)
    with transaction.atomic():
        vistos = set()
        for i, produto in enumerate(achados[:limite]):
            if _guardar(site, SiteAfiliado.VITRINE_BUSCA, produto, agora - timedelta(seconds=i)):
                vistos.add(str(produto["item_id"]))
        ProdutoSite.objects.filter(site=site, fonte=SiteAfiliado.VITRINE_BUSCA).exclude(item_id__in=vistos).delete()


def links_manuais(site) -> list[str]:
    return [l.strip() for l in (site.links_manuais or "").splitlines() if l.strip()][: planos.site(site.conta)["escolhidos"]]


def atualizar_manuais(site, agora) -> bool:
    """Busca os produtos dos links colados, MANUAIS_POR_VOLTA por volta (com 1.000 links, de
    uma vez travaria o worker). O andamento fica em site.manuais_rodada; a rodada recomeça
    quando a pessoa salva de novo. Devolve True quando terminou."""
    app_id, secret = _credenciais(site)
    links = links_manuais(site)
    pedido = site.pedido_vitrine_em.isoformat() if site.pedido_vitrine_em else ""
    rodada = site.manuais_rodada or {}
    if rodada.get("pedido") != pedido:
        rodada = {"pedido": pedido, "feitos": 0, "vistos": [], "problemas": 0, "exemplos": []}
    base = site.pedido_vitrine_em or agora  # a mesma em todas as voltas: a ordem dos links vale
    inicio = min(rodada["feitos"], len(links))
    fim = min(len(links), inicio + MANUAIS_POR_VOLTA)
    for i in range(inicio, fim):
        link = links[i]
        achados = copia.links_shopee(link)
        try:
            item_id = copia.identificar_produto(achados[0]) if achados else ""
            produto = shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id) if item_id else None
        except Exception:  # noqa: BLE001 - um link com problema não para os outros
            logger.exception("Meu site: produto escolhido %s", link[:80])
            produto = None
        if not produto:
            rodada["problemas"] += 1
            rodada["exemplos"] = (rodada["exemplos"] + [link[:60]])[:3]
            continue
        if _guardar(site, SiteAfiliado.VITRINE_MANUAL, produto, base - timedelta(seconds=i)):
            rodada["vistos"].append(str(produto["item_id"]))
    rodada["feitos"] = fim
    terminou = fim >= len(links)
    site.manuais_rodada = {} if terminou else rodada
    site.save(update_fields=["manuais_rodada"])
    if terminou:
        ProdutoSite.objects.filter(site=site, fonte=SiteAfiliado.VITRINE_MANUAL).exclude(item_id__in=rodada["vistos"]).delete()
        if rodada["problemas"]:
            raise ValueError(f"Não achei {rodada['problemas']} produto(s) na Shopee: {', '.join(rodada['exemplos'])}")
    return terminou


def link_do_site(site, link_produto: str, vitrine: bool = False) -> str:
    """Link de afiliado do site. A vitrine pode ter um Sub ID próprio (vazio = o do conversor)."""
    app_id, secret = _credenciais(site)
    sub_id = (site.sub_id_vitrine or site.sub_id) if vitrine else site.sub_id
    sub_ids = [sub_id] if sub_id else []
    return shopee_ofertas.gerar_link_afiliado(app_id, secret, link_produto, sub_ids, "site")


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
            elif not atualizar_manuais(site, agora):
                logs.append(f"Meu site: vitrine de {site.endereco}, {site.manuais_rodada['feitos']} links lidos")
                continue  # continua na próxima volta (a vitrine segue "pedida")
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
