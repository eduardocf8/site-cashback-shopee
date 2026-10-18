"""Bot de WhatsApp do Appfiliado rodando no servidor.

O painel (web) só lê e escreve nestas tabelas; quem conversa com o WhatsApp é o
worker (bot_whatsapp/gerenciador.py, rodando junto com o sincronizar_painel). A
sessão do WhatsApp em si (chaves de criptografia) fica nas tabelas whatsmeow_* que
a biblioteca cria no mesmo banco."""

from django.db import models

from licencas.models import ContaAppfiliado


class ConexaoWhatsApp(models.Model):
    DESCONECTADO = "desconectado"
    AGUARDANDO_QR = "aguardando_qr"
    CONECTADO = "conectado"
    RECONECTANDO = "reconectando"
    ESTADOS = [
        (DESCONECTADO, "Desconectado"),
        (AGUARDANDO_QR, "Esperando a leitura do QR Code"),
        (CONECTADO, "Conectado"),
        (RECONECTANDO, "Reconectando"),
    ]

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="whatsapp")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DESCONECTADO)
    qr_codigo = models.TextField(blank=True)
    qr_em = models.DateTimeField(null=True, blank=True)
    jid = models.TextField(blank=True, help_text="Aparelho conectado (JID em base64) - usado para retomar a sessão.")
    numero = models.CharField(max_length=32, blank=True)
    nome = models.CharField(max_length=120, blank=True)
    conectado_em = models.DateTimeField(null=True, blank=True)
    grupos = models.JSONField(default=list, blank=True)
    grupos_em = models.DateTimeField(null=True, blank=True)
    # Pedidos do painel para o worker (ele zera depois de atender).
    pedido_conectar = models.BooleanField(default=False)
    pedido_desconectar = models.BooleanField(default=False)
    pedido_grupos = models.BooleanField(default=False)
    erro = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conexão de WhatsApp"
        verbose_name_plural = "conexões de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} - {self.get_estado_display()}"

    @property
    def numero_formatado(self) -> str:
        n = self.numero
        if n.startswith("55") and len(n) in (12, 13):
            return f"+55 ({n[2:4]}) {n[4:-4]}-{n[-4:]}"
        return f"+{n}" if n else ""


class EnvioWhatsApp(models.Model):
    PENDENTE, ENVIADO, ERRO = "pendente", "enviado", "erro"
    ESTADOS = [(PENDENTE, "Na fila"), (ENVIADO, "Enviado"), (ERRO, "Erro")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="envios_whatsapp")
    destino = models.CharField(max_length=80, help_text='JID do grupo, ex: "120363...@g.us".')
    destino_nome = models.CharField(max_length=200, blank=True)
    texto = models.TextField(blank=True)
    imagem_url = models.URLField(max_length=1000, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDENTE)
    erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "envio de WhatsApp"
        verbose_name_plural = "envios de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} -> {self.destino_nome or self.destino} ({self.estado})"


class EventoWhatsApp(models.Model):
    """Histórico da conexão (conectou, caiu, reconectou...) - é o que mostra se a
    conexão pelo servidor está estável."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="eventos_whatsapp")
    tipo = models.CharField(max_length=30)
    detalhe = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "evento de WhatsApp"
        verbose_name_plural = "eventos de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} - {self.tipo}"
