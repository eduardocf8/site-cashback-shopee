"""Bot de WhatsApp do Appfiliado rodando no servidor.

O painel (web) só lê e escreve nestas tabelas; quem conversa com o WhatsApp é o
worker (bot_whatsapp/gerenciador.py, rodando junto com o sincronizar_painel). A
sessão do WhatsApp em si (chaves de criptografia) fica nas tabelas whatsmeow_* que
a biblioteca cria no mesmo banco."""

from datetime import time

from django.db import models

from licencas.models import ContaAppfiliado


class ConexaoWhatsApp(models.Model):
    DESCONECTADO = "desconectado"
    AGUARDANDO_QR = "aguardando_qr"
    CONECTADO = "conectado"
    RECONECTANDO = "reconectando"
    ESTADOS = [
        (DESCONECTADO, "Desconectado"),
        (AGUARDANDO_QR, "Esperando a leitura do QR Code"),
        (CONECTADO, "Conectado"),
        (RECONECTANDO, "Reconectando"),
    ]

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="whatsapp")
    estado = models.CharField(max_length=20, choices=ESTADOS, default=DESCONECTADO)
    qr_codigo = models.TextField(blank=True)
    qr_em = models.DateTimeField(null=True, blank=True)
    jid = models.TextField(blank=True, help_text="Aparelho conectado (JID em base64) - usado para retomar a sessão.")
    numero = models.CharField(max_length=32, blank=True)
    nome = models.CharField(max_length=120, blank=True)
    conectado_em = models.DateTimeField(null=True, blank=True)
    grupos = models.JSONField(default=list, blank=True)
    grupos_em = models.DateTimeField(null=True, blank=True)
    # Pedidos do painel para o worker (ele zera depois de atender).
    pedido_conectar = models.BooleanField(default=False)
    pedido_desconectar = models.BooleanField(default=False)
    pedido_grupos = models.BooleanField(default=False)
    erro = models.TextField(blank=True)
    # Bot parado sem a pessoa ter pedido (ver bot_whatsapp/avisos_de_queda.py): desde quando e por
    # quê ("deslogou": o WhatsApp tirou o aparelho, precisa do QR Code; "caiu": não voltou sozinho).
    # Volta a vazio quando conecta de novo ou quando a pessoa desconecta pelo painel.
    PARADO_DESLOGOU, PARADO_CAIU = "deslogou", "caiu"
    parado_desde = models.DateTimeField(null=True, blank=True)
    parado_motivo = models.CharField(max_length=10, blank=True)
    parado_avisos = models.PositiveSmallIntegerField(default=0)
    parado_avisado_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conexão de WhatsApp"
        verbose_name_plural = "conexões de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} - {self.get_estado_display()}"

    @property
    def numero_formatado(self) -> str:
        n = self.numero
        if n.startswith("55") and len(n) in (12, 13):
            return f"+55 ({n[2:4]}) {n[4:-4]}-{n[-4:]}"
        return f"+{n}" if n else ""


