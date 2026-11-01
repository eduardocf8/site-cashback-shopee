"""Carrossel "A linha do tempo de um cashback real".

Ponto central (pedido do dono em 01/11/2026): o que conta pra calcular o prazo de
liberação é a data de VALIDAÇÃO do pedido, não a data da compra - ver
calcular_data_prevista_liberacao em pedidos/services.py (libera no dia 1º do 2º mês
seguinte ao mês da validação) e a mesma explicação em
paginas/templates/paginas/regras_cashback.html.

O exemplo usa compra e validação em meses DIFERENTES de propósito (28/10 comprado,
3/11 validado) - se os dois caíssem no mesmo mês, o exemplo não provaria nada: o ponto
só fica claro quando mudar o mês da validação muda o mês da liberação. O motivo do
prazo (por que não libera na hora) é o mesmo texto de regras_cashback.html: acompanha o
prazo que a própria Shopee usa pra confirmar definitivamente a comissão.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MUTED,
    Slide,
    caso,
    cta_pill,
    destaque,
    gerar,
    numbered_step,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("A linha do tempo de um cashback, do clique ao Pix", 27, DARK_BG)}
    """, True, capa=True),

    Slide(LIGHT_BG, f"""
    {tag_label("os três status", BRAND_PRIMARY)}
    {titulo("Todo pedido passa por aqui", 27, DARK_BG)}
    <div style="margin-top:10px;">
        {numbered_step("01", "Pendente", "Comprou. A Shopee ainda está processando o pedido.")}
        {numbered_step("02", "Validado", "A Shopee confirmou a venda. É essa data que conta a partir daqui.")}
        {numbered_step("03", "Liberado", "Saldo liberado — já dá para sacar via Pix.")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {titulo("O que importa pra contar o prazo é a validação — não a compra.", 27)}
    {subtitulo(
        "Pode levar dias entre comprar e a Shopee validar o pedido. O relógio do "
        "prazo de liberação só começa a contar na validação.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("exemplo real", BRAND_PRIMARY)}
    {titulo("Um caso para ver na prática", 26, DARK_BG)}
    <div style="margin-top:14px;">
        {caso("Comprou", "28 de outubro")}
        {caso("Shopee validou", "3 de novembro")}
        {caso("Libera", "1º de janeiro")}
    </div>
    {destaque("<b>O mês que conta é novembro (validação), não outubro (compra).</b> Por isso a liberação cai em janeiro — não em dezembro.")}
    """, True),

    Slide(DARK_BG, f"""
    {titulo("A regra: libera no dia 1º do 2º mês depois do mês da validação.", 26)}
    {subtitulo(
        "Validou em janeiro? Libera em 1º de março. Validou em novembro? Libera "
        "em 1º de janeiro. Sempre contando a partir do mês da validação.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("por que esse prazo existe", BRAND_PRIMARY)}
    {titulo("Não é um número que a cash-b escolhe", 26, DARK_BG)}
    {subtitulo(
        "Esse prazo acompanha o prazo que a própria Shopee usa para confirmar "
        "definitivamente as comissões de afiliado.",
        MUTED, 300, 14.5)}
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("onde acompanhar", BRAND_PRIMARY)}
    {titulo("Sempre visível no seu painel", 27, DARK_BG)}
    {subtitulo(
        "Cada pedido mostra o status atual e a data prevista de liberação, "
        "atualizada direto da Shopee.",
        MUTED, 300, 14.5)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Do clique ao Pix, sem mistério nenhum.", 29)}
    {subtitulo("Acompanhe cada pedido no seu painel.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Comprou dia 28 de outubro. A Shopee só validou o pedido dia 3 de novembro. Quando é que o cashback libera? 🗓️

A resposta não depende da data da compra — depende da data em que a Shopee valida o pedido. Nesse exemplo, como a validação caiu em novembro, a liberação cai em 1º de janeiro (e não em 1º de dezembro, que seria a conta se contasse a partir da compra).

A regra é sempre a mesma: libera no dia 1º do 2º mês depois do mês da validação. Esse prazo acompanha o prazo que a própria Shopee usa para confirmar definitivamente a comissão — não é um número que a gente escolhe.

Cada pedido no seu painel mostra o status e a data prevista, sempre atualizados.

#cashback #shopeebrasil #dinheirodevolta #comoeconomizar #transparencia"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-14-linha-do-tempo", SLIDES, LEGENDA, exportar="--export" in sys.argv)
