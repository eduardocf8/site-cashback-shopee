"""Carrossel "O erro que quase todo mundo comete comprando na Shopee".

Diferente do carrossel de gasto anual (que é um exercício pessoal, "descubra o seu
número"), esse aqui explica o mecanismo: a comissão de afiliado existe em toda venda
e sempre vai para alguém. O "erro" é nunca ter sido esse alguém.

Números: pesquisa Klavi 2025 - 18 pedidos/ano na Shopee, ticket médio R$ 83,88. O piso
de 1,6% vem de SHOPEE_CASHBACK_PERCENTUAL (20%) x SHOPEE_COMISSAO_VENDA_DIRETA (8%).
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
    numero_gigante,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(DARK_BG, f"""
    {tag_label("o erro", "rgba(255,255,255,0.5)")}
    {titulo("Você não está perdendo dinheiro.", 32)}
    {subtitulo("Está deixando de ganhar. E a diferença é enorme.", "rgba(255,255,255,0.7)", 300, 15)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("Toda venda na Shopee paga uma comissão.", 28, DARK_BG)}
    {subtitulo(
        "É assim que blogs de review, páginas de achadinhos e canais de oferta se "
        "sustentam. A Shopee paga quem levou o cliente até o produto.",
        MUTED, 305, 14.5)}
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("na sua compra", "rgba(255,255,255,0.5)")}
    {titulo("Quem recebeu essa comissão?", 30)}
    {subtitulo(
        "Alguém que você nunca viu. Em toda compra sua, dos últimos anos, "
        "esse dinheiro foi para outra pessoa.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("o tamanho disso", BRAND_PRIMARY)}
    {titulo("Quanto poderia ter sido seu", 24, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Comprando R$ 100 por mês", "R$ 19/ano")}
        {linha_valor("Comprando R$ 300 por mês", "R$ 57/ano")}
        {linha_valor("Comprando R$ 500 por mês", "R$ 96/ano")}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        Calculado sobre 1,6%, que é o mínimo que a cash-b devolve.
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("e esse é o piso", "rgba(255,255,255,0.75)")}
    {numero_gigante("1,6%", "É o mínimo. Muitos produtos têm comissão extra e devolvem bem mais que isso.", "#fff", "rgba(255,255,255,0.85)")}
    """, False),

    Slide(LIGHT_BG, f"""
    {titulo("Não dá para recuperar o que já passou.", 28, DARK_BG)}
    {subtitulo("Dá para parar de deixar passar.", MUTED, 300, 15)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Da próxima vez, a comissão volta para você.", 29)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = (
    "Em toda compra na Shopee alguém recebe uma comissão. Nas suas, nunca foi você. "
    "Dá para mudar isso a partir da próxima. 👀"
)

if __name__ == "__main__":
    import sys

    gerar("carrossel-comissao-invisivel", SLIDES, LEGENDA, exportar="--export" in sys.argv)