class EnvioWhatsApp(models.Model):
    PENDENTE, ENVIADO, ERRO, SIMULADO = "pendente", "enviado", "erro", "simulado"
    # Simulado: o bot fez tudo (escolheu o produto, gerou o link, montou o texto), mas o
    # modo simulação estava ligado - não vai para o WhatsApp.
    ESTADOS = [(PENDENTE, "Na fila"), (ENVIADO, "Enviado"), (ERRO, "Erro"), (SIMULADO, "Simulado")]
    TESTE, OFERTA, CAMPANHA, ALERTA, MENSAGEM = "teste", "oferta", "campanha", "alerta", "mensagem"
    # CAMPANHA: a página da campanha da Shopee, mandada a cada N ofertas no modo campanha
    # (não conta no limite de ofertas por dia nem no "não repetir").
    # ALERTA: produto acompanhado que baixou de preço (alerta de preço), postado nos grupos.
    # MENSAGEM: mensagem avulsa escrita pela pessoa (aba Mensagens), agora ou agendada.
    ORIGENS = [(TESTE, "Mensagem de teste"), (OFERTA, "Oferta automática"), (CAMPANHA, "Página da campanha"),
               (ALERTA, "Alerta de preço"), (MENSAGEM, "Mensagem avulsa")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="envios_whatsapp")
    destino = models.CharField(max_length=80, help_text='JID do grupo, ex: "120363...@g.us".')
    destino_nome = models.CharField(max_length=200, blank=True)
    texto = models.TextField(blank=True)
    imagem_url = models.URLField(max_length=1000, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDENTE)
    erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    # Ofertas automáticas: qual produto foi para qual grupo (não repetir, limite diário).
    origem = models.CharField(max_length=10, choices=ORIGENS, default=TESTE)
    item_id = models.CharField(max_length=40, blank=True, db_index=True)
    produto = models.CharField(max_length=300, blank=True)
    link_afiliado = models.URLField(max_length=500, blank=True)
    # Foto baixada da mensagem copiada (arquivo temporário no worker).
    imagem_arquivo = models.CharField(max_length=300, blank=True)
    revisado_ia = models.BooleanField(default=False)
    # "foto" (foto com o texto; no canal, prévia pequena) ou "previa" (cartão grande do link).
    formato = models.CharField(max_length=10, default="foto")
    ia_motivo = models.CharField(max_length=300, blank=True, help_text="Por que a IA não revisou (com a IA ligada).")
    # Mensagem avulsa: de onde veio (a foto sai dela) e qual disparo foi (um envio por grupo).
    mensagem = models.ForeignKey("MensagemAvulsa", null=True, blank=True, on_delete=models.SET_NULL, related_name="envios")
    disparo_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "envio de WhatsApp"
        verbose_name_plural = "envios de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} -> {self.destino_nome or self.destino} ({self.estado})"


