from decimal import Decimal

from django.conf import settings
from django.db import models


class Oferta(models.Model):
    item_id = models.BigIntegerField("ID do produto na Shopee", unique=True)
    nome = models.CharField(max_length=255)
    nome_curto = models.CharField(
        max_length=255, blank=True,
        help_text="Versão enxuta do nome (via Gemini) pra exibição - ver ofertas/gemini_client.py. "
        "Sempre preenchido (cai pro nome original se o Gemini não estiver configurado/disponível).",
    )
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

    @property
    def _percentual_cashback_bruto(self) -> Decimal:
        """% de cashback sobre o preço, sem aplicar o teto por produto - mesma fórmula
        usada de verdade em pedidos/services.py (comissão x repasse do site), antes do
        min() com CASHBACK_MAXIMO_POR_PRODUTO."""
        repasse = (
            Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL))
            / Decimal("100")
            * Decimal(str(settings.CASHBACK_MULTIPLICADOR_CAMPANHA))
        )
        return self.percentual_comissao * Decimal("100") * repasse

    @property
    def valor_cashback_estimado(self) -> Decimal:
        """Estimativa em R$ do cashback sobre o preço mínimo, já limitada a
        CASHBACK_MAXIMO_POR_PRODUTO - mesmo teto aplicado de verdade em
        pedidos/services.py, pra nunca mostrar um valor maior do que o que é pago."""
        limite = Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO))
        valor_bruto = self.preco_min * self._percentual_cashback_bruto / Decimal("100")
        return min(valor_bruto, limite).quantize(Decimal("0.01"))

    @property
    def percentual_cashback(self) -> Decimal:
        """% de cashback exibida - já reduzida quando valor_cashback_estimado bate no
        teto por produto, pra badge (%) e valor (R$) sempre baterem um com o outro."""
        if not self.preco_min:
            return self._percentual_cashback_bruto.quantize(Decimal("0.1"))
        return (self.valor_cashback_estimado / self.preco_min * Decimal("100")).quantize(Decimal("0.1"))

    @property
    def cashback_no_limite(self) -> bool:
        """True quando o teto por produto reduziu o cashback abaixo do que a comissão
        real permitiria - usado pra mostrar um aviso de transparência no site."""
        limite = Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO))
        valor_bruto = self.preco_min * self._percentual_cashback_bruto / Decimal("100")
        return valor_bruto > limite


class FaixaCashbackCache(models.Model):
    """Faixa (mín-máx) de % de cashback entre as ofertas sincronizadas na última
    execução - calculada uma vez por sincronização (ver sincronizar_ofertas), não a cada
    visita à home, e usada lá pro "de X% a Y% de cashback" sempre bater com o que a
    pessoa realmente vê no catálogo (já com o teto por produto aplicado). Singleton -
    só existe uma linha (pk=1), sobrescrita a cada sincronização."""

    percentual_minimo = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    percentual_maximo = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    @classmethod
    def atualizar(cls, percentual_minimo: Decimal, percentual_maximo: Decimal) -> None:
        cls.objects.update_or_create(
            pk=1, defaults={"percentual_minimo": percentual_minimo, "percentual_maximo": percentual_maximo}
        )

    @classmethod
    def obter(cls) -> "FaixaCashbackCache | None":
        return cls.objects.filter(pk=1).first()

    def __str__(self):
        return f"{self.percentual_minimo}% – {self.percentual_maximo}%"


class NomeCurtoCache(models.Model):
    """Cache de nomes já encurtados pelo Gemini, guardado à parte da Oferta porque a
    sincronização apaga e recria todas as ofertas a cada execução (ver services.py) - sem
    isso, todo produto seria reprocessado (e cobrado) de novo em toda sincronização, mesmo
    quando o nome não mudou."""

    item_id = models.BigIntegerField(unique=True)
    nome_original = models.CharField(max_length=255)
    nome_curto = models.CharField(max_length=255)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome_original} -> {self.nome_curto}"
