"""Carrossel da campanha 10.10: "50% a mais de cashback" explicado em 5 slides.

É o post fixo da campanha: quem chega pelo teaser, pelo e-mail ou pelo story encontra aqui
a explicação inteira. Diferente do carrossel 11 (datas duplas, que de propósito não cita o
percentual), este diz o número: é uma campanha com data e valor definidos.

Os números NÃO são digitados aqui: vêm de `marketing/gerar_banner_email.py` (que os
documenta como cópia dos settings e da campanha cadastrada no admin) e de
`gerar_cards_vitrine.PRODUTO` (o produto de exemplo). Se o percentual da campanha mudar, o
carrossel, o banner do e-mail e os stories mudam juntos.

Slides: capa, como funciona (3 passos), quanto você recebe (os dois pisos), exemplo com um
produto real da vitrine (antes -> agora) e "bom saber" (condições + site).

IMPORTANTE ao postar: só publicar com a campanha cadastrada no admin ("Campanhas de
cashback": multiplicador 1,5, 10/10 das 00:00 às 23:59:59), ou nos dias anteriores, com a
legenda dizendo que é no dia 10/10. A legenda não diz "hoje" de propósito: o post fica no
perfil e continuaria dizendo "hoje" depois do dia.
"""
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
    HIGHLIGHT,
    LIGHT_BG,
    MARCA,
    MUTED,
    SUCCESS,
    Slide,
    cta_pill,
    destaque,
    gerar,
    linha_valor,
    numbered_step,
    subtitulo,
    tag_label,
    titulo,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gerar_cards_vitrine as vitrine  # noqa: E402
from gerar_banner_email import (  # noqa: E402
    DATA,
    DIA_MES,
    MINIMO_DIRETA,
    MINIMO_INDIRETA,
    MULTIPLICADOR,
    PERCENTUAL_EXTRA,
    SAQUE_MINIMO,
    _pct,
)

EXTRA = f"{PERCENTUAL_EXTRA}%"
# O verde da marca (#059669) é para fundo claro; sobre o fundo escuro do slide 3 ele some.
VERDE_ESCURO = "#4ade80"