class EventoWhatsApp(models.Model):
    """Histórico da conexão (conectou, caiu, reconectou...) - é o que mostra se a
    conexão pelo servidor está estável."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="eventos_whatsapp")
    tipo = models.CharField(max_length=30)
    detalhe = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "evento de WhatsApp"
        verbose_name_plural = "eventos de WhatsApp"

    def __str__(self):
        return f"{self.conta.email} - {self.tipo}"


def _todos_os_dias():
    return [0, 1, 2, 3, 4, 5, 6]


class ConfiguracaoOfertas(models.Model):
    """Ofertas automáticas buscadas na API da Shopee e enviadas nos grupos (mesmos
    filtros do app de Windows). Quem executa é o motor em bot_whatsapp/ofertas.py."""

    BUSCA_GERAL, BUSCA_PALAVRA, BUSCA_LOJA, BUSCA_CATEGORIA = "geral", "palavra_chave", "loja", "categoria"
    TIPOS_BUSCA = [
        (BUSCA_GERAL, "Ofertas em geral"),
        (BUSCA_PALAVRA, "Palavra-chave"),
        (BUSCA_LOJA, "Uma loja"),
        (BUSCA_CATEGORIA, "Categorias"),
    ]
    ORDENACOES = [
        ("mais_vendidos", "Mais vendidos"),
        ("maior_comissao", "Maior comissão"),
        ("maior_desconto", "Maior desconto"),
    ]

    MODO_SHOPEE, MODO_COPIAR = "shopee", "copiar"
    MODOS = [(MODO_SHOPEE, "Buscar na Shopee"), (MODO_COPIAR, "Copiar de grupos e canais")]
    # Buscando na Shopee: as mesmas ofertas pra todos os grupos ou cada nicho com os seus grupos
    # (Premium). Copiando de grupos, vale sempre o envio pra todos.
    ENVIO_TODOS, ENVIO_NICHO = "todos", "nicho"
    ENVIOS = [(ENVIO_TODOS, "Mesmas ofertas para todos"), (ENVIO_NICHO, "Por nicho")]

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="ofertas_config")
    ativo = models.BooleanField(default=False)
    modo = models.CharField(max_length=10, choices=MODOS, default=MODO_SHOPEE)
    # Modo copiar: grupos/canais de onde vêm as ofertas ([{"jid": ..., "nome": ...}]).
    origens = models.JSONField(default=list, blank=True)

    tipo_busca = models.CharField(max_length=20, choices=TIPOS_BUSCA, default=BUSCA_GERAL)
    palavra_chave = models.CharField(max_length=120, blank=True)
    loja = models.CharField(max_length=300, blank=True, help_text="Link da loja na Shopee ou o número dela.")
    categorias = models.JSONField(default=list, blank=True)
    ordenacao = models.CharField(max_length=20, choices=ORDENACOES, default="mais_vendidos")

    comissao_minima = models.PositiveSmallIntegerField(default=0)
    desconto_minimo = models.PositiveSmallIntegerField(default=0)
    preco_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preco_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vendas_minimas = models.PositiveIntegerField(default=0)
    avaliacao_minima = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    cupom = models.CharField(max_length=120, blank=True)
    sub_ids = models.CharField(max_length=300, blank=True, help_text="Até 5, separados por vírgula. Só letras e números.")
    # Sub ID próprio de cada grupo ({jid: "a, b"}); grupo sem um próprio usa o
    # sub_ids (padrão). Guarda também os de grupos desmarcados, para não perder o
    # que foi digitado.
    sub_ids_por_grupo = models.JSONField(default=dict, blank=True)

    grupos = models.JSONField(default=list, blank=True, help_text='[{"jid": "...@g.us", "nome": "..."}]')
    modo_envio = models.CharField("como distribuir", max_length=10, choices=ENVIOS, default=ENVIO_TODOS)
    # Envio por nicho: o nicho de cada grupo (id da categoria principal da Shopee), {"jid": "100631"}. Grupo fora daqui = "todos"
    # (ofertas em geral). Cada nicho em uso busca as próprias ofertas e manda só pros grupos dele.
    nichos = models.JSONField(default=dict, blank=True)
    # Onde a busca de cada nicho parou: {"100631": {"pagina": 3, "em": "2026-10-24T10:00:00+00:00"}}
    paginas_nichos = models.JSONField(default=dict, blank=True)
    intervalo_minutos = models.PositiveSmallIntegerField(default=5)
    horario_inicio = models.TimeField(default=time(7, 0))
    horario_fim = models.TimeField(default=time(23, 0))
    dias_semana = models.JSONField(default=_todos_os_dias, blank=True, help_text="0 = segunda ... 6 = domingo")
    limite_diario = models.PositiveSmallIntegerField(default=0, help_text="0 = sem limite.")
    repetir_apos_dias = models.PositiveSmallIntegerField(default=7)

    # Simulação: faz tudo, menos enviar (as ofertas aparecem na tela como "Simulado").
    simulacao = models.BooleanField("modo simulação", default=False)
    # Revisão do texto com IA (Gemini, chave única do Appfiliado - ver bot_whatsapp/ia.py).
    IA_LEVE, IA_CONTEXTUAL, IA_CRIATIVA = "leve", "contextual", "criativa"
    TIPOS_IA = [
        (IA_LEVE, "Leve: só português"),
        (IA_CONTEXTUAL, "Contextual: corrige frases que não combinam com o produto"),
        (IA_CRIATIVA, "Criativa: deixa a chamada mais atraente"),
    ]
    # Como a oferta vai para o WhatsApp.
    FORMATO_FOTO, FORMATO_PREVIA = "foto", "previa"
    FORMATOS_ENVIO = [
        (FORMATO_FOTO, "Foto com o texto"),
        (FORMATO_PREVIA, "Prévia grande do link"),
    ]
    formato_envio = models.CharField("como enviar", max_length=10, choices=FORMATOS_ENVIO, default=FORMATO_FOTO)
    ia_ativa = models.BooleanField("revisar o texto com IA", default=False)
    ia_tipo = models.CharField("tipo de revisão", max_length=12, choices=TIPOS_IA, default=IA_CONTEXTUAL)
    ia_status = models.CharField(max_length=300, blank=True, help_text="O que a IA fez na última oferta.")
    ia_dia = models.DateField(null=True, blank=True)
    ia_revisoes_no_dia = models.PositiveIntegerField(default=0)

    # Controle do motor.
    proximo_envio_em = models.DateTimeField(null=True, blank=True)
    ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    situacao = models.CharField(max_length=300, blank=True, help_text="Por que não está enviando agora.")
    ultimo_erro = models.TextField(blank=True)
    pagina_atual = models.PositiveIntegerField(default=1)
    pagina_em = models.DateTimeField(null=True, blank=True)
    # "Testar busca" (o painel pede, o worker responde).
    pedido_teste_em = models.DateTimeField(null=True, blank=True)
    teste_em = models.DateTimeField(null=True, blank=True)
    teste_resultado = models.JSONField(default=list, blank=True)
    teste_erro = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuração de ofertas automáticas"
        verbose_name_plural = "configurações de ofertas automáticas"

    def __str__(self):
        return f"{self.conta.email} - {'ligado' if self.ativo else 'pausado'}"

    @property
    def testando(self) -> bool:
        return bool(self.pedido_teste_em and (not self.teste_em or self.teste_em < self.pedido_teste_em))

    def lista_sub_ids(self, jid: str = "") -> list[str]:
        """Sub IDs do link desse grupo: os próprios dele, se tiver; senão, o padrão."""
        texto = (self.sub_ids_por_grupo or {}).get(jid, "") or self.sub_ids
        return [s.strip() for s in str(texto or "").split(",") if s.strip()][:5]

    @property
    def por_nicho(self) -> bool:
        return self.modo == self.MODO_SHOPEE and self.modo_envio == self.ENVIO_NICHO

    def chave_da_busca(self) -> str:
        """Muda quando muda algo que altera a lista de produtos (aí a busca recomeça)."""
        return "|".join(str(v) for v in (
            self.tipo_busca, self.palavra_chave, self.loja, sorted(self.categorias or []), self.ordenacao,
            self.comissao_minima, self.desconto_minimo, self.preco_minimo, self.preco_maximo,
            self.vendas_minimas, self.avaliacao_minima,
        ))


def _ligadas_padrao():
    from .campanhas import LIGADAS_PADRAO

    return list(LIGADAS_PADRAO)


class CampanhaBot(models.Model):
    """Modo campanha (ver bot_whatsapp/campanhas.py): nas datas ligadas, o bot usa estes
    valores no lugar dos da automação normal. Campo vazio = usa o da automação."""

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="campanha_bot")
    ativo = models.BooleanField("modo campanha ligado", default=False)
    datas_ligadas = models.JSONField(default=_ligadas_padrao, blank=True, help_text='Chaves: "11.11", "black_friday"...')
    datas_proprias = models.JSONField(default=list, blank=True,
                                      help_text='[{"data": "2026-11-25", "nome": "...", "anual": true}]')
    # Ritmo
    intervalo_minutos = models.PositiveSmallIntegerField(null=True, blank=True)
    limite_diario = models.PositiveSmallIntegerField(null=True, blank=True)
    horario_inicio = models.TimeField(default=time(0, 0))
    horario_fim = models.TimeField(default=time(23, 59))
    # Busca e filtros
    palavra_chave = models.CharField(max_length=120, blank=True)
    comissao_minima = models.PositiveSmallIntegerField(null=True, blank=True)
    desconto_minimo = models.PositiveSmallIntegerField(null=True, blank=True)
    # Texto das ofertas: vai em todas as ofertas do dia (desligado, saem como na Automação).
    mensagem_ativa = models.BooleanField("mudar o texto das ofertas", default=True)
    frase_abertura = models.CharField(max_length=120, blank=True)
    cupom = models.CharField(max_length=120, blank=True)
    # Página da campanha: uma mensagem à parte, só com o link da página, a cada N ofertas.
    pagina_ativa = models.BooleanField("enviar a página da campanha", default=False)
    titulo_pagina = models.CharField(max_length=120, blank=True)
    texto_pagina = models.CharField(max_length=200, blank=True)
    link_campanha = models.URLField(max_length=500, blank=True)
    link_campanha_a_cada = models.PositiveSmallIntegerField(default=10)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "modo campanha do bot"
        verbose_name_plural = "modo campanha do bot"

    def __str__(self):
        return f"{self.conta.email} - {'ligado' if self.ativo else 'desligado'}"


class OfertaRecebida(models.Model):
    """Mensagem com link da Shopee que chegou num grupo/canal de origem (modo copiar).
    O worker guarda aqui e o motor das ofertas repassa, respeitando horário,
    intervalo, limite e "não repetir"."""

    PENDENTE, ENVIADA, IGNORADA, ERRO = "pendente", "enviada", "ignorada", "erro"
    ESTADOS = [(PENDENTE, "Na fila"), (ENVIADA, "Repassada"), (IGNORADA, "Ignorada"), (ERRO, "Erro")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="ofertas_recebidas")
    mensagem_id = models.CharField(max_length=120)
    origem = models.CharField(max_length=80)
    origem_nome = models.CharField(max_length=200, blank=True)
    texto = models.TextField()
    imagem_arquivo = models.CharField(max_length=300, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDENTE)
    motivo = models.CharField(max_length=300, blank=True)
    produto = models.CharField(max_length=300, blank=True)
    item_id = models.CharField(max_length=40, blank=True)
    recebida_em = models.DateTimeField(auto_now_add=True)
    processada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["conta", "mensagem_id"], name="oferta_recebida_unica")]
        verbose_name = "oferta recebida (copiar de grupos)"
        verbose_name_plural = "ofertas recebidas (copiar de grupos)"

    def __str__(self):
        return f"{self.conta.email} <- {self.origem_nome or self.origem} ({self.estado})"


MODELO_ALERTA_PADRAO = (
    "📉 BAIXOU DE PREÇO!\n\n"
    "{produto}\n\n"
    "De {preco_antes} por {preco_agora} ({queda} mais barato)\n\n"
    "🛒 Compre aqui:\n{link}"
)


class AlertaPreco(models.Model):
    """Alerta de preço (aba do Bot de WhatsApp): a configuração da conta. Os produtos
    ficam em ProdutoAcompanhado; quem confere os preços é bot_whatsapp/alertas.py."""

    INTERVALOS = [(15, "15 minutos"), (30, "30 minutos"), (60, "1 hora"), (180, "3 horas"), (360, "6 horas")]

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="alerta_preco")
    ativo = models.BooleanField("alerta ligado", default=False)
    intervalo_minutos = models.PositiveSmallIntegerField("conferir a cada", choices=INTERVALOS, default=60)
    queda_minima = models.PositiveSmallIntegerField("queda mínima (%)", default=10)
    avisar_email = models.BooleanField("avisar por e-mail", default=True)
    # Os grupos são os mesmos da Automação do bot (ConfiguracaoOfertas.grupos).
    enviar_grupos = models.BooleanField("postar nos grupos", default=False)
    modelo_mensagem = models.TextField("mensagem", default=MODELO_ALERTA_PADRAO, blank=True)
    # Controle do motor
    proxima_conferencia_em = models.DateTimeField(null=True, blank=True)
    ultima_conferencia_em = models.DateTimeField(null=True, blank=True)
    pedido_conferir_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.CharField(max_length=500, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "alerta de preço"
        verbose_name_plural = "alertas de preço"

    def __str__(self):
        return f"{self.conta.email} - {'ligado' if self.ativo else 'pausado'}"


class ProdutoAcompanhado(models.Model):
    """Produto que a conta acompanha no alerta de preço. "referencia" é o preço contra o
    qual se mede a queda: sobe junto quando o preço sobe e vira o preço novo a cada alerta
    (assim o próximo alerta precisa de uma queda nova)."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="produtos_acompanhados")
    item_id = models.CharField(max_length=40)
    nome = models.CharField(max_length=300, blank=True)
    imagem = models.URLField(max_length=1000, blank=True)
    link = models.URLField(max_length=1000, blank=True, help_text="Link do produto na Shopee (sem afiliado).")
    preco_inicial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preco_atual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    menor_preco = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    referencia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    historico = models.JSONField(default=list, blank=True, help_text='[["2026-10-21T10:00", 49.9], ...] (só mudanças)')
    indisponivel = models.BooleanField(default=False, help_text="A Shopee parou de devolver o produto (sem estoque ou sem comissão).")
    adicionado_em = models.DateTimeField(auto_now_add=True)
    conferido_em = models.DateTimeField(null=True, blank=True)
    ultimo_alerta_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-adicionado_em"]
        constraints = [models.UniqueConstraint(fields=["conta", "item_id"], name="produto_acompanhado_unico")]
        verbose_name = "produto acompanhado"
        verbose_name_plural = "produtos acompanhados"

    def __str__(self):
        return f"{self.conta.email} - {self.nome[:60]}"

    @property
    def variacao(self):
        """% do preço atual em relação ao de quando foi adicionado (negativo = mais barato)."""
        if not self.preco_inicial or self.preco_atual is None:
            return None
        return round(float((self.preco_atual - self.preco_inicial) / self.preco_inicial * 100), 1)


