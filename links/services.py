from django.conf import settings

from ofertas.services import resolver_item_id_sem_rede

from .models import Click
from .shopee_client import gerar_link_curto


def gerar_click(usuario, tipo: str, url_original: str | None, item_id_alvo: int | None = None) -> Click:
    """Cria um Click com subIds próprios e obtém o link de afiliado na API Shopee.

    item_id_alvo identifica qual produto gerou o clique (link específico ou card da
    vitrine) - usado depois, na sincronização de pedidos, pra confirmar que a compra
    real bate com o produto do link antes de aplicar o piso de cashback de venda
    direta (ver pedidos/services.py e ROADMAP.md, Fase 41). Quem já sabe o item_id de
    antemão (ex: ir_para_oferta, que tem o campo Oferta.item_id à mão) passa direto;
    senão, tenta identificar da própria URL - só pelo padrão de texto, sem seguir
    redirecionamento (isso pode levar até 10s pra link curto - ver Fase 35 - e
    travaria essa ação do usuário). Fica None quando não dá pra saber sem isso -
    esses cliques só vão poder contar pro piso de venda indireta depois."""
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
