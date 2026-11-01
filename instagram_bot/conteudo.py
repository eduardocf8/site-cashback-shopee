"""Bancos de conteúdo e decisão do que publicar em cada dia.

Calendário (ver marketing/instagram/README.md para o histórico da decisão, e a
conversa de 01/11/2026 pela última revisão - menos fricção de aprovação, mais
variedade de story, 1 carrossel por semana em vez de institucional + ofertas da
semana):
    - Stories:
        todo dia         -> NUMERO_STORIES_OFERTAS_POR_DIA stories de oferta ao longo
                             do dia (1 categoria mais vendida por story - ver
                             instagram_bot/services.py, chamado várias vezes ao dia por
                             um cron dedicado, não pela tarefa diária única)
        terça e sábado    -> além das ofertas, 1 dica de economia (banco DICAS, rotativo)
        quinta e domingo  -> além das ofertas, 1 lembrete de cashback (banco LEMBRETES,
                             rotativo)
    - Posts no feed, 1x por semana:
        quarta -> carrossel temático em rotação (TEMAS_CARROSSEL, pré-desenhado à mão
                  em marketing/instagram/carrossel-NN-*) - substitui o banco
                  institucional (genérico demais, nunca aprovado) e o post de
                  "melhores ofertas da semana" (virou 2 posts por semana sem necessidade)
    - Tudo acima publica direto, sem e-mail de aprovação (INSTAGRAM_REQUER_APROVACAO
      não se aplica a esse conteúdo - ver pular_aprovacao em instagram_bot/services.py):
      é conteúdo fixo, revisado antes de entrar no banco/na pasta, não dado dinâmico
      que possa sair errado.
"""
from pathlib import Path

from .models import RegistroPublicacao

SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA, SABADO, DOMINGO = range(7)

# Dias em que postamos stories de oferta (ver instagram_bot/services.py,
# publicar_story_oferta_do_momento - chamado várias vezes ao dia, não é a tarefa
# diária única). Todo dia da semana, incluindo fim de semana.
DIAS_COM_STORIES_DE_OFERTA = (SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA, SABADO, DOMINGO)

DICAS = [
    "Sempre confira se tem cupom disponível antes de finalizar a compra: cashback e cupom não se excluem.",
    "Guarde o link convertido antes de sair navegando — comprando por outro caminho, o cashback não é rastreado.",
    "Produtos com campanha de comissão extra rendem mais cashback. Fique de olho nas ofertas em destaque.",
    "O cashback só é confirmado depois que a Shopee valida o pedido, então evite cancelar ou trocar a compra.",
    "Compras maiores geram cashback maior. Vale juntar os itens do carrinho numa compra só.",
    "Assim que o saldo aparece como \"Liberado\", já dá para sacar — não precisa esperar mais nada.",
    "Cadastre sua chave Pix com antecedência: assim que o saldo é liberado, o saque já sai na hora.",
]

LEMBRETES = [
    "Cashback de verdade: sem pegadinha, sem mensalidade.",
    "Toda compra na Shopee volta parte do dinheiro pro seu bolso.",
    "Cadastro grátis, cashback de verdade. Simples assim.",
    "Você compra do jeito que já compra — a diferença é que parte volta para você.",
    "Sem letra miúda. O que você vê é o que você recebe.",
    "Já usou a cash-b essa semana?",
]