class AlertaDisparado(models.Model):
    """Cada queda de preço que gerou alerta (aparece no painel; o e-mail e a postagem
    nos grupos ficam marcados aqui)."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="alertas_disparados")
    produto = models.ForeignKey(ProdutoAcompanhado, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas")
    nome = models.CharField(max_length=300, blank=True)
    imagem = models.URLField(max_length=1000, blank=True)
    link_afiliado = models.URLField(max_length=500, blank=True)
    preco_antes = models.DecimalField(max_digits=10, decimal_places=2)
    preco_agora = models.DecimalField(max_digits=10, decimal_places=2)
    queda = models.DecimalField(max_digits=5, decimal_places=1, help_text="Em %.")
    enviado_email = models.BooleanField(default=False)
    postado_grupos = models.BooleanField(default=False)
    visto = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "alerta disparado"
        verbose_name_plural = "alertas disparados"


class MensagemAvulsa(models.Model):
    """Mensagem escrita pela pessoa (aba Mensagens do Bot) pra mandar nos grupos agora, num dia e
    hora marcados ou toda semana. Quem dispara é bot_whatsapp/mensagens.py, no worker."""

    DESTINO_TODOS, DESTINO_NICHO, DESTINO_GRUPOS = "todos", "nicho", "grupos"
    DESTINOS = [(DESTINO_TODOS, "Todos os grupos do bot"), (DESTINO_NICHO, "Os grupos de um nicho"),
                (DESTINO_GRUPOS, "Escolher os grupos")]
    QUANDO_AGORA, QUANDO_AGENDAR, QUANDO_SEMANAL = "agora", "agendar", "semanal"
    QUANDOS = [(QUANDO_AGORA, "Agora"), (QUANDO_AGENDAR, "Agendar"), (QUANDO_SEMANAL, "Repetir toda semana")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="mensagens_avulsas")
    texto = models.TextField()
    foto = models.BinaryField(null=True, blank=True)  # JPEG (o disco do servidor não guarda arquivos)
    destino = models.CharField(max_length=10, choices=DESTINOS, default=DESTINO_TODOS)
    nicho = models.CharField(max_length=20, blank=True)
    grupos = models.JSONField(default=list, blank=True)  # jids, com destino "grupos"
    quando = models.CharField(max_length=10, choices=QUANDOS, default=QUANDO_AGORA)
    agendada_para = models.DateTimeField(null=True, blank=True)
    dias_semana = models.JSONField(default=list, blank=True)  # 0 = segunda ... 6 = domingo
    hora = models.TimeField(null=True, blank=True)
    proxima_em = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Vazio = já foi (não repete).")
    pausada = models.BooleanField(default=False)
    ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["proxima_em", "-id"]
        verbose_name = "mensagem avulsa"
        verbose_name_plural = "mensagens avulsas"

    def __str__(self):
        return f"{self.conta.email} - {self.texto[:40]}"


class GrupoMonitorado(models.Model):
    """Grupo que a pessoa escolheu acompanhar na aba Membros (bot_whatsapp/membros.py). Guarda a
    última contagem; o histórico fica em LeituraMembros (por hora) e DiaMembros (por dia).
    Só números: nunca quem entrou ou saiu."""

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="grupos_monitorados")
    jid = models.CharField(max_length=80)
    nome = models.CharField(max_length=200, blank=True)
    admin = models.BooleanField(default=False)
    no_grupo = models.BooleanField(default=True, help_text="Falso quando o número do bot saiu do grupo.")
    membros = models.PositiveIntegerField(null=True, blank=True)
    lido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome", "pk"]
        constraints = [models.UniqueConstraint(fields=["conta", "jid"], name="grupo_monitorado_unico")]
        verbose_name = "grupo monitorado"
        verbose_name_plural = "grupos monitorados"

    def __str__(self):
        return f"{self.conta.email} - {self.nome or self.jid}"


class LeituraMembros(models.Model):
    """Uma contagem por hora, guardada por 2 dias (para a variação das últimas 24 horas)."""

    grupo = models.ForeignKey(GrupoMonitorado, on_delete=models.CASCADE, related_name="leituras")
    em = models.DateTimeField(db_index=True)
    membros = models.PositiveIntegerField()

    class Meta:
        ordering = ["-em"]


class DiaMembros(models.Model):
    """Um dia de um grupo: a última contagem do dia e quantos entraram e saíram (13 meses)."""

    grupo = models.ForeignKey(GrupoMonitorado, on_delete=models.CASCADE, related_name="dias")
    dia = models.DateField()
    membros = models.PositiveIntegerField(null=True, blank=True)
    entradas = models.PositiveIntegerField(default=0)
    saidas = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-dia"]
        constraints = [models.UniqueConstraint(fields=["grupo", "dia"], name="dia_membros_unico")]


class PedidoGrupo(models.Model):
    """Pedido de grupo novo feito no painel (aba Membros). Quem cria é o worker, pelo número
    conectado (bot_whatsapp/grupos_novos.py): o grupo nasce vazio, com o link de convite."""

    PENDENTE, CRIADO, ERRO = "pendente", "criado", "erro"
    ESTADOS = [(PENDENTE, "Criando"), (CRIADO, "Criado"), (ERRO, "Erro")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="pedidos_de_grupo")
    nome = models.CharField(max_length=100)
    base_jid = models.CharField(max_length=80, blank=True, help_text="Grupo de onde copia foto, descrição, nicho e Sub ID.")
    copiar_foto_e_descricao = models.BooleanField(default=True)
    so_admins = models.BooleanField(default=True, help_text="Só administradores enviam mensagens.")
    administradores = models.JSONField(default=list, blank=True)  # números (DDI + DDD + número)
    incluir_na_automacao = models.BooleanField(default=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDENTE)
    jid = models.CharField(max_length=80, blank=True)
    link_convite = models.CharField(max_length=200, blank=True)
    avisos = models.TextField(blank=True)  # o que não deu certo, sem impedir o grupo (ex: um admin)
    erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "pedido de grupo novo"
        verbose_name_plural = "pedidos de grupo novo"

    def __str__(self):
        return f"{self.conta.email} - {self.nome} ({self.estado})"
