"""Carrossel "5 compras em que o cashback vale muito mais a pena".

O gancho é contraintuitivo de propósito: não são as compras mais caras. Com o teto de
R$ 10 por produto (CASHBACK_MAXIMO_POR_PRODUTO), o percentual cheio de 1,6% só rende
integralmente até R$ 625 - acima disso o valor trava. Falar isso abertamente é melhor
que deixar a pessoa descobrir sozinha depois de uma compra cara.

O ticket médio da Shopee é R$ 84 (pesquisa Klavi 2025), bem abaixo do teto, então na
prática ele quase nunca morde - mas quem vai comprar um item caro merece saber antes.
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
    subtitulo,
    tag_label,
    titulo,
)


def item(numero, titulo_item, texto, exemplo):
    return f"""
    {tag_label(f"{numero} de 5", BRAND_PRIMARY)}
    {titulo(titulo_item, 28, DARK_BG)}
    {subtitulo(texto, MUTED, 305, 14.5)}
    <div style="margin-top:18px; padding:12px 16px; background:#fff; border-left:3px solid {SUCCESS};
                border-radius:6px; font-family:Familjen; font-size:13px; color:{DARK_BG}; line-height:1.5;">
        {exemplo}
    </div>
    """


SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("guia rápido", BRAND_PRIMARY)}
    {titulo("5 compras em que o cashback vale muito mais a pena", 32, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("spoiler", "rgba(255,255,255,0.5)")}
    {titulo("Não são as mais caras.", 32)}
    {subtitulo(
        "O cashback tem teto de R$ 10 por produto. Ou seja: acima de R$ 625, "
        "o valor trava. É justamente por isso que a lista é outra.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, item(
        "1", "O que você compra todo mês",
        "Limpeza, higiene, item de casa. Sozinha, cada compra é pequena, mas ela se "
        "repete o ano inteiro — e o cashback se repete junto.",
        "12 compras por ano rendem 12 vezes.",
    ), True),

    Slide(LIGHT_BG, item(
        "2", "A faixa de R$ 100 a R$ 600",
        "É onde o percentual rende inteiro, sem chegar perto do teto. O ponto ideal "
        "para eletrônicos, roupas, itens pra casa.",
        "Uma compra de R$ 600 rende o percentual cheio.",
    ), True),

    Slide(LIGHT_BG, item(
        "3", "Carrinho com vários produtos",
        "O teto de R$ 10 é por produto, não por pedido. Um carrinho com cinco itens "
        "diferentes tem cinco cashbacks separados.",
        "5 produtos = 5 cashbacks, não 1.",
    ), True),

    Slide(LIGHT_BG, item(
        "4", "Presentes e lista de fim de ano",
        "Época de comprar várias coisas de uma vez para várias pessoas. Cada item "
        "da lista gera cashback.",
        "A lista toda te dá dinheiro de volta.",
    ), True),

    Slide(LIGHT_BG, item(
        "5", "A compra que você já decidiu fazer",
        "A melhor de todas. Você já ia comprar de qualquer jeito — o cashback é "
        "lucro puro em cima de uma decisão que já estava tomada.",
        "Zero esforço a mais, dinheiro de volta.",
    ), True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Comece pela próxima compra.", 30)}
    {subtitulo("É hora de receber dinheiro de volta.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Na Shopee, não são as compras mais caras que rendem mais cashback — e o motivo surpreende. 📌

Tem teto de R$ 10 por produto, então acima de R$ 625 o valor trava. Por isso a lista das melhores é outra: as que se repetem todo mês, as da faixa de R$ 100 a R$ 600 e o carrinho cheio (o teto é por produto, não por pedido — 5 itens são 5 cashbacks).

Salve para consultar antes da próxima compra na Shopee.

#cashback #shopeebrasil #achadinhosshopee #economizar #comprasinteligentes"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-05-melhores-compras", SLIDES, LEGENDA, exportar="--export" in sys.argv)
