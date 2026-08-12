from django.db import models


class Banner(models.Model):
    ALINHAMENTO_ESQUERDA = "esquerda"
    ALINHAMENTO_DIREITA = "direita"
    ALINHAMENTO_CHOICES = [
        (ALINHAMENTO_ESQUERDA, "Esquerda"),
        (ALINHAMENTO_DIREITA, "Direita"),
    ]

    selo = models.CharField(
        max_length=60, blank=True, help_text="Etiqueta pequena acima do título (ex: MÊS DE INAUGURAÇÃO). Opcional."
    )
    texto = models.CharField(
        max_length=200,
        help_text="Título grande. Pode usar &lt;mark&gt;palavra&lt;/mark&gt; pra destacar uma palavra "
        "com fundo verde-limão (ex: Cashback em &lt;mark&gt;DOBRO&lt;/mark&gt;).",
    )
    subtexto = models.CharField(max_length=200, blank=True, help_text="Linha menor, opcional, abaixo do título.")
    alinhamento = models.CharField(
        max_length=10,
        choices=ALINHAMENTO_CHOICES,
        default=ALINHAMENTO_ESQUERDA,
        help_text="Só vale quando tem imagem: de que lado o texto aparece sobre a foto - escolha o lado "
        "onde a foto não tem o assunto principal (rosto, produto), pra não cobrir.",
    )
    imagem_estatica = models.CharField(
        max_length=200,
        blank=True,
        help_text="Caminho dentro de static/, ex: images/banners/inauguracao.jpg. "
        "Vazio = banner sem foto, com fundo em degradê da marca e texto centralizado.",
    )
    botao_texto = models.CharField(max_length=40, blank=True, help_text="Texto do botão principal. Vazio = sem botão.")
    botao_link = models.CharField(
        max_length=300, blank=True, help_text="Caminho interno (ex: /ofertas/) ou URL completa."
    )
    botao2_texto = models.CharField(
        max_length=40, blank=True, help_text="Texto do botão secundário (contorno, opcional)."
    )
    botao2_link = models.CharField(max_length=300, blank=True, help_text="Caminho interno ou URL completa.")
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0, help_text="Banners com número menor aparecem primeiro.")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "criado_em"]

    def __str__(self):
        return self.texto
