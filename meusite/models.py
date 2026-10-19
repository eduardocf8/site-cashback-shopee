"""Meu site: o "link na bio" de cada conta do Appfiliado (seunome.appfiliado.com.br),
com perfil, botões, conversor de links e vitrine de ofertas."""

from django.db import models

from licencas.models import ContaAppfiliado

# Endereços que não podem ser de ninguém (são do próprio Appfiliado ou confundem).
ENDERECOS_RESERVADOS = {
    "app", "api", "www", "admin", "painel", "mail", "email", "smtp", "ftp", "blog", "ajuda", "suporte",
    "status", "static", "media", "cdn", "loja", "shopee", "appfiliado", "site", "sites", "teste", "dev",
}

# Redes sociais (ícones embaixo dos botões): campo -> (nome, como montar o link a partir do @).
REDES = [
    ("instagram", "Instagram", "https://instagram.com/{}"),
    ("tiktok", "TikTok", "https://tiktok.com/@{}"),
    ("youtube", "YouTube", "https://youtube.com/@{}"),
    ("x", "X (Twitter)", "https://x.com/{}"),
    ("facebook", "Facebook", "https://facebook.com/{}"),
    ("whatsapp", "WhatsApp", ""),
    ("telegram", "Telegram", "https://t.me/{}"),
]

CORES = [
    ("#E8541E", "Laranja"), ("#1F3A2E", "Verde"), ("#D6336C", "Rosa"),
    ("#2F6FDE", "Azul"), ("#7048E8", "Roxo"), ("#111111", "Preto"),
]


class SiteAfiliado(models.Model):
    VITRINE_BOT, VITRINE_BUSCA, VITRINE_MANUAL, VITRINE_NENHUMA = "bot", "busca", "manual", "nenhuma"
    FONTES_VITRINE = [
        (VITRINE_BOT, "As últimas ofertas que o bot enviou"),
        (VITRINE_BUSCA, "Uma busca na Shopee"),
        (VITRINE_MANUAL, "Produtos que eu escolher"),
        (VITRINE_NENHUMA, "Não mostrar vitrine"),
    ]
    BUSCA_GERAL, BUSCA_PALAVRA, BUSCA_LOJA, BUSCA_CATEGORIA = "geral", "palavra_chave", "loja", "categoria"
    TIPOS_BUSCA = [
        (BUSCA_GERAL, "Ofertas em geral"), (BUSCA_PALAVRA, "Palavra-chave"),
        (BUSCA_LOJA, "Uma loja"), (BUSCA_CATEGORIA, "Categorias"),
    ]

    conta = models.OneToOneField(ContaAppfiliado, on_delete=models.CASCADE, related_name="site")
    endereco = models.SlugField(max_length=40, unique=True, null=True, blank=True)
    publicado = models.BooleanField(default=True)
    nome = models.CharField(max_length=60, blank=True)
    frase = models.CharField(max_length=140, blank=True)
    foto = models.BinaryField(null=True, blank=True)  # JPEG pequeno (o disco do servidor não guarda arquivos)
    foto_versao = models.PositiveIntegerField(default=0)
    cor = models.CharField(max_length=7, choices=CORES, default="#E8541E")
    redes = models.JSONField(default=dict, blank=True, help_text="rede -> link (ver REDES).")
    mostrar_conversor = models.BooleanField(default=True)
    # Textos do conversor (em branco = o padrão).
    conversor_titulo = models.CharField(max_length=80, blank=True)
    conversor_texto = models.CharField(max_length=300, blank=True)
    conversor_botao = models.CharField(max_length=50, blank=True)
    sub_id = models.CharField(max_length=50, default="site", blank=True)

    vitrine = models.CharField(max_length=10, choices=FONTES_VITRINE, default=VITRINE_BOT)
    FORMATO_LISTA, FORMATO_CARROSSEL = "lista", "carrossel"
    FORMATOS_VITRINE = [(FORMATO_LISTA, "Lista"), (FORMATO_CARROSSEL, "Carrossel")]
    vitrine_formato = models.CharField(max_length=10, choices=FORMATOS_VITRINE, default=FORMATO_LISTA)
    busca_tipo = models.CharField(max_length=20, choices=TIPOS_BUSCA, default=BUSCA_GERAL)
    palavra_chave = models.CharField(max_length=120, blank=True)
    loja = models.CharField(max_length=300, blank=True)
    categorias = models.JSONField(default=list, blank=True)
    ordenacao = models.CharField(max_length=20, default="mais_vendidos")
    links_manuais = models.TextField(blank=True, help_text="Um link da Shopee por linha.")
    # O painel pede, o worker atualiza (busca na Shopee e links de afiliado).
    pedido_vitrine_em = models.DateTimeField(null=True, blank=True)
    vitrine_atualizada_em = models.DateTimeField(null=True, blank=True)
    vitrine_erro = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site do afiliado"
        verbose_name_plural = "sites dos afiliados"

    def __str__(self):
        return self.endereco or f"(sem endereço) {self.conta.email}"

    TITULO_PADRAO = "Achou algo na Shopee?"
    TEXTO_PADRAO = ("Cole o link do produto e compre pelo meu link. Você não paga nada a mais e me ajuda a "
                    "continuar postando ofertas.")
    BOTAO_PADRAO = "Ir para a Shopee com o meu link"

    def lista_de_redes(self) -> list[dict]:
        return [{"rede": rede, "nome": nome, "url": (self.redes or {}).get(rede)}
                for rede, nome, _ in REDES if (self.redes or {}).get(rede)]

    @property
    def titulo_do_conversor(self) -> str:
        return self.conversor_titulo or self.TITULO_PADRAO

    @property
    def texto_do_conversor(self) -> str:
        return self.conversor_texto or self.TEXTO_PADRAO

    @property
    def botao_do_conversor(self) -> str:
        return self.conversor_botao or self.BOTAO_PADRAO

    @property
    def vitrine_pedida(self) -> bool:
        return bool(self.pedido_vitrine_em and (
            not self.vitrine_atualizada_em or self.vitrine_atualizada_em < self.pedido_vitrine_em
        ))


