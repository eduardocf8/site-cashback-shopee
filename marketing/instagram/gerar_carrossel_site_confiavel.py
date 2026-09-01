"""Carrossel "Como saber se um site de cashback é confiável".

Versão para o Instagram da página /como-saber-se-site-de-cashback-e-confiavel/ - os
mesmos cinco critérios, no mesmo espírito: servem para avaliar qualquer site, não só a
cash-b. O carrossel não compara com concorrente nem cita nome de ninguém; entrega o
critério e deixa a pessoa conferir sozinha.

O último slide é o único que fala da cash-b, e mesmo assim só apontando onde conferir.
Um checklist que termina em "e nós passamos em todos" perde o valor de checklist.
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
    cta_pill,
    gerar,
    subtitulo,
    tag_label,
    titulo,
)


def ponto(numero, titulo_item, texto, sinal):
    return f"""
    {tag_label(f"ponto {numero} de 5", BRAND_PRIMARY)}
    {titulo(titulo_item, 27, DARK_BG)}
    {subtitulo(texto, MUTED, 305, 14.5)}
    <div style="margin-top:18px; padding:12px 16px; background:#fff; border-left:3px solid {SUCCESS};
                border-radius:6px; font-family:Familjen; font-size:13px; color:{DARK_BG}; line-height:1.5;">
        <b>Como checar:</b> {sinal}
    </div>
    """


SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("checklist", BRAND_PRIMARY)}
    {titulo("Como saber se um site de cashback é confiável", 31, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("Cadastrar CPF e chave PIX num site novo pede desconfiança.", 28)}
    {subtitulo(
        "Cinco pontos para checar antes. Servem para qualquer site de cashback — "
        "inclusive para conferir a cash-b.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, ponto(
        "1", "O cashback vem de uma comissão real",
        "Site de cashback devolve parte da comissão que a própria loja paga. O dinheiro "
        "não é criado do nada. Percentual muito acima do que a loja pagaria não se "
        "sustenta por muito tempo.",
        "veja se o site explica de onde vem o dinheiro.",
    ), True),

    Slide(LIGHT_BG, ponto(
        "2", "As regras e os prazos estão escritos",
        "Cashback não cai na hora: a loja precisa confirmar a compra antes. Isso é "
        "normal. O que não é normal é você ter que adivinhar por que o saldo está "
        "parado em pendente.",
        "procure uma página de regras com os status e o prazo de liberação.",
    ), True),

    Slide(LIGHT_BG, ponto(
        "3", "O saque é simples e sem taxa",
        "Olhe o valor mínimo, o prazo e se cobram alguma taxa em cima do que você já "
        "ganhou. Cashback que você não consegue sacar não é cashback.",
        "as condições de saque têm que estar visíveis antes do cadastro.",
    ), True),

    Slide(LIGHT_BG, ponto(
        "4", "Existe uma política de privacidade de verdade",
        "O site precisa dizer quais dados coleta, para que usa e com quem compartilha. "
        "Não um texto genérico copiado de outro lugar.",
        "leia se ela fala do site que você está usando ou serve para qualquer um.",
    ), True),

    Slide(LIGHT_BG, ponto(
        "5", "Fica claro que é afiliado, não a loja",
        "Site de cashback não é a Shopee, a Amazon nem nenhuma outra loja — é um "
        "parceiro afiliado independente. Um site sério diz isso, em vez de sugerir "
        "uma ligação oficial que não existe.",
        "procure essa frase no rodapé ou na página sobre.",
    ), True),

    Slide(DARK_BG, f"""
    {titulo(f"Agora use esses cinco pontos na {MARCA}.", 30)}
    {subtitulo(
        "As regras, os prazos, as condições de saque e a política de privacidade estão "
        "todos no site, escritos. É para ser conferido.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Desconfiar é saudável. Conferir é melhor ainda.", 30)}
    {subtitulo("Salve para usar no próximo site que te oferecerem.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Antes de cadastrar CPF e chave PIX em qualquer site de cashback, cheque estes cinco pontos. 🔍

1. O cashback vem de uma comissão real que a loja paga
2. As regras de prazo e status estão escritas
3. O saque é simples, com valor mínimo claro e sem taxa
4. A política de privacidade fala do site de verdade
5. Fica claro que é um afiliado independente, não a loja

Serve para qualquer um — e sim, serve para conferir a cash-b também. Está tudo escrito no site, é para ser lido.

Salve para usar no próximo que te oferecerem.

#cashback #shopeebrasil #segurancadigital #dinheirodevolta #golpesnainternet"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-09-site-confiavel", SLIDES, LEGENDA, exportar="--export" in sys.argv)
