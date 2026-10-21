import hashlib
import hmac
import logging
import time
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import MODULO_WHATSAPP, Assinatura, ContaAppfiliado

logger = logging.getLogger(__name__)


# --- Assinatura do webhook -------------------------------------------------------------

# A Zouti reenvia um aviso por até 4 dias: carimbo mais velho que isso é repetição.
CARIMBO_MAXIMO = timedelta(days=5)


def _carimbo_aceitavel(t: str) -> bool:
    """O "t=" do cabeçalho (ms ou s desde 1970). Sem ele, aceita (a assinatura já confere);
    com ele, recusa aviso velho demais ou "do futuro"."""
    if not t:
        return True
    if not t.isdigit():
        return False
    valor = int(t)
    segundos = valor / 1000 if valor > 10**11 else valor
    diferenca = time.time() - segundos
    return -600 <= diferenca <= CARIMBO_MAXIMO.total_seconds()


def assinatura_webhook_valida(corpo: bytes, cabecalho: str, segredo: str) -> bool:
    """Confere o cabeçalho x-zouti-signature ("t=<ms>,v1=<hex>").

    A documentação da Zouti diz que v1 é o HMAC-SHA256 do corpo bruto com o segredo do
    webhook. Também aceitamos o formato "<t>.<corpo>" (o padrão de quem manda o
    timestamp junto) para não quebrar se a Zouti assinar assim - os dois exigem o
    segredo, então nenhum enfraquece a verificação. Confirme com o "Testar Webhook" do
    painel da Zouti: o EventoWebhookZouti guarda se a assinatura bateu."""
    if not segredo or not cabecalho:
        return False
    partes = {}
    for pedaco in cabecalho.split(","):
        chave, _, valor = pedaco.strip().partition("=")
        if chave and valor:
            partes[chave] = valor
    recebida = partes.get("v1", "")
    if not recebida:
        return False
    if not _carimbo_aceitavel(partes.get("t", "")):
        return False
    chave = segredo.encode()
    candidatas = [hmac.new(chave, corpo, hashlib.sha256).hexdigest()]
    if partes.get("t"):
        candidatas.append(hmac.new(chave, partes["t"].encode() + b"." + corpo, hashlib.sha256).hexdigest())
    return any(hmac.compare_digest(recebida, esperada) for esperada in candidatas)


# --- Interpretação dos eventos ---------------------------------------------------------

def _datahora(valor) -> datetime | None:
    if not valor:
        return None
    try:
        # A Zouti manda algo como "2026-05-01T00:00:00.000Z"
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def _data(valor) -> date | None:
    dh = _datahora(valor)
    if not dh:
        return None
    return timezone.localtime(dh).date() if timezone.is_aware(dh) else dh.date()


STATUS_ZOUTI = {
    "ACTIVE": (Assinatura.STATUS_ATIVA, ""),
    "TRIAL": (Assinatura.STATUS_TESTE, ""),
    "PAST_DUE": (Assinatura.STATUS_ATRASADA, "Pagamento da assinatura está atrasado."),
    "CANCELED": (Assinatura.STATUS_CANCELADA, "Assinatura cancelada."),
    "INCOMPLETE": (Assinatura.STATUS_INCOMPLETA, "Pagamento ainda não confirmado."),
}

EVENTOS_ESTORNO = {"ORDER_REFUNDED", "PAYMENT_REFUNDED"}
EVENTOS_CHARGEBACK = {"ORDER_DISPUTED", "PAYMENT_DISPUTED"}


def processar_evento(tipo_evento: str, tipo_objeto: str, payload: dict) -> str:
    """Aplica um evento já verificado (assinatura do webhook conferida). Devolve um
    resumo do que foi feito, que fica guardado no EventoWebhookZouti."""
    tipo_evento = (tipo_evento or "").upper()
    tipo_objeto = tipo_objeto or ""

    if tipo_objeto == "Subscription" or tipo_evento.startswith("SUBSCRIPTION_"):
        return _aplicar_evento_assinatura(tipo_evento, payload)
    if tipo_evento in EVENTOS_ESTORNO or tipo_evento in EVENTOS_CHARGEBACK:
        return _aplicar_estorno_ou_chargeback(tipo_evento, payload)
    return f"Ignorado: evento {tipo_evento or '?'} não muda licenças."


