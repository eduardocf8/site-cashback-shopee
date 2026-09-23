"""Comunicação em massa por e-mail (ver UserAdmin em accounts/admin.py).

Manda tudo via BCC em lotes, numa única requisição síncrona do admin - o site
roda com 1 worker gunicorn só (ver README.md), então mandar 1 e-mail por
destinatário em série (dezenas/centenas de chamadas HTTP pra API do Brevo)
travaria o site inteiro por bom tempo. BCC deixa a API do Brevo mandar vários
destinatários numa chamada só; o tamanho do lote fica bem abaixo do limite
documentado da API (99 destinatários por chamada) por margem de segurança.
"""

import logging
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import QuerySet

from .models import ComunicacaoEmail, User

FILTROS = dict(ComunicacaoEmail.FILTRO_CHOICES)

TAMANHO_LOTE = 50

logger = logging.getLogger(__name__)


def obter_destinatarios(filtro: str) -> QuerySet:
    """Usuários com e-mail preenchido que batem no filtro escolhido. Sempre parte
    de quem tem e-mail (senão a API do Brevo recusa o endereço vazio)."""
    base = User.objects.exclude(email="")

    if filtro == ComunicacaoEmail.FILTRO_COM_PEDIDOS:
        return base.filter(pedidos__isnull=False).distinct()
    if filtro == ComunicacaoEmail.FILTRO_SEM_PEDIDOS:
        return base.filter(pedidos__isnull=True)
    if filtro == ComunicacaoEmail.FILTRO_EMAIL_VERIFICADO:
        return base.filter(email_verificado=True)
    if filtro == ComunicacaoEmail.FILTRO_EMAIL_NAO_VERIFICADO:
        return base.filter(email_verificado=False)
    if filtro == ComunicacaoEmail.FILTRO_JA_SACOU:
        return base.filter(saques__isnull=False).distinct()
    if filtro == ComunicacaoEmail.FILTRO_NUNCA_SACOU:
        return base.filter(saques__isnull=True)
    return base


def _lotes(itens: list, tamanho: int):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def enviar_comunicacao(*, assunto: str, corpo: str, filtro: str, enviado_por) -> ComunicacaoEmail:
    if filtro not in FILTROS:
        filtro = ComunicacaoEmail.FILTRO_TODOS

    emails = list(obter_destinatarios(filtro).values_list("email", flat=True))
    _, endereco_remetente = parseaddr(settings.DEFAULT_FROM_EMAIL)

    total_enviados = 0
    for lote in _lotes(emails, TAMANHO_LOTE):
        try:
            EmailMessage(subject=assunto, body=corpo, to=[endereco_remetente], bcc=lote).send()
            total_enviados += len(lote)
        except Exception:
            logger.warning("[comunicacoes] falha ao mandar lote de %d e-mail(s)", len(lote), exc_info=True)

    return ComunicacaoEmail.objects.create(
        assunto=assunto,
        corpo=corpo,
        filtro=filtro,
        total_destinatarios=len(emails),
        total_enviados=total_enviados,
        enviado_por=enviado_por,
    )
