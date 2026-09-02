import unicodedata

from django.conf import settings
from django.db import models


def _normalizar(texto: str) -> str:
    """minúsculas e sem acento, pra casar palavra-chave ignorando maiúscula/acento."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


class ContaInstagramConectada(models.Model):
    """Uma conta do Instagram conectada por um usuário do app (cada usuário só vê e
    gerencia as próprias contas - ver automacao_instagram/views.py)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contas_instagram"
    )
    nome_exibicao = models.CharField(
        "Nome de exibição", max_length=100, help_text="Ex: @usecashb - só pra identificar a conta nas telas."
    )
    instagram_business_account_id = models.CharField(
        "ID da conta comercial do Instagram",
        max_length=64,
        help_text="ID numérico da conta (não é o @usuário) - aparece no Meta Business Suite, em "
        "Configurações > Contas > Instagram, ou é retornado pela Graph API.",
    )
    access_token = models.CharField(
        "Access token",
        max_length=512,
        help_text="Token de longa duração gerado no painel da Meta pra essa conta.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conta do Instagram conectada"
        verbose_name_plural = "Contas do Instagram conectadas"
        ordering = ["nome_exibicao"]

    def __str__(self):
        return self.nome_exibicao


class AutomacaoComentario(models.Model):
    """Uma automação: vinculada a um post específico, dispara quando um comentário
    bate com alguma das palavras-chave cadastradas."""

    conta = models.ForeignKey(ContaInstagramConectada, on_delete=models.CASCADE, related_name="automacoes")
    nome = models.CharField("Nome da automação", max_length=100, help_text="Só pra identificar, ex: Sorteio de agosto")
    instagram_media_id = models.CharField("ID do post no Instagram", max_length=64)
    link_post = models.URLField("Link do post", blank=True)
    palavras_chave = models.TextField(
        "Palavras-chave", help_text="Uma palavra-chave por linha. Não diferencia maiúscula/minúscula nem acento."
    )
    responder_comentario = models.BooleanField("Responder o comentário publicamente", default=False)
    texto_resposta = models.TextField("Texto da resposta pública", blank=True)
    enviar_dm = models.BooleanField("Enviar mensagem direta (DM)", default=False)
    texto_dm = models.TextField("Texto da DM", blank=True)
    ativa = models.BooleanField("Ativa", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Automação de comentário"
        verbose_name_plural = "Automações de comentário"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome} ({self.conta.nome_exibicao})"

    def lista_palavras_chave(self) -> list[str]:
        return [linha.strip() for linha in self.palavras_chave.splitlines() if linha.strip()]

    def encontra_palavra_chave(self, texto_comentario: str) -> str | None:
        texto_normalizado = _normalizar(texto_comentario or "")
        for palavra in self.lista_palavras_chave():
            if _normalizar(palavra) in texto_normalizado:
                return palavra
        return None


class AutomacaoStory(models.Model):
    """Uma automação de resposta a story: vinculada a UM story específico (escolhido
    na hora de criar, igual AutomacaoComentario escolhe um post) - diferente de
    comentário, story não tem palavra-chave: qualquer resposta (ou reação) a esse
    story dispara. Ver automacao_instagram/webhook.py."""

    MODO_LINK_PRODUTO = "link_produto"
    MODO_PERSONALIZADA = "personalizada"
    MODO_CHOICES = [
        (MODO_LINK_PRODUTO, "Link do produto do story (detectado automaticamente)"),
        (MODO_PERSONALIZADA, "Mensagem personalizada"),
    ]

    conta = models.ForeignKey(ContaInstagramConectada, on_delete=models.CASCADE, related_name="automacoes_story")
    nome = models.CharField("Nome da automação", max_length=100, help_text="Só pra identificar, ex: Fone bluetooth 02/09")
    instagram_story_media_id = models.CharField("ID do story no Instagram", max_length=64)
    story_permalink = models.URLField("Link do story", blank=True)
    modo_resposta = models.CharField(
        "O que enviar por DM", max_length=20, choices=MODO_CHOICES, default=MODO_PERSONALIZADA,
    )
    texto_personalizado = models.TextField(
        "Mensagem personalizada", blank=True,
        help_text="Usado quando o modo é \"Mensagem personalizada\" - ignorado no modo \"Link do produto\".",
    )
    ativa = models.BooleanField("Ativa", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Automação de story"
        verbose_name_plural = "Automações de story"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.nome} ({self.conta.nome_exibicao})"


class RespostaStoryProcessada(models.Model):
    """Uma resposta/reação a um story com automação ativa - histórico e base dos
    indicadores, mesmo papel que ComentarioProcessado tem pra automação de post."""

    automacao = models.ForeignKey(AutomacaoStory, on_delete=models.CASCADE, related_name="respostas")
    instagram_autor_id = models.CharField(max_length=64, blank=True)
    autor_username = models.CharField(max_length=150, blank=True)
    texto_recebido = models.TextField(blank=True)
    dm_enviada = models.BooleanField(default=False)
    dm_erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resposta a story processada"
        verbose_name_plural = "Respostas a stories processadas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"@{self.autor_username or '?'}: {self.texto_recebido[:40]}"


class ComentarioProcessado(models.Model):
    """Um comentário que bateu com a palavra-chave de uma automação - registro de
    histórico e base dos indicadores (contagens agregadas por automação)."""

    automacao = models.ForeignKey(AutomacaoComentario, on_delete=models.CASCADE, related_name="comentarios")
    instagram_comment_id = models.CharField(max_length=64, unique=True)
    instagram_autor_id = models.CharField(max_length=64, blank=True)
    autor_username = models.CharField(max_length=150, blank=True)
    texto_comentario = models.TextField(blank=True)
    palavra_chave_encontrada = models.CharField(max_length=100, blank=True)
    resposta_publica_enviada = models.BooleanField(default=False)
    resposta_publica_erro = models.TextField(blank=True)
    dm_enviada = models.BooleanField(default=False)
    dm_erro = models.TextField(blank=True)
    dm_respondida = models.BooleanField(default=False)
    dm_respondida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentário processado"
        verbose_name_plural = "Comentários processados"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"@{self.autor_username or '?'}: {self.texto_comentario[:40]}"
