"""Carrossel "O erro que quase todo mundo comete comprando na Shopee".

Diferente do carrossel de gasto anual (que é um exercício pessoal, "descubra o seu
número"), esse aqui explica o mecanismo: a comissão de afiliado existe em toda venda
e sempre vai para alguém. O "erro" é nunca ter sido esse alguém.

Os valores da escala são conta própria (gasto mensal hipotético x 1,6%), não dado de
pesquisa - por isso nenhum slide leva crédito de fonte, diferente do carrossel de gasto
anual. O piso de 1,6% vem de SHOPEE_CASHBACK_PERCENTUAL (20%) x
SHOPEE_COMISSAO_VENDA_DIRETA (8%).
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
    caso,
    cta_pill,
    destaque,
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
    {subtitulo("Está deixando de ganhar. E a diferença é enorme.", "rgba(255,255,255,0.7)", 280, 15)}
    """, False, capa=True),

    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("Venda que passa por link de afiliado paga comissão.", 27, DARK_BG)}
    {subtitulo(
        "A Shopee paga uma parte para quem levou o cliente até o produto. É assim "
        "que blogs de review, páginas de achadinhos e canais de oferta se sustentam.",
        MUTED, 305, 14.5)}
    """, True),

    # Sem link de afiliado não existe comissão nenhuma - a Shopee simplesmente fica
    # com essa parte. Dizer que em toda compra o dinheiro "foi para outra pessoa"
    # seria falso para quem compra entrando direto no app.
    Slide(DARK_BG, f"""
    {tag_label("na sua compra", "rgba(255,255,255,0.5)")}
    {titulo("E quando você compra sem link nenhum?", 26)}
    <div style="margin-top:12px;">
        {caso("Entrando direto no app da Shopee", "A comissão nem chega a existir.", escuro=True)}
        {caso("Entrando pelo link de outra pessoa", "Ela recebe, você não.", escuro=True)}
    </div>
    {destaque("<b>Nunca sobrou nada para você</b> — e você é quem pagou a conta.", escuro=True)}
    """, False),

    # Mesmo tratamento do carrossel de gasto anual: "no mínimo" no título, "+" colado
    # no valor e caixa de destaque. Aqui o destaque fica curto de propósito - quem
    # explica o piso é o slide seguinte, que abre com o 1,6% em corpo gigante.
    Slide(LIGHT_BG, f"""
    {tag_label("o tamanho disso", BRAND_PRIMARY)}
    {titulo("O mínimo que poderia ter sido seu", 24, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Comprando R$ 100 por mês", "R$ 19+ /ano")}
        {linha_valor("Comprando R$ 300 por mês", "R$ 57+ /ano")}
        {linha_valor("Comprando R$ 500 por mês", "R$ 96+ /ano")}
    </div>
    {destaque("<b>Isso é o piso, não o teto.</b> E o piso tem nome — arrasta para ver.")}
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

LEGENDA = """Quando a compra na Shopee passa por um link de afiliado, alguém recebe uma comissão. 👀

Nas suas, nunca foi você — e se você entrou direto no app, ela nem chegou a existir.

Dá para mudar isso a partir da próxima compra.

#cashback #shopeebrasil #economizar #dinheirodevolta #comprasonline"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-comissao-invisivel", SLIDES, LEGENDA, exportar="--export" in sys.argv)
