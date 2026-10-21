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
    TESTE, OFERTA, CAMPANHA = "teste", "oferta", "campanha"
    # CAMPANHA: a página da campanha da Shopee, mandada a cada N ofertas no modo campanha
    # (não conta no limite de ofertas por dia nem no "não repetir").
    ORIGENS = [(TESTE, "Mensagem de teste"), (OFERTA, "Oferta automática"), (CAMPANHA, "Página da campanha")]

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
    # Mensagem (com ela desligada, as ofertas saem com o texto e o cupom da Automação)
    mensagem_ativa = models.BooleanField("usar a mensagem da campanha", default=True)
    frase_abertura = models.CharField(max_length=120, blank=True)
    cupom = models.CharField(max_length=120, blank=True)
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
