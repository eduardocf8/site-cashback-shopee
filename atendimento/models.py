from django.db import models


class Conversa(models.Model):
    """Uma pessoa falando com o WhatsApp de vendas do Appfiliado."""

    IA = "ia"
    HUMANO = "humano"
    ESTADOS = [(IA, "Agente respondendo"), (HUMANO, "Com você (agente pausado)")]

    chat = models.CharField("chat", max_length=80, unique=True)  # ex: 5545999990000@s.whatsapp.net ou 123@lid
    telefone = models.CharField(max_length=20, blank=True)
    nome = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=IA)
    motivo_humano = models.CharField("por que chamou você", max_length=500, blank=True)
    humano_desde = models.DateTimeField(null=True, blank=True)
    ultima_recebida_em = models.DateTimeField(null=True, blank=True)
    respostas_no_dia = models.PositiveIntegerField(default=0)
    dia_das_respostas = models.DateField(null=True, blank=True)
    # Até quando as suas respostas nesta conversa já viraram (ou não) sugestão de resposta aprendida.
    aprendizado_em = models.DateTimeField(null=True, blank=True)
    # Assinante que vinculou este número no painel (Configurações) para pedir os resultados por aqui.
    conta = models.ForeignKey("licencas.ContaAppfiliado", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="conversas_whatsapp")
    vinculada_em = models.DateTimeField(null=True, blank=True)
    # Comandos (resultados, metas...) e tentativas de vínculo do dia: corta abuso e chute de código.
    comandos_no_dia = models.PositiveIntegerField(default=0)
    tentativas_vinculo = models.PositiveIntegerField(default=0)
    dia_dos_comandos = models.DateField(null=True, blank=True)
    # Pediu a comissão validada de hoje e espera a busca na Shopee terminar (ver comandos.validadas_prontas).
    validada_pedida_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ultima_recebida_em"]

    def __str__(self):
        return self.nome or self.telefone or self.chat

    @property
    def link_whatsapp(self) -> str:
        return f"https://wa.me/{self.telefone}" if self.telefone else ""


class Mensagem(models.Model):
    CLIENTE = "cliente"
    AGENTE = "agente"
    VOCE = "voce"
    AUTORES = [(CLIENTE, "Cliente"), (AGENTE, "Agente (IA)"), (VOCE, "Você (pelo celular)")]

    conversa = models.ForeignKey(Conversa, on_delete=models.CASCADE, related_name="mensagens")
    autor = models.CharField(max_length=10, choices=AUTORES)
    texto = models.TextField()
    whatsapp_id = models.CharField(max_length=120, blank=True, db_index=True)
    respondida = models.BooleanField(default=False)  # mensagem do cliente que o agente já tratou
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criada_em", "id"]

    def __str__(self):
        return f"{self.get_autor_display()}: {self.texto[:60]}"


class RespostaAprendida(models.Model):
    """Pergunta e resposta que o agente aprendeu com você (ver atendimento/aprendizado.py). Só as
    aprovadas entram no que ele sabe, e valem pra todos os clientes."""

    SUGERIDA, APROVADA, DESCARTADA = "sugerida", "aprovada", "descartada"
    ESTADOS = [(SUGERIDA, "Sugerida (esperando você)"), (APROVADA, "Aprovada (o agente usa)"),
               (DESCARTADA, "Descartada")]

    pergunta = models.TextField()
    resposta = models.TextField()
    estado = models.CharField(max_length=12, choices=ESTADOS, default=SUGERIDA, db_index=True)
    conversa = models.ForeignKey(Conversa, null=True, blank=True, on_delete=models.SET_NULL, related_name="aprendidas",
                                 help_text="De onde veio (vazio = criada por você no admin).")
    whatsapp_id = models.CharField(max_length=120, blank=True, db_index=True,
                                   help_text="A mensagem com a sugestão no seu WhatsApp (para saber a que você respondeu).")
    enviada_em = models.DateTimeField(null=True, blank=True)
    decidida_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "resposta aprendida"
        verbose_name_plural = "respostas aprendidas"

    def __str__(self):
        return self.pergunta[:80]


class CodigoVinculo(models.Model):
    """Código que o assinante gera no painel e manda ("VINCULAR 123456") pro WhatsApp do Appfiliado,
    para ligar o número dele à conta. Vale por pouco tempo e some quando é usado."""

    conta = models.OneToOneField("licencas.ContaAppfiliado", on_delete=models.CASCADE, related_name="codigo_whatsapp")
    codigo = models.CharField(max_length=6, db_index=True)
    criado_em = models.DateTimeField()

    class Meta:
        verbose_name = "código de vínculo do WhatsApp"
        verbose_name_plural = "códigos de vínculo do WhatsApp"

    def __str__(self):
        return f"{self.conta} ({self.criado_em:%d/%m %H:%M})"
