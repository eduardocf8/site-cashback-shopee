import secrets
from datetime import date

from django.db import models
from django.utils import timezone

# Módulos que uma conta do Appfiliado pode ter liberados. O código (chave) é o que vai
# na resposta do /licencas/validar/ e o que o app usa para decidir o que mostrar - não
# mude um código existente sem atualizar o app também.
MODULO_WHATSAPP = "whatsapp"
MODULO_SITE = "site"
MODULO_VITRINE = "vitrine"
MODULO_VIDEOS = "videos"
MODULO_INSTAGRAM = "instagram"
MODULOS = [
    (MODULO_WHATSAPP, "Bot de WhatsApp"),
    (MODULO_SITE, "Meu site (conversor)"),
    (MODULO_VITRINE, "Vitrine"),
    (MODULO_VIDEOS, "Gerador de vídeos"),
    (MODULO_INSTAGRAM, "Automação do Instagram"),
]
CODIGOS_MODULOS = [codigo for codigo, _ in MODULOS]


def gerar_chave() -> str:
    """Chave de licença legível e com entropia suficiente (80 bits) para não dar para
    adivinhar por tentativa. Formato "AF-XXXXXXXXXXXXXXXXXXXX" (hex maiúsculo)."""
    return f"AF-{secrets.token_hex(10).upper()}"


def modulos_de_texto(texto: str) -> list[str]:
    """"whatsapp, site" -> ["whatsapp", "site"], ignorando códigos desconhecidos e
    mantendo a ordem de MODULOS."""
    escolhidos = {parte.strip() for parte in (texto or "").split(",") if parte.strip()}
    return [codigo for codigo in CODIGOS_MODULOS if codigo in escolhidos]


class ContaAppfiliado(models.Model):
    """Uma pessoa que usa o Appfiliado. A chave de licença é da conta (uma só, vale para
    todos os módulos): comprar outro serviço depois só soma módulos à mesma chave.

    Criada sozinha pelo webhook da Zouti na primeira assinatura daquele e-mail. Também
    dá para criar à mão no /admin/ para liberar módulos de cortesia (uso próprio, clientes
    antigos do conversor etc.) - ver modulos_cortesia."""

    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=140, blank=True)
    chave = models.CharField(max_length=40, unique=True, default=gerar_chave, db_index=True)
    chave_enviada_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Quando o e-mail com a chave foi enviado. Vazio = ainda não enviado.",
    )

    modulos_cortesia = models.CharField(
        max_length=200, blank=True,
        help_text="Módulos liberados à mão, sem assinatura (ex: uso próprio).",
    )
    cortesia_ate = models.DateField(
        null=True, blank=True,
        help_text="Até quando a cortesia vale. Vazio = sem prazo.",
    )

    # Login no painel web (app.appfiliado.com.br) - ver painel/autenticacao.py.
    # Senha guardada com o hasher padrão do Django (nunca em texto). Vazia = a
    # pessoa ainda não definiu (o link vai no e-mail da chave).
    senha = models.CharField(max_length=128, blank=True)
    ultimo_login = models.DateTimeField(null=True, blank=True)

    # Credenciais da Open API de afiliados da Shopee da própria pessoa - os
    # relatórios e o bot do painel usam essas, não as da cash-b. O Secret fica
    # cifrado (painel/cripto.py).
    shopee_app_id = models.CharField(max_length=64, blank=True)
    shopee_secret_cifrado = models.TextField(blank=True)
    shopee_validado_em = models.DateTimeField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "conta do Appfiliado"
        verbose_name_plural = "contas do Appfiliado"

    def __str__(self):
        return f"{self.email} ({self.chave})"

    def definir_senha(self, senha_crua: str):
        from django.contrib.auth.hashers import make_password

        self.senha = make_password(senha_crua)

    def confere_senha(self, senha_crua: str) -> bool:
        from django.contrib.auth.hashers import check_password

        return bool(self.senha) and check_password(senha_crua, self.senha)

    @property
    def tem_senha(self) -> bool:
        return bool(self.senha)

    @property
    def shopee_configurada(self) -> bool:
        return bool(self.shopee_app_id and self.shopee_secret_cifrado)

    def cortesia_vigente(self, hoje: date | None = None) -> list[str]:
        hoje = hoje or timezone.localdate()
        if self.cortesia_ate and self.cortesia_ate < hoje:
            return []
        return modulos_de_texto(self.modulos_cortesia)

    def modulos_liberados(self, hoje: date | None = None) -> list[str]:
        """Junta a cortesia com os módulos de todas as assinaturas que dão acesso hoje."""
        hoje = hoje or timezone.localdate()
        liberados = set(self.cortesia_vigente(hoje))
        mapa = ProdutoZouti.mapa_modulos()
        for assinatura in self.assinaturas.all():
            if assinatura.da_acesso(hoje):
                liberados.update(assinatura.modulos(mapa))
        return [codigo for codigo in CODIGOS_MODULOS if codigo in liberados]


