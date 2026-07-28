import uuid

from django.conf import settings
from django.db import models


class Click(models.Model):
    TIPO_PRODUTO = "produto"
    TIPO_HOME = "home"
    TIPO_CHOICES = [
        (TIPO_PRODUTO, "Produto específico"),
        (TIPO_HOME, "Página inicial da Shopee"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clicks")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    url_original = models.URLField("URL original da Shopee")
    link_gerado = models.URLField("Link de afiliado gerado")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def sub_id_usuario(self) -> str:
        return f"user{self.usuario_id}"

    def sub_id_click(self) -> str:
        return str(self.id)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario} - {self.criado_em:%d/%m/%Y}"
