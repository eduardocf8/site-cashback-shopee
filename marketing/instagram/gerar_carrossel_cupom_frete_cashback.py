"""Carrossel "Cupom, frete grátis ou cashback: qual economiza mais?".

A virada do carrossel é o slide 5: a pergunta do título está errada de propósito.
Cupom e frete grátis não competem com cashback - os três entram na mesma compra.
Quem chega achando que precisa escolher sai sabendo que pode somar.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    HIGHLIGHT,
    LIGHT_BG,
    MUTED,
    SUCCESS,
    Slide,
    cta_pill,
    gerar,
    linha_valor,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("cash-b explica", BRAND_PRIMARY)}
    {titulo("Cupom, frete grátis ou cashback: qual economiza mais?", 32, DARK_BG)}
    {subtitulo("A resposta não é a que você está pensando.", MUTED, 280, 15)}
    """, True, capa=True),

    Slide(LIGHT_BG, f"""
    {tag_label("opção 1", BRAND_PRIMARY)}
    {titulo("Cupom", 30, DARK_BG)}
    {subtitulo(
        "Desconto na hora, direto no valor. O melhor dos três quando existe — "
        "o problema é justamente esse: só quando existe, e só naquela compra.",
        MUTED, 300, 14.5)}
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("opção 2", BRAND_PRIMARY)}
    {titulo("Frete grátis", 30, DARK_BG)}
    {subtitulo(
        "Economiza o envio, que às vezes custa mais que o produto. Mas depende "
        "de valor mínimo e de vendedor participante.",
        MUTED, 300, 14.5)}
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("opção 3", "rgba(255,255,255,0.5)")}
    {titulo("Cashback", 30)}
    {subtitulo(
        "Volta em dinheiro na sua conta. Não depende de cupom disponível nem de "
        "valor mínimo: vale em toda compra, sempre.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("a virada", "rgba(255,255,255,0.75)")}
    {titulo("Você não precisa escolher.", 34)}
    {subtitulo(
        "Os três funcionam na mesma compra. Cupom e frete grátis são da Shopee. "
        "O cashback é da cash-b — um não anula o outro.",
        "rgba(255,255,255,0.9)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("na prática", BRAND_PRIMARY)}
    {titulo("Os três na mesma compra", 25, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Produto", "R$ 120", DARK_BG)}
        {linha_valor("Cupom da Shopee", "− R$ 15", DARK_BG)}
        {linha_valor("Frete", "grátis", DARK_BG)}
        {linha_valor("Cashback da cash-b", "+ 1,6%", SUCCESS)}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        O cupom vale uma vez. O cashback vale em toda compra, para sempre.
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Já que dá para usar tudo, use tudo.", 30)}
    {subtitulo("O cashback é a parte que ninguém lembra de ativar.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Muita gente acha que na Shopee precisa escolher entre cupom, frete grátis e cashback. Não precisa — os três entram na mesma compra. 🛒

Cupom e frete grátis são da Shopee. O cashback é da cash-b. Um não anula o outro.

Salve para lembrar na hora da próxima compra.

#cashback #shopeebrasil #cupomdedesconto #economizar #comprasonline"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-cupom-frete-cashback", SLIDES, LEGENDA, exportar="--export" in sys.argv)
