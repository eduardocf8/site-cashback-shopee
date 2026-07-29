import re
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from links.models import Click
from links.shopee_client import buscar_conversoes

from .models import Pedido

PADRAO_USUARIO = re.compile(r"^user(\d+)$")
PADRAO_UUID_HEX = re.compile(r"^[0-9a-fA-F]{32}$")

# Valores confirmados em uso real pela API Shopee (vistos em produção em outra
# integração). UNPAID entra como cancelado porque pedidos nesse status não
# geram comissão (o valor já vem zerado da própria Shopee).
STATUS_EXATO = {
    "COMPLETED": Pedido.STATUS_VALIDADO,
    "PENDING": Pedido.STATUS_PENDENTE,
    "UNPAID": Pedido.STATUS_CANCELADO,
    "CANCELLED": Pedido.STATUS_CANCELADO,
}
TERMOS_CANCELADO = ("CANCEL", "INVALID", "REJECT", "UNPAID", "FRAUD")
TERMOS_VALIDADO = ("COMPLETE", "CONFIRM", "PAID", "SUCCESS")


def mapear_status(status_bruto: str) -> str:
    """Mapeia o status textual da Shopee para nosso status interno.

    Usa primeiro os valores exatos já confirmados em uso real (STATUS_EXATO);
    qualquer valor diferente desses cai numa aproximação por palavras-chave,
    para não quebrar caso a Shopee use algum status ainda não visto.
    """
    valor = (status_bruto or "").upper()
    if valor in STATUS_EXATO:
        return STATUS_EXATO[valor]
    if any(termo in valor for termo in TERMOS_CANCELADO):
        return Pedido.STATUS_CANCELADO
    if any(termo in valor for termo in TERMOS_VALIDADO):
        return Pedido.STATUS_VALIDADO
    return Pedido.STATUS_PENDENTE


def resolver_click(utm_content: str) -> Click | None:
    """Tenta identificar o Click original a partir do utmContent devolvido pela Shopee."""
    if not utm_content:
        return None

    partes = re.split(r"[^0-9a-fA-F]+", utm_content)
    click_id = next((parte for parte in partes if PADRAO_UUID_HEX.match(parte)), None)
    if not click_id:
        return None

    return Click.objects.filter(id=click_id).select_related("usuario").first()


def _converter_timestamp(valor):
    if not valor:
        return None
    return datetime.fromtimestamp(int(valor), tz=dt_timezone.utc)


def calcular_data_prevista_liberacao(data_validacao):
    """1º dia do mês seguinte a dois meses após a validação (mês N -> libera no mês N+2)."""
    if not data_validacao:
        return None
    mes = data_validacao.month + 2
    ano = data_validacao.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return date(ano, mes, 1)


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
                status_shopee = mapear_status(pedido_shopee.get("orderStatus"))
                itens = pedido_shopee.get("items", [])
                comissao = sum(
                    (Decimal(str(item.get("itemTotalCommission") or "0")) for item in itens),
                    Decimal("0"),
                )
                tempos_conclusao = [item["completeTime"] for item in itens if item.get("completeTime")]
                data_validacao = _converter_timestamp(max(tempos_conclusao)) if tempos_conclusao else None

                nomes_produto = []
                for item in itens:
                    nome = item.get("itemName") or ""
                    if nome and nome not in nomes_produto:
                        nomes_produto.append(nome)
                imagem_produto = next((item.get("imageUrl") for item in itens if item.get("imageUrl")), "")

                existente = Pedido.objects.filter(order_id=pedido_shopee["orderId"]).first()
                # Uma vez liberado, o saldo já pode ter sido considerado disponível pro
                # usuário - uma nova sincronização não pode "desliberar" o pedido só
                # porque a Shopee ainda reporta o status antigo (COMPLETED).
                if existente and existente.status == Pedido.STATUS_LIBERADO:
                    status_final = Pedido.STATUS_LIBERADO
                else:
                    status_final = status_shopee

                motivo_cancelamento = ""
                if status_final == Pedido.STATUS_CANCELADO:
                    motivos = []
                    for item in itens:
                        motivo = item.get("fraudReason") or ""
                        if motivo and motivo not in motivos:
                            motivos.append(motivo)
                    motivo_cancelamento = "; ".join(motivos)[:255]

                _, criado = Pedido.objects.update_or_create(
                    order_id=pedido_shopee["orderId"],
                    defaults={
                        "conversion_id": str(conversao.get("conversionId", "")),
                        "click": click,
                        "usuario": click.usuario if click else None,
                        "status": status_final,
                        "status_shopee_bruto": pedido_shopee.get("orderStatus") or "",
                        "valor_comissao": comissao,
                        "valor_cashback": (comissao * percentual).quantize(Decimal("0.01")),
                        "produto_nome": ", ".join(nomes_produto)[:255],
                        "produto_imagem_url": imagem_produto,
                        "motivo_cancelamento": motivo_cancelamento,
                        "data_compra": data_compra,
                        "data_validacao": data_validacao,
                        "data_prevista_liberacao": calcular_data_prevista_liberacao(data_validacao),
                    },
                )
                novos += criado
                atualizados += not criado

        scroll_id = pagina["pageInfo"].get("scrollId")
        if not pagina["pageInfo"].get("hasNextPage"):
            break

    return {"novos": novos, "atualizados": atualizados, "nao_identificados": nao_identificados}


def liberar_saldo() -> int:
    """Libera (muda para STATUS_LIBERADO) os pedidos validados cuja data prevista já chegou."""
    hoje = timezone.localdate()
    return Pedido.objects.filter(
        status=Pedido.STATUS_VALIDADO,
        data_prevista_liberacao__lte=hoje,
    ).update(status=Pedido.STATUS_LIBERADO, data_liberacao=timezone.now())
