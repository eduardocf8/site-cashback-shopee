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
