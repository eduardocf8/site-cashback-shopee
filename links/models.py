import uuid

from django.conf import settings
from django.db import models


class Click(models.Model):
    TIPO_PRODUTO = "produto"
    TIPO_VITRINE = "vitrine"
    TIPO_HOME = "home"
    TIPO_STORY_DM = "story_dm"
    TIPO_CHOICES = [
        (TIPO_PRODUTO, "Link de produto convertido"),
        (TIPO_VITRINE, "Vitrine de ofertas"),
        (TIPO_HOME, "Página inicial da Shopee"),
        (TIPO_STORY_DM, "Link enviado por DM (resposta a story)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clicks")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    url_original = models.URLField("URL original da Shopee")
    item_id_alvo = models.BigIntegerField(
        "Item ID do produto clicado", null=True, blank=True,
        help_text="Preenchido quando dá pra identificar de cara qual produto gerou "
        "esse clique (link específico ou card da vitrine), sem seguir "
        "redirecionamento nenhum - usado só pra confirmar depois que a compra real é "
        "do mesmo produto, não pra garantir cashback de campanha nem nada do tipo. "
        "Fica vazio pra cliques na home ('Ir pra Shopee') e pra links que não dá pra "
        "identificar sem seguir redirecionamento (ver ROADMAP.md, Fase 41).",
    )
    link_gerado = models.URLField("Link de afiliado gerado")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def sub_id_usuario(self) -> str:
        return f"user{self.usuario_id}"

    def sub_id_click(self) -> str:
        # A API Shopee só aceita letras e números no subId (sem hífen/símbolo),
        # por isso usamos o UUID em formato hexadecimal puro (sem os traços).
        return self.id.hex

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario} - {self.criado_em:%d/%m/%Y}"
