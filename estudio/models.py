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


# --- Estúdio Instagram (painel do afiliado) ------------------------------------------------------
# Imagens ficam no banco (BinaryField), como no resto do painel: o disco do servidor não guarda arquivos.

TEMAS_AFILIADO = [("verde", "Verde"), ("laranja", "Laranja"), ("rosa", "Rosa"), ("azul", "Azul"), ("preto", "Preto"),
                  ("marca", "Minha marca")]
FONTES_AFILIADO = [("moderna", "Moderna"), ("geometrica", "Geométrica"), ("impacto", "Impacto"), ("elegante", "Elegante"),
                   ("serifa", "Serifada"), ("suave", "Suave")]


class PostInstagram(models.Model):
    """Post ou sequência de stories que o afiliado faz no Estúdio Instagram do painel."""

    RASCUNHO = "rascunho"
    ESTADOS = [(RASCUNHO, "Rascunho"), ("agendado", "Agendado"), ("publicado", "Publicado"), ("erro", "Erro ao publicar")]

    conta = models.ForeignKey("licencas.ContaAppfiliado", on_delete=models.CASCADE, related_name="posts_instagram")
    formato = models.CharField(max_length=20, choices=FORMATOS, default="retrato")
    tema = models.CharField(max_length=20, choices=TEMAS_AFILIADO, default="verde")
    nome = models.CharField(max_length=120, default="Novo post")
    slides = models.JSONField(default=list, blank=True)
    legenda = models.TextField(blank=True)
    # Produto da Shopee quando o post nasceu de um link: nome, preco, de, desconto, imagem, link (de afiliado).
    produto = models.JSONField(default=dict, blank=True)
    miniatura = models.BinaryField(null=True, blank=True)  # JPEG pequeno do primeiro slide
    estado = models.CharField(max_length=20, choices=ESTADOS, default=RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em"]
        verbose_name = "post do Estúdio Instagram"
        verbose_name_plural = "posts do Estúdio Instagram"

    def __str__(self):
        return self.nome


class MarcaAfiliado(models.Model):
    """"Minha marca": o @ (todos os planos) e a identidade que entra nos posts (Premium)."""

    conta = models.OneToOneField("licencas.ContaAppfiliado", on_delete=models.CASCADE, related_name="marca_instagram")
    nome = models.CharField("nome exibido", max_length=60, blank=True)
    arroba = models.CharField("@ do Instagram", max_length=31, blank=True)
    cor = models.CharField("cor principal", max_length=7, default="#1F3A2E")
    cor_destaque = models.CharField("cor de destaque", max_length=7, default="#F2C230")
    fonte = models.CharField(max_length=20, choices=FONTES_AFILIADO, default="moderna")
    logo = models.BinaryField(null=True, blank=True)  # PNG
    atualizada_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.arroba or self.nome or f"Marca da conta {self.conta_id}"


class ImagemAfiliado(models.Model):
    """Imagem enviada pelo afiliado: foto de produto (todos os planos) ou fundo de slide (Premium)."""

    conta = models.ForeignKey("licencas.ContaAppfiliado", on_delete=models.CASCADE, related_name="imagens_instagram")
    dados = models.BinaryField()
    tipo = models.CharField(max_length=20, default="image/jpeg")
    nome = models.CharField(max_length=120, blank=True)
    enviada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviada_em"]
