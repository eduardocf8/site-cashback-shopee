"""Carrossel "Black Friday: o que muda na conta".

Mesma lógica do carrossel-11-datas-duplas (campanha de cashback aumentado por cima do
que a Shopee já faz), mas dedicado à Black Friday especificamente: é o maior evento de
vendas do ano na Shopee, dura a semana toda (não só a sexta) e tende a trazer mais
produtos com campanha de comissão extra do vendedor - o que também tende a aumentar o
que a cash-b consegue devolver nesses produtos.

Por isso, igual ao carrossel de datas duplas, o valor do aumento não aparece de
propósito: o multiplicador é configurável (ver CampanhaCashback em pedidos/models.py) e
pode mudar. Número fixo na arte vira promessa que não dá pra garantir todo ano.

IMPORTANTE ao postar: só publicar com a campanha de fato ligada (ou às vésperas dela).
O carrossel afirma que a cash-b aumenta o cashback nessa semana - postar sem a campanha
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
    {tag_label("black friday", BRAND_PRIMARY)}
    {titulo("Black Friday: o que muda na conta", 31, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("o que é", "rgba(255,255,255,0.5)")}
    {titulo("Não é um dia. É a semana toda.", 29)}
    {subtitulo(
        "A Shopee espalha as ofertas durante os dias que antecedem a sexta e vai "
        "aumentando até o pico. O nome marca um dia, mas a janela é bem maior.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("o que costuma aparecer", BRAND_PRIMARY)}
    {titulo("Tudo fica maior nessa semana", 27, DARK_BG)}
    <div style="margin-top:12px;">
        {check_item("Cupons mais altos que o normal", "Os valores do mês inteiro costumam ficar menores do que os dessa semana.", SUCCESS)}
        {check_item("Frete grátis mais fácil de alcançar", "Valor mínimo mais baixo que o de um dia comum.", SUCCESS)}
        {check_item("Mais produtos com comissão extra", "Vendedores aumentam a comissão de afiliado pra aparecer mais nessa semana.", SUCCESS)}
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("e tem mais uma camada", "rgba(255,255,255,0.75)")}
    {titulo(f"Nessa semana, a {MARCA} também costuma aumentar o cashback.", 30)}
    {subtitulo(
        "Campanha nossa, por cima de tudo que a Shopee já está fazendo. O cashback "
        "da semana sai acima do normal.",
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
        "O valor maior fica gravado no pedido. Mesmo depois que a Black Friday "
        "passar, quem comprou dentro da janela continua com o cashback aumentado.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("como não perder", BRAND_PRIMARY)}
    {titulo("Continua valendo a regra de sempre", 27, DARK_BG)}
    {subtitulo(
        "Clique pelo link da cash-b antes de fechar a compra, mesmo na Black "
        "Friday — é isso que liga a venda a você.",
        MUTED, 305, 14.5)}
    {destaque("Avisamos aqui no perfil quando a campanha estiver no ar.", cor=HIGHLIGHT)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Cupom, frete grátis e cashback aumentado — tudo na mesma semana.", 27)}
    {subtitulo("Já vai separando a lista.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Black Friday na Shopee não é um dia só — é a semana toda ficando melhor até o pico. 🛍️

É quando saem os cupons mais altos do ano, o frete grátis fica mais fácil de alcançar e aparecem mais produtos com comissão extra de vendedor.

E nessa semana a cash-b entra com mais uma camada: campanha de cashback aumentado, por cima de tudo que a Shopee já está fazendo. Uma coisa não anula a outra — o cupom baixa o que você paga, o cashback devolve parte do que você pagou.

Detalhe que vale saber: o valor maior fica gravado no pedido. Comprou durante a campanha, o cashback aumentado é seu mesmo depois que a semana passar.

Continua valendo a regra de sempre: clique pela cash-b antes de fechar a compra. Avisamos aqui quando a campanha estiver no ar.

#blackfriday #cashback #shopeebrasil #ofertasshopee #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-12-black-friday", SLIDES, LEGENDA, exportar="--export" in sys.argv)
