"""Carrossel "Dois jeitos de comprar pela cash-b".

Explica venda direta x venda indireta (regras em paginas/templates/regras_cashback.html)
sem tratar uma como certa e a outra como errada: as duas geram cashback, e cada uma serve
a um momento de compra diferente. O que muda é o acesso ao bônus de comissão extra, que
só existe na venda direta.

Nota de voz (VOZ.md): o cashback base é sempre afirmativo ("gera", "volta"), mas o bônus
de campanha é de fato condicional - por isso "pode render mais" está certo aqui.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MARCA,
    MUTED,
    SUCCESS,
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
    {tag_label("cash-b explica", BRAND_PRIMARY)}
    {titulo(f"Tem dois jeitos de comprar pela {MARCA}", 33, DARK_BG)}
    {subtitulo("Os dois geram cashback. A diferença é outra.", MUTED, 280, 15)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("jeito 1", "rgba(255,255,255,0.5)")}
    {titulo("Venda indireta", 32)}
    {subtitulo(
        'Você clica em "Ir pra Shopee" e compra o que quiser. Não precisa escolher o '
        "produto antes — entra na loja e navega normalmente.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    {destaque("Toda compra gera cashback do mesmo jeito.", escuro=True, cor=SUCCESS)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("jeito 2", BRAND_PRIMARY)}
    {titulo("Venda direta", 32, DARK_BG)}
    {subtitulo(
        "Você converte o link de um produto específico ou abre ele pela vitrine de "
        "ofertas — e compra aquele produto.",
        MUTED, 300, 14.5)}
    {destaque("Também gera cashback, e ainda abre uma porta a mais.", cor=SUCCESS)}
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("a diferença", BRAND_PRIMARY)}
    {titulo("A porta a mais", 30, DARK_BG)}
    {subtitulo(
        "A Shopee às vezes roda campanha de comissão extra em produtos específicos. "
        "Quando isso acontece, o cashback daquele produto sobe.",
        MUTED, 305, 14.5)}
    <div style="margin-top:16px;">
        {caso("Venda indireta", "Cashback normal, sempre")}
        {caso("Venda direta", "Cashback normal + o bônus, quando o produto está em campanha")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("na prática", "rgba(255,255,255,0.5)")}
    {titulo("Qual usar em cada situação", 29)}
    <div style="margin-top:16px;">
        {caso("Você já sabe o que vai comprar", "Converta o link do produto ou abra ele pela vitrine", escuro=True)}
        {caso("Você vai olhar, comparar, encher o carrinho", 'Entre por "Ir pra Shopee"', escuro=True)}
    </div>
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Os dois caminhos te dão dinheiro de volta.", 30)}
    {subtitulo(
        "Um deles pode render mais quando a Shopee está com campanha no produto. "
        "Saber disso já muda a próxima compra.",
        "rgba(255,255,255,0.9)", 300, 14.5)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Tem dois jeitos de comprar na Shopee pela cash-b — e os dois geram cashback. 🛒

Venda indireta: você clica em "Ir pra Shopee" e compra o que quiser, sem escolher nada antes.

Venda direta: você converte o link do produto ou abre ele pela vitrine de ofertas e compra aquele produto. Aqui entra o bônus das campanhas de comissão extra da Shopee, que só existe nesse caminho.

Resumindo: se você já sabe o que vai comprar, vale converter o link. Se vai só navegar, entra pelo botão.

#cashback #shopeebrasil #dinheirodevolta #economizar #comprasonline"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-direta-indireta", SLIDES, LEGENDA, exportar="--export" in sys.argv)
