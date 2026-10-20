from django.db import models

from licencas.models import ContaAppfiliado


class ResultadoDiario(models.Model):
    """Totais de um dia de uma conta, vindos da API de afiliados da Shopee (ver
    painel/resultados.py). As telas de Resultados, Metas e Início só leem daqui -
    nunca chamam a Shopee durante a página.

    - faturamento / pedidos / comissao_estimada: pela DATA DA COMPRA (pedidos não
      cancelados), o mesmo critério do "faturamento do mês" das metas da Shopee.
    - comissao_validada: pela DATA DE VALIDAÇÃO dos itens (pedidos concluídos)."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="resultados_diarios")
    dia = models.DateField()
    pedidos = models.PositiveIntegerField(default=0)
    faturamento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    comissao_estimada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    comissao_validada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dia"]
        constraints = [models.UniqueConstraint(fields=["conta", "dia"], name="resultado_diario_unico")]

    def __str__(self):
        return f"{self.conta.email} {self.dia:%d/%m/%Y}"


class ResultadoSubIdDiario(models.Model):
    """Comissão estimada de um dia separada por Sub ID (pela data da compra)."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="resultados_sub_id")
    dia = models.DateField()
    sub_id = models.CharField(max_length=120)
    vendas = models.PositiveIntegerField(default=0)
    comissao_estimada = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conta", "dia", "sub_id"], name="resultado_sub_id_unico"),
        ]


class SincronizacaoResultados(models.Model):
    """Quando os resultados da conta foram buscados na Shopee pela última vez, e se
    a pessoa pediu uma atualização (botão "Atualizar agora") - quem atende é o
    comando sincronizar_painel, rodando em segundo plano."""

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="sincronizacao_resultados")
    pedido_em = models.DateTimeField(null=True, blank=True)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)
    erro = models.TextField(blank=True)
    cobertura_inicio = models.DateField(
        null=True, blank=True,
        help_text="Dia mais antigo com dados guardados (a API da Shopee só alcança ~3 meses para trás).",
    )
    completa_em = models.DateTimeField(
        null=True, blank=True, help_text="Última busca completa (~3 meses); as outras pegam só 30 dias.",
    )
    vendas_desde = models.DateTimeField(
        null=True, blank=True, help_text="Desde quando há itens vendidos guardados (VendaItem).",
    )

    class Meta:
        verbose_name = "sincronização de resultados"
        verbose_name_plural = "sincronizações de resultados"

    def __str__(self):
        return f"{self.conta.email}"

    @property
    def em_andamento(self) -> bool:
        return bool(self.iniciada_em and (not self.concluida_em or self.iniciada_em > self.concluida_em))

    @property
    def aguardando(self) -> bool:
        return bool(self.pedido_em and (not self.iniciada_em or self.pedido_em > self.iniciada_em))

    @property
    def atualizando(self) -> bool:
        return self.aguardando or self.em_andamento


