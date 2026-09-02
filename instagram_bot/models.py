from datetime import date

from django.db import models


class EstadoTokenInstagram(models.Model):
    """Uma linha só (singleton) - controla o lembrete de renovação do
    INSTAGRAM_ACCESS_TOKEN, que dura 60 dias e precisa ser renovado à mão (ver
    marketing/instagram/README.md, seção "Renovação do token de acesso")."""

    renovado_em = models.DateField(
        default=date.today,
        help_text="Data em que o INSTAGRAM_ACCESS_TOKEN foi gerado/renovado pela última "
        "vez. Atualize sempre que trocar o token no Render (ou use a ação "
        "\"Marcar token como renovado hoje\" aqui no Admin).",
    )
    ultimo_lembrete_em = models.DateField(
        null=True, blank=True, help_text="Data do último e-mail de lembrete enviado (evita mandar um por dia)."
    )

    class Meta:
        verbose_name = "Estado do token do Instagram"
        verbose_name_plural = "Estado do token do Instagram"

    def __str__(self):
        return f"Token renovado em {self.renovado_em:%d/%m/%Y}"


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
    CONTEUDO_COMBO_DIARIO = "combo_diario"
    CONTEUDO_CHOICES = [
        (CONTEUDO_OFERTA_DIARIA, "Destaque de ofertas do dia"),
        (CONTEUDO_DICA, "Dica de economia"),
        (CONTEUDO_LEMBRETE, "Lembrete de cashback"),
        (CONTEUDO_INSTITUCIONAL, "Institucional"),
        (CONTEUDO_OFERTAS_SEMANA, "Melhores ofertas da semana"),
        # Sem o "(3 stories)" que tinha antes: o assunto do e-mail de aprovação já traz
        # a posição ("1/3"), e as duas informações juntas ficavam redundantes.
        (CONTEUDO_COMBO_DIARIO, "Combo do dia"),
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
    oferta_categoria_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Só preenchido em stories de oferta - usado pra não repetir categoria no mesmo dia "
        "(ver instagram_bot/services.py, publicar_story_oferta_do_momento).",
    )
    oferta_item_id = models.BigIntegerField(null=True, blank=True)
    oferta_nome = models.CharField(
        max_length=255, blank=True,
        help_text="Nome do produto no momento da publicação - usado pra não repetir o mesmo produto "
        "(vindo de lojas diferentes) no mesmo dia.",
    )
    link_produto_original = models.URLField(
        blank=True,
        help_text="Link do produto na Shopee (product_link) no momento da publicação - só preenchido em "
        "stories de oferta. Guardado aqui (e não só na Oferta) porque o catálogo sincronizado é "
        "apagado/recriado todo dia (pk muda) e uma OfertaManual/OfertaDestaqueManual pode ser "
        "editada ou removida depois - sem isso, o link enviado por DM quando alguém responde ao "
        "story (ver webhook.py) quebraria fora da hora. Ver instagram_bot/views.py, ir_para_story_de_oferta.",
    )
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
