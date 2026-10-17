"""Reclamação de compra não registrada (Fase 64).

Fluxo: a pessoa informa o nº do pedido da Shopee no painel (abrir_reclamacao). Se o
pedido já chegou na sincronização sem clique ("fora do site"), a reclamação fica em
análise e o admin vincula com 1 clique (vincular). Se ainda não chegou, a tarefa diária
volta a procurar por DIAS_PROCURANDO dias (atualizar_reclamacoes) antes de encerrar.
"""
import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Pedido, ReclamacaoPedido
from .notificacoes import notificar_reclamacao_encerrada, notificar_reclamacao_vinculada
from .services import cashback_item_vinculado_manualmente

# O pedido aparece em até 2 dias (sincronização diária das 10h) - antes disso não é
# reclamação, é só espera.
DIAS_MINIMOS_DESDE_A_COMPRA = 2
# A reconciliação semanal só reprocessa 60 dias; acima disso fica difícil conferir.
DIAS_MAXIMOS_DESDE_A_COMPRA = 60
# Quantos dias a tarefa diária continua procurando um pedido que ainda não chegou.
DIAS_PROCURANDO = 10
MAXIMO_ABERTAS_POR_USUARIO = 3

PADRAO_ORDER_ID = re.compile(r"^[0-9A-Z]{8,32}$")

RESPOSTA_NAO_ENCONTRADA = (
    "A Shopee não registrou essa compra na conta da cash-b. Isso costuma acontecer "
    "quando outro link de afiliado é aberto depois do nosso, ou quando a compra é "
    "finalizada sem passar pelo link."
)
RESPOSTA_OUTRA_CONTA = "Esse pedido foi registrado em outra conta da cash-b."
RESPOSTA_RECUSADA_PADRAO = "Não conseguimos confirmar que essa compra é sua."


class ReclamacaoInvalida(Exception):
    """Mensagem pronta para mostrar à pessoa no formulário."""


def normalizar_order_id(valor: str) -> str:
    return re.sub(r"[\s#-]", "", valor or "").upper()


def abrir_reclamacao(usuario, order_id: str, data_compra, produto: str) -> ReclamacaoPedido:
    order_id = normalizar_order_id(order_id)
    if not PADRAO_ORDER_ID.match(order_id):
        raise ReclamacaoInvalida(
            "Confira o número do pedido: na Shopee, ele fica em Minhas compras > abrir o pedido > "
            "Nº do pedido (só letras e números)."
        )

    hoje = timezone.localdate()
    if data_compra > hoje:
        raise ReclamacaoInvalida("A data da compra não pode ser no futuro.")
    if (hoje - data_compra).days < DIAS_MINIMOS_DESDE_A_COMPRA:
        liberada_em = data_compra + timedelta(days=DIAS_MINIMOS_DESDE_A_COMPRA)
        raise ReclamacaoInvalida(
            f"A compra aparece na sua conta em até 2 dias. Se ela não aparecer, "
            f"volte aqui a partir de {liberada_em:%d/%m}."
        )
    if (hoje - data_compra).days > DIAS_MAXIMOS_DESDE_A_COMPRA:
        raise ReclamacaoInvalida(
            f"Só conseguimos conferir compras dos últimos {DIAS_MAXIMOS_DESDE_A_COMPRA} dias."
        )

    reclamacoes = ReclamacaoPedido.objects.filter(usuario=usuario)
    if reclamacoes.filter(order_id=order_id).exclude(
        status__in=[ReclamacaoPedido.STATUS_RECUSADA, ReclamacaoPedido.STATUS_NAO_ENCONTRADA]
    ).exists():
        raise ReclamacaoInvalida("Você já avisou sobre esse pedido. Acompanhe o andamento abaixo.")
    if reclamacoes.filter(status__in=ReclamacaoPedido.STATUS_ABERTOS).count() >= MAXIMO_ABERTAS_POR_USUARIO:
        raise ReclamacaoInvalida(
            f"Você já tem {MAXIMO_ABERTAS_POR_USUARIO} avisos em andamento. Espere a resposta "
            "deles antes de mandar outro."
        )

    pedido = Pedido.objects.filter(order_id=order_id).first()
    if pedido and pedido.usuario_id == usuario.pk:
        raise ReclamacaoInvalida("Esse pedido já está na sua conta, na lista de Meus pedidos.")
    if pedido and pedido.usuario_id:
        raise ReclamacaoInvalida(f"{RESPOSTA_OUTRA_CONTA} O cashback fica com quem gerou o link.")

    return ReclamacaoPedido.objects.create(
        usuario=usuario,
        order_id=order_id,
        data_compra_informada=data_compra,
        produto_informado=produto.strip()[:200],
        pedido=pedido,
        status=ReclamacaoPedido.STATUS_EM_ANALISE if pedido else ReclamacaoPedido.STATUS_AGUARDANDO,
    )


def _encerrar(reclamacao: ReclamacaoPedido, status: str, resposta: str = "", notificar=True) -> None:
    reclamacao.status = status
    reclamacao.resposta = resposta
    reclamacao.resolvido_em = timezone.now()
    reclamacao.save(update_fields=["status", "resposta", "resolvido_em", "pedido"])
    if notificar:
        if status == ReclamacaoPedido.STATUS_VINCULADA:
            notificar_reclamacao_vinculada(reclamacao)
        else:
            notificar_reclamacao_encerrada(reclamacao)