# Mesma conta do site (ofertas/models.py): % do produto x multiplicador arredondado em 0,1;
# valor = preço base x % x multiplicador, arredondado em centavos.
_PCT_PRODUTO = Decimal(vitrine.PRODUTO["percentual_direta"])
_BASE = Decimal(str(vitrine.PRODUTO["preco_base"]))
PCT_ANTES = _pct(_PCT_PRODUTO)
PCT_AGORA = _pct((_PCT_PRODUTO * MULTIPLICADOR).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
VALOR_ANTES = vitrine._reais(vitrine._valor(_PCT_PRODUTO))
VALOR_AGORA = vitrine._reais(
    (_BASE * _PCT_PRODUTO / 100 * MULTIPLICADOR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
)
NOME_PRODUTO = vitrine.PRODUTO["nome"].split(" com ")[0]
PRECO_BASE = vitrine._reais(_BASE)

SLIDES = [
    Slide(BRAND_GRADIENT, f"""
    {tag_label("campanha", "rgba(255,255,255,0.75)")}
    <div style="font-family:Familjen; font-size:84px; font-weight:700; line-height:0.95;
                letter-spacing:-0.05em; color:#fff; white-space:nowrap;">{DATA}</div>
    <div style="font-family:Familjen; font-size:26px; font-weight:700; line-height:1.1;
                letter-spacing:-0.01em; color:{HIGHLIGHT}; text-transform:uppercase; margin-top:14px;">
        {EXTRA} a mais de cashback</div>
    {subtitulo(f"Em todo pedido feito no dia {DIA_MES}.", "rgba(255,255,255,0.9)", 280, 15)}
    """, False, capa=True),

    Slide(LIGHT_BG, f"""
    {tag_label("como funciona", BRAND_PRIMARY)}
    {titulo("Compre no dia, receba mais", 28, DARK_BG)}
    <div style="margin-top:10px;">
        {numbered_step("1", f"Entre na {MARCA} e escolha o produto",
                       "Cole o link, use a vitrine ou o botão “Ir pra Shopee”.")}
        {numbered_step("2", f"Compre na Shopee no dia {DIA_MES}",
                       "Vale para qualquer pedido do dia.")}
        {numbered_step("3", f"Receba {EXTRA} a mais de cashback",
                       f"Ele entra na sua conta da {MARCA}.")}
    </div>
    """, True),

    Slide(DARK_BG, f"""
    {tag_label("quanto você recebe", "rgba(255,255,255,0.5)")}
    {titulo("O mínimo sobe junto", 28)}
    <div style="margin-top:14px;">
        {linha_valor("Por link ou vitrine", f"{_pct(MINIMO_DIRETA)} → {_pct(MINIMO_DIRETA * MULTIPLICADOR)}", VERDE_ESCURO, escuro=True)}
        {linha_valor("Botão “Ir pra Shopee”", f"{_pct(MINIMO_INDIRETA)} → {_pct(MINIMO_INDIRETA * MULTIPLICADOR)}", VERDE_ESCURO, escuro=True)}
    </div>
    <div style="font-family:Familjen; font-size:13px; color:rgba(255,255,255,0.65); margin-top:14px; line-height:1.5;">
        Esse é o cashback mínimo de cada tipo de compra. Muitas vezes, bem mais: o valor de
        cada produto aparece no card da vitrine.
    </div>
    """, False),

    Slide(LIGHT_BG, f"""
    {tag_label("um exemplo de verdade", BRAND_PRIMARY)}
    {titulo("Mesmo produto, mais dinheiro de volta", 26, DARK_BG)}
    <div style="margin-top:14px;">
        {linha_valor("Dia normal", f"{PCT_ANTES} · {VALOR_ANTES}", MUTED)}
        {linha_valor(f"No {DATA}", f"{PCT_AGORA} · {VALOR_AGORA}", SUCCESS)}
    </div>
    <div style="font-family:Familjen; font-size:12.5px; color:{MUTED}; margin-top:14px; line-height:1.5;">
        {NOME_PRODUTO}, sobre {PRECO_BASE}. É o número que a vitrine mostra no card.
    </div>
    {destaque(f"Em um pedido de {vitrine._reais(Decimal('100'))} pelo link, o mínimo já vira "
              f"{vitrine._reais(Decimal('100') * MINIMO_DIRETA * MULTIPLICADOR / 100)}, "
              f"em vez de {vitrine._reais(Decimal('100') * MINIMO_DIRETA / 100)}.", cor=SUCCESS)}
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {tag_label("bom saber", "rgba(255,255,255,0.75)")}
    {titulo("O que vale a pena conferir", 28)}
    <div style="font-family:Familjen; font-size:14px; color:rgba(255,255,255,0.92); margin-top:16px; line-height:1.55;">
        • O dia vale no horário de Brasília, das 0h às 23h59.<br>
        • O cashback fica pendente até a Shopee validar a compra.<br>
        • Saque via Pix a partir de R$ {SAQUE_MINIMO}, com o e-mail verificado.
    </div>
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = f"""{DATA}: {EXTRA} a mais de cashback em todos os pedidos feitos no dia {DIA_MES}. 🔥

Como funciona: você entra na cash-b, escolhe o produto, compra na Shopee no dia e recebe {EXTRA} a mais de cashback.

O mínimo sobe junto: por link ou vitrine, de {_pct(MINIMO_DIRETA)} para {_pct(MINIMO_DIRETA * MULTIPLICADOR)}; pelo botão "Ir pra Shopee", de {_pct(MINIMO_INDIRETA)} para {_pct(MINIMO_INDIRETA * MULTIPLICADOR)}. Muitas vezes, bem mais: o valor de cada produto aparece no card da vitrine.

Bom saber: o dia vale no horário de Brasília, o cashback fica pendente até a Shopee validar a compra e o saque via Pix é a partir de R$ {SAQUE_MINIMO}, com o e-mail verificado.

Deixe a sua lista pronta e comece pela cash-b.com no dia.

#cashback #shopeebrasil #datasduplas #1010 #ofertasshopee #economizar"""

if __name__ == "__main__":
    gerar("carrossel-12-10-10", SLIDES, LEGENDA, exportar="--export" in sys.argv)
