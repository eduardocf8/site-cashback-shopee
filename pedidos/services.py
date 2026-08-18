import re
from collections import defaultdict
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from accounts.models import Indicacao
from links.models import Click
from links.shopee_client import buscar_conversoes

from .models import Pedido
from .notificacoes import notificar_indicador_bonus_pendente, notificar_pedido_liberado, notificar_pedido_validado

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
    """Dia 1º do segundo mês seguinte ao mês da validação (mês N -> libera no mês N+2)."""
    if not data_validacao:
        return None
    mes = data_validacao.month + 2
    ano = data_validacao.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return date(ano, mes, 1)


CAMPOS_ATUALIZAVEIS = [
    "conversion_id",
    "click",
    "usuario",
    "status",
    "status_shopee_bruto",
    "valor_comissao",
    "valor_cashback",
    "multiplicador_campanha",
    "produto_nome",
    "produto_imagem_url",
    "motivo_cancelamento",
    "data_compra",
    "data_validacao",
    "data_prevista_liberacao",
]


def _montar_defaults(conversao, pedido_shopee, click, data_compra, percentual_base, multiplicador):
    status_shopee = mapear_status(pedido_shopee.get("orderStatus"))
    itens = pedido_shopee.get("items", [])
    # O teto acompanha o multiplicador de campanha: numa campanha de cashback em dobro,
    # o teto também dobra. Sem isso, item de comissão alta ficaria capado no mesmo valor
    # de sempre e não veria diferença nenhuma na campanha. Mesma lógica que
    # _limite_cashback_indicacao aplica ao bônus de indicação.
    percentual = percentual_base * multiplicador
    limite_por_produto = Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO)) * multiplicador

    # O teto é por produto, não por pedido - por isso cada item é limitado individualmente
    # antes de somar. itemTotalCommission já inclui o bônus de campanha do vendedor quando
    # ativo (confirmado comparando com o painel oficial de afiliados da Shopee), então sem
    # esse teto um único item de comissão alta pagaria um cashback desproporcional ao preço.
    #
    # Sem Click identificado, o pedido não veio daqui (outra campanha, compra pessoal etc.
    # - ver OrigemFilter em pedidos/admin.py) e não tem usuário pra receber o cashback, então
    # não faz sentido calcular um valor que nunca vai ser pago a ninguém. valor_comissao
    # continua sendo somado normalmente - é o que a Shopee realmente paga pra conta de
    # afiliado, independente da origem do pedido.
    comissao = Decimal("0")
    cashback = Decimal("0")
    for item in itens:
        comissao_item = Decimal(str(item.get("itemTotalCommission") or "0"))
        comissao += comissao_item
        if click:
            cashback += min(comissao_item * percentual, limite_por_produto).quantize(Decimal("0.01"))

    tempos_conclusao = [item["completeTime"] for item in itens if item.get("completeTime")]
    data_validacao = _converter_timestamp(max(tempos_conclusao)) if tempos_conclusao else None

    nomes_produto = []
    for item in itens:
        nome = item.get("itemName") or ""
        if nome and nome not in nomes_produto:
            nomes_produto.append(nome)
    imagem_produto = next((item.get("imageUrl") for item in itens if item.get("imageUrl")), "")

    motivo_cancelamento = ""
    if status_shopee == Pedido.STATUS_CANCELADO:
        motivos = []
        for item in itens:
            motivo = item.get("fraudReason") or ""
            if motivo and motivo not in motivos:
                motivos.append(motivo)
        motivo_cancelamento = "; ".join(motivos)[:255]

    return {
        "conversion_id": str(conversao.get("conversionId", "")),
        "click": click,
        "usuario": click.usuario if click else None,
        "status": status_shopee,
        "status_shopee_bruto": pedido_shopee.get("orderStatus") or "",
        "valor_comissao": comissao,
        "valor_cashback": cashback,
        "produto_nome": ", ".join(nomes_produto)[:255],
        "produto_imagem_url": imagem_produto,
        "motivo_cancelamento": motivo_cancelamento,
        "data_compra": data_compra,
        "data_validacao": data_validacao,
        "data_prevista_liberacao": calcular_data_prevista_liberacao(data_validacao),
    }


