"""Carrossel "5 coisas que fazem você perder o cashback".

Conteúdo de utilidade pura, tirado de paginas/templates/regras_cashback.html (o que
cancela o cashback) mais o caso mais óbvio de todos: comprar sem passar pelo link.

O slide 2 explica o mecanismo antes da lista de propósito. Sem entender que o cashback
vem de uma comissão que a Shopee só paga se registrar quem indicou a venda, os cinco
itens viram regra arbitrária; com o mecanismo na cabeça, todos eles fazem sentido
sozinhos e a pessoa consegue julgar casos que a lista não cobre.

Uma marca que avisa onde você pode perder passa mais confiança do que uma que só fala
do que você ganha - mesma lógica do carrossel "não é motivo".
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
    destaque,
    gerar,
    numbered_step,
    subtitulo,
    tag_label,
    titulo,
)


def item(numero, titulo_item, texto, saida):
    """Um erro por slide: o problema em cima, o que fazer no lugar embaixo. A caixa
    verde existe para o carrossel não virar só uma lista de coisas ruins."""
    return f"""
    {tag_label(f"{numero} de 5", BRAND_PRIMARY)}
    {titulo(titulo_item, 28, DARK_BG)}
    {subtitulo(texto, MUTED, 305, 14.5)}
    <div style="margin-top:18px; padding:12px 16px; background:#fff; border-left:3px solid {SUCCESS};
                border-radius:6px; font-family:Familjen; font-size:13px; color:{DARK_BG}; line-height:1.5;">
        {saida}
    </div>
    """


SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("guia rápido", BRAND_PRIMARY)}
    {titulo("5 coisas que fazem você perder o cashback", 32, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("antes da lista", "rgba(255,255,255,0.5)")}
    {titulo("De onde vem o dinheiro", 30)}
    {subtitulo(
        "A Shopee paga uma comissão para quem indicou a venda. A cash-b devolve parte "
        "dessa comissão para você. Se a Shopee não registrar que a indicação foi da "
        "cash-b, não tem comissão — e sem comissão não tem cashback.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    {destaque("Os cinco itens da lista são as formas de esse registro se perder.", escuro=True)}
    """, False),

    Slide(LIGHT_BG, item(
        "1", "Comprar sem passar pelo link",
        "Abrir o app da Shopee direto e comprar por lá. A compra acontece, mas nada "
        "liga ela à cash-b — então não tem comissão para devolver.",
        'Comece sempre pela cash-b: pelo link do produto ou por "Ir pra Shopee".',
    ), True),

    Slide(LIGHT_BG, item(
        "2", "Passar por outro link de afiliado",
        "Se você clica no link da cash-b e, antes de fechar a compra, clica no link de "
        "outro site ou app de cashback, a comissão pode acabar indo para o outro.",
        "Escolha um caminho e vá até o fim por ele.",
    ), True),

    Slide(LIGHT_BG, item(
        "3", "Deixar a compra parada por dias",
        "Quanto mais tempo passa entre o clique e a finalização, mais chance de outro "
        "link entrar no meio — um anúncio, um grupo de ofertas, outro app.",
        "Clicou e decidiu? Feche a compra.",
    ), True),

    Slide(LIGHT_BG, item(
        "4", "Cancelar ou devolver a compra",
        "Cashback vem da comissão de uma venda concluída. Pedido cancelado ou "
        "devolvido não gera comissão para ninguém.",
        "Normal e justo: o dinheiro da compra volta inteiro para você.",
    ), True),

    Slide(LIGHT_BG, item(
        "5", "O pagamento não ser confirmado",
        "Boleto que vence, PIX que não é pago, cartão recusado. Para a Shopee, esse "
        "pedido nunca virou venda.",
        "Confira se o pagamento passou antes de contar com o cashback.",
    ), True),

    Slide(LIGHT_BG, f"""
    {tag_label("o resumo", BRAND_PRIMARY)}
    {titulo("Três hábitos resolvem os cinco", 26, DARK_BG)}
    <div style="margin-top:10px;">
        {numbered_step("01", "Comece pela cash-b", "O link é o que liga a compra a você.")}
        {numbered_step("02", "Não desvie no caminho", "Nenhum outro link de afiliado no meio.")}
        {numbered_step("03", "Feche a compra", "Decidiu, finaliza. Sem deixar para depois.")}
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("O resto é a Shopee confirmar e o dinheiro cair.", 30)}
    {subtitulo("Salve para conferir antes da próxima compra.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Cashback na Shopee tem cinco jeitos comuns de escapar — e quase todos dá para evitar. 📌

O cashback vem de uma comissão que a Shopee paga para quem indicou a venda. Se ela não registra que a indicação foi da cash-b, não tem comissão para devolver. Todos os itens da lista são formas desse registro se perder.

Os três hábitos que resolvem: comece pela cash-b, não clique no link de outro app de cashback no meio do caminho, e feche a compra sem deixar para depois.

Salve para conferir antes da próxima compra.

#cashback #shopeebrasil #dinheirodevolta #dicasdecompra #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-08-perder-cashback", SLIDES, LEGENDA, exportar="--export" in sys.argv)
