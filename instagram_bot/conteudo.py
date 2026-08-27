"""Bancos de conteúdo e decisão do que publicar em cada dia.

Calendário (ver marketing/instagram/README.md para o histórico da decisão):
    - Stories:
        todo dia -> NUMERO_STORIES_OFERTAS_POR_DIA stories de oferta ao longo do dia
                    (1 categoria mais vendida por story - ver instagram_bot/services.py,
                    chamado várias vezes ao dia por um cron dedicado, não pela tarefa
                    diária única)
        sábado    -> além das ofertas, 1 dica de economia (banco DICAS, rotativo)
        domingo   -> além das ofertas, 1 lembrete de cashback (banco LEMBRETES, rotativo)
    - Posts no feed, 2x por semana:
        quarta -> institucional (banco POSTS_INSTITUCIONAIS, rotativo)
        sexta  -> melhores ofertas da semana
"""
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
    "Assim que o saldo aparece como \"Liberado\", já dá pra sacar — não precisa esperar mais nada.",
    "Cadastre sua chave PIX com antecedência: assim que o saldo é liberado, o saque já sai na hora.",
]

LEMBRETES = [
    "Cashback de verdade: sem pegadinha, sem mensalidade.",
    "Toda compra na Shopee volta parte do dinheiro pro seu bolso.",
    "Cadastro grátis, cashback de verdade. Simples assim.",
    "Você compra do jeito que já compra — a diferença é que parte volta pra você.",
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
            "pra você. 💚 Sem mensalidade, sem enrolação, sem mudar nada no seu jeito de comprar.\n"
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
            "Link na bio pra começar.\n#cashback #shopee #comofunciona"
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
            "Uma dica pra quem quer render mais: quando a Shopee ativa comissão extra num produto, "
            "o bônus só vale pra quem converteu o link daquele produto específico. ⚡ Fora isso, "
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
        "texto": "Do clique ao PIX: total transparência em cada fase.",
        "legenda": (
            "Você sabe exatamente em que fase seu cashback está, o tempo todo: pendente, validado ou "
            "liberado. 📊 Nada de saldo que aparece do nada ou some sem explicação — tudo visível no "
            "seu painel.\n#cashback #shopee #transparencia"
        ),
    },
    {
        "texto": "Saldo liberado é seu. Peça o saque via PIX quando quiser.",
        "legenda": (
            "Saldo liberado é saldo seu. 💸 Cadastre sua chave PIX e peça o saque — sem burocracia, "
            "direto na sua conta. 🏦\n#cashback #pix #shopee #dinheirodevolta"
        ),
    },
    {
        "texto": "Chave PIX cadastrada, saque liberado na hora que você pedir.",
        "legenda": (
            "Assim que o saldo é liberado, o saque é rapidinho: com a chave PIX já cadastrada, "
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
            "Zero taxa escondida, zero mensalidade, zero desculpa. A cash-b existe pra uma coisa só: "
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
            "desse dinheiro volta pra você em vez de ficar só na loja. 💰📈\n"
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
        "texto": "Sem custo pra começar: cadastre-se e ganhe cashback.",
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

    if dia_semana == SABADO:
        tipos.append(RegistroPublicacao.CONTEUDO_DICA)
    elif dia_semana == DOMINGO:
        tipos.append(RegistroPublicacao.CONTEUDO_LEMBRETE)

    if dia_semana == QUARTA:
        tipos.append(RegistroPublicacao.CONTEUDO_INSTITUCIONAL)
    elif dia_semana == SEXTA:
        tipos.append(RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA)

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
    """A oferta que mais devolve agora, em %. É o número que melhor segura o dedo de
    quem está passando o story - e é dado nosso, que nenhum concorrente tem."""
    from ofertas.models import Oferta

    oferta = max(
        (o for o in Oferta.objects.exclude(preco_min=0)[:400]),
        key=lambda o: o.percentual_cashback,
        default=None,
    )
    if oferta is None:
        return None
    nome = (oferta.nome_curto or oferta.nome).strip().rstrip(".")
    return {
        "numero": _formatar_percentual(oferta.percentual_cashback),
        "rotulo": "o maior cashback de hoje",
        "apoio": f"É quanto volta pra você comprando {nome} pela cash-b.",
    }


def maior_valor_de_volta_hoje() -> "dict | None":
    """Mesma ideia, mas em reais. Fala com quem entende melhor "R$ 9" do que "6,5%"."""
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
        "rotulo": "quanto volta hoje",
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
            ("Volta pra você", _formatar_reais(volta)),
        ],
        "destaque": ("Saiu por", _formatar_reais(oferta.preco_min - volta)),
        "rodape": "Mesmo preço, mesma loja. A diferença é o que volta depois.",
    }