@transaction.atomic
def _aplicar_evento_assinatura(tipo_evento: str, payload: dict) -> str:
    sub_id = str(payload.get("id") or "")[:64]
    customer = payload.get("customer") or {}
    email = str(customer.get("email") or "").strip().lower()[:254]
    nome = str(customer.get("name") or "")[:140]
    if not sub_id or not email:
        raise ValueError("Evento de assinatura sem id ou sem e-mail do cliente.")

    conta, _ = ContaAppfiliado.objects.get_or_create(email=email, defaults={"nome": nome})
    if not conta.nome and nome:
        conta.nome = nome
        conta.save(update_fields=["nome", "atualizada_em"])

    assinatura, _ = Assinatura.objects.select_for_update().get_or_create(
        zouti_subscription_id=sub_id, defaults={"conta": conta},
    )

    atualizado_em = _datahora(payload.get("updated_at"))
    if assinatura.zouti_atualizada_em and atualizado_em and atualizado_em < assinatura.zouti_atualizada_em:
        return f"Ignorado: {tipo_evento} mais antigo que o último já aplicado em {sub_id}."

    status_zouti = (payload.get("status") or "").upper()
    novo_status, motivo = STATUS_ZOUTI.get(
        status_zouti, (Assinatura.STATUS_INCOMPLETA, "Status da assinatura não reconhecido - fale com o suporte."),
    )
    if status_zouti not in STATUS_ZOUTI:
        logger.warning("Licencas: status de assinatura desconhecido da Zouti: %r", status_zouti)
    if tipo_evento == "SUBSCRIPTION_LATE_RENEWAL_WARNING":
        novo_status, motivo = STATUS_ZOUTI["PAST_DUE"]
    elif tipo_evento == "SUBSCRIPTION_CANCELED":
        novo_status, motivo = STATUS_ZOUTI["CANCELED"]

    # Estorno e chargeback só são desfeitos por uma renovação paga de verdade - nunca
    # por um evento de status qualquer que chegue depois.
    # E a renovação tem de ser mais nova que o estorno: um aviso antigo reenviado (ou
    # capturado e repetido por alguém) não devolve o acesso.
    bloqueio_forte = assinatura.status in (Assinatura.STATUS_REEMBOLSADA, Assinatura.STATUS_CHARGEBACK)
    renovacao_nova = (tipo_evento == "SUBSCRIPTION_RENEWED" and atualizado_em is not None
                      and (assinatura.zouti_atualizada_em is None or atualizado_em > assinatura.zouti_atualizada_em))
    if bloqueio_forte and not renovacao_nova:
        novo_status, motivo = assinatura.status, assinatura.motivo

    plano = payload.get("plan") or {}
    product_ids = [i.get("product_id") for i in payload.get("line_items") or [] if i.get("product_id")]

    assinatura.conta = conta
    assinatura.status = novo_status
    assinatura.motivo = motivo
    assinatura.plano = str(plano.get("name") or assinatura.plano)[:80]
    if product_ids:
        assinatura.zouti_product_ids = ",".join(dict.fromkeys(str(p) for p in product_ids))[:300]
    assinatura.zouti_order_id = str(payload.get("order_id") or assinatura.zouti_order_id)[:64]
    assinatura.proxima_cobranca = _data(payload.get("next_payment_date")) or _data(payload.get("current_period_end"))
    assinatura.acesso_ate = (
        _data(payload.get("current_period_end")) if novo_status == Assinatura.STATUS_CANCELADA else None
    )
    if atualizado_em:
        assinatura.zouti_atualizada_em = atualizado_em
    assinatura.save()

    if novo_status in Assinatura.STATUS_QUE_LIBERAM and conta.chave_enviada_em is None:
        transaction.on_commit(lambda: enviar_email_chave(conta.pk))

    return f"{tipo_evento}: assinatura {sub_id} de {email} agora está '{novo_status}'."


@transaction.atomic
def _aplicar_estorno_ou_chargeback(tipo_evento: str, payload: dict) -> str:
    status_objeto = (payload.get("status") or "").upper()
    estorno = tipo_evento in EVENTOS_ESTORNO
    if estorno and status_objeto != "REFUNDED":
        # Estorno parcial (PARTIALLY_REFUNDED) não tira o acesso.
        return f"Ignorado: {tipo_evento} com status {status_objeto or '?'} (estorno parcial)."

    # Payment traz subscription_id e order_id; Order só o próprio id (= order_id).
    if tipo_evento.startswith("PAYMENT_"):
        sub_id = payload.get("subscription_id") or ""
        order_id = payload.get("order_id") or ""
    else:
        sub_id = ""
        order_id = payload.get("id") or ""

    assinaturas = []
    if sub_id:
        assinaturas = list(Assinatura.objects.select_for_update().filter(zouti_subscription_id=sub_id))
    if not assinaturas and order_id:
        assinaturas = list(Assinatura.objects.select_for_update().filter(zouti_order_id=order_id))
    if not assinaturas:
        return f"{tipo_evento}: nenhuma assinatura vinculada (pedido {order_id or '?'})."

    novo_status = Assinatura.STATUS_REEMBOLSADA if estorno else Assinatura.STATUS_CHARGEBACK
    motivo = "Compra reembolsada." if estorno else "Chargeback registrado nesta compra."
    ids = []
    agora = timezone.now()
    for assinatura in assinaturas:
        assinatura.status = novo_status
        assinatura.motivo = motivo
        assinatura.acesso_ate = None
        # Marca a hora do estorno: só uma renovação depois dela libera de novo.
        assinatura.zouti_atualizada_em = max(assinatura.zouti_atualizada_em or agora, agora)
        assinatura.save()
        ids.append(assinatura.zouti_subscription_id)
    return f"{tipo_evento}: {', '.join(ids)} agora '{novo_status}'."