# Cada um dos 8 temas institucionais originais (ver marketing/instagram/README.md pro
# histórico da semeadura manual) entra aqui com 2 variações de texto/legenda - assim o
# bot não republica pro mesmo público exatamente a mesma arte que você já postou na mão.
# "texto" é a frase curta desenhada na imagem (gerar_imagem_texto_simples não usa emoji
# aqui - ver services.py); "legenda" é o texto completo do post no Instagram.
POSTS_INSTITUCIONAIS = [
    {
        "texto": "Cash-b: parte do que você gasta na Shopee volta pro seu bolso.",
        "legenda": (
            "A cash-b é simples: você compra na Shopee do jeito que já compra, e recebe parte do "
            "dinheiro de volta. 💸 Sem mensalidade, sem pegadinha — só cashback de verdade caindo "
            "no seu saldo. 💚\nAinda não conhece? Link na bio.\n"
            "#cashback #shopee #cashbackshopee #economia #dinheirodevolta"
        ),
    },
    {
        "texto": "Compra na Shopee do seu jeito. Cashback de verdade no fim.",
        "legenda": (
            "Não é papo de vendedor: você compra normalmente na Shopee, e uma parte do valor volta "
            "para você. 💚 Sem mensalidade, sem enrolação, sem mudar nada no seu jeito de comprar.\n"
            "Quer testar? Link na bio.\n#cashback #shopee #economia #cashbackshopee"
        ),
    },
    {
        "texto": "3 passos: gera o link, compra normal, recebe cashback.",
        "legenda": (
            "Não tem mistério: 🔗 gera o link (ou vai direto pra Shopee), 🛍️ compra normalmente, e "
            "💰 recebe parte de volta assim que a Shopee confirma o pedido. 3 passos, sem burocracia.\n"
            "Teste você mesmo — link na bio.\n#cashback #shopee #comofunciona #economia"
        ),
    },
    {
        "texto": "Sem burocracia: link, compra, e o cashback cai sozinho.",
        "legenda": (
            "Resumindo a cash-b em uma frase: gera o link, compra na Shopee, e o cashback aparece "
            "no seu saldo assim que a Shopee confirma. 🔗🛍️💰 Nenhum passo a mais que isso.\n"
            "Link na bio para começar.\n#cashback #shopee #comofunciona"
        ),
    },
    {
        "texto": "Link do produto específico pode render cashback extra.",
        "legenda": (
            "Sabia que converter o link do produto específico pode render mais cashback? ⚡ Quando a "
            "Shopee tem campanha de comissão extra ativa, só quem usa o link direto tem acesso ao "
            "bônus. Já quem prefere só entrar e comprar o que quiser, também garante cashback — sem "
            "escolher nada antes.\nDuas formas, o mesmo cashback de verdade. ✅\n#cashback #shopee #dicas"
        ),
    },
    {
        "texto": "Campanha de comissão extra? Só quem usa o link direto garante.",
        "legenda": (
            "Uma dica para quem quer render mais: quando a Shopee ativa comissão extra num produto, "
            "o bônus só vale para quem converteu o link daquele produto específico. ⚡ Fora isso, "
            "comprar do jeito que preferir também garante cashback normal.\n#cashback #shopee #dicas"
        ),
    },
    {
        "texto": "Pendente, validado, liberado: acompanhe seu cashback em 3 fases.",
        "legenda": (
            "Depois da compra, seu cashback passa por 3 fases: ⏳ pendente (aguardando a Shopee "
            "confirmar), ✅ validado (compra confirmada, aguardando o prazo) e 💸 liberado (já pode "
            "sacar). Acompanhe tudo direto no seu painel.\n#cashback #shopee #transparencia"
        ),
    },
    {
        "texto": "Do clique ao Pix: total transparência em cada fase.",
        "legenda": (
            "Você sabe exatamente em que fase seu cashback está, o tempo todo: pendente, validado ou "
            "liberado. 📊 Nada de saldo que aparece do nada ou some sem explicação — tudo visível no "
            "seu painel.\n#cashback #shopee #transparencia"
        ),
    },
    {
        "texto": "Saldo liberado é seu. Peça o saque via Pix quando quiser.",
        "legenda": (
            "Saldo liberado é saldo seu. 💸 Cadastre sua chave Pix e peça o saque — sem burocracia, "
            "direto na sua conta. 🏦\n#cashback #pix #shopee #dinheirodevolta"
        ),
    },
    {
        "texto": "Chave Pix cadastrada, saque liberado na hora que você pedir.",
        "legenda": (
            "Assim que o saldo é liberado, o saque é rapidinho: com a chave Pix já cadastrada, "
            "cai direto na sua conta. 🏦💸 Sem enrolação nenhuma.\n#cashback #pix #shopee"
        ),
    },
    {
        "texto": "Sem mensalidade. Sem letra miúda. Cashback de verdade.",
        "legenda": (
            "🚫 Sem mensalidade. 🚫 Sem letra miúda. 🚫 Sem \"cashback\" que nunca cai na conta. Você "
            "compra, a Shopee confirma, você recebe. Simples assim. ✅\n#cashback #semmensalidade #shopee"
        ),
    },
    {
        "texto": "Cashback que realmente cai na sua conta. Sem pegadinha.",
        "legenda": (
            "Zero taxa escondida, zero mensalidade, zero desculpa. A cash-b existe para uma coisa só: "
            "colocar parte do que você já gasta na Shopee de volta no seu bolso. ✅\n"
            "#cashback #semmensalidade #shopee"
        ),
    },
    {
        "texto": "Compre do seu jeito. Economize sem esforço nenhum.",
        "legenda": (
            "Você não precisa mudar nada no seu jeito de comprar — só ganhar mais no final. 📈 Toda "
            "compra que você já ia fazer na Shopee volta parte do dinheiro pro seu bolso. 💰\n"
            "Comece a economizar sem esforço — link na bio.\n#cashback #economia #shopee #dinheirodevolta"
        ),
    },
    {
        "texto": "Todo real que você já ia gastar volta pro seu bolso.",
        "legenda": (
            "A conta é simples: você já compra na Shopee de qualquer jeito — com a cash-b, parte "
            "desse dinheiro volta para você em vez de ficar só na loja. 💰📈\n"
            "#cashback #economia #shopee #dinheirodevolta"
        ),
    },
    {
        "texto": "Cadastro grátis. Cashback de verdade. Comece agora.",
        "legenda": (
            "🚀 Cadastro grátis, sem custo nenhum. Compra na Shopee do jeito que já compra e começa a "
            "receber cashback de verdade.\n👉 cash-b.com\n#cashback #shopee #cadastrese"
        ),
    },
    {
        "texto": "Sem custo para começar: cadastre-se e ganhe cashback.",
        "legenda": (
            "Criar sua conta na cash-b não custa nada e leva menos de um minuto. 🚀 Depois é só "
            "comprar na Shopee normalmente e ver o saldo crescer.\n👉 cash-b.com\n#cashback #shopee #cadastrese"
        ),
    },
]


