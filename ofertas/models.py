from django.db import models


class Oferta(models.Model):
    item_id = models.BigIntegerField("ID do produto na Shopee", unique=True)
    nome = models.CharField(max_length=255)
    imagem_url = models.URLField(blank=True)
    preco_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco_max = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    percentual_desconto = models.PositiveIntegerField(
        default=0, help_text="Desconto mostrado na Shopee, ex: 10 representa 10%."
    )
    percentual_comissao = models.DecimalField(
        max_digits=5, decimal_places=4, default=0, help_text="Ex: 0.0500 representa 5%."
    )
    avaliacao = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    vendas = models.PositiveIntegerField(default=0)
    categoria_id = models.PositiveIntegerField("ID da categoria (nível 1)", db_index=True)
    categoria_nome = models.CharField("Nome da categoria (nível 1)", max_length=100, blank=True)
    loja_nome = models.CharField(max_length=255, blank=True)
    product_link = models.URLField(
        "Link original do produto", help_text="Convertido em link de afiliado só na hora do clique."
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-vendas"]

    def __str__(self):
        return f"{self.nome} (R$ {self.preco_min}–{self.preco_max})"
