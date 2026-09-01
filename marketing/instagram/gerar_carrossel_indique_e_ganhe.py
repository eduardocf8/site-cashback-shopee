"""Carrossel "Indique e ganhe: cashback em dobro para os dois".

Mecânica real: o primeiro pedido validado de quem foi indicado vem com o dobro do
cashback, e o pedido seguinte de quem indicou também (ver pedidos/services.py,
_selecionar_bonus_indicacao). Não é bônus fixo em reais - dobra o cashback daquele
pedido específico.

O programa não fica ligado o tempo todo (accounts/views.py lê
ConfiguracaoIndicacao.esta_ativa()), e isso precisa aparecer no carrossel, não só na
legenda: post que promete um programa desligado gera decepção e comentário irritado.
Por isso o aviso tem slide próprio, antes do fechamento, e não uma nota de rodapé.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    LIGHT_BG,
    MUTED,
    SUCCESS,
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
    {tag_label("indique e ganhe", BRAND_PRIMARY)}
    {titulo("Cashback em dobro para você e para quem você indicar", 30, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("Não é desconto. É o seu cashback vezes dois.", 29)}
    {subtitulo(
        "O valor que ia cair na sua conta cai dobrado. E não é só para você: quem "
        "você indicou recebe o dobro também.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("Quatro passos", 27, DARK_BG)}
    <div style="margin-top:10px;">
        {numbered_step("01", "Você compartilha seu link", "Ele fica no seu painel, pronto para copiar.")}
        {numbered_step("02", "A pessoa cria a conta e compra", "Pelo seu link, como qualquer compra.")}
        {numbered_step("03", "A primeira compra dela vem em dobro", "Assim que a Shopee validar o pedido.")}
        {numbered_step("04", "A sua próxima compra também", "O bônus fica guardado esperando você.")}
    </div>
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("os dois lados", BRAND_PRIMARY)}
    {titulo("Ninguém perde para o outro ganhar", 28, DARK_BG)}
    <div style="margin-top:16px;">
        {caso("Quem foi indicado", "Dobro do cashback na primeira compra")}
        {caso("Quem indicou", "Dobro do cashback na compra seguinte")}
    </div>
    {subtitulo(
        "O dobro sai da parte da comissão que a cash-b guardaria. Não sai do bolso "
        "de nenhum dos dois.",
        MUTED, 305, 13.5)}
    """, True),

    Slide(DARK_BG, f"""
    {titulo("E não tem limite de quantas pessoas você indica.", 29)}
    {subtitulo(
        "Cada indicação que compra pela primeira vez ativa um novo dobro na sua "
        "próxima compra.",
        "rgba(255,255,255,0.7)", 300, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("importante", BRAND_PRIMARY)}
    {titulo("O programa não fica ligado o tempo todo", 28, DARK_BG)}
    {subtitulo(
        "Ele abre em períodos específicos. Enquanto está fora do ar, o link de "
        "indicação não aparece no painel.",
        MUTED, 305, 14.5)}
    {destaque(
        "Quando abrir, a gente avisa aqui no Instagram e no site. É só ficar de olho.",
        cor=SUCCESS)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Quando abrir, seu link estará no painel.", 30)}
    {subtitulo(
        "Já cria a conta agora — assim, no dia que ligar, é só copiar e mandar.",
        "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Indique e ganhe: o cashback vem em dobro para os dois lados. 💜

Como funciona: você compartilha seu link, a pessoa cria a conta e compra. A primeira compra dela vem com o dobro do cashback — e, assim que a Shopee valida esse pedido, a sua próxima compra também vem dobrada.

Não tem limite de quantas pessoas você indica, e o dobro não sai do bolso de ninguém: sai da parte da comissão que a cash-b guardaria.

⚠️ Um aviso importante: o programa não fica ligado o tempo todo. Ele abre em períodos específicos, e enquanto está fora do ar o link de indicação não aparece no painel. Quando abrir, avisamos aqui no perfil e no site — vale seguir e ficar de olho.

#cashback #shopeebrasil #indiqueeganhe #dinheirodevolta #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-10-indique-e-ganhe", SLIDES, LEGENDA, exportar="--export" in sys.argv)