def _escolher_da_lista(lista: list, data) -> "str | dict":
    """Roda pela lista usando o número ordinal do dia (dia do ano), sem repetir em sequência."""
    indice = data.toordinal() % len(lista)
    return lista[indice]


def escolher_dica(data) -> str:
    return _escolher_da_lista(DICAS, data)


def escolher_lembrete(data) -> str:
    return _escolher_da_lista(LEMBRETES, data)


def escolher_post_institucional(data) -> dict:
    indice = data.toordinal() % len(POSTS_INSTITUCIONAIS)
    post = POSTS_INSTITUCIONAIS[indice]
    # Alterna o fundo entre as duas variações de cada tema, pra também não repetir a
    # mesma paleta toda vez que o mesmo tema voltar.
    estilo = "highlight" if indice % 2 == 0 else "brand"
    return {**post, "estilo": estilo}


# Pasta onde moram os carrosséis feitos à mão (ver marketing/instagram/README.md,
# seção "Carrosséis") - cada um em marketing/instagram/<pasta>/, com slide_1.png,
# slide_2.png... e legenda.txt. Esse módulo só lê o que já foi exportado - gerar um
# carrossel novo continua sendo manual (python3 gerar_carrossel_<tema>.py --export).
PASTA_CARROSSEIS = Path(__file__).resolve().parent.parent / "marketing" / "instagram"

