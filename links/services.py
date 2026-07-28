from django.conf import settings

from .models import Click
from .shopee_client import gerar_link_curto


def gerar_click(usuario, tipo: str, url_original: str | None) -> Click:
    """Cria um Click com subIds próprios e obtém o link de afiliado na API Shopee."""
    url_alvo = url_original if tipo == Click.TIPO_PRODUTO else settings.SHOPEE_HOME_URL

    click = Click.objects.create(
        usuario=usuario,
        tipo=tipo,
        url_original=url_alvo,
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
