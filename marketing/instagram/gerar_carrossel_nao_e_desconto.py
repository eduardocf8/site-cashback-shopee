"""Carrossel "Cashback não é desconto".

Confusão comum: achar que o cashback abate o preço na hora do pagamento, igual um
cupom. Esse carrossel separa os dois mecanismos - o motivo de o cashback chegar depois
é o mesmo já explicado no carrossel-02 (a comissão só existe depois que a Shopee
confirma a venda), então aqui só reaparece em uma frase, sem reexplicar tudo.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MARCA,
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
    {tag_label("tira a dúvida", BRAND_PRIMARY)}
    {titulo("Cashback não é desconto. É dinheiro que volta depois.", 27, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("O preço que você vê no carrinho é o preço da Shopee.", 28)}
    {subtitulo(
        "O cashback não entra nessa conta. Não existe campo de cashback no "
        "checkout, porque ele não muda o valor da compra.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("as duas coisas são diferentes", BRAND_PRIMARY)}
    {titulo("Desconto x cashback", 28, DARK_BG)}
    <div style="margin-top:16px;">
        {caso("Desconto (cupom)", "Abate na hora. O valor que você paga já sai menor.")}
        {caso("Cashback", "Não abate nada na hora. Uma parte volta depois, separada da compra.")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("por que chega depois", "rgba(255,255,255,0.5)")}
    {titulo("A comissão só existe depois que a venda é confirmada.", 27)}
    {subtitulo(
        f"O cashback vem dessa comissão. Por isso ele nunca entra na hora de "
        f"pagar — a {MARCA} só sabe o valor exato depois que a Shopee confirma o pedido.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {titulo("Uma coisa não troca a outra", 27, DARK_BG)}
    {subtitulo(
        "O cupom baixa o preço. O cashback devolve parte do que você pagou. "
        "Elas somam — nenhuma substitui a outra.",
        MUTED, 300, 14.5)}
    {destaque("Por isso vale usar cupom e comprar pela cash-b na mesma compra: as duas coisas acontecem juntas.")}
    """, True),

    Slide(DARK_BG, f"""
    {titulo("Então, quando o dinheiro aparece?", 28)}
    {subtitulo(
        "Depois que a Shopee valida o pedido e o prazo de liberação passa, o "
        "valor cai disponível no seu painel pra sacar via Pix. Sempre depois, "
        "sempre separado da compra.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Pague o preço de sempre. Receba uma parte dele de volta.", 28)}
    {subtitulo("Só muda quando o dinheiro aparece — não quanto você paga.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Cashback não é desconto — e misturar os dois é a confusão mais comum sobre como isso funciona. 💭

O preço que você vê no carrinho é o preço da Shopee. O cashback não abate nada ali, porque ele não é um cupom: é uma parte da comissão que a Shopee paga depois que confirma a venda, e só existe depois disso.

Por isso o cupom e o cashback não competem entre si — eles somam. Um baixa o que você paga, o outro devolve parte do que você já pagou, separado e depois.

#cashback #shopeebrasil #comoeconomizar #dinheirodevolta #comprasonline"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-13-nao-e-desconto", SLIDES, LEGENDA, exportar="--export" in sys.argv)