def _montar_linhas(brutos_por_order_id: dict[str, tuple], percentual_base: Decimal) -> dict[str, dict]:
    """Monta os defaults de cada pedido já com o multiplicador de campanha correto.

    Pedido novo usa o multiplicador vigente agora; pedido que já existe reusa o que
    ficou gravado nele na primeira vez. Isso é o que impede a campanha de vazar pros
    dois lados - a Shopee reenvia o mesmo pedido em toda sincronização seguinte, e o
    _montar_defaults recalcula valor_cashback do zero a cada vez, então sem congelar
    o multiplicador:

    - o dobro prometido numa campanha sumiria na primeira sincronização depois dela
      acabar, justamente pra quem comprou por causa da campanha;
    - ligar uma campanha dobraria retroativamente pedidos antigos que ainda estejam
      dentro da janela de sincronização.

    É o mesmo cuidado que _reaplicar_bonus_ja_concedido tem com o bônus de indicação.
    """
    multiplicador_atual = Decimal(str(settings.CASHBACK_MULTIPLICADOR_CAMPANHA))
    ja_gravados = dict(
        Pedido.objects.filter(order_id__in=brutos_por_order_id.keys()).values_list(
            "order_id", "multiplicador_campanha"
        )
    )

    linhas: dict[str, dict] = {}
    for order_id, (conversao, pedido_shopee, click, data_compra) in brutos_por_order_id.items():
        multiplicador = ja_gravados.get(order_id, multiplicador_atual)
        defaults = _montar_defaults(
            conversao, pedido_shopee, click, data_compra, percentual_base, multiplicador
        )
        defaults["multiplicador_campanha"] = multiplicador
        linhas[order_id] = defaults
    return linhas


def sincronizar(purchase_time_start: int, purchase_time_end: int) -> dict:
    """Busca conversões da Shopee no período e cria/atualiza os Pedidos correspondentes.

    Processa tudo em lote (poucas consultas ao banco no total, em vez de várias por
    pedido) porque uma conta com muitos pedidos reais pode ter milhares de linhas, e
    fazer isso uma de cada vez é rápido demais no SQLite local mas estoura o tempo
    limite do servidor contra um banco remoto de verdade.
    """
    percentual_base = Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL)) / Decimal("100")

    nao_identificados = 0
    scroll_id = None
    # Guarda os dados crus da Shopee em vez dos defaults já calculados: o cashback só
    # pode ser calculado depois de saber quais desses pedidos já existem no banco, pra
    # cada um usar o multiplicador de campanha certo (ver _montar_linhas).
    brutos_por_order_id: dict[str, tuple] = {}

    while True:
        pagina = buscar_conversoes(purchase_time_start, purchase_time_end, scroll_id)

        for conversao in pagina["nodes"]:
            click = resolver_click(conversao.get("utmContent"))
            if click is None:
                nao_identificados += 1

            data_compra = _converter_timestamp(conversao.get("purchaseTime"))

            for pedido_shopee in conversao.get("orders", []):
                # Se o mesmo pedido aparecer mais de uma vez nesta sincronização,
                # fica valendo a última ocorrência.
                brutos_por_order_id[pedido_shopee["orderId"]] = (conversao, pedido_shopee, click, data_compra)

        scroll_id = pagina["pageInfo"].get("scrollId")
        if not pagina["pageInfo"].get("hasNextPage"):
            break

    linhas_por_order_id = _montar_linhas(brutos_por_order_id, percentual_base)

    _reaplicar_bonus_ja_concedido(linhas_por_order_id)

    novos = 0
    atualizados = 0
    existentes = {p.order_id: p for p in Pedido.objects.filter(order_id__in=linhas_por_order_id.keys())}

    novos_objs = []
    atualizados_objs = []
    recem_validados = []
    for order_id, defaults in linhas_por_order_id.items():
        existente = existentes.get(order_id)
        if existente:
            status_antes = existente.status
            # Uma vez liberado, o saldo já pode ter sido considerado disponível pro
            # usuário - uma nova sincronização não pode "desliberar" o pedido só
            # porque a Shopee ainda reporta o status antigo (COMPLETED).
            if existente.status == Pedido.STATUS_LIBERADO:
                defaults = {**defaults, "status": Pedido.STATUS_LIBERADO, "motivo_cancelamento": ""}
            for campo, valor in defaults.items():
                setattr(existente, campo, valor)
            atualizados_objs.append(existente)
            atualizados += 1
            if status_antes != Pedido.STATUS_VALIDADO and existente.status == Pedido.STATUS_VALIDADO:
                recem_validados.append(existente)
        else:
            novo = Pedido(order_id=order_id, **defaults)
            novos_objs.append(novo)
            novos += 1
            if novo.status == Pedido.STATUS_VALIDADO:
                recem_validados.append(novo)

    # Dobra o cashback dos pedidos que disparam bônus de indicação antes de salvar -
    # os objetos em recem_validados são os mesmos que estão em novos_objs/atualizados_objs.
    vinculos_indicacao = _selecionar_bonus_indicacao(recem_validados)

    # batch_size evita um único UPDATE/INSERT gigante quando a janela de 60 dias
    # acumula muitos pedidos - sem isso, o Postgres pode demorar a ponto de
    # estourar o timeout do servidor (visto em produção com bulk_update sem lote).
    if novos_objs:
        Pedido.objects.bulk_create(novos_objs, batch_size=200)
    if atualizados_objs:
        Pedido.objects.bulk_update(atualizados_objs, CAMPOS_ATUALIZAVEIS, batch_size=200)

    _persistir_vinculos_indicacao(vinculos_indicacao)

    for indicacao, campo, _order_id in vinculos_indicacao:
        if campo == "pedido_bonus_indicado":
            notificar_indicador_bonus_pendente(indicacao)

    for pedido in recem_validados:
        if pedido.usuario_id:
            notificar_pedido_validado(pedido)

    return {"novos": novos, "atualizados": atualizados, "nao_identificados": nao_identificados}