class ProdutoZouti(models.Model):
    """Diz quais módulos cada produto da Zouti libera. Cadastrado à mão no /admin/
    depois de criar o produto na Zouti - assim um pacote novo não precisa de deploy.

    O vínculo é pelo ID do produto (prod_...), que vem em line_items[].product_id dos
    webhooks de assinatura. Como os módulos são calculados na hora da validação, mudar
    o mapeamento aqui vale na hora para todo mundo que já assinou aquele produto."""

    zouti_product_id = models.CharField("ID do produto na Zouti", max_length=64, unique=True)
    nome = models.CharField(max_length=140, help_text="Só para você reconhecer o produto aqui.")
    modulos = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "produto da Zouti"
        verbose_name_plural = "produtos da Zouti"

    def __str__(self):
        return f"{self.nome} ({self.zouti_product_id})"

    def lista_modulos(self) -> list[str]:
        return modulos_de_texto(self.modulos)

    @classmethod
    def mapa_modulos(cls) -> dict[str, list[str]]:
        return {p.zouti_product_id: p.lista_modulos() for p in cls.objects.all()}


class Assinatura(models.Model):
    """Uma assinatura da Zouti (sub_...). Mantida em dia só pelos webhooks."""

    STATUS_INCOMPLETA = "incompleta"
    STATUS_ATIVA = "ativa"
    STATUS_TESTE = "teste"
    STATUS_ATRASADA = "atrasada"
    STATUS_CANCELADA = "cancelada"
    STATUS_REEMBOLSADA = "reembolsada"
    STATUS_CHARGEBACK = "chargeback"
    STATUS_CHOICES = [
        (STATUS_INCOMPLETA, "Aguardando pagamento"),
        (STATUS_ATIVA, "Ativa"),
        (STATUS_TESTE, "Em teste grátis"),
        (STATUS_ATRASADA, "Pagamento atrasado"),
        (STATUS_CANCELADA, "Cancelada"),
        (STATUS_REEMBOLSADA, "Reembolsada"),
        (STATUS_CHARGEBACK, "Chargeback"),
    ]
    # Qualquer outro status bloqueia por padrão - inclusive um que a Zouti venha a
    # mandar e a gente ainda não tenha mapeado.
    STATUS_QUE_LIBERAM = {STATUS_ATIVA, STATUS_TESTE}

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="assinaturas")
    zouti_subscription_id = models.CharField(max_length=64, unique=True)
    zouti_order_id = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="Pedido que originou a assinatura - usado para achar a assinatura num estorno/chargeback.",
    )
    zouti_product_ids = models.CharField(
        max_length=300, blank=True,
        help_text="IDs dos produtos da assinatura, separados por vírgula.",
    )
    plano = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_INCOMPLETA)
    motivo = models.CharField(
        max_length=200, blank=True,
        help_text="Texto mostrado no app quando a assinatura não dá acesso.",
    )
    proxima_cobranca = models.DateField(null=True, blank=True)
    acesso_ate = models.DateField(
        null=True, blank=True,
        help_text="Pra assinatura cancelada: acesso continua até o fim do período já pago.",
    )

    zouti_atualizada_em = models.DateTimeField(
        null=True, blank=True,
        help_text="updated_at do último evento aplicado - evita que um evento antigo, reenviado "
                  "depois, desfaça um mais novo.",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self):
        return f"{self.zouti_subscription_id} - {self.conta.email} ({self.get_status_display()})"

    def lista_product_ids(self) -> list[str]:
        return [p.strip() for p in self.zouti_product_ids.split(",") if p.strip()]

    def modulos(self, mapa: dict[str, list[str]] | None = None) -> list[str]:
        mapa = mapa if mapa is not None else ProdutoZouti.mapa_modulos()
        resultado = set()
        for product_id in self.lista_product_ids():
            resultado.update(mapa.get(product_id, []))
        return [codigo for codigo in CODIGOS_MODULOS if codigo in resultado]

    def da_acesso(self, hoje: date | None = None) -> bool:
        if self.status in self.STATUS_QUE_LIBERAM:
            return True
        hoje = hoje or timezone.localdate()
        return self.status == self.STATUS_CANCELADA and bool(self.acesso_ate) and self.acesso_ate >= hoje


class EventoWebhookZouti(models.Model):
    """Guarda cada webhook recebido, cru, antes de qualquer interpretação - serve para
    depurar, para auditoria e para não processar duas vezes o mesmo evento (a Zouti
    reenvia por até 4 dias quando não recebe 2xx)."""

    zouti_event_id = models.CharField(max_length=64, blank=True, db_index=True)
    tipo_evento = models.CharField(max_length=60, blank=True, db_index=True)
    tipo_objeto = models.CharField(max_length=30, blank=True)
    zouti_object_id = models.CharField(max_length=64, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    corpo_bruto = models.TextField()
    assinatura_valida = models.BooleanField(default=False)
    processado_com_sucesso = models.BooleanField(default=False)
    resultado = models.CharField(max_length=200, blank=True)
    erro = models.TextField(blank=True)
    recebido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recebido_em"]
        verbose_name = "evento de webhook da Zouti"
        verbose_name_plural = "eventos de webhook da Zouti"

    def __str__(self):
        return f"{self.tipo_evento or '?'} ({self.recebido_em:%d/%m/%Y %H:%M})"
