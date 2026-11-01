"""Carrossel "Indique e ganhe, com conta real".

Companheiro do carrossel-10-indique-e-ganhe (que explica a mecânica em si) - esse aqui
é o ângulo "faz a conta": usa o piso de 1,6% já divulgado no carrossel-02 e no
carrossel-04 pra montar um exemplo em reais, em vez de só dizer "dobro do cashback".

Mecânica confirmada em pedidos/services.py (_selecionar_bonus_indicacao): cada
indicação garante UM dobro pra uma próxima compra validada de quem indicou (fila por
indicação, não um multiplicador acumulado numa única compra) - por isso o exemplo fala
em "3 indicações = 3 das suas próximas compras em dobro", nunca em tudo dobrando de
uma vez.

Mesmo aviso do carrossel-10 (programa não fica ligado o tempo todo), só que resumido -
quem quiser o motivo completo já tem o outro carrossel pra isso.
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
    caso,
    cta_pill,
    destaque,
    gerar,
    linha_valor,
    subtitulo,
    tag_label,
    titulo,
)

SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("indique e ganhe", BRAND_PRIMARY)}
    {titulo("Indicou 3 amigas. Veja a conta real.", 29, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {titulo("Cada indicação guarda um dobro pra sua próxima compra.", 27)}
    {subtitulo(
        "Não é na hora. É um dobro reservado, que entra assim que a pessoa "
        "indicada faz a primeira compra validada.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("fazendo a conta", BRAND_PRIMARY)}
    {titulo("Uma compra de R$ 150, pelo piso de 1,6%", 25, DARK_BG)}
    <div style="margin-top:14px;">
        {caso("Sem o dobro da indicação", "R$ 150 x 1,6% = R$ 2,40 de cashback")}
        {caso("Com o dobro de uma indicação", "Os mesmos R$ 150 rendem R$ 4,80")}
    </div>
    {destaque("1,6% é o piso — produtos com comissão extra rendem mais, e o dobro se aplica do mesmo jeito.", cor=HIGHLIGHT)}
    """, True),

    Slide(LIGHT_BG, f"""
    {tag_label("e indicando mais gente", BRAND_PRIMARY)}
    {titulo("O dobro multiplica junto", 27, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("1 amiga indicada", "1 compra sua em dobro")}
        {linha_valor("3 amigas indicadas", "3 compras suas em dobro")}
        {linha_valor("5 amigas indicadas", "5 compras suas em dobro")}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.45;">
        Uma por vez, guardada pra próxima compra validada — sem limite de quantas pessoas você indica.
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("importante", "rgba(255,255,255,0.5)")}
    {titulo("O programa não fica ligado o tempo todo.", 27)}
    {subtitulo(
        "Ele abre em períodos específicos. Enquanto está fora do ar, o link de "
        "indicação não aparece no painel.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    {destaque("Quando abrir, avisamos aqui no perfil e no site.", escuro=True, cor=SUCCESS)}
    """, False),

    Slide(BRAND_GRADIENT, f"""
    {titulo("Faça a conta com quem você já ia indicar de qualquer jeito.", 27)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Indicou 3 amigas. Quanto isso significa de verdade? Vamos fazer a conta. 🧮

Cada indicação guarda um dobro pra uma das suas próximas compras — não é na hora, é reservado. Pelo piso de 1,6% já divulgado por aqui, uma compra de R$ 150 que renderia R$ 2,40 de cashback passa a render R$ 4,80 com o dobro. Indicou 3 amigas? São 3 das suas próximas compras em dobro, uma por vez — sem limite de quantas pessoas você indica.

⚠️ O programa não fica ligado o tempo todo: ele abre em períodos específicos, e avisamos aqui e no site quando estiver no ar.

#indiqueeganhe #cashback #shopeebrasil #dinheirodevolta #economizar"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-17-indicacao-conta-real", SLIDES, LEGENDA, exportar="--export" in sys.argv)
