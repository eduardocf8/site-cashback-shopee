import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_cpf

# Sem caracteres ambíguos (0/O, 1/I/L) - o código é pra gente compartilhar em texto/voz.
ALFABETO_CODIGO_INDICACAO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO_INDICACAO = 8


class User(AbstractUser):
    TIPO_CHAVE_CPF = "CPF"
    TIPO_CHAVE_CNPJ = "CNPJ"
    TIPO_CHAVE_EMAIL = "EMAIL"
    TIPO_CHAVE_TELEFONE = "PHONE"
    TIPO_CHAVE_ALEATORIA = "EVP"
    TIPO_CHAVE_CHOICES = [
        (TIPO_CHAVE_CPF, "CPF"),
        (TIPO_CHAVE_CNPJ, "CNPJ"),
        (TIPO_CHAVE_EMAIL, "E-mail"),
        (TIPO_CHAVE_TELEFONE, "Telefone"),
        (TIPO_CHAVE_ALEATORIA, "Chave aleatória"),
    ]

    # Vazio (NULL) só em conta criada pelo login com Google: o CPF é pedido junto com a
    # chave Pix, antes do primeiro saque (ver ChavePixForm). NULL e não "" porque a
    # unicidade (uma conta por CPF) precisa ignorar quem ainda não informou.
    cpf = models.CharField(
        "CPF",
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        help_text="Apenas números, sem pontos ou traço.",
    )
    google_sub = models.CharField(
        "ID da conta Google", max_length=255, unique=True, null=True, blank=True, editable=False,
        help_text="Identificador estável da conta Google vinculada (accounts/google_oauth.py).",
    )
    nome_completo = models.CharField(
        "Nome completo", max_length=150, blank=True,
        help_text="Nome real da pessoa - comparado com o titular da chave Pix (accounts/verificacao_pix.py). "
        "Vazio só em contas criadas antes de o campo existir.",
    )
    celular = models.CharField(
        "Celular", max_length=11, blank=True,
        help_text="DDD + número, só dígitos (ex: 11987654321). Vazio só em contas antigas.",
    )
    chave_pix = models.CharField("Chave Pix", max_length=140, blank=True)
    tipo_chave_pix = models.CharField(
        "Tipo da chave Pix", max_length=10, choices=TIPO_CHAVE_CHOICES, blank=True
    )
    # Verificação da titularidade da chave Pix na Asaas (accounts/verificacao_pix.py):
    # o CPF do titular da chave tem que bater com o CPF da conta. Bloqueia CPF de
    # gerador (não tem chave Pix de ninguém) e saque pra chave de outra pessoa.
    PIX_NAO_VERIFICADA = ""
    PIX_VERIFICADA = "verificada"
    PIX_RECUSADA = "recusada"
    PIX_PENDENTE = "pendente"
    PIX_STATUS_CHOICES = [
        (PIX_NAO_VERIFICADA, "Não verificada"),
        (PIX_VERIFICADA, "Verificada"),
        (PIX_RECUSADA, "Recusada (titular não confere)"),
        (PIX_PENDENTE, "Verificação pendente"),
    ]
    chave_pix_status = models.CharField(
        "Verificação da chave Pix", max_length=12, choices=PIX_STATUS_CHOICES, blank=True, default="",
    )
    chave_pix_titular_nome = models.CharField(
        "Titular da chave Pix (Asaas)", max_length=200, blank=True,
        help_text="Nome devolvido pela Asaas na consulta da chave - conferir no admin antes de aprovar saques.",
    )
    chave_pix_titular_documento = models.CharField(
        "CPF/CNPJ do titular (mascarado)", max_length=20, blank=True,
    )
    chave_pix_verificada_em = models.DateTimeField("Chave Pix verificada em", null=True, blank=True)
    chave_pix_nome_confere = models.BooleanField(
        "Nome do titular confere", null=True, blank=True,
        help_text="Nome completo x titular devolvido pela Asaas. Não bloqueia sozinho (bancos abreviam "
        "nomes) - Não = conferir no admin antes de aprovar saques.",
    )
    email_verificado = models.BooleanField("E-mail verificado", default=False)
    aceita_email_marketing = models.BooleanField(
        "Aceita e-mails de promoções/anúncios",
        default=True,
        help_text="Desligado quando a pessoa clica em \"não quero mais receber\" num anúncio. Não afeta "
        "e-mails transacionais (verificação, senha, avisos de saque) nem comunicações gerais.",
    )
    codigo_indicacao = models.CharField(
        "Código de indicação", max_length=TAMANHO_CODIGO_INDICACAO, unique=True, blank=True
    )
    # Preenchidos só no cadastro, a partir do utm_source/utm_campaign da primeira
    # visita (ver accounts/middleware.py). Vazio = entrou sem UTM (direto, busca,
    # indicação sem link com UTM) ou se cadastrou antes de existir o campo.
    origem_cadastro = models.CharField(
        "Origem do cadastro", max_length=50, blank=True, db_index=True,
        help_text="utm_source da primeira visita (ex: pinterest, instagram).",
    )
    origem_campanha = models.CharField("Campanha de origem", max_length=100, blank=True)

    def clean(self):
        super().clean()
        if self.cpf:
            self.cpf = validar_cpf(self.cpf)

    def save(self, *args, **kwargs):
        if not self.codigo_indicacao:
            self.codigo_indicacao = self._gerar_codigo_indicacao()
        super().save(*args, **kwargs)

    @classmethod
    def _gerar_codigo_indicacao(cls):
        while True:
            codigo = "".join(secrets.choice(ALFABETO_CODIGO_INDICACAO) for _ in range(TAMANHO_CODIGO_INDICACAO))
            if not cls.objects.filter(codigo_indicacao=codigo).exists():
                return codigo

    @property
    def chave_pix_verificada(self) -> bool:
        return bool(self.chave_pix) and self.chave_pix_status == self.PIX_VERIFICADA

    def __str__(self):
        return self.username