def _calcular_cashback_vinculado(pedido: Pedido):
    """(itens com cashback recalculado, total) - venda indireta, sem salvar nada."""
    percentual_base = Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL)) / Decimal("100")
    itens = list(pedido.itens.all())
    if not itens:
        total = cashback_item_vinculado_manualmente(
            pedido.valor_pedido, pedido.valor_comissao, percentual_base, pedido.multiplicador_campanha
        )
        return [], total
    total = Decimal("0")
    for item in itens:
        item.cashback_pago = cashback_item_vinculado_manualmente(
            item.valor_item, item.comissao_item, percentual_base, pedido.multiplicador_campanha
        )
        item.venda_direta = False
        total += item.cashback_pago
    return itens, total


def cashback_previsto(pedido: Pedido) -> Decimal:
    """Quanto a pessoa recebe se o admin vincular o pedido (mostrado no admin)."""
    return _calcular_cashback_vinculado(pedido)[1]


def vincular(reclamacao: ReclamacaoPedido) -> None:
    """Liga o pedido "fora do site" à conta de quem reclamou e calcula o cashback como
    venda indireta. Levanta ReclamacaoInvalida se o pedido não puder mais ser vinculado."""
    if reclamacao.status != ReclamacaoPedido.STATUS_EM_ANALISE or not reclamacao.pedido_id:
        raise ReclamacaoInvalida("Só dá pra vincular reclamação em análise, com pedido encontrado.")

    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=reclamacao.pedido_id)
        if pedido.usuario_id or pedido.click_id:
            raise ReclamacaoInvalida("Esse pedido já tem dono.")

        itens, total = _calcular_cashback_vinculado(pedido)
        if itens:
            type(itens[0]).objects.bulk_update(itens, ["cashback_pago", "venda_direta"])

        pedido.usuario = reclamacao.usuario
        pedido.vinculado_manualmente_em = timezone.now()
        pedido.valor_cashback = total
        pedido.save(update_fields=["usuario", "vinculado_manualmente_em", "valor_cashback", "atualizado_em"])

        _encerrar(reclamacao, ReclamacaoPedido.STATUS_VINCULADA, notificar=False)
        # Outras pessoas que reclamaram o mesmo pedido.
        outras = list(
            ReclamacaoPedido.objects.filter(pedido=pedido, status__in=ReclamacaoPedido.STATUS_ABERTOS)
            .exclude(pk=reclamacao.pk)
            .select_related("usuario")
        )
        for outra in outras:
            _encerrar(outra, ReclamacaoPedido.STATUS_RECUSADA, RESPOSTA_OUTRA_CONTA, notificar=False)

    notificar_reclamacao_vinculada(reclamacao)
    for outra in outras:
        notificar_reclamacao_encerrada(outra)


def recusar(reclamacao: ReclamacaoPedido, resposta: str = "") -> None:
    if not reclamacao.aberta:
        raise ReclamacaoInvalida("Essa reclamação já foi encerrada.")
    _encerrar(reclamacao, ReclamacaoPedido.STATUS_RECUSADA, resposta or RESPOSTA_RECUSADA_PADRAO)


def atualizar_reclamacoes() -> dict:
    """Tarefa diária, depois da sincronização: procura de novo os pedidos que ainda não
    tinham chegado e encerra os que passaram de DIAS_PROCURANDO dias."""
    resultado = {"encontradas": 0, "ja_na_conta": 0, "outra_conta": 0, "nao_encontradas": 0}
    limite = timezone.now() - timedelta(days=DIAS_PROCURANDO)
    aguardando = ReclamacaoPedido.objects.filter(status=ReclamacaoPedido.STATUS_AGUARDANDO).select_related("usuario")
    pedidos = {p.order_id: p for p in Pedido.objects.filter(order_id__in=[r.order_id for r in aguardando])}

    for reclamacao in aguardando:
        pedido = pedidos.get(reclamacao.order_id)
        if pedido is None:
            if reclamacao.criado_em < limite:
                _encerrar(reclamacao, ReclamacaoPedido.STATUS_NAO_ENCONTRADA, RESPOSTA_NAO_ENCONTRADA)
                resultado["nao_encontradas"] += 1
            continue
        reclamacao.pedido = pedido
        if pedido.usuario_id == reclamacao.usuario_id:
            # Chegou pela sincronização normal, com o clique da própria pessoa.
            _encerrar(reclamacao, ReclamacaoPedido.STATUS_VINCULADA, notificar=False)
            resultado["ja_na_conta"] += 1
        elif pedido.usuario_id:
            _encerrar(reclamacao, ReclamacaoPedido.STATUS_RECUSADA, RESPOSTA_OUTRA_CONTA)
            resultado["outra_conta"] += 1
        else:
            reclamacao.status = ReclamacaoPedido.STATUS_EM_ANALISE
            reclamacao.save(update_fields=["status", "pedido"])
            resultado["encontradas"] += 1
    return resultado
