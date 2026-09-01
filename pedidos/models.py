from decimal import Decimal

from django.conf import settings
from django.db import models

from links.models import Click


class Pedido(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_VALIDADO = "validado"
    STATUS_LIBERADO = "liberado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_VALIDADO, "Validado"),
        (STATUS_LIBERADO, "Liberado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    order_id = models.CharField(max_length=64, unique=True)
    conversion_id = models.CharField(max_length=64)
    click = models.ForeignKey(Click, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="pedidos"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    status_shopee_bruto = models.CharField(
        max_length=64, help_text="Valor original retornado pela Shopee, guardado para conferência."
    )
    valor_pedido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Valor realmente pago pelo comprador (actualAmount da Shopee, já descontando cupom/desconto).",
    )
    valor_comissao = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    valor_cashback = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    multiplicador_campanha = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1"),
        help_text=(
            "Multiplicador de CampanhaCashback que valia na data_compra deste pedido, "
            "carimbado aqui quando ele foi registrado pela primeira vez. Fica congelado de "
            "propósito: a Shopee reenvia o mesmo pedido em toda sincronização seguinte, e sem "
            "isso o cashback seria recalculado com o multiplicador vigente naquele momento - o "
            "dobro prometido numa campanha sumiria assim que ela acabasse. Ver "
            "pedidos/services.py::sincronizar."
        ),
    )
    produto_nome = models.CharField(max_length=255, blank=True)
    produto_imagem_url = models.URLField(blank=True)
    motivo_cancelamento = models.CharField(
        max_length=255, blank=True, help_text="Motivo informado pela Shopee (fraudReason), quando cancelado."
    )
    data_compra = models.DateTimeField(null=True, blank=True)
    data_validacao = models.DateTimeField(null=True, blank=True)
    data_prevista_liberacao = models.DateField(
        null=True, blank=True, help_text="1º dia do mês em que o saldo deste pedido fica liberado (mês da validação + 2)."
    )
    data_liberacao = models.DateTimeField(
        null=True, blank=True, help_text="Momento em que o comando liberar_saldo efetivamente liberou este pedido."
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_compra"]

    def __str__(self):
        return f"Pedido {self.order_id} ({self.get_status_display()})"


class CampanhaCashback(models.Model):
    """Janela de datas com multiplicador de cashback em dobro (ou outro valor) -
    substitui o antigo CASHBACK_MULTIPLICADOR_CAMPANHA fixo no .env (ver ROADMAP.md,
    Fase 44).

    O problema do jeito antigo: o multiplicador era carimbado num pedido com o valor
    vigente NA SINCRONIZAÇÃO (uma vez por dia, de madrugada - ver
    pedidos/services.py::_montar_linhas), não com o valor vigente na hora da compra
    (data_compra). Uma compra feita às 23h de um dia de campanha só seria sincronizada
    horas depois, no dia seguinte - se a campanha já tivesse sido desligada (mudando o
    .env e fazendo deploy) antes dessa sincronização rodar, esse pedido perdia o dobro
    injustamente. Pra evitar isso, era preciso lembrar de manter a campanha ligada até
    depois da sincronização seguinte ao fim planejado dela.

    Com a campanha guardada aqui (data de início/fim, editável no admin sem deploy),
    o multiplicador de cada pedido é escolhido comparando a data_compra real contra a
    janela da campanha (ver multiplicador_em) - não importa quando a sincronização
    roda, o resultado é sempre o mesmo. Ligar/desligar vira só uma data no admin.

    Pode haver várias linhas (histórico de campanhas passadas) - multiplicador_em
    busca a que cobre o momento pedido; fim em branco = campanha ainda sem data de
    término definida (continua valendo até você editar ou apagar)."""

    multiplicador = models.DecimalField(
        "Multiplicador", max_digits=4, decimal_places=2, default=Decimal("2"),
        help_text="Ex: 2 = cashback em dobro durante essa janela.",
    )
    inicio = models.DateTimeField("Início")
    fim = models.DateTimeField(
        "Fim", null=True, blank=True,
        help_text="Deixe em branco se ainda não sabe quando a campanha termina.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Campanha de cashback"
        verbose_name_plural = "Campanhas de cashback"
        ordering = ["-inicio"]

    def __str__(self):
        fim = self.fim.strftime("%d/%m/%Y %H:%M") if self.fim else "sem fim definido"
        return f"{self.multiplicador}x ({self.inicio.strftime('%d/%m/%Y %H:%M')} até {fim})"

    @classmethod
    def listar(cls) -> list["CampanhaCashback"]:
        """Todas as campanhas cadastradas, mais recentes primeiro - carregada uma vez
        e reusada pra resolver o multiplicador de vários pedidos numa sincronização em
        lote sem fazer 1 consulta ao banco por pedido (ver
        pedidos/services.py::_montar_linhas)."""
        return list(cls.objects.order_by("-inicio"))

    @classmethod
    def multiplicador_em(cls, momento, campanhas: "list[CampanhaCashback] | None" = None) -> Decimal:
        """Multiplicador vigente num momento específico - usado pra carimbar o
        cashback de um pedido pela data_compra real (ver pedidos/services.py).
        Decimal("1") (sem campanha) se nenhuma linha cobre esse momento, ou se
        momento é None (ex: purchaseTime ausente na resposta da Shopee).

        Aceita uma lista de campanhas já carregada (ver listar()) pra evitar 1
        consulta ao banco por pedido numa sincronização em lote - sem isso, buscar
        milhares de pedidos ficaria lento demais (ver
        SincronizarTests.test_sincroniza_muitos_pedidos_com_poucas_consultas_ao_banco).
        Sem passar `campanhas`, busca do banco - ok pra uma chamada avulsa."""
        if momento is None:
            return Decimal("1")
        if campanhas is None:
            campanhas = cls.listar()
        for campanha in campanhas:
            if campanha.inicio <= momento and (campanha.fim is None or campanha.fim >= momento):
                return campanha.multiplicador
        return Decimal("1")

    @classmethod
    def multiplicador_atual(cls) -> Decimal:
        """Multiplicador vigente agora - usado pra exibir o cashback estimado nos
        cards de oferta (ver ofertas/models.py), já que ali não existe uma
        data_compra real (a compra ainda não aconteceu)."""
        from django.utils import timezone

        return cls.multiplicador_em(timezone.now())
