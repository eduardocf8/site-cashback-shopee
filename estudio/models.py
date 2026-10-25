from django.conf import settings
from django.db import models

MARCAS = [("appfiliado", "Appfiliado"), ("cashb", "cash-b")]
FORMATOS = [("quadrado", "Post 1:1"), ("retrato", "Post 4:5"), ("story", "Story 9:16")]


class Projeto(models.Model):
    """Um post (com um ou mais slides) ou uma sequência de stories feita no estúdio."""

    marca = models.CharField(max_length=20, choices=MARCAS)
    formato = models.CharField(max_length=20, choices=FORMATOS)
    nome = models.CharField(max_length=120, default="Sem nome")
    slides = models.JSONField(default=list, blank=True)
    legenda = models.TextField(blank=True)
    miniatura = models.ImageField(upload_to="estudio/miniaturas/", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-atualizado_em"]
        verbose_name = "post do estúdio"
        verbose_name_plural = "posts do estúdio"

    def __str__(self):
        return self.nome


class _DaMarca(models.Manager):
    def __init__(self, marca):
        super().__init__()
        self.marca = marca

    def get_queryset(self):
        return super().get_queryset().filter(marca=self.marca)


class ProjetoAppfiliado(Projeto):
    objects = _DaMarca("appfiliado")

    class Meta:
        proxy = True
        verbose_name = "post do Appfiliado"
        verbose_name_plural = "Estúdio de posts do Appfiliado"


class ProjetoCashb(Projeto):
    objects = _DaMarca("cashb")

    class Meta:
        proxy = True
        verbose_name = "post da cash-b"
        verbose_name_plural = "Estúdio de posts da cash-b"


class ImagemEstudio(models.Model):
    """Imagem enviada para usar como fundo de slide."""

    marca = models.CharField(max_length=20, choices=MARCAS)
    arquivo = models.ImageField(upload_to="estudio/imagens/%Y/%m/")
    nome = models.CharField(max_length=120, blank=True)
    enviada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviada_em"]
        verbose_name = "imagem do estúdio"
        verbose_name_plural = "imagens do estúdio"

    def __str__(self):
        return self.nome or self.arquivo.name
