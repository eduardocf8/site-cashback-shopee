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
    # O Instagram em que a automação foi criada: ela só responde quando esse Instagram está conectado.
    # Vazio: criada antes deste registro (vale para o Instagram que estiver conectado).
    ig_id = models.CharField(max_length=64, blank=True, db_index=True)
    ig_username = models.CharField(max_length=64, blank=True)
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
    # Premium: botões na DM, de 0 a 3 (o Instagram aceita até 3). O 1º abre o link acima; o 2º e o 3º têm
    # texto e link próprios em botoes_extras: [{"texto", "link", "link_afiliado"}]. Se o Instagram não
    # aceitar os botões, os links vão no texto.
    MAXIMO_BOTOES = 3
    botoes = models.PositiveSmallIntegerField(default=1)
    texto_botao = models.CharField(max_length=20, default="Ver produto", blank=True)
    botoes_extras = models.JSONField(default=list, blank=True)
    # Premium: Sub ID próprio. O link de afiliado é gerado de novo com ele (link_afiliado) e é esse que vai na DM.
    sub_id = models.CharField("Sub ID", max_length=50, blank=True)
    link_afiliado = models.URLField(max_length=600, blank=True)
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

    @property
    def e_anuncio(self) -> bool:
        """Presa a um anúncio (ver AnuncioVisto), e não a um post ou story do perfil."""
        if self.gatilho == self.COMENTARIO:
            return self.midia_id.startswith("post:")
        return self.gatilho == self.STORY and self.midia_id.startswith(("ad:", "post:", "story:"))


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
    # Passou do limite por hora do Instagram (post viralizando): espera na fila e sai na hora seguinte.
    na_fila = models.BooleanField(default=False, db_index=True)
    enviado_em = models.DateTimeField(null=True, blank=True, db_index=True)
    # Quem comentou (ou mandou DM) antes e foi achado pelo botão "Responder quem já comentou" (ver
    # anteriores.py): quando foi o comentário/a mensagem, que é de onde conta o prazo do Instagram.
    anterior = models.BooleanField(default=False)
    evento_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [models.UniqueConstraint(fields=["automacao", "evento_id"], name="disparo_unico_por_evento")]


class Repasse(models.Model):
    """Um pedido de "Responder quem já comentou" (ou quem já mandou DM) de uma automação: o worker busca
    no Instagram o que ainda está no prazo e põe na fila quem ainda não recebeu (ver anteriores.py)."""

    FILA, BUSCANDO, PRONTO, ERRO = "fila", "buscando", "pronto", "erro"
    ESTADOS = [(FILA, "Na fila"), (BUSCANDO, "Buscando"), (PRONTO, "Pronto"), (ERRO, "Erro")]

    automacao = models.ForeignKey(Automacao, on_delete=models.CASCADE, related_name="repasses")
    estado = models.CharField(max_length=10, choices=ESTADOS, default=FILA, db_index=True)
    encontrados = models.PositiveIntegerField(default=0)  # comentários/mensagens no prazo
    enfileirados = models.PositiveIntegerField(default=0)  # entraram na fila agora
    pulados = models.PositiveIntegerField(default=0)  # a pessoa já tinha recebido (ou já está na fila)
    sem_palavra = models.PositiveIntegerField(default=0)  # não escreveram uma das palavras
    de_outra = models.PositiveIntegerField(default=0)  # bateram com outra automação, que vem antes
    mensagem = models.CharField(max_length=300, blank=True)
    pedido_em = models.DateTimeField(auto_now_add=True)
    terminado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pedido_em"]


class AnuncioVisto(models.Model):
    """Um anúncio (ou story/post que não está no perfil) de onde já chegou resposta por DM ou comentário.

    Os anúncios de reels que também rodam nos stories não aparecem na lista de stories da conta: o
    Instagram só conta deles quando alguém responde. Cada resposta guarda aqui o que veio junto (o ID do
    anúncio, o reels de origem, o story de onde a pessoa respondeu) e a tela da automação lista isso na
    opção "Um anúncio". A `chave` é o que fica em Automacao.midia_id:
    - "ad:<id>" quando o Instagram mandou o ID do anúncio (o mais estável);
    - "post:<id>" quando só mandou o post/reels de origem;
    - "story:<id>" quando é uma resposta a story sem nada do anúncio (e o story não está no perfil).
    Nos comentários (origem "comentario"), a chave é "post:<id da mídia>": o reels subido direto no
    Gerenciador de Anúncios recebe comentário, mas não está na lista de posts do perfil."""

    MENSAGEM, COMENTARIO = "mensagem", "comentario"

    ig_id = models.CharField(max_length=64, db_index=True)
    origem = models.CharField(max_length=20, default=MENSAGEM)  # de onde veio: DM/resposta a story ou comentário
    chave = models.CharField(max_length=80)
    anuncio_id = models.CharField(max_length=64, blank=True)
    post_id = models.CharField(max_length=64, blank=True)
    story_id = models.CharField(max_length=64, blank=True, db_index=True)
    titulo = models.CharField(max_length=200, blank=True)
    imagem = models.URLField(max_length=1000, blank=True)
    # O story respondido é um story de verdade do perfil (aí não é anúncio e não aparece na lista).
    do_perfil = models.BooleanField(default=False)
    respostas = models.PositiveIntegerField(default=0)
    ultimo_texto = models.CharField(max_length=200, blank=True)
    bruto = models.JSONField("o que veio do anúncio (referral e reply_to)", default=dict, blank=True)
    # A última vez que o Appfiliado perguntou ao Instagram o tipo, a foto e a legenda da mídia, e o que ele
    # respondeu ("AD", "STORY"... ou o erro). A foto expira: a tela pergunta de novo de tempos em tempos.
    conferido_em = models.DateTimeField(null=True, blank=True)
    consulta = models.CharField("resposta do Instagram", max_length=300, blank=True)
    primeira_em = models.DateTimeField(auto_now_add=True)
    ultima_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ultima_em"]
        constraints = [models.UniqueConstraint(fields=["ig_id", "origem", "chave"], name="anuncio_visto_por_origem_e_chave")]

    def __str__(self):
        return self.titulo or self.chave


class AvisoRecebido(models.Model):
    """Registro dos avisos (webhook) que a Meta mandou, de qualquer conta: mostra na tela de teste se
    os avisos estão chegando. Fica só a última semana."""

    ig_id = models.CharField(max_length=64, db_index=True)
    campo = models.CharField(max_length=40)
    resumo = models.TextField(blank=True)
    # O aviso como veio (cortado): mostra no admin o que o Instagram manda de verdade,
    # por exemplo numa resposta a um anúncio de reels que também roda nos stories.
    bruto = models.JSONField(default=dict, blank=True)
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
    # O Instagram para onde vai (o conectado na hora de agendar). Se trocar a conta antes, não publica na outra.
    ig_id = models.CharField(max_length=64, blank=True)
    ig_username = models.CharField(max_length=64, blank=True)
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
