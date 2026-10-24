"""Radar de ofertas (menu, todos os planos): busca no catálogo de ofertas que a cash-b já
sincroniza todo dia (ofertas/catalogo.py, até 30 mil produtos, 27 categorias), em vez de
chamar a API da Shopee a cada busca. Fica rápido, não gasta as chamadas de cada afiliado e
permite filtrar tudo junto (palavra, categoria, preço, comissão, desconto...), com
paginação numerada. O link de afiliado de cada produto continua sendo gerado na hora, com a
conta de quem clicou (views_radar.py)."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from ofertas.models import Oferta, SincronizacaoCatalogo
from ofertas.services import carregar_categorias_nivel1

ORDENS = [("mais_vendidos", "Mais vendidos"), ("maior_comissao", "Maior comissão"), ("maior_desconto", "Maior desconto")]
ORDEM_NO_BANCO = {"mais_vendidos": ("-vendas", "-id"), "maior_comissao": ("-percentual_comissao", "-vendas", "-id"),
                  "maior_desconto": ("-percentual_desconto", "-vendas", "-id")}
PRODUTOS_POR_PAGINA = 24
SUB_ID = "radar"
CATALOGO_ATRASADO = timedelta(hours=48)  # sem rodada terminada há tanto tempo, avisa na tela


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


def categorias() -> list[tuple[int, str]]:
    """As categorias principais da Shopee (as mesmas do filtro da cash-b), por nome."""
    return sorted(carregar_categorias_nivel1().items(), key=lambda item: item[1])


def filtros_da_requisicao(dados) -> dict:
    ordem = dados.get("ordem") if dados.get("ordem") in dict(ORDENS) else "mais_vendidos"
    categoria = str(dados.get("categoria", ""))
    return {
        "palavra": " ".join(str(dados.get("palavra", "")).split())[:80],
        "ordem": ordem,
        "categoria": int(categoria) if categoria.isdigit() and int(categoria) in carregar_categorias_nivel1() else "",
        "preco_min": _numero(dados.get("preco_min")),
        "preco_max": _numero(dados.get("preco_max")),
        "comissao_min": _numero(dados.get("comissao_min"), 0, 100),
        "desconto_min": _numero(dados.get("desconto_min"), 0, 100),
        "avaliacao_min": _numero(dados.get("avaliacao_min"), 0, 5),
        "so_extra": dados.get("so_extra") in ("1", "on", "true"),
    }


def consulta(filtros: dict):
    """As ofertas do catálogo que passam nos filtros, já na ordem escolhida. Produto sem
    preço fica de fora (não dá para estimar a comissão nem mandar a oferta)."""
    ofertas = Oferta.objects.filter(preco_min__gt=0)
    for palavra in filtros["palavra"].split():  # todas as palavras, em qualquer ordem
        ofertas = ofertas.filter(nome__icontains=palavra)
    if filtros["categoria"]:
        ofertas = ofertas.filter(categoria_id=filtros["categoria"])
    if filtros["preco_min"] is not None:
        ofertas = ofertas.filter(preco_min__gte=filtros["preco_min"])
    if filtros["preco_max"] is not None:
        ofertas = ofertas.filter(preco_min__lte=filtros["preco_max"])
    if filtros["comissao_min"] is not None:  # no banco a comissão é uma fração: 0,05 = 5%
        ofertas = ofertas.filter(percentual_comissao__gte=filtros["comissao_min"] / 100)
    if filtros["desconto_min"] is not None:
        ofertas = ofertas.filter(percentual_desconto__gte=filtros["desconto_min"])
    if filtros["avaliacao_min"] is not None:
        ofertas = ofertas.filter(avaliacao__gte=filtros["avaliacao_min"])
    if filtros["so_extra"]:
        ofertas = ofertas.filter(percentual_comissao_extra__gt=0)
    return ofertas.order_by(*ORDEM_NO_BANCO[filtros["ordem"]])


def cartao(oferta: Oferta) -> dict:
    """O produto no formato que a tela do Radar usa."""
    comissao = float(oferta.percentual_comissao) * 100
    return {
        "item_id": str(oferta.item_id),
        "nome": oferta.nome_curto or oferta.nome,
        "imagem": oferta.imagem_url,
        "link": oferta.product_link,
        "preco": float(oferta.preco_min),
        "comissao": comissao,
        "comissao_extra": float(oferta.percentual_comissao_extra) * 100,
        "desconto": oferta.percentual_desconto,
        "vendas": oferta.vendas,
        "avaliacao": float(oferta.avaliacao) if oferta.avaliacao else 0,
        "loja": oferta.loja_nome,
        "ganho": round(float(oferta.preco_min) * comissao / 100, 2),  # comissão estimada por venda
    }


def situacao_do_catalogo() -> dict:
    """Quando os dados do catálogo foram atualizados pela última vez e se estão atrasados."""
    estado = SincronizacaoCatalogo.objects.first()
    ultima = None
    if estado:
        ultima = estado.finalizada_em or (estado.iniciada_em if estado.ultima_completa else None)
    atrasado = ultima is None or timezone.now() - ultima > CATALOGO_ATRASADO
    return {"atualizado_em": timezone.localtime(ultima) if ultima else None, "atrasado": atrasado,
            "total": Oferta.objects.filter(preco_min__gt=0).count()}
