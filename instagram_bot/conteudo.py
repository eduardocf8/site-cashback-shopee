"""Bancos de conteúdo e decisão do que publicar em cada dia.

Calendário (ver marketing/instagram/README.md para o histórico da decisão):
    - Stories, todo dia:
        segunda a sexta -> destaque de ofertas do dia
        sábado          -> dica de economia (banco DICAS, rotativo)
        domingo         -> lembrete de cashback (banco LEMBRETES, rotativo)
    - Posts no feed, 2x por semana:
        quarta -> institucional (reaproveita os posts de semeadura em rotação)
        sexta  -> melhores ofertas da semana
"""
from pathlib import Path

from .models import RegistroPublicacao

SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA, SABADO, DOMINGO = range(7)

REPO_ROOT = Path(__file__).resolve().parent.parent
PASTA_POSTS_SEMEADURA = REPO_ROOT / "marketing" / "instagram" / "posts-semeadura"

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
    "Toda compra na Shopee pode voltar parte do dinheiro pro seu bolso.",
    "Cadastro grátis, cashback de verdade. Simples assim.",
    "Você compra do jeito que já compra — a diferença é que parte volta pra você.",
    "Sem letra miúda. O que você vê é o que você recebe.",
    "Já usou o cash-b essa semana?",
]

# Reaproveita os 8 posts de semeadura em rotação semanal pros posts institucionais
# de quarta-feira (ver marketing/instagram/README.md pro cronograma original de semeadura).
POSTS_INSTITUCIONAIS = [
    {
        "arquivo": "01-o-que-e-cashb.png",
        "legenda": (
            "O cash-b é simples: você compra na Shopee do jeito que já compra, e recebe parte do "
            "dinheiro de volta. 💸 Sem mensalidade, sem pegadinha — só cashback de verdade caindo "
            "no seu saldo. 💚\nAinda não conhece? Link na bio.\n"
            "#cashback #shopee #cashbackshopee #economia #dinheirodevolta"
        ),
    },
    {
        "arquivo": "02-como-funciona.png",
        "legenda": (
            "Não tem mistério: 🔗 gera o link (ou vai direto pra Shopee), 🛍️ compra normalmente, e "
            "💰 recebe parte de volta assim que a Shopee confirma o pedido. 3 passos, sem burocracia.\n"
            "Testa você mesmo — link na bio.\n#cashback #shopee #comofunciona #economia"
        ),
    },
    {
        "arquivo": "03-venda-direta-indireta.png",
        "legenda": (
            "Sabia que converter o link do produto específico pode render mais cashback? ⚡ Quando a "
            "Shopee tem campanha de comissão extra ativa, só quem usa o link direto tem acesso ao "
            "bônus. Já quem prefere só entrar e comprar o que quiser, também garante cashback — sem "
            "escolher nada antes.\nDuas formas, o mesmo cashback de verdade. ✅\n#cashback #shopee #dicas"
        ),
    },
    {
        "arquivo": "04-do-clique-ao-pix.png",
        "legenda": (
            "Depois da compra, seu cashback passa por 3 fases: ⏳ pendente (aguardando a Shopee "
            "confirmar), ✅ validado (compra confirmada, aguardando o prazo) e 💸 liberado (já pode "
            "sacar). Acompanha tudo direto no seu painel.\n#cashback #shopee #transparencia"
        ),
    },
    {
        "arquivo": "05-saque-pix.png",
        "legenda": (
            "Saldo liberado é saldo seu. 💸 Cadastra sua chave PIX e pede o saque — sem burocracia, "
            "direto na sua conta. 🏦\n#cashback #pix #shopee #dinheirodevolta"
        ),
    },
    {
        "arquivo": "06-sem-pegadinha.png",
        "legenda": (
            "🚫 Sem mensalidade. 🚫 Sem letra miúda. 🚫 Sem \"cashback\" que nunca cai na conta. Você "
            "compra, a Shopee confirma, você recebe. Simples assim. ✅\n#cashback #semmensalidade #shopee"
        ),
    },
    {
        "arquivo": "07-quanto-economizar.png",
        "legenda": (
            "Você não precisa mudar nada no seu jeito de comprar — só ganhar mais no final. 📈 Toda "
            "compra que você já ia fazer na Shopee pode voltar parte do dinheiro pro seu bolso. 💰\n"
            "Comece a economizar sem esforço — link na bio.\n#cashback #economia #shopee #dinheirodevolta"
        ),
    },
    {
        "arquivo": "08-cadastre-se.png",
        "legenda": (
            "🚀 Cadastro grátis, sem custo nenhum. Compra na Shopee do jeito que já compra e começa a "
            "receber cashback de verdade.\n👉 cash-b.com\n#cashback #shopee #cadastrese"
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
    post = _escolher_da_lista(POSTS_INSTITUCIONAIS, data)
    return {**post, "caminho": PASTA_POSTS_SEMEADURA / post["arquivo"]}


def tipo_de_conteudo_do_dia(data) -> list[str]:
    """Retorna os tipos de conteúdo previstos pro calendário nesse dia (pode ter mais de um)."""
    dia_semana = data.weekday()
    tipos = []

    if dia_semana in (SEGUNDA, TERCA, QUARTA, QUINTA, SEXTA):
        tipos.append(RegistroPublicacao.CONTEUDO_OFERTA_DIARIA)
    elif dia_semana == SABADO:
        tipos.append(RegistroPublicacao.CONTEUDO_DICA)
    elif dia_semana == DOMINGO:
        tipos.append(RegistroPublicacao.CONTEUDO_LEMBRETE)

    if dia_semana == QUARTA:
        tipos.append(RegistroPublicacao.CONTEUDO_INSTITUCIONAL)
    elif dia_semana == SEXTA:
        tipos.append(RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA)

    return tipos
