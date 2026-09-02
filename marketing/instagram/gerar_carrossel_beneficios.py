"""Carrossel "Benefícios de usar a cash-b" - o primeiro da conta.

Nasceu antes do carrossel_base.py, com as ~400 linhas de paleta, fontes, componentes,
moldura e exportação embutidas no próprio arquivo. Migrado para a base porque ficou
insustentável manter duas cópias disso: correções feitas nos outros carrosséis (o
recorte da grade, o "capa=True", o legenda.txt) não chegavam aqui.

Duas coisas foram corrigidas na migração:

1. A capa era cortada na grade do perfil ("Toda compra na Shopee" virava "oda compra
   na Shopee") - resolvido pelo capa=True, ver PADDING_CAPA no carrossel_base.
2. O slide 2 dizia "Toda vez que você compra, alguém ganha uma comissão", que é falso:
   sem link de afiliado não existe comissão nenhuma, a Shopee fica com tudo. Mesmo
   erro que já tinha sido corrigido nos carrosséis de gasto anual e comissão invisível.

O conteúdo dos outros slides é o mesmo da versão publicada.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_LIGHT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MUTED,
    SUCCESS,
    Slide,
    check_item,
    cta_pill,
    gerar,
    numbered_step,
    pill,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("cash-b explica", BRAND_PRIMARY)}
    {titulo("Toda compra na Shopee gera cashback para você.", 32, DARK_BG)}
    {subtitulo("E a maioria das pessoas nem sabe disso.", MUTED, 280, 15)}
    """, True, capa=True),

    # "Toda vez que você compra" era falso - só existe comissão quando a compra passa
    # por um link de afiliado. Comprando direto no app, ninguém ganha nada.
    Slide(DARK_BG, f"""
    {tag_label("o problema", "rgba(255,255,255,0.5)")}
    {titulo("Quando a compra passa por um link, alguém ganha uma comissão.", 27)}
    {subtitulo(
        "A Shopee paga essa comissão para quem te levou até o produto. Ela nunca "
        "volta para quem realmente comprou.",
        "rgba(255,255,255,0.65)", 310, 14)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("a solução", "rgba(255,255,255,0.75)")}
    {titulo("A cash-b devolve essa comissão para você.", 30)}
    {subtitulo(
        "Você compra do jeito que já compra na Shopee. A diferença é que parte do "
        "dinheiro cai de volta na sua conta, via PIX.",
        "rgba(255,255,255,0.88)", 300, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("por que usar", BRAND_PRIMARY)}
    {titulo("Os benefícios, direto ao ponto", 24, DARK_BG)}
    <div style="margin-top:12px;">
        {check_item("Cashback real", "Toda compra participante gera dinheiro de volta.", SUCCESS)}
        {check_item("Cadastro grátis", "Sem mensalidade, sem taxa escondida.", BRAND_PRIMARY)}
        {check_item("Saque via PIX", "Direto na sua conta, sem burocracia.", SUCCESS)}
        {check_item("Do seu jeito", "Você compra como sempre comprou na Shopee.", BRAND_PRIMARY)}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("sem complicação", "rgba(255,255,255,0.5)")}
    {titulo("Sem pegadinha.", 30)}
    {subtitulo("Você não paga nada, apenas ganha.", "rgba(255,255,255,0.7)", 300, 14)}
    <div style="display:flex; gap:10px; margin-top:24px; flex-wrap:wrap;">
        {pill("Sem mensalidade", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
        {pill("Sem taxa", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
        {pill("Sem burocracia", BRAND_LIGHT, "rgba(255,255,255,0.08)")}
    </div>
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("3 passos e pronto", 24, DARK_BG)}
    <div style="margin-top:14px;">
        {numbered_step("01", "Encontre o produto", 'Converta o link, acesse pela vitrine ou clique em "Ir pra Shopee".')}
        {numbered_step("02", "Compre normalmente", "Do jeito que você já compra, sem nada a mais.")}
        {numbered_step("03", "Receba cashback", "Depois que o pedido for validado, o dinheiro vai pro seu saldo liberado.")}
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    <div style="text-align:center;">
        {titulo("Bora começar?", 32)}
    </div>
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Toda compra na Shopee gera cashback para você — e a maioria das pessoas nem sabe disso. 💜

Quando a compra passa por um link de afiliado, a Shopee paga uma comissão. Ela nunca volta para quem comprou. A cash-b devolve uma parte dela para você.

Cadastro grátis, sem mensalidade, saque via PIX. Você compra do jeito que já compra.

Salve para começar pela próxima compra.

#cashback #shopeebrasil #economizar #dinheirodevolta #achadinhosshopee"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-01-beneficios", SLIDES, LEGENDA, exportar="--export" in sys.argv)
