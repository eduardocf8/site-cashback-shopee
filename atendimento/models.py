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
