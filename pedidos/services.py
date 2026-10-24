import re
from collections import defaultdict
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from accounts.models import Indicacao, User
from links.models import Click
from links.shopee_client import buscar_conversoes

from .models import CampanhaCashback, ItemPedido, Pedido
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
    "valor_pedido",
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


def _item_bate_com_o_click(click: Click, item_id_bruto) -> bool:
    """Confirma que o item efetivamente comprado é o mesmo que gerou o clique (link
    específico ou card da vitrine) - sem isso, dava pra converter QUALQUER link de
    produto (ou clicar em qualquer card da vitrine) só pra destravar o piso de venda
    direta numa compra completamente diferente (ver ROADMAP.md, Fase 41). Clique sem
    item_id_alvo identificado (ex: link curto, resolvido só depois de seguir
    redirecionamento - ver Fase 35) não consegue provar o vínculo, então conta como
    não bate por padrão (mais seguro errar pro lado de baixo aqui)."""
    if click.item_id_alvo is None or not item_id_bruto:
        return False
    try:
        return int(item_id_bruto) == click.item_id_alvo
    except (TypeError, ValueError):
        return False


def _percentual_minimo_garantido(click: Click, item_bate_com_o_link: bool) -> Decimal:
    """Cashback mínimo garantido por produto, mesmo quando a comissão real da Shopee
    resultaria em menos - ao contrário do resto do cálculo (sempre uma fração da
    comissão real recebida, nunca um prejuízo), esse piso pode fazer a cash-b pagar
    mais do que recebeu de comissão naquele item específico. Só vale quando a Shopee
    reporta ALGUMA comissão (mesmo pequena) - item com comissão zerada (ex: categorias
    como alimentos/bebidas, que a Shopee não paga comissão de afiliado nenhuma) não
    tem direito ao piso, senão a cash-b pagaria cashback do próprio bolso sem ter
    recebido nada em troca (ver chamada em _montar_defaults). Venda direta (link
    específico/vitrine) só tem o piso maior quando o item comprado é comprovadamente
    o mesmo do link/card clicado (ver _item_bate_com_o_click) - senão vale o piso de
    venda indireta, mesmo que o Click tenha vindo de um link/vitrine específico."""
    eh_direta_verificada = click.tipo != Click.TIPO_HOME and item_bate_com_o_link
    if eh_direta_verificada:
        return Decimal(str(settings.CASHBACK_MINIMO_VENDA_DIRETA)) / Decimal("100")
    return Decimal(str(settings.CASHBACK_MINIMO_VENDA_INDIRETA)) / Decimal("100")


def cashback_item_vinculado_manualmente(valor_item, comissao_item, percentual_base, multiplicador) -> Decimal:
    """Cashback de um item de pedido vinculado pelo admin (reclamação de compra não
    registrada, ver ReclamacaoPedido): sem clique não dá pra provar qual link a pessoa
    usou, então vale a regra de venda indireta - mesma fórmula de _montar_defaults com
    o piso indireto, e zero pra item sem comissão."""
    if comissao_item <= 0:
        return Decimal("0.00")
    piso = Decimal(str(settings.CASHBACK_MINIMO_VENDA_INDIRETA)) / Decimal("100")
    base = max(comissao_item * percentual_base, valor_item * piso)
    return (base * multiplicador).quantize(Decimal("0.01"))