# Ordem da rotação: primeiro os que você ainda não tinha postado manualmente (01, 03,
# 05, 10), depois os 6 que já foram ao ar entre agosto e outubro de 2026 (conferido
# contra o grid do perfil em 01/11/2026) - assim ninguém vê repetido antes de ver
# tudo pelo menos uma vez. Os 5 últimos (13 a 17) entraram depois, na mesma conversa,
# e ficam no fim da lista por isso - mesma regra de sempre, novo carrossel entra no fim.
#
# "11-datas-duplas" e "12-black-friday" ficam de fora de propósito: só são verdade com
# campanha de cashback aumentado de fato ativa (ver ROADMAP.md) - publicar fora disso
# afirmaria um benefício que não existe naquele momento. Esses dois são postados na mão
# (via Shell do Render, chamando publicar_carrossel_tematico com data/request manuais -
# não existe comando dedicado pra pular a rotação e postar um tema específico) só
# quando a campanha estiver no ar.
TEMAS_CARROSSEL = [
    ("carrossel-01-beneficios", 7),
    ("carrossel-03-cupom-frete-cashback", 7),
    ("carrossel-05-melhores-compras", 8),
    ("carrossel-10-indique-e-ganhe", 7),
    ("carrossel-02-comissao-invisivel", 7),
    ("carrossel-04-gasto-anual", 7),
    ("carrossel-06-nao-e-motivo", 6),
    ("carrossel-07-direta-indireta", 6),
    ("carrossel-08-perder-cashback", 9),
    ("carrossel-09-site-confiavel", 9),
    ("carrossel-13-nao-e-desconto", 7),
    ("carrossel-14-linha-do-tempo", 8),
    ("carrossel-15-shopee-ganha-voce-ganha", 6),
    ("carrossel-16-erros-saque-pix", 9),
    ("carrossel-17-indicacao-conta-real", 6),
]


def escolher_carrossel_tematico() -> dict:
    """Próximo carrossel da rotação. Pela quantidade já publicada (nunca com erro),
    não pelo dia do ano como escolher_dica/escolher_lembrete: aqui a ordem de
    TEMAS_CARROSSEL importa (os inéditos primeiro), e um post por semana já muda o
    número a cada vez que roda, sem precisar de aleatoriedade nem do dia como pivô."""
    publicados = RegistroPublicacao.objects.filter(
        conteudo_tipo=RegistroPublicacao.CONTEUDO_CARROSSEL_TEMATICO,
    ).exclude(status=RegistroPublicacao.STATUS_ERRO).count()
    pasta, numero_slides = TEMAS_CARROSSEL[publicados % len(TEMAS_CARROSSEL)]
    caminho = PASTA_CARROSSEIS / pasta
    legenda = (caminho / "legenda.txt").read_text(encoding="utf-8").strip()
    slides = [caminho / f"slide_{i}.png" for i in range(1, numero_slides + 1)]
    return {"legenda": legenda, "slides": slides}


def tipo_de_conteudo_do_dia(data) -> list[str]:
    """Retorna os tipos de conteúdo previstos pro calendário nesse dia (pode ter mais de um)."""
    dia_semana = data.weekday()
    tipos = []

    # CONTEUDO_OFERTA_DIARIA não entra aqui - é postado várias vezes ao dia por um
    # cron dedicado (ver publicar_story_oferta_do_momento), não uma vez só junto com
    # o resto da tarefa diária.

    # O combo sai todo dia. Diferente das dicas e lembretes (listas fixas escritas à
    # mão, que repetem quando a lista dá a volta), ele é montado a partir do catálogo
    # sincronizado - muda sozinho a cada dia, então a frequência diária não vira
    # repetição. Se a sincronização falhar, o publicador devolve vazio e o dia
    # simplesmente não tem combo.
    tipos.append(RegistroPublicacao.CONTEUDO_COMBO_DIARIO)

    if dia_semana in (TERCA, SABADO):
        tipos.append(RegistroPublicacao.CONTEUDO_DICA)
    elif dia_semana in (QUINTA, DOMINGO):
        tipos.append(RegistroPublicacao.CONTEUDO_LEMBRETE)

    if dia_semana == QUARTA:
        tipos.append(RegistroPublicacao.CONTEUDO_CARROSSEL_TEMATICO)

    return tipos


# ---------------------------------------------------------------------------
# Conteúdo com dado real do catálogo
#
# O resto deste arquivo é texto fixo escrito à mão, e por isso repete: são listas
# finitas que voltam do começo. Estas funções montam o conteúdo a partir das ofertas
# sincronizadas, então mudam sozinhas todo dia sem ninguém escrever nada - o que é o
# que torna viável postar mais de uma vez por semana.
#
# Todas devolvem None quando não há catálogo (sincronização falhou, banco vazio), pra
# quem chama simplesmente pular esse conteúdo em vez de publicar uma imagem com número
# errado ou zerado.
# ---------------------------------------------------------------------------


