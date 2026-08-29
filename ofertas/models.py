from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse


class _CashbackEstimadoMixin:
    """Fórmulas de cashback estimado compartilhadas entre Oferta (sincronizada com a
    Shopee) e OfertaManual (cadastrada à mão no admin) - mesma matemática usada de
    verdade em pedidos/services.py (comissão x repasse do site, com teto por produto).
    Cada subclasse só precisa expor `percentual_comissao` e `preco_base_cashback`."""

    @property
    def _percentual_cashback_bruto(self) -> Decimal:
        """% de cashback sobre o preço, sem aplicar o teto por produto."""
        repasse = (
            Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL))
            / Decimal("100")
            * Decimal(str(settings.CASHBACK_MULTIPLICADOR_CAMPANHA))
        )
        return self.percentual_comissao * Decimal("100") * repasse

    @property
    def _limite_por_produto(self) -> Decimal:
        """Teto por produto vigente, já com o multiplicador de campanha - numa campanha
        de cashback em dobro o teto dobra junto. Usa o multiplicador atual (e não um
        congelado) porque aqui é estimativa de uma compra que ainda vai acontecer."""
        return Decimal(str(settings.CASHBACK_MAXIMO_POR_PRODUTO)) * Decimal(
            str(settings.CASHBACK_MULTIPLICADOR_CAMPANHA)
        )

    @property
    def valor_cashback_estimado(self) -> Decimal:
        """Estimativa em R$ do cashback, já limitada ao teto por produto - mesmo teto
        aplicado de verdade em pedidos/services.py, pra nunca mostrar um valor diferente
        do que é pago."""
        valor_bruto = self.preco_base_cashback * self._percentual_cashback_bruto / Decimal("100")
        return min(valor_bruto, self._limite_por_produto).quantize(Decimal("0.01"))

    @property
    def percentual_cashback(self) -> Decimal:
        """% de cashback exibida - já reduzida quando valor_cashback_estimado bate no
        teto por produto, pra badge (%) e valor (R$) sempre baterem um com o outro."""
        if not self.preco_base_cashback:
            return self._percentual_cashback_bruto.quantize(Decimal("0.1"))
        return (self.valor_cashback_estimado / self.preco_base_cashback * Decimal("100")).quantize(Decimal("0.1"))

    @property
    def cashback_no_limite(self) -> bool:
        """True quando o teto por produto reduziu o cashback abaixo do que a comissão
        real permitiria - usado pra mostrar um aviso de transparência no site."""
        valor_bruto = self.preco_base_cashback * self._percentual_cashback_bruto / Decimal("100")
        return valor_bruto > self._limite_por_produto


class Oferta(_CashbackEstimadoMixin, models.Model):
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
    def preco_base_cashback(self) -> Decimal:
        return self.preco_min

    @property
    def url_ir(self) -> str:
        return reverse("ofertas_ir", args=[self.id])


class CashbackMaximoCache(models.Model):
    """Maior % de cashback real entre as ofertas sincronizadas na última execução,
    ignorando ofertas onde o teto por produto reduziu o valor (ver
    ofertas/services.py::_atualizar_cashback_maximo) - senão um produto caro e capado
    poderia "roubar" o topo com um valor artificialmente baixo. Calculado uma vez por
    sincronização, não a cada visita à home. Singleton - só existe uma linha (pk=1),
    sobrescrita a cada sincronização."""

    percentual_maximo = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    @classmethod
    def atualizar(cls, percentual_maximo: Decimal) -> None:
        cls.objects.update_or_create(pk=1, defaults={"percentual_maximo": percentual_maximo})

    @classmethod
    def obter(cls) -> "CashbackMaximoCache | None":
        return cls.objects.filter(pk=1).first()

    def __str__(self):
        return f"até {self.percentual_maximo}%"


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


class _OfertaCuradaBase(_CashbackEstimadoMixin, models.Model):
    """Campos comuns entre OfertaManual (carrossel "Ofertas em alta") e
    OfertaDestaqueManual (hero "Oferta do dia") - produtos cadastrados à mão no admin,
    fora do catálogo sincronizado com a Shopee. Nunca são apagados por
    sincronizar_ofertas() (que só mexe em Oferta)."""

    product_link = models.URLField("Link do produto na Shopee")
    nome = models.CharField(max_length=255)
    imagem_url = models.URLField("URL da imagem do produto")
    preco_antigo = models.DecimalField(
        "Preço antigo", max_digits=10, decimal_places=2, help_text="Preço original, exibido riscado."
    )
    preco_novo = models.DecimalField("Preço novo", max_digits=10, decimal_places=2)
    preco_avista = models.DecimalField(
        "Preço à vista (com desconto)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Ex: preço no Pix/boleto, se for menor que o preço novo. Opcional - "
        "usado como base do cashback quando preenchido (senão usa o preço novo).",
    )
    percentual_desconto = models.PositiveIntegerField(
        "% de desconto", default=0, blank=True, help_text="Desconto mostrado no selo, ex: 10 representa 10%."
    )
    percentual_comissao = models.DecimalField(
        "% de comissão", max_digits=5, decimal_places=4,
        help_text="% de comissão desse produto (ex: 0.0500 representa 5%) - confira no seu extrato de "
        "afiliado ou no app da Shopee. O % de cashback exibido é calculado a partir daqui, igual às "
        "ofertas sincronizadas.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.nome} (R$ {self.preco_novo})"

    @property
    def preco_base_cashback(self) -> Decimal:
        return self.preco_avista or self.preco_novo


class OfertaManual(_OfertaCuradaBase):
    """Entra no carrossel "Ofertas em alta" da home, ocupando vaga antes das ofertas
    mais vendidas - ver ofertas/services.py::selecionar_carrossel_home. Fica até
    alguém remover aqui no admin; sem limite de quantas podem existir."""

    imperdivel = models.BooleanField(
        "Oferta imperdível", default=False, help_text="Mostra um selo de destaque no card, no carrossel da home."
    )

    class Meta:
        verbose_name = "Oferta manual"
        verbose_name_plural = "Ofertas manuais"
        ordering = ["-criado_em"]

    @property
    def url_ir(self) -> str:
        return reverse("ofertas_manual_ir", args=[self.id])


class OfertaDestaqueManual(_OfertaCuradaBase):
    """Substitui a "Oferta do dia" (hero da home) por um produto escolhido à mão, no
    lugar do mais vendido do catálogo sincronizado - ver
    ofertas/services.py::selecionar_carrossel_home. Singleton na prática: nunca existe
    mais de um registro, mas isso é garantido em OfertaDestaqueManualAdmin
    (has_add_permission só libera "adicionar" quando não existe nenhuma ainda) - não
    aqui no model, pra evitar forçar um pk fixo e corromper o auto_now_add de
    criado_em num "salvar por cima" de uma instância nova. Editar em vez de trocar já
    atualiza a mesma linha; trocar de produto é excluir e cadastrar de novo. Excluir a
    única que existe volta a "Oferta do dia" pro automático."""

    class Meta:
        verbose_name = "Oferta do dia (destaque manual)"
        verbose_name_plural = "Oferta do dia (destaque manual)"

    @property
    def url_ir(self) -> str:
        return reverse("ofertas_destaque_manual_ir", args=[self.id])