def _limite_cashback_indicacao(multiplicador_campanha: Decimal) -> Decimal:
    """Teto do cashback num pedido com bônus de indicação: o teto normal por produto
    (CASHBACK_MAXIMO_POR_PRODUTO) x o multiplicador de indicação. Existe porque o teto
    normal é por produto, não por pedido - um pedido com mais de um item já pode somar
    mais que o teto de um produto só antes do dobro entrar em cena (ex: 2 itens capados
    a R$10 cada = R$20 no pedido), e sem esse teto o dobro multiplicaria esse total em
    vez de dobrar só o limite de um produto.

    Os dois multiplicadores se compõem: num pedido feito durante uma campanha de
    cashback em dobro, o teto por item já dobrou em _montar_defaults, então o teto da
    indicação precisa dobrar junto - senão o bônus de indicação seria inteiramente
    engolido pelo teto e a segunda promessa não pagaria nada."""
    return (
        Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO))
        * multiplicador_campanha
        * Decimal(str(settings.CASHBACK_MULTIPLICADOR_INDICACAO))
    )


def _reaplicar_bonus_ja_concedido(linhas_por_order_id: dict[str, dict]) -> None:
    """A Shopee reenvia o mesmo pedido validado em toda sincronização seguinte, e
    _montar_defaults recalcula valor_cashback do zero a cada vez - sem isso, o dobro
    de cashback já concedido por indicação seria substituído pelo valor normal na
    primeira sincronização depois de concedido. Muta linhas_por_order_id em memória,
    antes de qualquer Pedido ser criado/atualizado."""
    order_ids = list(linhas_por_order_id.keys())
    if not order_ids:
        return

    indicacoes = Indicacao.objects.filter(
        Q(pedido_bonus_indicado__order_id__in=order_ids) | Q(pedido_bonus_indicador__order_id__in=order_ids)
    ).select_related("pedido_bonus_indicado", "pedido_bonus_indicador")

    multiplicador = Decimal(str(settings.CASHBACK_MULTIPLICADOR_INDICACAO))
    for indicacao in indicacoes:
        for pedido_bonus in (indicacao.pedido_bonus_indicado, indicacao.pedido_bonus_indicador):
            if pedido_bonus and pedido_bonus.order_id in linhas_por_order_id:
                defaults = linhas_por_order_id[pedido_bonus.order_id]
                limite = _limite_cashback_indicacao(defaults["multiplicador_campanha"])
                defaults["valor_cashback"] = min(
                    (defaults["valor_cashback"] * multiplicador).quantize(Decimal("0.01")), limite
                )