def _formatar_reais(valor) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def _formatar_percentual(valor) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def maior_cashback_de_hoje() -> "dict | None":
    """A oferta que mais devolve agora, em %, dentre as ~400 mais vendidas (mesmo
    corte de combo_de_stories_do_dia - ver o comentário lá sobre por que o rótulo não
    pode prometer "o maior de hoje" sem qualificar)."""
    from ofertas.models import Oferta

    oferta = max(
        Oferta.objects.exclude(preco_min=0)[:400],
        key=lambda o: o.percentual_cashback,
        default=None,
    )
    if oferta is None:
        return None
    nome = (oferta.nome_curto or oferta.nome).strip().rstrip(".")
    return {
        "numero": _formatar_percentual(oferta.percentual_cashback),
        "rotulo": "o maior cashback em %",
        "subrotulo": "entre os mais vendidos",
        "apoio": f"É quanto volta para você comprando {nome} pela cash-b.",
    }


def maior_valor_de_volta_hoje() -> "dict | None":
    """Mesma ideia, mas em reais (mesmo corte de 400 mais vendidos - ver
    maior_cashback_de_hoje). Fala com quem entende melhor "R$ 9" do que "6,5%"."""
    from ofertas.models import Oferta

    oferta = max(
        (o for o in Oferta.objects.exclude(preco_min=0)[:400]),
        key=lambda o: o.valor_cashback_estimado,
        default=None,
    )
    if oferta is None:
        return None
    nome = (oferta.nome_curto or oferta.nome).strip().rstrip(".")
    return {
        "numero": _formatar_reais(oferta.valor_cashback_estimado),
        "rotulo": "o maior cashback em R$",
        "subrotulo": "entre os mais vendidos",
        "apoio": f"É o que cai no seu saldo comprando {nome}.",
    }


def a_conta_de_uma_oferta() -> "dict | None":
    """A conta armada de um produto real do catálogo: o que você paga, o que volta e
    quanto a compra custou de verdade. Mostrar a conta convence mais que afirmar o
    resultado - a pessoa acompanha em vez de ter que acreditar."""
    from ofertas.models import Oferta

    oferta = max(
        (o for o in Oferta.objects.exclude(preco_min=0)[:400]),
        key=lambda o: o.valor_cashback_estimado,
        default=None,
    )
    if oferta is None:
        return None
    volta = oferta.valor_cashback_estimado
    nome = (oferta.nome_curto or oferta.nome).strip().rstrip(".")
    return {
        "titulo": f"A conta de {nome}",
        "linhas": [
            ("Preço na Shopee", _formatar_reais(oferta.preco_min)),
            ("Volta para você", _formatar_reais(volta)),
        ],
        "destaque": ("Saiu por", _formatar_reais(oferta.preco_min - volta)),
        "rodape": "Mesmo preço, mesma loja. A diferença é o que volta depois.",
    }


# Rótulos exatos das duas ordenações na vitrine (ver ofertas/views.py,
# ORDENACOES_ROTULOS) - se mudar lá, o passo a passo do story passa a ensinar um
# caminho que não existe mais.
ORDENACAO_MAIOR_CASHBACK = "Maior cashback (%)"
ORDENACAO_MAIOR_CASHBACK_REAIS = "Maior cashback (R$)"


def como_achar_na_vitrine() -> dict:
    """O último story do combo: como chegar nos dois produtos que acabaram de ser
    mostrados (o de maior % e o de maior R$).

    A API de stories do Instagram não aceita sticker de link, então o bot publica a
    imagem mas não consegue deixar nada clicável. Sem esse passo a passo, a pessoa vê um
    produto devolvendo 8% e não tem como chegar nele - os stories anteriores viram beco
    sem saída. Ensinar as duas ordenações também vale por si: quem aprende a ordenar
    por maior cashback volta sozinho depois."""
    return {
        "titulo": "Como achar esses produtos",
        "passos": [
            "Abra cash-b.com",
            "Toque em Ofertas",
            f'Ordene por "{ORDENACAO_MAIOR_CASHBACK}" ou "{ORDENACAO_MAIOR_CASHBACK_REAIS}"',
        ],
        # O "link na bio" sai daqui e vira elemento próprio no template (link_bio=True):
        # dentro da frase ele lê como parte da explicação, não como a ação a tomar.
        "rodape": "Eles vão estar no topo da lista.",
        "link_bio": True,
    }


