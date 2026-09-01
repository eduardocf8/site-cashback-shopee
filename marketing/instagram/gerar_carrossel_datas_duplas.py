"""Carrossel "Datas duplas: o dia em que tudo acontece junto".

9.9, 10.10, 11.11, 12.12 - a Shopee concentra cupom de desconto, cupom de frete grátis
e ofertas nas datas de número repetido. A cash-b entra com uma camada a mais nesses
dias: campanha de cashback aumentado (CASHBACK_MULTIPLICADOR_CAMPANHA em settings.py -
o pedido guarda o multiplicador que valia quando entrou, então quem comprou durante a
campanha continua com o valor maior mesmo depois que ela termina).

O carrossel não diz de quanto é o aumento de propósito: o multiplicador é configurável e
pode mudar de campanha para campanha. Número fixo na arte vira promessa que amarra a
próxima data.

IMPORTANTE ao postar: só publicar com a campanha de fato ligada (ou às vésperas dela).
O carrossel afirma que a cash-b aumenta o cashback nessas datas - postar sem a campanha
no ar transforma isso em promessa vazia.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    HIGHLIGHT,
    LIGHT_BG,
    MARCA,
    MUTED,
    SUCCESS,
    Slide,
    check_item,
    cta_pill,
    destaque,
    gerar,
    linha_valor,
    realce,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("datas duplas", BRAND_PRIMARY)}
    {titulo("9.9, 10.10, 11.11: por que essas datas mudam a conta", 30, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("o que são", "rgba(255,255,255,0.5)")}
    {titulo("Dia de número repetido é dia de campanha na Shopee.", 29)}
    {subtitulo(
        "Em vez de espalhar promoção pelo mês, a Shopee junta tudo em datas marcadas. "
        "É o dia em que mais coisa fica boa ao mesmo tempo.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("o que costuma aparecer", BRAND_PRIMARY)}
    {titulo("Tudo no mesmo dia", 28, DARK_BG)}
    <div style="margin-top:12px;">
        {check_item("Cupons de desconto", "Os valores mais altos do mês costumam sair aqui.", SUCCESS)}
        {check_item("Cupons de frete grátis", "Às vezes com valor mínimo mais baixo que o normal.", SUCCESS)}
        {check_item("Preços de campanha", "Produtos que passam o mês inteiro no mesmo preço mudam nesse dia.", SUCCESS)}
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("e tem mais uma camada", "rgba(255,255,255,0.75)")}
    {titulo(f"Nessas datas, a {MARCA} aumenta o cashback.", 32)}
    {subtitulo(
        "Campanha nossa, por cima de tudo que a Shopee já está fazendo. O cashback do "
        "dia sai acima do normal.",
        "rgba(255,255,255,0.9)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("as camadas na mesma compra", BRAND_PRIMARY)}
    {titulo("Uma coisa não anula a outra", 26, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Cupom de desconto", "Shopee", DARK_BG)}
        {linha_valor("Frete grátis", "Shopee", DARK_BG)}
        {linha_valor("Preço de campanha", "Shopee", DARK_BG)}
        {linha_valor("Cashback aumentado", "cash-b", SUCCESS)}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        As três primeiras baixam o que você paga. A última {realce("devolve")} parte do que você pagou.
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {titulo("O aumento vale pelas compras feitas durante a campanha.", 28)}
    {subtitulo(
        "O valor maior fica gravado no pedido. Quando a campanha acaba, quem comprou "
        "dentro dela continua com o cashback aumentado.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    {destaque("Comprar no dia certo muda o valor. Comprar depois, não.", escuro=True)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("como não perder", BRAND_PRIMARY)}
    {titulo("Guarde a lista para a data", 28, DARK_BG)}
    {subtitulo(
        "O que você já ia comprar de qualquer jeito rende mais se esperar o dia da "
        "campanha. Anote agora, compre lá.",
        MUTED, 305, 14.5)}
    {destaque("Avisamos aqui no perfil quando a campanha estiver no ar.", cor=HIGHLIGHT)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Cupom, frete e cashback aumentado, no mesmo dia.", 29)}
    {subtitulo("Só falta a sua lista estar pronta.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """9.9, 10.10, 11.11 — as datas duplas da Shopee são o dia em que tudo acontece junto. 🔥

É quando saem os cupons de desconto mais altos, os cupons de frete grátis e os preços de campanha. Em vez de promoção espalhada pelo mês, tudo cai no mesmo dia.

E nessas datas a cash-b entra com mais uma camada: campanha de cashback aumentado, por cima de tudo que a Shopee já está fazendo. Uma coisa não anula a outra — o cupom baixa o que você paga, o cashback devolve parte do que você pagou.

Detalhe que vale saber: o valor maior fica gravado no pedido. Comprou durante a campanha, o cashback aumentado é seu mesmo depois que ela acaba.

Vai comprar algo esse mês? Guarde para a data. Avisamos aqui quando estiver no ar.

#cashback #shopeebrasil #datasduplas #ofertasshopee #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-datas-duplas", SLIDES, LEGENDA, exportar="--export" in sys.argv)
