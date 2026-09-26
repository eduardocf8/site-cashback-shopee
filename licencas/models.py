import secrets

from django.db import models


def gerar_chave() -> str:
    """Chave de licença legível e com entropia suficiente (80 bits) pra não dar pra
    adivinhar por tentativa. Formato "AF-XXXXXXXXXXXXXXXXXXXX" (hex maiúsculo)."""
    return f"AF-{secrets.token_hex(10).upper()}"


class Licenca(models.Model):
    """Uma assinatura do Appfiliado, identificada pela chave que o comprador cola na
    tela de ativação do app. Criada e mantida em dia só pelos webhooks da Kiwify (ver
    views.webhook_kiwify) - não existe cadastro manual no fluxo normal."""

    STATUS_ATIVA = "ativa"
    STATUS_CANCELADA = "cancelada"
    STATUS_ATRASADA = "atrasada"
    STATUS_REEMBOLSADA = "reembolsada"
    STATUS_CHARGEBACK = "chargeback"
    STATUS_RECUSADA = "recusada"
    STATUS_CHOICES = [
        (STATUS_ATIVA, "Ativa"),
        (STATUS_CANCELADA, "Cancelada"),
        (STATUS_ATRASADA, "Pagamento atrasado"),
        (STATUS_REEMBOLSADA, "Reembolsada"),
        (STATUS_CHARGEBACK, "Chargeback"),
        (STATUS_RECUSADA, "Compra recusada"),
    ]

    # Só os status acima liberam o bot - qualquer outro valor (inclusive um novo status
    # que a Kiwify venha a mandar e a gente ainda não tenha mapeado) fica bloqueado por
    # padrão, propositalmente (ver services.aplicar_evento_webhook).
    STATUS_QUE_LIBERAM = {STATUS_ATIVA}

    chave = models.CharField(max_length=40, unique=True, default=gerar_chave, db_index=True)
    email = models.EmailField(db_index=True)
    nome = models.CharField(max_length=140, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ATIVA)
    motivo = models.CharField(
        max_length=200, blank=True,
        help_text="Texto mostrado pro usuário no app quando a licença não está válida.",
    )
    plano = models.CharField(max_length=80, blank=True)
    expira_em = models.DateField(null=True, blank=True, help_text="Próxima cobrança prevista pela Kiwify.")

    kiwify_subscription_id = models.CharField(max_length=64, blank=True, db_index=True)
    kiwify_customer_email = models.EmailField(
        blank=True, help_text="Cópia do e-mail no momento da criação, caso o comprador troque o e-mail depois."
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self):
        return f"{self.chave} - {self.email} ({self.get_status_display()})"

    @property
    def ativa(self) -> bool:
        return self.status in self.STATUS_QUE_LIBERAM


class EventoWebhookKiwify(models.Model):
    """Guarda cada webhook recebido, cru, antes de qualquer interpretação - serve pra
    depurar (o formato exato de cada tipo de evento ainda não está 100% mapeado) e pra
    auditoria, no mesmo espírito de resposta_asaas/resposta_inter em saques/models.py."""

    webhook_event_type = models.CharField(max_length=60, blank=True, db_index=True)
    order_status = models.CharField(max_length=30, blank=True)
    subscription_status = models.CharField(max_length=30, blank=True)
    kiwify_subscription_id = models.CharField(max_length=64, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    corpo_bruto = models.TextField()
    assinatura_valida = models.BooleanField(default=False)
    processado_com_sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True)
    recebido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recebido_em"]

    def __str__(self):
        return f"{self.webhook_event_type or '?'} ({self.recebido_em:%d/%m/%Y %H:%M})"