def _montar_defaults(
    conversao, pedido_shopee, click, data_compra, percentual_base, multiplicador, usuario_manual=None
):
    status_shopee = mapear_status(pedido_shopee.get("orderStatus"))
    itens = pedido_shopee.get("items", [])

    # itemTotalCommission já inclui o bônus de campanha do vendedor quando ativo
    # (confirmado comparando com o painel oficial de afiliados da Shopee). O cashback
    # normalmente é uma fração fixa dela (percentual_base, nunca mais que 100%) - sem
    # teto em R$. Quando isso resultaria em menos que o piso mínimo garantido (ver
    # _percentual_minimo_garantido), vale o piso em vez da fração da comissão - a
    # única parte do cálculo em que a cash-b pode pagar mais do que recebeu. O piso
    # maior de venda direta só vale por item, e só quando esse item específico bate
    # com o que gerou o clique (ver _item_bate_com_o_click) - um pedido com vários
    # itens pode ter só um deles qualificado.
    #
    # O piso só entra quando comissao_item > 0: categoria sem comissão de afiliado
    # nenhuma (ex: alimentos/bebidas) tem que pagar cashback zero, nunca o piso - senão
    # contradiria a mensagem mostrada ao converter o link ("sem comissão, sem
    # cashback", ver links/views.py::_buscar_cashback_real) e a cash-b pagaria do
    # próprio bolso por um item que não gerou nenhuma receita de comissão.
    #
    # Sem Click identificado, o pedido não veio daqui (outra campanha, compra pessoal etc.
    # - ver OrigemFilter em pedidos/admin.py) e não tem usuário pra receber o cashback, então
    # não faz sentido calcular um valor que nunca vai ser pago a ninguém. Mesma lógica pro
    # clique que existe mas ainda é anônimo (click.usuario_id vazio - ROADMAP 13.11): tem
    # Click, só não tem usuário ainda. valor_comissao continua sendo somado normalmente - é
    # o que a Shopee realmente paga pra conta de afiliado, independente da origem do
    # pedido ou de ter usuário. Exceção: pedido sem clique que o admin já vinculou a
    # alguém (usuario_manual, ver ReclamacaoPedido) - esse paga cashback como venda
    # indireta, senão a sincronização seguinte zeraria o que foi aprovado.
    pedido_valor = Decimal("0")
    comissao = Decimal("0")
    cashback = Decimal("0")
    itens_detalhe = []
    for item in itens:
        valor_item = Decimal(str(item.get("actualAmount") or "0"))
        pedido_valor += valor_item
        comissao_item = Decimal(str(item.get("itemTotalCommission") or "0"))
        comissao += comissao_item
        venda_direta_item = False
        cashback_item = Decimal("0.00")
        # click.usuario_id vazio = clique ainda anônimo (ROADMAP 13.11): a comissão
        # continua sendo somada normalmente (comissao, abaixo), mas sem cashback pra
        # ninguém ainda - se a pessoa se cadastrar dentro da janela de 7 dias, o
        # clique ganha usuario (ver accounts/cliques_anonimos.py) e a sincronização
        # seguinte recalcula esse mesmo item com o cashback correto, nesse mesmo "if".
        if click and click.usuario_id and comissao_item > 0:
            item_bate_com_o_link = _item_bate_com_o_click(click, item.get("itemId"))
            venda_direta_item = click.tipo != Click.TIPO_HOME and item_bate_com_o_link
            percentual_minimo = _percentual_minimo_garantido(click, item_bate_com_o_link)
            cashback_base_item = max(comissao_item * percentual_base, valor_item * percentual_minimo)
            cashback_item = (cashback_base_item * multiplicador).quantize(Decimal("0.01"))
            cashback += cashback_item
        elif click is None and usuario_manual is not None:
            cashback_item = cashback_item_vinculado_manualmente(
                valor_item, comissao_item, percentual_base, multiplicador
            )
            cashback += cashback_item

        # Detalhe por item - ver ItemPedido (pedidos/models.py) e _persistir_itens.
        # Gravado mesmo quando não bate com o clique ou não tem clique nenhum, pra
        # manter o mesmo retrato completo do pedido que produto_nome/imagem_produto
        # já dão hoje.
        try:
            item_id_int = int(item["itemId"]) if item.get("itemId") else None
        except (TypeError, ValueError):
            item_id_int = None
        itens_detalhe.append({
            "item_id": item_id_int,
            "nome": (item.get("itemName") or "")[:255],
            "imagem_url": item.get("imageUrl") or "",
            "valor_item": valor_item,
            "comissao_item": comissao_item,
            "venda_direta": venda_direta_item,
            "cashback_pago": cashback_item,
        })

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

    defaults = {
        "conversion_id": str(conversao.get("conversionId", "")),
        "click": click,
        "usuario": click.usuario if click else usuario_manual,
        "status": status_shopee,
        "status_shopee_bruto": pedido_shopee.get("orderStatus") or "",
        "valor_pedido": pedido_valor,
        "valor_comissao": comissao,
        "valor_cashback": cashback,
        "produto_nome": ", ".join(nomes_produto)[:255],
        "produto_imagem_url": imagem_produto,
        "motivo_cancelamento": motivo_cancelamento,
        "data_compra": data_compra,
        "data_validacao": data_validacao,
        "data_prevista_liberacao": calcular_data_prevista_liberacao(data_validacao),
    }
    return defaults, itens_detalhe