def _selecionar_bonus_indicacao(recem_validados: list[Pedido]) -> list[tuple[Indicacao, str, str]]:
    """Decide quais pedidos recém-validados NESTA sincronização ganham o dobro de
    cashback do programa "indique e ganhe", e já dobra o valor_cashback deles.

    Só considera pedidos validando pela primeira vez agora (não todo pedido validado
    já existente) - o vínculo gravado em Indicacao garante que o mesmo pedido continue
    dobrado nas sincronizações seguintes, mesmo que a Shopee reenvie o mesmo pedido
    validado repetidas vezes.

    Retorna uma lista de (indicacao, nome_do_campo, order_id) pra gravar depois que os
    Pedidos existirem de verdade no banco (bulk_create ainda não rodou nesse ponto).
    """
    usuario_ids = {pedido.usuario_id for pedido in recem_validados if pedido.usuario_id}
    if not usuario_ids:
        return []

    indicacoes = list(
        Indicacao.objects.filter(
            Q(indicado_id__in=usuario_ids, pedido_bonus_indicado__isnull=True)
            | Q(indicador_id__in=usuario_ids, pedido_bonus_indicado__isnull=False, pedido_bonus_indicador__isnull=True)
        ).order_by("criado_em")
    )
    indicado_pendente = {i.indicado_id: i for i in indicacoes if i.pedido_bonus_indicado_id is None}
    indicador_fila = defaultdict(list)
    for i in indicacoes:
        if i.pedido_bonus_indicado_id is not None and i.pedido_bonus_indicador_id is None:
            indicador_fila[i.indicador_id].append(i)

    multiplicador = Decimal(str(settings.CASHBACK_MULTIPLICADOR_INDICACAO))
    epoca_minima = datetime.min.replace(tzinfo=dt_timezone.utc)
    vinculos = []
    for pedido in sorted(recem_validados, key=lambda p: p.data_compra or epoca_minima):
        limite = _limite_cashback_indicacao(pedido.multiplicador_campanha)
        if pedido.usuario_id in indicado_pendente:
            indicacao = indicado_pendente.pop(pedido.usuario_id)
            pedido.valor_cashback = min((pedido.valor_cashback * multiplicador).quantize(Decimal("0.01")), limite)
            vinculos.append((indicacao, "pedido_bonus_indicado", pedido.order_id))
        elif indicador_fila.get(pedido.usuario_id):
            indicacao = indicador_fila[pedido.usuario_id].pop(0)
            pedido.valor_cashback = min((pedido.valor_cashback * multiplicador).quantize(Decimal("0.01")), limite)
            vinculos.append((indicacao, "pedido_bonus_indicador", pedido.order_id))

    return vinculos


def _persistir_vinculos_indicacao(vinculos: list[tuple[Indicacao, str, str]]) -> None:
    """Grava em Indicacao qual Pedido concreto disparou cada bônus - roda depois do
    bulk_create/bulk_update, quando os Pedidos já existem de verdade no banco."""
    if not vinculos:
        return

    order_ids = [order_id for _, _, order_id in vinculos]
    pedidos_por_order_id = Pedido.objects.in_bulk(order_ids, field_name="order_id")
    for indicacao, campo, order_id in vinculos:
        setattr(indicacao, campo, pedidos_por_order_id[order_id])

    Indicacao.objects.bulk_update(
        [indicacao for indicacao, _, _ in vinculos], ["pedido_bonus_indicado", "pedido_bonus_indicador"]
    )


def liberar_saldo() -> int:
    """Libera (muda para STATUS_LIBERADO) os pedidos validados cuja data prevista já chegou."""
    hoje = timezone.localdate()
    pedidos = list(
        Pedido.objects.filter(
            status=Pedido.STATUS_VALIDADO,
            data_prevista_liberacao__lte=hoje,
        ).select_related("usuario")
    )
    for pedido in pedidos:
        if pedido.usuario_id:
            notificar_pedido_liberado(pedido)

    if not pedidos:
        return 0
    return Pedido.objects.filter(pk__in=[p.pk for p in pedidos]).update(
        status=Pedido.STATUS_LIBERADO, data_liberacao=timezone.now()
    )