class PushSubscription(models.Model):
    """Uma inscrição de push por navegador/dispositivo (ver accounts/push.py).

    Um usuário pode ter várias - uma por navegador/aparelho onde ele clicou em "Ativar
    notificações". O endpoint por si só já identifica o dispositivo de forma única
    (é gerado pelo próprio navegador), por isso a unicidade fica nele, não no par
    (usuario, endpoint)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=500, unique=True)
    chave_p256dh = models.CharField(max_length=255)
    chave_auth = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inscrição push de {self.usuario}"


class Indicacao(models.Model):
    """Vínculo entre quem indicou e quem se cadastrou pelo link - e os pedidos que
    dispararam o bônus de cashback em dobro de cada lado (ver pedidos/services.py)."""

    indicador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="indicacoes_feitas"
    )
    indicado = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="indicacao_recebida"
    )
    pedido_bonus_indicado = models.ForeignKey(
        "pedidos.Pedido", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="1ª compra validada do indicado - dispara o cashback em dobro dela.",
    )
    pedido_bonus_indicador = models.ForeignKey(
        "pedidos.Pedido", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Próxima compra validada de quem indicou depois do bônus acima - cashback em dobro dela.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.indicador} indicou {self.indicado}"


class ConfiguracaoIndicacao(models.Model):
    """Liga/pausa a campanha "indique e ganhe" pelo admin, sem precisar de deploy -
    pensado pra situações como um mês de campanha com cashback em dobro, onde somar o
    dobro de indicação em cima também inviabilizaria o custo. Linha única (pk=1).

    Pausada: só bloqueia indicações NOVAS (cadastro com ?ref=, ver
    accounts/views.py::_criar_indicacao_se_valida) e esconde a seção/link no dashboard.
    Indicações já existentes continuam recebendo o dobro normalmente - o cálculo do
    bônus em pedidos/services.py não lê esse flag, só a criação de vínculos novos."""

    ativa = models.BooleanField("Campanha ativa", default=True)

    class Meta:
        verbose_name = "Configuração de indicação"
        verbose_name_plural = "Configuração de indicação"

    def __str__(self):
        return "Ativa" if self.ativa else "Pausada"

    @classmethod
    def esta_ativa(cls) -> bool:
        config = cls.objects.filter(pk=1).first()
        return config.ativa if config else True


class ComunicacaoEmail(models.Model):
    """Registro de uma comunicação em massa mandada pelo admin (ver
    accounts/comunicacoes.py) - histórico só, criado pelo envio em si, nunca
    editado depois."""

    FILTRO_TODOS = "todos"
    FILTRO_COM_PEDIDOS = "com_pedidos"
    FILTRO_SEM_PEDIDOS = "sem_pedidos"
    FILTRO_EMAIL_VERIFICADO = "email_verificado"
    FILTRO_EMAIL_NAO_VERIFICADO = "email_nao_verificado"
    FILTRO_JA_SACOU = "ja_sacou"
    FILTRO_NUNCA_SACOU = "nunca_sacou"
    FILTRO_CHOICES = [
        (FILTRO_TODOS, "Todos os usuários cadastrados"),
        (FILTRO_COM_PEDIDOS, "Já fizeram pelo menos 1 pedido"),
        (FILTRO_SEM_PEDIDOS, "Ainda não fizeram nenhum pedido"),
        (FILTRO_EMAIL_VERIFICADO, "E-mail verificado"),
        (FILTRO_EMAIL_NAO_VERIFICADO, "E-mail ainda não verificado"),
        (FILTRO_JA_SACOU, "Já sacaram pelo menos uma vez"),
        (FILTRO_NUNCA_SACOU, "Nunca sacaram"),
    ]

    TIPO_GERAL = "geral"
    TIPO_ANUNCIO = "anuncio"
    TIPO_CHOICES = [
        (TIPO_ANUNCIO, "Anúncio/promoção"),
        (TIPO_GERAL, "Comunicação geral"),
    ]

    assunto = models.CharField("Assunto", max_length=200)
    corpo = models.TextField("Corpo do e-mail", help_text="Texto simples, sem HTML.")
    tipo = models.CharField(
        "Tipo",
        max_length=10,
        choices=TIPO_CHOICES,
        default=TIPO_ANUNCIO,
        help_text="Anúncio/promoção respeita quem desligou e-mail de marketing e inclui o link de "
        "descadastro. Comunicação geral vai pra todo mundo do filtro, sem esse link.",
    )
    filtro = models.CharField("Filtro de destinatários", max_length=30, choices=FILTRO_CHOICES)
    ofertas = models.ManyToManyField(
        "ofertas.Oferta",
        blank=True,
        related_name="+",
        verbose_name="Ofertas em destaque",
        help_text="Vitrine de produtos incluída no e-mail (imagem + link de cashback de cada uma).",
    )
    banner = models.ImageField(
        "Imagem de banner (opcional)",
        upload_to="comunicacoes/banners/",
        blank=True,
        null=True,
        help_text="Aparece no topo do e-mail, antes do texto - ex: banner de campanha/promoção.",
    )
    corpo_html = models.TextField(
        "Corpo em HTML (com a vitrine)",
        blank=True,
        help_text="Gerado automaticamente a partir do corpo em texto + ofertas escolhidas - guardado aqui pra "
        "manter fiel o que foi realmente mandado, mesmo que preço/imagem da oferta mude depois.",
    )
    total_destinatarios = models.PositiveIntegerField("Total de destinatários", default=0)
    total_enviados = models.PositiveIntegerField("Total enviados com sucesso", default=0)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    enviado_em = models.DateTimeField("Enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "Comunicação por e-mail"
        verbose_name_plural = "Comunicações por e-mail"
        ordering = ["-enviado_em"]

    def __str__(self):
        return f"{self.assunto} ({self.enviado_em:%d/%m/%Y %H:%M})"