class MetaMensal(models.Model):
    """As faixas de meta de faturamento que a Shopee deu pra conta num mês (até 3,
    ex: 100%, 125% e 150%, cada uma com um bônus). Cadastradas à mão - a Shopee não
    entrega isso pela API. faixas = [{"percentual": 100, "faturamento": 30000.0,
    "bonus": 300.0}, ...]; ver painel/metas.py."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="metas_mensais")
    ano = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    faixas = models.JSONField(default=list)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ano", "-mes"]
        verbose_name = "meta mensal"
        verbose_name_plural = "metas mensais"
        constraints = [models.UniqueConstraint(fields=["conta", "ano", "mes"], name="meta_mensal_unica")]

    def __str__(self):
        return f"{self.conta.email} {self.mes:02d}/{self.ano}"


class VendaItem(models.Model):
    """Cada produto vendido (um item de um pedido de uma conversão), guardado a cada
    sincronização. A API só alcança ~3 meses; guardando aqui o histórico fica com a
    conta por DIAS_DE_HISTORICO_VENDAS (ver resultados.py)."""

    PENDENTE, CONCLUIDO, CANCELADO = "pendente", "concluido", "cancelado"
    SITUACOES = [(PENDENTE, "Pendente"), (CONCLUIDO, "Concluído"), (CANCELADO, "Cancelado")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="vendas_itens")
    conversao_id = models.CharField(max_length=40)
    pedido_id = models.CharField(max_length=40)
    posicao = models.PositiveSmallIntegerField(default=0)  # ordem do item no pedido
    item_id = models.CharField(max_length=30, blank=True)
    nome = models.CharField(max_length=300, blank=True)
    imagem_url = models.CharField(max_length=500, blank=True)
    loja = models.CharField(max_length=200, blank=True)
    quantidade = models.PositiveIntegerField(default=1)
    preco = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # preço x quantidade
    comissao = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status_shopee = models.CharField(max_length=20, blank=True)  # orderStatus como veio
    situacao = models.CharField(max_length=10, choices=SITUACOES, default=PENDENTE)
    sub_id = models.CharField(max_length=120, default="sem_subid")
    comprado_em = models.DateTimeField()
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-comprado_em", "pedido_id", "posicao"]
        constraints = [
            models.UniqueConstraint(fields=["conta", "conversao_id", "pedido_id", "posicao"], name="venda_item_unico"),
        ]
        indexes = [models.Index(fields=["conta", "comprado_em"])]
        verbose_name = "item vendido"
        verbose_name_plural = "itens vendidos"

    def __str__(self):
        return f"{self.nome} ({self.pedido_id})"


class RegraSubId(models.Model):
    """Junta vários Sub IDs num nome só nas telas (ex: todo Sub ID que começa com
    "grupo" aparece como "Grupos de WhatsApp"). As regras são conferidas na ordem em que foram
    criadas; vale a primeira que casar. Não mexe nos dados guardados."""

    COMECA, NAO_COMECA = "comeca", "nao_comeca"
    CONTEM, NAO_CONTEM = "contem", "nao_contem"
    TERMINA, NAO_TERMINA = "termina", "nao_termina"
    OPERADORES = [
        (COMECA, "começa com"), (NAO_COMECA, "não começa com"),
        (CONTEM, "contém"), (NAO_CONTEM, "não contém"),
        (TERMINA, "termina com"), (NAO_TERMINA, "não termina com"),
    ]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="regras_sub_id")
    operador = models.CharField(max_length=12, choices=OPERADORES)
    texto = models.CharField(max_length=120)
    nome = models.CharField("nome do grupo", max_length=60)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "regra de Sub ID"
        verbose_name_plural = "regras de Sub ID"

    def __str__(self):
        return f'{self.get_operador_display()} "{self.texto}" -> {self.nome}'

    def casa(self, sub_id: str) -> bool:
        """Sem diferenciar maiúsculas de minúsculas."""
        valor, texto = sub_id.lower(), self.texto.lower()
        testes = {
            self.COMECA: valor.startswith(texto), self.CONTEM: texto in valor, self.TERMINA: valor.endswith(texto),
        }
        positivo = self.operador.replace("nao_", "")
        resultado = testes.get(positivo, False)
        return not resultado if self.operador.startswith("nao_") else resultado


class RelatorioEmail(models.Model):
    """Relatório diário por e-mail (resultados de ontem e do mês). Quem envia é o worker
    (comando sincronizar_painel), no horário escolhido, depois que os números de ontem chegam."""

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="relatorio_email")
    ativo = models.BooleanField("receber o relatório diário por e-mail", default=False)
    emails_extras = models.CharField(
        "enviar também para (opcional)", max_length=300, blank=True,
        help_text="Até 3 e-mails, separados por vírgula.",
    )
    hora = models.PositiveSmallIntegerField(
        "horário do envio", default=8, choices=[(h, f"{h:02d}:00") for h in range(7, 23)],
        help_text="Horário de Brasília. A Shopee costuma liberar os números de ontem entre 7h e 8h: se na hora "
                  "eles ainda não tiverem saído, você recebe um aviso e o relatório vai assim que saírem.",
    )
    ultimo_envio_dia = models.DateField(null=True, blank=True)
    # Os números de ontem ainda não tinham saído na Shopee: o aviso já foi neste dia e o worker
    # tenta de novo a partir de proxima_tentativa_em.
    aviso_dia = models.DateField(null=True, blank=True)
    proxima_tentativa_em = models.DateTimeField(null=True, blank=True)
    envio_agora_pedido_em = models.DateTimeField(null=True, blank=True)  # "Enviar e-mail agora"
    ultimo_erro = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "relatório por e-mail"
        verbose_name_plural = "relatórios por e-mail"

    def __str__(self):
        return f"{self.conta.email} - {'ligado' if self.ativo else 'desligado'}"

    def destinatarios(self) -> list[str]:
        extras = [e.strip() for e in (self.emails_extras or "").split(",") if e.strip()]
        return list(dict.fromkeys([self.conta.email, *extras]))
