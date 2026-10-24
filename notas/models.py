"""Emissor de notas fiscais de serviço (NFS-e de Padrão Nacional) para afiliados.

Cada conta cadastra a empresa (o CNPJ que emite) com o certificado digital A1 dela.
As notas são enviadas uma a uma para a API do governo (Sefin Nacional) e ficam
guardadas aqui com o XML que voltou, para baixar e mandar por e-mail."""

from django.db import models

from licencas.models import ContaAppfiliado

AMBIENTE_PRODUCAO = "1"
AMBIENTE_TESTE = "2"  # "produção restrita" do governo: igual à de verdade, mas sem valor fiscal
AMBIENTES = [(AMBIENTE_PRODUCAO, "Produção"), (AMBIENTE_TESTE, "Testes do governo")]


class EmpresaNotas(models.Model):
    REGIME_MEI = "mei"
    REGIME_SIMPLES = "simples"
    REGIMES = [(REGIME_MEI, "MEI"), (REGIME_SIMPLES, "Simples Nacional (ME/EPP)")]

    conta = models.ForeignKey(ContaAppfiliado, on_delete=models.CASCADE, related_name="empresas_notas")
    cnpj = models.CharField(max_length=14)  # só os dígitos (já pronto para o CNPJ com letras)
    razao_social = models.CharField(max_length=150)
    municipio_ibge = models.CharField(max_length=7)
    municipio_nome = models.CharField(max_length=80, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    inscricao_municipal = models.CharField(max_length=20, blank=True)
    regime = models.CharField(max_length=10, choices=REGIMES, default=REGIME_MEI)

    # O serviço que vai em todas as notas (código nacional de 6 dígitos, código do
    # município quando a prefeitura pede, e a descrição).
    codigo_tributacao = models.CharField(max_length=6, blank=True)
    codigo_municipal = models.CharField(max_length=20, blank=True)
    descricao_servico = models.TextField(blank=True)
    # NBS (Nomenclatura Brasileira de Serviços), 9 dígitos: exigido junto com o IBS/CBS.
    codigo_nbs = models.CharField(max_length=9, blank=True)

    # Certificado A1 (.pfx) e a senha, cifrados (painel/cripto.py). Nunca saem do servidor.
    certificado_cifrado = models.TextField(blank=True)
    senha_cifrada = models.TextField(blank=True)
    certificado_titular = models.CharField(max_length=200, blank=True)
    certificado_validade = models.DateTimeField(null=True, blank=True)

    # Série 1 a 49999 é a faixa de "aplicativo próprio". A numeração é por ambiente.
    serie = models.CharField(max_length=5, default="1")
    ultimo_numero_producao = models.BigIntegerField(default=0)
    ultimo_numero_teste = models.BigIntegerField(default=0)
    # Quando o governo recusa o certificado, a fila para de mandar as notas dessa empresa
    # (senão todas seriam recusadas uma a uma) até a pessoa trocar o certificado ou retomar.
    emissao_pausada = models.CharField(max_length=300, blank=True)
    # Hora (0-23, horário de Brasília) para mandar os e-mails das notas aos vendedores.
    # Vazio = logo depois que as notas saem.
    email_horario = models.PositiveSmallIntegerField(null=True, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "empresa (notas)"
        verbose_name_plural = "empresas (notas)"
        constraints = [models.UniqueConstraint(fields=["conta", "cnpj"], name="empresa_notas_por_conta")]

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    @property
    def tem_certificado(self) -> bool:
        return bool(self.certificado_cifrado and self.senha_cifrada)

    @property
    def cnpj_formatado(self) -> str:
        c = self.cnpj
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


class CadastroCNPJ(models.Model):
    """Dados públicos de um CNPJ (Receita), guardados para não consultar de novo a cada nota.
    Serve para o endereço do vendedor, que o relatório da Shopee traz só em texto corrido."""

    cnpj = models.CharField(max_length=14, primary_key=True)
    dados = models.JSONField(default=dict)
    consultado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cadastro de CNPJ"
        verbose_name_plural = "cadastros de CNPJ"

    def __str__(self):
        return f"{self.cnpj} {self.dados.get('razao_social', '')}"


class CEPConsultado(models.Model):
    """CEP já consultado (município pelo código do IBGE), para não consultar de novo a cada nota.
    dados vazio = o CEP não existe."""

    cep = models.CharField(max_length=8, primary_key=True)
    dados = models.JSONField(default=dict)
    consultado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CEP consultado"
        verbose_name_plural = "CEPs consultados"

    def __str__(self):
        return self.cep


class LoteNotas(models.Model):
    """Um Relatório Mensal da Shopee importado: vira uma nota por linha (por loja)."""

    PREVIA = "previa"
    EMITINDO = "emitindo"
    CONCLUIDO = "concluido"
    ESTADOS = [(PREVIA, "Prévia"), (EMITINDO, "Emitindo"), (CONCLUIDO, "Concluído")]

    empresa = models.ForeignKey(EmpresaNotas, on_delete=models.CASCADE, related_name="lotes")
    ambiente = models.CharField(max_length=1, choices=AMBIENTES, default=AMBIENTE_PRODUCAO)
    mes_referencia = models.DateField()  # "Mês de conclusão" do relatório (dia 1)
    competencia = models.DateField()  # data de competência das notas (dia em que foram emitidas)
    nome_arquivo = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PREVIA)
    # Linhas que não viram nota (já emitidas antes, estrangeiras por enquanto, com problema).
    ignoradas = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    confirmado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "lote de notas"
        verbose_name_plural = "lotes de notas"

    def __str__(self):
        return f"{self.empresa} · {self.mes_referencia:%m/%Y} ({self.get_estado_display()})"


class NotaFiscal(models.Model):
    TIPO_SHOPEE = "shopee"
    TIPO_VENDEDOR = "vendedor"
    TIPO_TESTE = "teste"
    TIPO_ASSINATURA = "assinatura"  # assinatura do Appfiliado paga na Zouti (notas/assinaturas.py)
    TIPOS = [(TIPO_SHOPEE, "Shopee"), (TIPO_VENDEDOR, "Vendedor"), (TIPO_TESTE, "Teste"),
             (TIPO_ASSINATURA, "Assinatura do Appfiliado")]

    PREVIA = "previa"  # importada, esperando a pessoa confirmar o lote
    FILA = "fila"
    ENVIANDO = "enviando"
    AUTORIZADA = "autorizada"
    RECUSADA = "recusada"
    ERRO = "erro"  # não deu para saber a resposta (queda, tempo esgotado): conferir antes de reenviar
    CANCELADA = "cancelada"
    SITUACOES = [(PREVIA, "Prévia"), (FILA, "Na fila"), (ENVIANDO, "Enviando"), (AUTORIZADA, "Autorizada"),
                 (RECUSADA, "Recusada"), (ERRO, "Sem resposta"), (CANCELADA, "Cancelada")]

    EMAIL_PENDENTE = "pendente"
    EMAIL_ENVIADO = "enviado"
    EMAIL_SEM = "sem_email"
    EMAIL_FALHOU = "falhou"
    EMAIL_NAO = "nao_envia"  # nota de teste ou nota da Shopee (vai pelo portal deles)
    EMAILS = [(EMAIL_PENDENTE, "A enviar"), (EMAIL_ENVIADO, "Enviado"), (EMAIL_SEM, "Sem e-mail"),
              (EMAIL_FALHOU, "Falhou"), (EMAIL_NAO, "Não se aplica")]

    empresa = models.ForeignKey(EmpresaNotas, on_delete=models.CASCADE, related_name="notas")
    lote = models.ForeignKey(LoteNotas, on_delete=models.CASCADE, related_name="notas", null=True, blank=True)
    loja_id = models.CharField(max_length=30, blank=True)  # "ID da Loja" do relatório
    loja_nome = models.CharField(max_length=200, blank=True)
    ambiente = models.CharField(max_length=1, choices=AMBIENTES, default=AMBIENTE_TESTE)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    competencia = models.DateField()

    # Tomador: quem recebe a nota (a Shopee ou o vendedor).
    tomador_tipo = models.CharField(max_length=4, default="cnpj")  # cnpj, cpf, nif (estrangeiro)
    tomador_documento = models.CharField(max_length=40)
    tomador_nome = models.CharField(max_length=300)
    tomador_email = models.CharField(max_length=254, blank=True)
    tomador_pais = models.CharField(max_length=2, blank=True)  # ISO, só para estrangeiro
    tomador_endereco = models.CharField(max_length=300, blank=True)  # como veio no relatório da Shopee
    valor = models.DecimalField(max_digits=15, decimal_places=2)

    # Serviço próprio desta nota (vazio = o serviço cadastrado na empresa). Usado nas notas das
    # assinaturas do Appfiliado, que a mesma empresa emite com outro código.
    servico_codigo = models.CharField(max_length=6, blank=True)
    servico_codigo_municipal = models.CharField(max_length=20, blank=True)
    servico_descricao = models.TextField(blank=True)
    servico_nbs = models.CharField(max_length=9, blank=True)
    # De onde veio a nota, pra nunca emitir duas vezes a mesma coisa (ex: "zouti:sub_x:2026-10-21").
    referencia = models.CharField(max_length=120, blank=True)

    # Série e número só são definidos na primeira tentativa de envio (sem buracos na
    # numeração por causa de prévias descartadas).
    serie = models.CharField(max_length=5, blank=True)
    numero = models.BigIntegerField(null=True, blank=True)
    dps_id = models.CharField(max_length=45, blank=True)

    situacao = models.CharField(max_length=10, choices=SITUACOES, default=FILA)
    chave = models.CharField(max_length=50, blank=True)  # chave de acesso da NFS-e
    numero_nfse = models.CharField(max_length=20, blank=True)
    xml_nfse = models.TextField(blank=True)
    mensagens = models.JSONField(default=list, blank=True)  # [{"codigo", "descricao"}] do governo
    tentativas = models.PositiveSmallIntegerField(default=0)
    enviada_em = models.DateTimeField(null=True, blank=True)
    autorizada_em = models.DateTimeField(null=True, blank=True)

    # Cancelamento (evento 101101 no emissor nacional, pedido pela própria empresa).
    MOTIVOS_CANCELAMENTO = [("1", "Erro na emissão"), ("2", "Serviço não prestado"), ("9", "Outro motivo")]
    cancelada_em = models.DateTimeField(null=True, blank=True)
    cancelamento_motivo = models.CharField(max_length=1, choices=MOTIVOS_CANCELAMENTO, blank=True)
    cancelamento_justificativa = models.CharField(max_length=255, blank=True)
    xml_cancelamento = models.TextField(blank=True)  # o evento registrado, como o governo devolveu
    cancelamento_email_em = models.DateTimeField(null=True, blank=True)  # aviso ao vendedor

    email_situacao = models.CharField(max_length=10, choices=EMAILS, default=EMAIL_NAO)
    email_enviar_em = models.DateTimeField(null=True, blank=True)  # agendado (vazio = logo que der)
    email_enviado_em = models.DateTimeField(null=True, blank=True)
    email_erro = models.CharField(max_length=300, blank=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "nota fiscal"
        verbose_name_plural = "notas fiscais"
        constraints = [
            models.UniqueConstraint(fields=["empresa", "ambiente", "serie", "numero"], name="nota_numero_unico"),
            models.UniqueConstraint(fields=["empresa", "ambiente", "referencia"], condition=~models.Q(referencia=""),
                                    name="nota_referencia_unica"),
        ]
        indexes = [models.Index(fields=["empresa", "situacao"]), models.Index(fields=["situacao", "criada_em"]),
                   models.Index(fields=["email_situacao"])]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero or '-'} → {self.tomador_nome[:40]} ({self.get_situacao_display()})"
