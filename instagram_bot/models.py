from django.db import models


class RegistroPublicacao(models.Model):
    TIPO_STORY = "story"
    TIPO_FEED = "feed"
    TIPO_CHOICES = [
        (TIPO_STORY, "Story"),
        (TIPO_FEED, "Post no feed"),
    ]

    CONTEUDO_OFERTA_DIARIA = "oferta_diaria"
    CONTEUDO_DICA = "dica"
    CONTEUDO_LEMBRETE = "lembrete"
    CONTEUDO_INSTITUCIONAL = "institucional"
    CONTEUDO_OFERTAS_SEMANA = "ofertas_semana"
    CONTEUDO_CHOICES = [
        (CONTEUDO_OFERTA_DIARIA, "Destaque de ofertas do dia"),
        (CONTEUDO_DICA, "Dica de economia"),
        (CONTEUDO_LEMBRETE, "Lembrete de cashback"),
        (CONTEUDO_INSTITUCIONAL, "Institucional"),
        (CONTEUDO_OFERTAS_SEMANA, "Melhores ofertas da semana"),
    ]

    STATUS_SIMULADO = "simulado"
    STATUS_PENDENTE_APROVACAO = "pendente_aprovacao"
    STATUS_PUBLICADO = "publicado"
    STATUS_REJEITADO = "rejeitado"
    STATUS_ERRO = "erro"
    STATUS_CHOICES = [
        (STATUS_SIMULADO, "Simulado (bot desligado)"),
        (STATUS_PENDENTE_APROVACAO, "Aguardando aprovação"),
        (STATUS_PUBLICADO, "Publicado"),
        (STATUS_REJEITADO, "Rejeitado"),
        (STATUS_ERRO, "Erro"),
    ]

    data = models.DateField("Data de referência", db_index=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    conteudo_tipo = models.CharField(max_length=20, choices=CONTEUDO_CHOICES)
    legenda = models.TextField(blank=True)
    imagem_url = models.URLField(blank=True)
    imagem_urls = models.TextField(
        blank=True,
        help_text="Uma URL por linha - só usado quando é carrossel (várias imagens). Nesse caso imagem_url fica vazio.",
    )
    instagram_media_id = models.CharField(max_length=64, blank=True)
    modo_simulacao = models.BooleanField(
        default=True, help_text="True quando o bot ainda estava desligado (INSTAGRAM_BOT_ATIVO=False)."
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SIMULADO, db_index=True)
    sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        simulado = " (simulação)" if self.modo_simulacao else ""
        return f"{self.data} - {self.get_tipo_display()}/{self.get_conteudo_tipo_display()} - {self.get_status_display()}{simulado}"