class BotaoSite(models.Model):
    site = models.ForeignKey(SiteAfiliado, on_delete=models.CASCADE, related_name="botoes")
    texto = models.CharField(max_length=80)
    url = models.URLField(max_length=500)
    destaque = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "botão do site"
        verbose_name_plural = "botões do site"

    def __str__(self):
        return self.texto


class ProdutoSite(models.Model):
    """Um produto da vitrine. O link de afiliado (com o Sub ID do site) é gerado pelo
    worker; até lá, o clique gera na hora."""

    site = models.ForeignKey(SiteAfiliado, on_delete=models.CASCADE, related_name="produtos")
    fonte = models.CharField(max_length=10, choices=SiteAfiliado.FONTES_VITRINE)
    item_id = models.CharField(max_length=30)
    nome = models.CharField(max_length=300)
    imagem_url = models.URLField(max_length=500, blank=True)
    preco = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preco_original = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    desconto = models.PositiveSmallIntegerField(default=0)
    categoria = models.CharField(max_length=30, blank=True)
    link_produto = models.URLField(max_length=500)
    link_afiliado = models.URLField(max_length=500, blank=True)
    posicao_em = models.DateTimeField(help_text="Mais recente primeiro (o bot reenviar põe de novo no topo).")

    class Meta:
        ordering = ["-posicao_em", "-id"]
        constraints = [models.UniqueConstraint(fields=["site", "fonte", "item_id"], name="produto_site_unico")]
        verbose_name = "produto da vitrine"
        verbose_name_plural = "produtos da vitrine"

    def __str__(self):
        return self.nome


class CliqueSite(models.Model):
    """Contagem por dia: visitas ao site e cliques em botões, produtos e no conversor."""

    VISITA, BOTAO, REDE, PRODUTO, CONVERSOR = "visita", "botao", "rede", "produto", "conversor"
    TIPOS = [(VISITA, "Visita"), (BOTAO, "Botão"), (REDE, "Rede social"), (PRODUTO, "Produto"), (CONVERSOR, "Conversor")]

    site = models.ForeignKey(SiteAfiliado, on_delete=models.CASCADE, related_name="cliques")
    dia = models.DateField()
    tipo = models.CharField(max_length=10, choices=TIPOS)
    alvo_id = models.PositiveIntegerField(default=0)  # id do botão ou do produto (0 nos outros)
    alvo_nome = models.CharField(max_length=300, blank=True)
    total = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["site", "dia", "tipo", "alvo_id"], name="clique_site_unico")]
        verbose_name = "clique no site"
        verbose_name_plural = "cliques no site"
