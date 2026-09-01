"""Carrossel "Existem 2 formas de comprar pela cash-b".

Explica venda direta x venda indireta (regras em paginas/templates/regras_cashback.html).
As duas geram cashback, mas não em igual medida: a indireta rende menos - o piso
garantido é menor (CASHBACK_MINIMO_VENDA_INDIRETA x CASHBACK_MINIMO_VENDA_DIRETA em
settings.py) e ela não alcança as campanhas de comissão extra da Shopee, que só valem
quando o item comprado bate com o link convertido.

Por isso o carrossel recomenda a venda direta em vez de tratar as duas como equivalentes:
dizer que "cada uma serve a um momento" esconderia da pessoa que um dos caminhos paga
menos - informação que é dela, não nossa.

Nota de voz (VOZ.md): o cashback base é sempre afirmativo ("gera", "volta"), mas o bônus
de campanha é de fato condicional - por isso "caso esteja ativa" está certo aqui.
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
    {titulo(f"Existem 2 formas de comprar pela {MARCA}", 33, DARK_BG)}
    {subtitulo("Todas geram cashback, porém uma delas é menor.", MUTED, 280, 15)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("forma 1", "rgba(255,255,255,0.5)")}
    {titulo("Venda indireta", 32)}
    {subtitulo(
        'Você clica em "Ir pra Shopee" e compra o que quiser. Não precisa escolher o '
        "produto antes — entra na loja e navega normalmente.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    {destaque("A venda indireta dá menos cashback que a direta.", escuro=True)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("forma 2", BRAND_PRIMARY)}
    {titulo("Venda direta", 32, DARK_BG)}
    {subtitulo(
        "Você converte o link de um produto específico ou abre ele pela vitrine de "
        "ofertas do site e faz a compra.",
        MUTED, 300, 14.5)}
    {destaque("Assim você ganha ainda mais cashback.", cor=SUCCESS)}
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("a diferença", BRAND_PRIMARY)}
    {titulo("Ganhando mais cashback", 30, DARK_BG)}
    {subtitulo(
        "Alguns produtos têm campanha de comissão extra e somente a venda direta tem "
        "acesso a essas campanhas. Quando a comissão aumenta, seu cashback também "
        "aumenta.",
        MUTED, 305, 14)}
    <div style="margin-top:16px;">
        {caso("Venda indireta", "Cashback normal, porém reduzido")}
        {caso("Venda direta", "Cashback normal + bônus de campanha (caso esteja ativa)")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("na prática", "rgba(255,255,255,0.5)")}
    {titulo("Qual usar em cada situação", 29)}
    <div style="margin-top:16px;">
        {caso("Você já sabe o que vai comprar", "Converta o link do produto ou abra ele pela vitrine", escuro=True)}
        {caso("Você vai olhar, comparar, encher o carrinho", 'Entre por "Ir pra Shopee"', escuro=True)}
    </div>
    {destaque(
        "Nesse último caso, você ainda tem a opção de, após escolher os produtos, "
        "converter os links diretamente no site para ganhar mais cashback.",
        escuro=True)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Os dois caminhos te dão dinheiro de volta.", 30)}
    {subtitulo(
        "Porém, é possível maximizar seus ganhos escolhendo sempre a venda direta. "
        "Lembre-se disso na próxima compra.",
        "rgba(255,255,255,0.9)", 300, 14.5)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Existem 2 formas de comprar na Shopee pela cash-b — e uma delas rende menos. 🛒

Venda indireta: você clica em "Ir pra Shopee" e compra o que quiser, sem escolher nada antes. Gera cashback, só que reduzido.

Venda direta: você converte o link do produto ou abre ele pela vitrine de ofertas do site e faz a compra. Rende mais, e é a única que alcança as campanhas de comissão extra da Shopee.

E dá para juntar as duas coisas: mesmo entrando para navegar, depois de escolher os produtos você pode voltar e converter os links no site antes de fechar a compra.

#cashback #shopeebrasil #dinheirodevolta #economizar #comprasonline"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-07-direta-indireta", SLIDES, LEGENDA, exportar="--export" in sys.argv)