# Rótulo exato da ordenação na vitrine (ver ofertas/views.py, ORDENACOES_ROTULOS) - se
# mudar lá, o passo a passo do story passa a ensinar um caminho que não existe mais.
ORDENACAO_MAIOR_CASHBACK = "Maior cashback"


def como_achar_na_vitrine() -> dict:
    """O último story do combo: como chegar no produto que acabou de ser mostrado.

    A API de stories do Instagram não aceita sticker de link, então o bot publica a
    imagem mas não consegue deixar nada clicável. Sem esse passo a passo, a pessoa vê um
    produto devolvendo 8% e não tem como chegar nele - os stories anteriores viram beco
    sem saída. Ensinar a ordenação também vale por si: quem aprende a ordenar por maior
    cashback volta sozinho depois."""
    return {
        "titulo": "Como achar esse produto",
        "passos": [
            "Abra cash-b.com",
            "Toque em Ofertas",
            f'Ordene por "{ORDENACAO_MAIOR_CASHBACK}"',
        ],
        # O "link na bio" sai daqui e vira elemento próprio no template (link_bio=True):
        # dentro da frase ele lê como parte da explicação, não como a ação a tomar.
        "rodape": "Ele vai estar no topo da lista.",
        "link_bio": True,
    }


def combo_de_stories_do_dia() -> "list[dict] | None":
    """A sequência do dia: abre com a foto e o número, mostra a conta, e fecha ensinando
    onde achar. Devolve None quando não há catálogo - ver o comentário no topo da seção.

    Só o primeiro story leva foto do produto: ela serve pra abrir e dar cara ao número.
    Repetida nos três, a sequência fica monótona e parece catálogo."""
    from ofertas.models import Oferta

    oferta = max(
        (o for o in Oferta.objects.exclude(preco_min=0)[:400]),
        key=lambda o: o.valor_cashback_estimado,
        default=None,
    )
    if oferta is None:
        return None

    nome = (oferta.nome_curto or oferta.nome).strip().rstrip(".")
    volta = oferta.valor_cashback_estimado
    # O nome do produto entra uma vez só, como legenda da foto: repetido no texto de
    # apoio e no título da conta, ocupava o espaço três vezes sem acrescentar nada - a
    # foto já diz do que se trata, e o nome vindo do Gemini às vezes é longo.
    return [
        {
            "formato": "numero_com_produto",
            "numero": _formatar_percentual(oferta.percentual_cashback),
            "rotulo": "o maior cashback de hoje",
            "apoio": "É quanto volta para você aproveitando essa oferta.",
            "legenda_produto": nome,
            "imagem_url": oferta.imagem_url,
        },
        {
            "formato": "conta",
            "titulo": "A conta do produto",
            "linhas": [
                ("Preço na Shopee", _formatar_reais(oferta.preco_min)),
                ("Volta pra você", _formatar_reais(volta)),
            ],
            "destaque": ("Saiu por", _formatar_reais(oferta.preco_min - volta)),
            "rodape": "Mesmo preço, mesma loja. A diferença é o que volta depois.",
        },
        {"formato": "passos", **como_achar_na_vitrine()},
    ]
