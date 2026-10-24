"""Gerador de carrosséis: cada carrossel guarda o produto (como veio da Shopee), os
roteiros (os textos de cada slide) e as escolhas visuais. Os slides em si não ficam
salvos: são desenhados no navegador, a partir do roteiro, toda vez que a pessoa abre."""

from django.db import models
from django.utils import timezone

from licencas.models import ContaAppfiliado


class Carrossel(models.Model):
    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="carrosseis")
    item_id = models.CharField(max_length=32, blank=True)
    link_original = models.URLField(max_length=600)
    # nome, preco, de, desconto, nota, vendas, imagem, loja, link (o de afiliado, Sub ID "instagram")
    produto = models.JSONField(default=dict)
    # {"padrao": [slides], "premium": [slides]}: um roteiro para cada família de modelos
    roteiros = models.JSONField(default=dict)
    # O que a IA escreveu, para o "Voltar ao original" de cada slide.
    originais = models.JSONField(default=dict)
    # modelo, tema, cor, fonte, mostrar nota/preço antigo/"Arrasta", @...
    opcoes = models.JSONField(default=dict)
    # Foto enviada pela pessoa no lugar da da Shopee (premium). JPEG pequeno: o disco do
    # servidor não guarda arquivos (mesmo jeito da foto do Meu site).
    foto_propria = models.BinaryField(null=True, blank=True)
    # O produto sem fundo (PNG com transparência), feito no navegador a partir da foto em uso
    # (premium). Troca de foto apaga o recorte, que era dela.
    recorte = models.BinaryField(null=True, blank=True)
    legenda = models.TextField(blank=True)
    hashtags = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "carrossel"
        verbose_name_plural = "carrosséis"

    def __str__(self):
        return f"{self.produto.get('nome', 'Carrossel')[:60]} ({self.conta.email})"


class PadraoCarrossel(models.Model):
    """"Salvar como meu padrão" (premium): as escolhas visuais que já vêm nos próximos."""

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="padrao_carrossel")
    opcoes = models.JSONField(default=dict)
    atualizado_em = models.DateTimeField(auto_now=True)


class UsoCarrossel(models.Model):
    """Quantas vezes a conta usou a IA no dia (protege a cota da chave única do Gemini)."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="uso_carrosseis")
    dia = models.DateField(default=timezone.localdate)
    geracoes = models.PositiveIntegerField(default=0)
    reescritas = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conta", "dia"], name="uso_carrossel_por_dia")]
