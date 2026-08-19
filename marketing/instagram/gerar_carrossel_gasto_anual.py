"""Carrossel "Quanto você gastou na Shopee esse ano?".

Conteúdo de topo de funil: o gancho é um número que a pessoa não sabe de cabeça e
consegue descobrir na hora, no próprio celular. A cash-b só aparece no fim, como
desfecho - carrossel que começa falando da marca não alcança quem ainda não segue.

Números: pesquisa Klavi 2025 (50 mil consumidores) - 18 pedidos/ano na Shopee, ticket
médio de R$ 83,88, o que dá R$ 1.509/ano. O piso de 1,6% vem de
SHOPEE_CASHBACK_PERCENTUAL (20%) x SHOPEE_COMISSAO_VENDA_DIRETA (8%).
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_LIGHT,
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
    numbered_step,
    numero_gigante,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("faça as contas", BRAND_PRIMARY)}
    {titulo("Quanto você gastou na Shopee esse ano?", 34, DARK_BG)}
    {subtitulo("Quase ninguém sabe responder de cabeça.", MUTED, 300, 15)}
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("o dado", "rgba(255,255,255,0.5)")}
    {titulo("O brasileiro faz 18 compras por ano na Shopee.", 28)}
    {subtitulo(
        "Com ticket médio de R$ 84 por compra. É pouco de cada vez — "
        "o que engana é a soma.",
        "rgba(255,255,255,0.65)", 310, 14)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("a soma", "rgba(255,255,255,0.75)")}
    {numero_gigante("R$ 1.509", "É quanto a média gasta por ano na Shopee, sem perceber.", "#fff", "rgba(255,255,255,0.85)")}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("descubra o seu", BRAND_PRIMARY)}
    {titulo("Como ver o seu número agora", 25, DARK_BG)}
    <div style="margin-top:14px;">
        {numbered_step("01", "Abra o app da Shopee", "No canto inferior direito, toque em “Eu”.")}
        {numbered_step("02", "Entre em Minhas Compras", "Ali fica o histórico completo dos seus pedidos.")}
        {numbered_step("03", "Role até janeiro", "E some. Prepare-se para o susto.")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("a pergunta que importa", "rgba(255,255,255,0.5)")}
    {titulo("Desse dinheiro todo, quanto voltou para você?", 28)}
    <div style="font-family:'JB Mono'; font-size:52px; font-weight:700; color:{HIGHLIGHT}; margin-top:24px; letter-spacing:-0.03em;">R$ 0,00</div>
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("com a cash-b", BRAND_PRIMARY)}
    {titulo("O que voltaria para a sua conta", 24, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Gastando R$ 100 por mês", "R$ 19/ano")}
        {linha_valor("Gastando R$ 300 por mês", "R$ 57/ano")}
        {linha_valor("Gastando R$ 500 por mês", "R$ 96/ano")}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        E esse é o piso: muitos produtos têm comissão extra e devolvem bem mais.
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("O dinheiro já é gasto de qualquer jeito.", 30)}
    {subtitulo("A diferença é uma parte dele voltar.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = (
    "Faça o teste: abra o app da Shopee, vá em Minhas Compras e role até janeiro. "
    "O número assusta — e nada dele voltou para você. Salve para fazer depois. 💸"
)

if __name__ == "__main__":
    import sys

    gerar("carrossel-gasto-anual", SLIDES, LEGENDA, exportar="--export" in sys.argv)
