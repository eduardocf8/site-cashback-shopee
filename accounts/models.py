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

    cpf = models.CharField(
        "CPF",
        max_length=11,
        unique=True,
        help_text="Apenas números, sem pontos ou traço.",
    )
    chave_pix = models.CharField("Chave Pix", max_length=140, blank=True)
    tipo_chave_pix = models.CharField(
        "Tipo da chave Pix", max_length=10, choices=TIPO_CHAVE_CHOICES, blank=True
    )
    email_verificado = models.BooleanField("E-mail verificado", default=False)
    codigo_indicacao = models.CharField(
        "Código de indicação", max_length=TAMANHO_CODIGO_INDICACAO, unique=True, blank=True
    )

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
