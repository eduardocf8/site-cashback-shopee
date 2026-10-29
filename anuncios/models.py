"""Campanhas da Meta dos afiliados (Facebook e Instagram), só leitura: o gasto de cada campanha por dia,
para mostrar o lucro ao lado da comissão da Shopee. Desconectar apaga tudo (a conexão leva o resto)."""

from decimal import Decimal

from django.db import models

from licencas.models import ContaAppfiliado
from painel import cripto

IMPOSTO_PADRAO = Decimal("12.15")  # ISS, PIS e Cofins que a Meta cobra no Brasil por cima do valor gasto


class ConexaoMeta(models.Model):
    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="conexao_meta")
    usuario_id = models.CharField(max_length=64, db_index=True)  # o ID do Facebook da pessoa neste app
    nome = models.CharField(max_length=150, blank=True)
    token_cifrado = models.TextField()
    token_expira_em = models.DateTimeField(null=True, blank=True)
    imposto = models.DecimalField("imposto da Meta (%)", max_digits=5, decimal_places=2, default=IMPOSTO_PADRAO)
    lido_em = models.DateTimeField(null=True, blank=True)
    pedido_em = models.DateTimeField(null=True, blank=True)  # botão "Atualizar agora"
    erro = models.CharField(max_length=300, blank=True)
    conectada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conexão com a Meta"
        verbose_name_plural = "conexões com a Meta"

    def __str__(self):
        return f"{self.conta.email} - {self.nome}"

    @property
    def token(self) -> str:
        return cripto.decifrar(self.token_cifrado)


class ContaAnuncios(models.Model):
    conexao = models.ForeignKey(ConexaoMeta, on_delete=models.CASCADE, related_name="contas")
    account_id = models.CharField(max_length=32)  # só os números (sem o "act_")
    nome = models.CharField(max_length=200, blank=True)
    moeda = models.CharField(max_length=8, blank=True)
    acompanhar = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["conexao", "account_id"], name="conta_anuncios_unica")]

    def __str__(self):
        return f"{self.nome} ({self.account_id})"


class CampanhaMeta(models.Model):
    conta_anuncios = models.ForeignKey(ContaAnuncios, on_delete=models.CASCADE, related_name="campanhas")
    campanha_id = models.CharField(max_length=32)
    nome = models.CharField(max_length=300)
    situacao = models.CharField(max_length=40, blank=True)  # effective_status da Meta (ACTIVE, PAUSED...)
    criada_na_meta = models.DateTimeField(null=True, blank=True)
    # Sub ID da Shopee desta campanha. Vazio = pelo nome da campanha (o jeito mais comum).
    sub_id = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["conta_anuncios", "campanha_id"], name="campanha_meta_unica")]

    def __str__(self):
        return self.nome


class DiaCampanha(models.Model):
    campanha = models.ForeignKey(CampanhaMeta, on_delete=models.CASCADE, related_name="dias")
    dia = models.DateField()
    gasto = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # sem o imposto
    impressoes = models.PositiveIntegerField(default=0)
    cliques = models.PositiveIntegerField(default=0)  # cliques no link

    class Meta:
        ordering = ["-dia"]
        constraints = [models.UniqueConstraint(fields=["campanha", "dia"], name="dia_campanha_unico")]
