"""Carrossel "O que a Shopee ganha, o que você ganha".

Explica o modelo de negócio sem citar concorrente e, de propósito, sem citar o
percentual exato que a cash-b repassa (SHOPEE_CASHBACK_PERCENTUAL em settings.py) -
esse número é configurável e nunca apareceu em nenhum carrossel anterior (os outros só
mostram o piso final em cashback pro usuário, nunca a divisão da comissão em si). Dar
esse número de cabeça, sem o dono confirmar que pode ser público, seria expor um
detalhe interno que ele não pediu para revelar.

O ângulo é estrutural: existe uma comissão, uma parte fica com a cash-b (operação, Pix,
suporte) e outra parte volta pro usuário - sem dizer qual é maior.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MUTED,
    Slide,
    caso,
    cta_pill,
    destaque,
    gerar,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("por dentro do modelo", BRAND_PRIMARY)}
    {titulo("O que a Shopee ganha, o que você ganha", 29, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("Toda venda que vem por um link de afiliado paga uma comissão.", 27)}
    {subtitulo(
        "A Shopee paga essa comissão pra quem levou o cliente até o produto — é "
        "assim que ela vende mais sem pagar por anúncio em cada venda.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("os dois lados", BRAND_PRIMARY)}
    {titulo("Quem ganha o quê", 28, DARK_BG)}
    <div style="margin-top:16px;">
        {caso("A Shopee", "Vende mais, pagando comissão só pra quem de fato trouxe a venda.")}
        {caso("A cash-b", "Recebe essa comissão por ter trazido você até o produto.")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("e você?", "rgba(255,255,255,0.5)")}
    {titulo("A cash-b devolve parte dessa comissão pra quem comprou.", 27)}
    {subtitulo(
        "Uma parte fica com a cash-b, pra manter o site, o Pix e o suporte "
        "funcionando. A outra parte é o seu cashback.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {titulo("Ninguém paga mais por isso.", 28, DARK_BG)}
    {subtitulo(
        "O preço do produto não muda pra você nem pra Shopee. A comissão já "
        "existia antes de qualquer cashback — a diferença é que, com a cash-b, "
        "uma parte dela chega até você.",
        MUTED, 305, 14.5)}
    {destaque("Sem mensalidade, sem taxa escondida: você recebe parte de um dinheiro que, sem a cash-b, ficaria todo com outra empresa.")}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Nenhum lado perde. Você só passa a ganhar também.", 28)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Sem rodeio: de onde vem o dinheiro que cai na sua conta? 🔍

Toda venda que passa por um link de afiliado paga uma comissão — é assim que a Shopee vende mais sem gastar com anúncio em cada venda, e é assim que a cash-b existe. Uma parte dessa comissão fica com a cash-b, pra manter o site, o Pix e o suporte no ar. A outra parte volta pra quem comprou, como cashback.

O preço do produto não muda pra ninguém. A comissão já existia antes — a diferença é que, com a cash-b, parte dela chega até você em vez de ficar só com outra empresa.

#cashback #shopeebrasil #transparencia #dinheirodevolta #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-15-shopee-ganha-voce-ganha", SLIDES, LEGENDA, exportar="--export" in sys.argv)
