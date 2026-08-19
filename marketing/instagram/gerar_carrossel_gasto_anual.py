"""Carrossel "O que o brasileiro gasta na Shopee em um ano".

Primeira versão pedia para a pessoa somar o próprio histórico de pedidos no app - ideia
descartada: a Shopee não tem relatório de gastos, as únicas formas de chegar nesse
número são extensão de navegador ou colar script no console (que, além de técnico
demais, é exatamente o formato de golpe que se ensina a não fazer). Sem esse caminho,
o carrossel passou a ser informativo: mostra o dado público e o que ele renderia.

Números (fontes creditadas no próprio slide):
- 18 pedidos/ano na Shopee, ticket médio R$ 83,88 = R$ 1.509/ano - Klavi, 2025,
  50 mil consumidores.
- R$ 130 bilhões movimentados por Shopee, Shein e TikTok no Brasil em 2025, ou
  R$ 356 milhões por dia - EY e Klavi, 2025.
- Piso de 1,6%: SHOPEE_CASHBACK_PERCENTUAL (20%) x SHOPEE_COMISSAO_VENDA_DIRETA (8%).

Só usa dado de Shopee, não de e-commerce em geral: a cash-b devolve cashback de compra
na Shopee, então citar o gasto total do brasileiro em marketplaces prometeria uma
conta que a gente não entrega.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    HIGHLIGHT,
    LIGHT_BG,
    MUTED,
    Slide,
    cta_pill,
    destaque,
    fonte,
    gerar,
    linha_valor,
    numero_gigante,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("os números", BRAND_PRIMARY)}
    {titulo("O que o brasileiro gasta na Shopee em um ano", 34, DARK_BG)}
    {subtitulo("O valor é maior do que quase todo mundo imagina.", MUTED, 300, 15)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("por pessoa, por ano", "rgba(255,255,255,0.75)")}
    {numero_gigante("R$ 1.509", "São 18 compras por ano, de R$ 84 em média. Pouco de cada vez — o que engana é a soma.", "#fff", "rgba(255,255,255,0.85)")}
    {fonte("Fonte: pesquisa Klavi (2025), com 50 mil consumidores.", escuro=True)}
    """, False),

    Slide(DARK_BG, f"""
    {tag_label("no país inteiro", "rgba(255,255,255,0.5)")}
    {numero_gigante("R$ 356 mi", "É quanto os brasileiros gastam POR DIA em Shopee, Shein e TikTok. R$ 130 bilhões no ano.", HIGHLIGHT, "rgba(255,255,255,0.7)")}
    {fonte("Fonte: estudo EY e Klavi (2025).", escuro=True)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("o detalhe", BRAND_PRIMARY)}
    {titulo("Em toda essa movimentação, existe comissão de afiliado.", 28, DARK_BG)}
    {subtitulo(
        "A Shopee paga uma parte de cada venda para quem levou o cliente até o "
        "produto. É assim que canais de oferta e páginas de achadinhos se sustentam.",
        MUTED, 305, 14.5)}
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("a pergunta que importa", "rgba(255,255,255,0.5)")}
    {titulo("Quanto dessa comissão volta para quem comprou?", 28)}
    <div style="font-family:'JB Mono'; font-size:52px; font-weight:700; color:{HIGHLIGHT}; margin-top:24px; letter-spacing:-0.03em;">R$ 0,00</div>
    """, False),

    # O "no mínimo" aparece em três lugares de propósito (título, o "+" colado no
    # valor e a caixa de destaque): a versão anterior deixava isso só numa nota
    # cinza no rodapé, que é justamente onde a informação morre.
    Slide(LIGHT_BG, f"""
    {tag_label("com a cash-b", BRAND_PRIMARY)}
    {titulo("O mínimo que volta para a sua conta", 24, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Gastando R$ 100 por mês", "R$ 19+ /ano")}
        {linha_valor("Gastando R$ 300 por mês", "R$ 57+ /ano")}
        {linha_valor("Gastando R$ 500 por mês", "R$ 96+ /ano")}
    </div>
    {destaque("<b>Isso é o piso, não o teto.</b> Produtos com comissão extra devolvem bem mais que esses valores.")}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("O dinheiro sai da sua conta de qualquer jeito.", 30)}
    {subtitulo("A diferença é uma parte dele voltar.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = (
    "R$ 1.509 por ano, por pessoa, só na Shopee — e R$ 356 milhões por dia no país "
    "inteiro. Em toda essa movimentação existe uma comissão que nunca volta para "
    "quem comprou. Salve para lembrar. 📊"
)

if __name__ == "__main__":
    import sys

    gerar("carrossel-gasto-anual", SLIDES, LEGENDA, exportar="--export" in sys.argv)
