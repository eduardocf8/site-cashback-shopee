from django.conf import settings

from ofertas.services import resolver_item_id_com_rede, resolver_item_id_sem_rede

from .models import Click
from .shopee_client import gerar_link_curto

LIMITE_RESOLUCOES_POR_EXECUCAO = 30


def gerar_click(usuario, tipo: str, url_original: str | None, item_id_alvo: int | None = None) -> Click:
    """Cria um Click com subIds próprios e obtém o link de afiliado na API Shopee.

    item_id_alvo identifica qual produto gerou o clique (link específico ou card da
    vitrine) - usado depois, na sincronização de pedidos, pra confirmar que a compra
    real bate com o produto do link antes de aplicar o piso de cashback de venda
    direta (ver pedidos/services.py e ROADMAP.md, Fase 41). Quem já sabe o item_id de
    antemão (ex: ir_para_oferta, que tem o campo Oferta.item_id à mão) passa direto;
    senão, tenta identificar da própria URL - só pelo padrão de texto, sem seguir
    redirecionamento (isso pode levar até 10s pra link curto - ver Fase 35 - e
    travaria essa ação do usuário). Fica None quando não dá pra saber sem isso - esses
    cliques só contam pro piso de venda indireta até a tarefa agendada
    (resolver_item_id_alvo_pendentes) conseguir resolver de verdade, seguindo
    redirecionamento, em segundo plano (ver ROADMAP.md, Fase 42)."""
    url_alvo = url_original if tipo != Click.TIPO_HOME else settings.SHOPEE_HOME_URL

    if item_id_alvo is None and tipo != Click.TIPO_HOME and url_alvo:
        item_id_alvo = resolver_item_id_sem_rede(url_alvo)

    click = Click.objects.create(
        usuario=usuario,
        tipo=tipo,
        url_original=url_alvo,
        item_id_alvo=item_id_alvo,
        link_gerado="",
    )

    sub_ids = [click.sub_id_usuario(), click.sub_id_click()]
    try:
        link_gerado = gerar_link_curto(url_alvo, sub_ids)
    except Exception:
        click.delete()
        raise

    click.link_gerado = link_gerado
    click.save(update_fields=["link_gerado"])
    return click


def resolver_item_id_alvo_pendentes() -> dict:
    """Tenta resolver, seguindo redirecionamento de verdade, o item_id_alvo dos
    cliques que a resolução rápida (sem rede, feita na hora do clique - ver
    gerar_click) não conseguiu - tipicamente links curtos (s.shopee.com.br, shp.ee).

    Roda numa tarefa agendada própria (ver cashback_shopee/views.py,
    executar_resolucao_item_id_alvo), separada da sincronização de pedidos: seguir
    redirecionamento pode levar até 10s por clique, e o orçamento de 120s de uma
    requisição não sobra pra isso junto com o resto (mesmo motivo de
    encurtar_nomes_pendentes ter tarefa própria, ver ofertas/services.py). Processa
    em lotes limitados (LIMITE_RESOLUCOES_POR_EXECUCAO) - sem pressa real, porque a
    Shopee só reporta um pedido de verdade alguns dias depois da compra (ver Fase 28),
    então uma tarefa diária dá conta do volume tranquilamente. Enquanto um clique
    continua sem item_id_alvo, ele só conta pro piso de venda indireta (ver
    pedidos/services.py, ROADMAP.md Fase 41)."""
    pendentes = (
        Click.objects.exclude(tipo=Click.TIPO_HOME)
        .filter(item_id_alvo__isnull=True)
        .order_by("criado_em")[:LIMITE_RESOLUCOES_POR_EXECUCAO]
    )

    tentados = 0
    resolvidos = 0
    for click in pendentes:
        tentados += 1
        item_id = resolver_item_id_com_rede(click.url_original)
        if item_id is not None:
            click.item_id_alvo = item_id
            click.save(update_fields=["item_id_alvo"])
            resolvidos += 1

    return {"tentados": tentados, "resolvidos": resolvidos}
