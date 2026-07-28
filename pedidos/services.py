import re
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings

from links.models import Click
from links.shopee_client import buscar_conversoes

from .models import Pedido

PADRAO_USUARIO = re.compile(r"^user(\d+)$")
PADRAO_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

TERMOS_CANCELADO = ("CANCEL", "INVALID", "REJECT", "UNPAID", "FRAUD")
TERMOS_VALIDADO = ("COMPLETE", "CONFIRM", "PAID", "SUCCESS")


def mapear_status(status_bruto: str) -> str:
    """Mapeia o status textual da Shopee para nosso status interno.

    Os valores exatos que a Shopee usa não são documentados publicamente;
    esse mapeamento é uma aproximação por palavras-chave e deve ser ajustado
    assim que virmos pedidos reais passando por aqui.
    """
    valor = (status_bruto or "").upper()
    if any(termo in valor for termo in TERMOS_CANCELADO):
        return Pedido.STATUS_CANCELADO
    if any(termo in valor for termo in TERMOS_VALIDADO):
        return Pedido.STATUS_VALIDADO
    return Pedido.STATUS_PENDENTE


def resolver_click(utm_content: str) -> Click | None:
    """Tenta identificar o Click original a partir do utmContent devolvido pela Shopee."""
    if not utm_content:
        return None

    partes = re.split(r"[^0-9a-fA-F\-]+", utm_content)
    click_id = next((parte for parte in partes if PADRAO_UUID.match(parte)), None)
    if not click_id:
        return None

    return Click.objects.filter(id=click_id).select_related("usuario").first()


def _converter_timestamp(valor):
    if not valor:
        return None
    return datetime.fromtimestamp(int(valor), tz=dt_timezone.utc)


def sincronizar(purchase_time_start: int, purchase_time_end: int) -> dict:
    """Busca conversões da Shopee no período e cria/atualiza os Pedidos correspondentes."""
    percentual = Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL)) / Decimal("100")

    novos = 0
    atualizados = 0
    nao_identificados = 0
    scroll_id = None

    while True:
        pagina = buscar_conversoes(purchase_time_start, purchase_time_end, scroll_id)

        for conversao in pagina["nodes"]:
            click = resolver_click(conversao.get("utmContent"))
            if click is None:
                nao_identificados += 1

            data_compra = _converter_timestamp(conversao.get("purchaseTime"))

            for pedido_shopee in conversao.get("orders", []):
                status = mapear_status(pedido_shopee.get("orderStatus"))
                comissao = Decimal(str(pedido_shopee.get("netCommission") or "0"))

                _, criado = Pedido.objects.update_or_create(
                    order_id=pedido_shopee["orderId"],
                    defaults={
                        "conversion_id": str(conversao.get("conversionId", "")),
                        "click": click,
                        "usuario": click.usuario if click else None,
                        "status": status,
                        "status_shopee_bruto": pedido_shopee.get("orderStatus") or "",
                        "valor_comissao": comissao,
                        "valor_cashback": (comissao * percentual).quantize(Decimal("0.01")),
                        "data_compra": data_compra,
                        "data_validacao": _converter_timestamp(pedido_shopee.get("completeTime")),
                    },
                )
                novos += criado
                atualizados += not criado

        scroll_id = pagina["pageInfo"].get("scrollId")
        if not pagina["pageInfo"].get("hasNextPage"):
            break

    return {"novos": novos, "atualizados": atualizados, "nao_identificados": nao_identificados}
