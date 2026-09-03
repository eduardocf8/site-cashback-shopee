from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from pedidos.models import CampanhaCashback


class _CashbackEstimadoMixin:
    """Fórmulas de cashback estimado compartilhadas entre Oferta (sincronizada com a
    Shopee) e OfertaManual (cadastrada à mão no admin) - mesma matemática usada de
    verdade em pedidos/services.py: cashback é uma fração fixa (SHOPEE_CASHBACK_PERCENTUAL)
    da comissão recebida, com o piso mínimo de venda direta (CASHBACK_MINIMO_VENDA_DIRETA)
    quando isso resultaria em menos - toda oferta aqui vira um clique de link/vitrine
    específico (ver ofertas/views.py::ir_para_oferta), verificado 1:1 com o item
    comprado (ver ROADMAP.md, Fase 41), então sempre conta como venda direta. Cada
    subclasse só precisa expor `percentual_comissao` e `preco_base_cashback`."""

    @property
    def _fracao_cashback_sem_piso(self) -> Decimal:
        """Fração do preço (0-1) antes de aplicar o piso mínimo e o multiplicador de
        campanha - mesma matemática de pedidos/services.py, só sem o max() com o piso
        ainda."""
        return (
            self.percentual_comissao
            * Decimal(str(settings.SHOPEE_CASHBACK_PERCENTUAL))
            / Decimal("100")
        )

    @property
    def _fracao_cashback(self) -> Decimal:
        """Fração do preço (0-1) já com o piso mínimo de venda direta aplicado, antes
        do multiplicador de campanha - equivalente a `cashback_base_item` em
        pedidos/services.py::_montar_defaults."""
        piso = Decimal(str(settings.CASHBACK_MINIMO_VENDA_DIRETA)) / Decimal("100")
        return max(self._fracao_cashback_sem_piso, piso)

    @property
    def valor_cashback_estimado(self) -> Decimal:
        """Estimativa em R$ do cashback - mesma fórmula usada de verdade em
        pedidos/services.py (piso mínimo incluso), pra nunca mostrar um valor
        diferente do que é pago. Usa o multiplicador de campanha vigente AGORA (ver
        CampanhaCashback.multiplicador_atual) - é uma estimativa de quem comprar
        agora, não uma promessa carimbada como no pedido de verdade."""
        multiplicador = CampanhaCashback.multiplicador_atual()
        valor_bruto = self.preco_base_cashback * self._fracao_cashback * multiplicador
        return valor_bruto.quantize(Decimal("0.01"))

    @property
    def percentual_cashback(self) -> Decimal:
        """% de cashback exibida, derivada do valor em R$ (já arredondado, já com o
        piso aplicado) - pra badge (%) e valor (R$) sempre baterem um com o outro."""
        if not self.preco_base_cashback:
            multiplicador = CampanhaCashback.multiplicador_atual()
            return (self._fracao_cashback * Decimal("100") * multiplicador).quantize(Decimal("0.1"))
        return (self.valor_cashback_estimado / self.preco_base_cashback * Decimal("100")).quantize(Decimal("0.1"))


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
    """Maior % de cashback real entre as ofertas sincronizadas na última execução (ver
    ofertas/services.py::_atualizar_cashback_maximo). Calculado uma vez por
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
        "Preço antigo", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Preço original, exibido riscado. Opcional - deixe em branco quando a loja não mostrar "
        "um preço \"de\" pra esse produto.",
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

    # Aliases pra reaproveitar instagram_bot/templates_imagem.py::gerar_imagem_oferta_story
    # e instagram_bot/services.py::_publicar_story_de_oferta sem duplicar - esses dois
    # foram escritos pro catálogo sincronizado (Oferta) e esperam esses nomes/campos, que
    # uma oferta curada à mão não tem por natureza (não veio da sincronização com item_id
    # nem categoria, e não passa pelo encurtamento via Gemini que gera nome_curto). Ver
    # "Criar story" em ofertas/admin.py.
    @property
    def nome_curto(self) -> str:
        return self.nome

    @property
    def preco_min(self) -> Decimal:
        return self.preco_base_cashback

    @property
    def categoria_id(self):
        return None

    @property
    def item_id(self):
        return None


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
