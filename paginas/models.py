from django.db import models


class Banner(models.Model):
    texto = models.CharField(max_length=200, help_text="Título grande, sobre a imagem.")
    subtexto = models.CharField(max_length=200, blank=True, help_text="Linha menor, opcional, abaixo do título.")
    imagem_estatica = models.CharField(
        max_length=200,
        blank=True,
        help_text="Caminho dentro de static/, ex: images/banners/inauguracao.jpg. "
        "Vazio = mostra só o degradê de fundo, sem foto.",
    )
    link = models.CharField(
        max_length=300,
        blank=True,
        help_text="Opcional. Caminho interno (ex: /ofertas/) ou URL completa. Vazio = banner não é clicável.",
    )
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0, help_text="Banners com número menor aparecem primeiro.")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "criado_em"]

    def __str__(self):
        return self.texto