def _montar_linhas(
    brutos_por_order_id: dict[str, tuple], percentual_base: Decimal
) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Monta os defaults de cada pedido já com o multiplicador de campanha correto.

    Pedido novo usa o multiplicador que valia na data_compra real (ver
    CampanhaCashback.multiplicador_em) - não o multiplicador "de agora"; pedido que já
    existe reusa o que ficou gravado nele na primeira vez. Isso é o que impede a
    campanha de vazar pros dois lados - a Shopee reenvia o mesmo pedido em toda
    sincronização seguinte, e o _montar_defaults recalcula valor_cashback do zero a
    cada vez, então sem congelar o multiplicador:

    - o dobro prometido numa campanha sumiria na primeira sincronização depois dela
      acabar, justamente pra quem comprou por causa da campanha;
    - ligar uma campanha dobraria retroativamente pedidos antigos que ainda estejam
      dentro da janela de sincronização.

    Usar a data_compra (em vez do momento da sincronização, que roda uma vez por dia
    de madrugada - ver ROADMAP.md, Fase 44) evita um problema à parte: antes, uma
    compra feita de noite só era sincronizada horas depois, e se a campanha já tivesse
    sido desligada até lá, esse pedido perdia o dobro injustamente - obrigando a
    manter a campanha ligada até depois da sincronização seguinte "por segurança".
    Comparando a data_compra contra a janela da campanha, o resultado é sempre o
    mesmo não importa quando a sincronização roda.

    É o mesmo cuidado que _reaplicar_bonus_ja_concedido tem com o bônus de indicação.

    Retorna (linhas, itens_por_order_id): o 2º dicionário traz o detalhe por item de
    cada pedido (ver ItemPedido), na mesma chave order_id - usado por
    _persistir_itens depois que os Pedidos existem de verdade no banco.
    """
    ja_gravados = dict(
        Pedido.objects.filter(order_id__in=brutos_por_order_id.keys()).values_list(
            "order_id", "multiplicador_campanha"
        )
    )
    # Carregada uma vez fora do loop - sem isso, cada pedido novo faria sua própria
    # consulta ao banco (ver CampanhaCashback.multiplicador_em), o que não escala
    # numa sincronização com muitos pedidos.
    campanhas = CampanhaCashback.listar()
    # Pedidos sem clique que o admin já vinculou a alguém (ReclamacaoPedido) - o vínculo
    # não vem da Shopee, então precisa ser lido daqui pra sobreviver a cada sincronização.
    vinculados_manualmente = {
        p.order_id: p.usuario
        for p in Pedido.objects.filter(
            order_id__in=brutos_por_order_id.keys(),
            vinculado_manualmente_em__isnull=False,
            usuario__isnull=False,
        ).select_related("usuario")
    }

    linhas: dict[str, dict] = {}
    itens_por_order_id: dict[str, list[dict]] = {}
    for order_id, (conversao, pedido_shopee, click, data_compra) in brutos_por_order_id.items():
        if order_id in ja_gravados:
            multiplicador = ja_gravados[order_id]
        else:
            multiplicador = CampanhaCashback.multiplicador_em(data_compra, campanhas=campanhas)
        defaults, itens_detalhe = _montar_defaults(
            conversao, pedido_shopee, click, data_compra, percentual_base, multiplicador,
            usuario_manual=vinculados_manualmente.get(order_id),
        )
        defaults["multiplicador_campanha"] = multiplicador
        linhas[order_id] = defaults
        itens_por_order_id[order_id] = itens_detalhe
    return linhas, itens_por_order_id


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

    linhas_por_order_id, itens_por_order_id = _montar_linhas(brutos_por_order_id, percentual_base)

    _reaplicar_bonus_ja_concedido(linhas_por_order_id, itens_por_order_id)

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
    vinculos_indicacao = _selecionar_bonus_indicacao(recem_validados, itens_por_order_id)

    # batch_size evita um único UPDATE/INSERT gigante quando a janela de 60 dias
    # acumula muitos pedidos - sem isso, o Postgres pode demorar a ponto de
    # estourar o timeout do servidor (visto em produção com bulk_update sem lote).
    if novos_objs:
        Pedido.objects.bulk_create(novos_objs, batch_size=200)
    if atualizados_objs:
        Pedido.objects.bulk_update(atualizados_objs, CAMPOS_ATUALIZAVEIS, batch_size=200)

    pedidos_por_order_id = {p.order_id: p for p in novos_objs + atualizados_objs}
    _persistir_itens(pedidos_por_order_id, itens_por_order_id)

    _persistir_vinculos_indicacao(vinculos_indicacao)

    for indicacao, campo, _order_id in vinculos_indicacao:
        if campo == "pedido_bonus_indicado":
            notificar_indicador_bonus_pendente(indicacao)

    for pedido in recem_validados:
        if pedido.usuario_id:
            notificar_pedido_validado(pedido)

    return {"novos": novos, "atualizados": atualizados, "nao_identificados": nao_identificados}


def _dobrar_cashback_dos_itens(order_id: str, multiplicador: Decimal, itens_por_order_id: dict[str, list[dict]]) -> None:
    """Aplica o mesmo multiplicador de bônus de indicação no cashback_pago de cada
    item do pedido (ver ItemPedido) - sem isso, a soma dos itens de um pedido com
    bônus de indicação ficaria menor que o valor_cashback agregado do Pedido
    (que já leva o dobro), o que faria o lembrete de venda indireta por produto (ver
    accounts/comunicacoes.py) subestimar o cashback já pago nesses pedidos."""
    for item in itens_por_order_id.get(order_id, []):
        item["cashback_pago"] = (item["cashback_pago"] * multiplicador).quantize(Decimal("0.01"))


def _reaplicar_bonus_ja_concedido(linhas_por_order_id: dict[str, dict], itens_por_order_id: dict[str, list[dict]]) -> None:
    """A Shopee reenvia o mesmo pedido validado em toda sincronização seguinte, e
    _montar_defaults recalcula valor_cashback do zero a cada vez - sem isso, o dobro
    de cashback já concedido por indicação seria substituído pelo valor normal na
    primeira sincronização depois de concedido. Muta linhas_por_order_id (e os itens
    em itens_por_order_id) em memória, antes de qualquer Pedido ser criado/atualizado."""
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
                defaults["valor_cashback"] = (defaults["valor_cashback"] * multiplicador).quantize(Decimal("0.01"))
                _dobrar_cashback_dos_itens(pedido_bonus.order_id, multiplicador, itens_por_order_id)


def _selecionar_bonus_indicacao(
    recem_validados: list[Pedido], itens_por_order_id: dict[str, list[dict]]
) -> list[tuple[Indicacao, str, str]]:
    """Decide quais pedidos recém-validados NESTA sincronização ganham o dobro de
    cashback do programa "indique e ganhe", e já dobra o valor_cashback deles (e o
    cashback_pago de cada item deles - ver _dobrar_cashback_dos_itens).

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

    # O bônus só é ativado quando as chaves Pix dos DOIS lados estão verificadas
    # (titular = CPF da conta, accounts/verificacao_pix.py) - fecha a fraude de indicar
    # a si mesmo com uma conta de CPF gerado. Enquanto isso a Indicacao segue
    # pendente e o dobro vale na 1ª compra validada depois da verificação.
    verificado = User.PIX_VERIFICADA
    indicacoes = list(
        Indicacao.objects.filter(
            Q(indicado_id__in=usuario_ids, pedido_bonus_indicado__isnull=True)
            | Q(indicador_id__in=usuario_ids, pedido_bonus_indicado__isnull=False, pedido_bonus_indicador__isnull=True)
        )
        .filter(indicado__chave_pix_status=verificado, indicador__chave_pix_status=verificado)
        .exclude(indicado__chave_pix="")
        .exclude(indicador__chave_pix="")
        .order_by("criado_em")
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
        # Pedido que já leva o extra de uma campanha não consome o bônus de indicação:
        # a Indicacao continua pendente (é ela mesma a fila) e o próximo pedido fora de
        # campanha pega o bônus. Sem isso os dois dobros se somariam no mesmo pedido.
        #
        # A checagem é no multiplicador gravado no pedido, não no setting atual: um
        # pedido comprado durante a campanha pode só validar semanas depois, já com a
        # campanha desligada - e ele continua sendo um pedido que ganhou o extra dela.
        if pedido.multiplicador_campanha > 1:
            continue

        if pedido.usuario_id in indicado_pendente:
            indicacao = indicado_pendente.pop(pedido.usuario_id)
            pedido.valor_cashback = (pedido.valor_cashback * multiplicador).quantize(Decimal("0.01"))
            _dobrar_cashback_dos_itens(pedido.order_id, multiplicador, itens_por_order_id)
            vinculos.append((indicacao, "pedido_bonus_indicado", pedido.order_id))
        elif indicador_fila.get(pedido.usuario_id):
            indicacao = indicador_fila[pedido.usuario_id].pop(0)
            pedido.valor_cashback = (pedido.valor_cashback * multiplicador).quantize(Decimal("0.01"))
            _dobrar_cashback_dos_itens(pedido.order_id, multiplicador, itens_por_order_id)
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


def _persistir_itens(pedidos_por_order_id: dict[str, Pedido], itens_por_order_id: dict[str, list[dict]]) -> None:
    """Grava o detalhe por item de cada pedido sincronizado (ver ItemPedido). Sempre
    apaga e recria os itens do pedido em vez de tentar casar item a item entre
    sincronizações - a Shopee não garante uma chave estável por linha (ex: duas
    compras do mesmo item no mesmo pedido), e o volume por pedido é pequeno o
    bastante pra isso não pesar. Roda depois do bulk_create/bulk_update de Pedido
    (precisa do pk de cada um já existir de verdade no banco).

    Processado em lote (1 delete + 1 bulk_create, não por pedido) pelo mesmo motivo
    do resto da sincronização - ver sincronizar()."""
    pedido_ids = [pedido.pk for pedido in pedidos_por_order_id.values()]
    if not pedido_ids:
        return

    ItemPedido.objects.filter(pedido_id__in=pedido_ids).delete()

    novos_itens = [
        ItemPedido(pedido=pedidos_por_order_id[order_id], **item_detalhe)
        for order_id, itens_detalhe in itens_por_order_id.items()
        if order_id in pedidos_por_order_id
        for item_detalhe in itens_detalhe
    ]
    if novos_itens:
        ItemPedido.objects.bulk_create(novos_itens, batch_size=200)


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
