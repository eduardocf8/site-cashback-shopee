"""Instagram dos afiliados do Appfiliado: a conta conectada (Login do Instagram para empresas) e as
automações de resposta (comentário, resposta a story e DM).

É diferente do app automacao_instagram, que é a automação das contas da cash-b (login próprio,
token colado à mão). Os dois recebem os avisos da Meta pelo mesmo webhook: cada aviso vem com o ID
da conta do Instagram, e é por ele que se sabe de quem é (ver webhook.py)."""

from django.db import models

from licencas.models import ContaAppfiliado


class ContaInstagram(models.Model):
    """O Instagram profissional que o afiliado conectou. O token fica cifrado (painel/cripto.py)."""

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="instagram")
    # ID da conta profissional: é o "entry.id" dos avisos do webhook e o dono das mensagens.
    ig_id = models.CharField("ID da conta no Instagram", max_length=64, unique=True)
    # ID do usuário "por app" (vem no login e no aviso de "tirou o app"); é outro número.
    app_user_id = models.CharField(max_length=64, blank=True, db_index=True)
    username = models.CharField(max_length=64)
    nome = models.CharField(max_length=150, blank=True)
    foto = models.URLField(max_length=1000, blank=True)
    token_cifrado = models.TextField()
    token_expira_em = models.DateTimeField(null=True, blank=True)
    token_renovado_em = models.DateTimeField(null=True, blank=True)
    permissoes = models.CharField(max_length=500, blank=True)
    avisos_ligados = models.BooleanField("recebe os avisos (webhook)", default=False)
    erro = models.CharField("último erro", max_length=300, blank=True)
    conectada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Instagram conectado"
        verbose_name_plural = "Instagrams conectados"

    def __str__(self):
        return f"@{self.username}"

    @property
    def token(self) -> str:
        from painel import cripto

        return cripto.decifrar(self.token_cifrado)


class Automacao(models.Model):
    COMENTARIO, STORY, DIRETO = "comentario", "story", "direto"
    GATILHOS = [
        (COMENTARIO, "Comentou no post"),
        (STORY, "Respondeu o story"),
        (DIRETO, "Mandou DM"),
    ]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="automacoes_instagram")
    nome = models.CharField(max_length=100)
    gatilho = models.CharField(max_length=20, choices=GATILHOS, default=COMENTARIO)
    # Post ou story escolhido. Vazio: vale para todos os posts (ou todos os stories).
    midia_id = models.CharField(max_length=64, blank=True)
    midia_link = models.URLField(max_length=600, blank=True)
    midia_imagem = models.URLField(max_length=1000, blank=True)
    midia_legenda = models.CharField(max_length=200, blank=True)
    # Uma por linha (ou separadas por vírgula). Vazio: qualquer comentário ou resposta (na DM, nunca vazio).
    palavras = models.TextField(blank=True)
    responder_comentario = models.BooleanField(default=True)
    respostas = models.TextField("respostas públicas", blank=True, help_text="Uma por linha. Sai uma delas, sorteada.")
    enviar_dm = models.BooleanField(default=True)
    texto_dm = models.TextField(blank=True)
    link = models.URLField(max_length=600, blank=True)
    ativa = models.BooleanField(default=True)
    # O post do Estúdio que deu origem (atalho "Criar automação" no editor).
    post_estudio = models.ForeignKey("estudio.PostInstagram", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "automação de Instagram"
        verbose_name_plural = "automações de Instagram"

    def __str__(self):
        return self.nome


class Disparo(models.Model):
    """Cada vez que uma automação respondeu alguém (ou tentou). Também evita responder duas vezes."""

    automacao = models.ForeignKey(Automacao, on_delete=models.CASCADE, related_name="disparos")
    # ID do comentário ou da mensagem: a Meta pode mandar o mesmo aviso mais de uma vez.
    evento_id = models.CharField(max_length=200)
    autor_id = models.CharField(max_length=64, blank=True)
    autor_username = models.CharField(max_length=64, blank=True)
    texto = models.TextField(blank=True)
    resposta_ok = models.BooleanField(default=False)
    dm_ok = models.BooleanField(default=False)
    erro = models.CharField(max_length=400, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [models.UniqueConstraint(fields=["automacao", "evento_id"], name="disparo_unico_por_evento")]


class AvisoRecebido(models.Model):
    """Registro dos avisos (webhook) que a Meta mandou, de qualquer conta: mostra na tela de teste se
    os avisos estão chegando. Fica só a última semana."""

    ig_id = models.CharField(max_length=64, db_index=True)
    campo = models.CharField(max_length=40)
    resumo = models.TextField(blank=True)
    recebido_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-recebido_em"]


class Publicacao(models.Model):
    """Um post do Estúdio mandado para o Instagram: agora ou num horário marcado.

    As imagens (JPEG, já no tamanho final) vêm do navegador e ficam aqui até a publicação; a Meta
    baixa cada uma por um endereço público e secreto (ImagemPublicacao.token). Quem publica é o
    worker do painel (instagram_painel/publicar.py)."""

    FEED, STORY = "feed", "story"
    TIPOS = [(FEED, "Post no feed"), (STORY, "Stories")]
    PENDENTE, PUBLICANDO, PUBLICADA, ERRO, CANCELADA = "pendente", "publicando", "publicada", "erro", "cancelada"
    ESTADOS = [(PENDENTE, "Agendada"), (PUBLICANDO, "Publicando"), (PUBLICADA, "Publicada"),
               (ERRO, "Não publicada"), (CANCELADA, "Cancelada")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="publicacoes_instagram")
    post = models.ForeignKey("estudio.PostInstagram", null=True, blank=True, on_delete=models.SET_NULL, related_name="publicacoes")
    nome = models.CharField(max_length=120)
    tipo = models.CharField(max_length=10, choices=TIPOS, default=FEED)
    legenda = models.TextField(blank=True)
    agendada_para = models.DateTimeField(db_index=True)
    agora = models.BooleanField("pediu para publicar na hora", default=False)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=PENDENTE, db_index=True)
    tentativas = models.PositiveSmallIntegerField(default=0)
    iniciada_em = models.DateTimeField(null=True, blank=True)
    publicada_em = models.DateTimeField(null=True, blank=True)
    # IDs das mídias já publicadas (nos stories, um por story: se cair no meio, não repete os que já foram).
    midias = models.JSONField(default=list, blank=True)
    permalink = models.URLField(max_length=600, blank=True)
    erro = models.CharField(max_length=400, blank=True)
    miniatura = models.BinaryField(null=True, blank=True)  # JPEG pequeno da primeira imagem
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-agendada_para"]
        verbose_name = "publicação no Instagram"
        verbose_name_plural = "publicações no Instagram"

    def __str__(self):
        return f"{self.nome} ({self.get_estado_display()})"

    @property
    def ativa(self) -> bool:
        return self.estado in (self.PENDENTE, self.PUBLICANDO)


class ImagemPublicacao(models.Model):
    publicacao = models.ForeignKey(Publicacao, on_delete=models.CASCADE, related_name="imagens")
    ordem = models.PositiveSmallIntegerField(default=0)
    dados = models.BinaryField()
    # Parte do endereço público que a Meta baixa: não dá para adivinhar e some depois de publicar.
    token = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["ordem"]