# --- Validação pelo app ----------------------------------------------------------------

def resposta_validacao(conta: ContaAppfiliado) -> dict:
    """Corpo da resposta do /licencas/validar/.

    "valido", "motivo", "plano" e "expira_em" são o contrato que o app já usa hoje
    (Appfiliado/licenca.py) e continuam querendo dizer "pode abrir o bot de WhatsApp".
    "conta_ativa" e "modulos" são novos: a versão do app com módulos usa esses dois
    para decidir o que liberar e o que mostrar com cadeado."""
    hoje = timezone.localdate()
    modulos = conta.modulos_liberados(hoje)
    assinaturas = list(conta.assinaturas.all())
    com_acesso = [a for a in assinaturas if a.da_acesso(hoje)]

    planos = [a.plano for a in com_acesso if a.plano]
    if not planos and conta.cortesia_vigente(hoje):
        planos = ["Cortesia"]

    datas = [a.proxima_cobranca or a.acesso_ate for a in com_acesso]
    if conta.cortesia_vigente(hoje):
        datas.append(conta.cortesia_ate)
    datas = [d for d in datas if d]
    expira_em = min(datas).isoformat() if datas else ""

    valido = MODULO_WHATSAPP in modulos
    if valido:
        motivo = ""
    elif modulos:
        motivo = "Seu plano não inclui o bot de WhatsApp."
    elif assinaturas:
        mais_recente = max(assinaturas, key=lambda a: a.atualizada_em)
        motivo = mais_recente.motivo or "Assinatura não está ativa."
    else:
        motivo = "Nenhuma assinatura ativa nesta conta."

    return {
        "valido": valido,
        "motivo": motivo,
        "plano": " + ".join(dict.fromkeys(planos)),
        "expira_em": expira_em,
        "conta_ativa": bool(modulos),
        "modulos": modulos,
    }


# --- E-mail com a chave ----------------------------------------------------------------

def _trecho_painel(conta: ContaAppfiliado) -> str:
    """Convite pro painel web no e-mail da chave: link de criar senha para quem
    ainda não tem, ou só o endereço para quem já tem."""
    from painel.emails import link_definir_senha, url_do_painel

    if conta.tem_senha:
        return f"Seu painel: {url_do_painel('painel_inicio')}\n\n"
    return (
        "Crie sua senha para acessar o painel do Appfiliado (o link vale por 3 dias - "
        "depois disso, use \"Criar ou recuperar senha\" na tela de entrar):\n"
        f"{link_definir_senha(conta)}\n\n"
    )


def enviar_email_chave(conta_pk: int) -> bool:
    conta = ContaAppfiliado.objects.filter(pk=conta_pk).first()
    if not conta or not conta.email:
        logger.warning("Licencas: conta %s sem e-mail, não foi possível enviar a chave.", conta_pk)
        return False

    corpo = (
        f"Olá{', ' + conta.nome if conta.nome else ''}!\n\n"
        "Sua assinatura do Appfiliado foi confirmada. Essa é a sua chave de licença - "
        "cole ela na tela de ativação do aplicativo:\n\n"
        f"{conta.chave}\n\n"
        "Ela vale para todos os serviços que você assinar com este e-mail: se contratar "
        "outro depois, é só continuar usando a mesma chave.\n\n"
        "Guarde esse e-mail: se precisar reinstalar o app ou trocar de computador, "
        "é só usar a chave de novo.\n\n"
        f"{_trecho_painel(conta)}"
        "Equipe Appfiliado\nFerramentas para afiliados Shopee"
    )
    try:
        EmailMessage(
            subject="Appfiliado — sua chave de licença",
            body=corpo,
            to=[conta.email],
            from_email=settings.APPFILIADO_EMAIL_REMETENTE,
        ).send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de licença para %s", conta.email)
        return False

    conta.chave_enviada_em = timezone.now()
    conta.save(update_fields=["chave_enviada_em", "atualizada_em"])
    return True
