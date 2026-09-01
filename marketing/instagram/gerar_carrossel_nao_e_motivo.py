"""Carrossel "Cashback não é motivo para comprar".

Conteúdo contraintuitivo de propósito: é uma marca de cashback dizendo para não
comprar por causa do cashback. Isso gera comentário e, principalmente, confiança —
uma marca que avisa contra o próprio produto tem mais credibilidade quando fala a
favor dele. Mesma linha da página /cashback-na-shopee-vale-a-pena/.

Fecha reforçando o outro lado: na compra que já ia acontecer, o cashback é ganho puro.

Nota de voz (VOZ.md): "para comprar" e não "pra comprar" — "pra" só vale como
contração de para + a (artigo feminino), que não é o caso aqui.
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
    linha_valor,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("conversa franca", BRAND_PRIMARY)}
    {titulo("Cashback não é motivo para comprar.", 34, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("Sim, quem está falando isso é uma marca de cashback.", 28)}
    {subtitulo("E é justamente por isso que vale ouvir.", "rgba(255,255,255,0.7)", 300, 15)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("a armadilha", BRAND_PRIMARY)}
    {titulo("A conta que engana", 26, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Produto que você não precisava", "R$ 200", DARK_BG)}
        {linha_valor("Cashback recebido", "R$ 3,20", SUCCESS)}
        {linha_valor("Resultado real", "− R$ 196,80", "#dc2626")}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        Você não ganhou R$ 3,20. Você gastou R$ 196,80.
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {titulo("Cashback não transforma uma compra ruim em compra boa.", 28)}
    {subtitulo(
        "Ele é uma porcentagem pequena. Nunca vai compensar o valor inteiro de "
        "algo que você não ia comprar.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("agora o outro lado", BRAND_PRIMARY)}
    {titulo("Na compra que você já ia fazer, a conta vira.", 28, DARK_BG)}
    {subtitulo(
        "O dinheiro ia sair do mesmo jeito. A decisão já estava tomada. "
        "A única coisa que muda é uma parte voltar.",
        MUTED, 305, 14.5)}
    """, True),

    # Fecha na mensagem que importa, com o CTA no mesmo slide: separar em dois
    # gradientes seguidos repetia a ideia e quebrava o ritmo claro/escuro.
    Slide(BRAND_GRADIENT, f"""
    {titulo("Aí, sim: a cash-b te faz ganhar dinheiro.", 31)}
    {subtitulo(
        "Sem gastar nada a mais, sem comprar nada além do que você já compraria.",
        "rgba(255,255,255,0.9)", 300, 14.5)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Uma marca de cashback falando para você não comprar por causa do cashback. 💜

Comprar na Shopee algo de R$ 200 que você não precisava para receber R$ 3 de volta não é ganhar R$ 3. É gastar R$ 197.

Agora, na compra que você já ia fazer de qualquer jeito, aí sim é ganho de verdade — e é essa que vale ativar.

Concorda ou acha exagero? Conta nos comentários. 👇

#cashback #shopeebrasil #consumoconsciente #economizar #dinheirodevolta"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-nao-e-motivo", SLIDES, LEGENDA, exportar="--export" in sys.argv)