def combo_de_stories_do_dia() -> "list[dict] | None":
    """A sequência do dia: capa, produto com maior % de cashback + a conta dele em R$
    (o % sozinho não mostra o valor), produto com maior cashback em R$ (esse já mostra
    o R$ de cara, não precisa de conta), e por fim como achar os dois na vitrine.
    Devolve None quando não há catálogo - ver o comentário no topo da seção.

    % e R$ são escolhidos separadamente, de propósito - podem ser produtos diferentes:
    um caro com % baixo pode valer mais em R$ que um barato com % alto (por isso a
    vitrine também tem as duas ordenações, ver ofertas/views.py).

    Busca só entre as ~400 ofertas mais vendidas (`Oferta.Meta.ordering = ["-vendas"]`),
    não no catálogo inteiro - de propósito, pra não arriscar destacar um produto pouco
    testado/pouco vendido só porque ele tem um % ou R$ mais alto. Por causa desse
    corte, o número aqui pode ser MENOR que o "Maior cashback (%)"/"(R$)" da vitrine
    (que ordena o catálogo inteiro, sem esse filtro) - por isso o rótulo diz "entre os
    mais vendidos", nunca "o maior de hoje" (isso já confundiu quem comparou os dois -
    ver conversa de 2026-09-02)."""
    from ofertas.models import Oferta

    oferta_percentual = max(
        Oferta.objects.exclude(preco_min=0)[:400],
        key=lambda o: o.percentual_cashback,
        default=None,
    )
    if oferta_percentual is None:
        return None

    oferta_reais = max(
        Oferta.objects.exclude(preco_min=0)[:400],
        key=lambda o: o.valor_cashback_estimado,
        default=None,
    )

    nome_percentual = (oferta_percentual.nome_curto or oferta_percentual.nome).strip().rstrip(".")
    nome_reais = (oferta_reais.nome_curto or oferta_reais.nome).strip().rstrip(".")
    volta_percentual = oferta_percentual.valor_cashback_estimado
    # O nome de cada produto entra uma vez só, como legenda da foto dele: repetido no
    # texto de apoio ou no título da conta, ocupava o espaço sem acrescentar nada - a
    # foto já diz do que se trata, e o nome vindo do Gemini às vezes é longo.
    return [
        {
            "formato": "capa",
            "titulo": "Os maiores cashbacks entre os mais vendidos hoje",
        },
        {
            "formato": "numero_com_produto",
            "numero": _formatar_percentual(oferta_percentual.percentual_cashback),
            "rotulo": "o maior cashback em %",
            "subrotulo": "entre os mais vendidos",
            "apoio": "É quanto volta para você aproveitando essa oferta.",
            "legenda_produto": nome_percentual,
            "imagem_url": oferta_percentual.imagem_url,
        },
        {
            "formato": "conta",
            "titulo": "A conta do produto",
            "linhas": [
                ("Preço na Shopee", _formatar_reais(oferta_percentual.preco_min)),
                ("Volta para você", _formatar_reais(volta_percentual)),
            ],
            "destaque": ("Saiu por", _formatar_reais(oferta_percentual.preco_min - volta_percentual)),
            "rodape": "Mesmo preço, mesma loja. A diferença é o que volta depois.",
        },
        {
            "formato": "numero_com_produto",
            "numero": _formatar_reais(oferta_reais.valor_cashback_estimado),
            "rotulo": "o maior cashback em R$",
            "subrotulo": "entre os mais vendidos",
            "apoio": "É o que cai no seu saldo comprando essa oferta.",
            "legenda_produto": nome_reais,
            "imagem_url": oferta_reais.imagem_url,
        },
        {"formato": "passos", **como_achar_na_vitrine()},
    ]
