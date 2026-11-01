"""Carrossel "5 erros que travam seu saque via Pix".

Diferente do carrossel-08-perder-cashback (que é sobre perder o cashback NA COMPRA,
antes de o pedido virar saldo), esse aqui é sobre o SAQUE em si - erros que impedem o
saldo já liberado de sair pra conta da pessoa. Fontes: saques/services.py
(solicitar_saque, ChavePixNaoConfiguradaError/ChavePixNaoVerificadaError/
ValorAbaixoDoMinimoError) e accounts/verificacao_pix.py (titular da chave tem que ser
o CPF da conta; nome batendo só parcialmente cai em conferência manual, não é erro).

O valor mínimo de saque (R$ 20,00) vem de SAQUE_VALOR_MINIMO em settings.py - confirmar
se é esse o valor em produção antes de publicar, já que é configurável por ambiente.
"""
from carrossel_base import (
    BRAND_GRADIENT,
    BRAND_PRIMARY,
    DARK_BG,
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
    return f"""
    {tag_label(f"{numero} de 5", BRAND_PRIMARY)}
    {titulo(titulo_item, 27, DARK_BG)}
    {subtitulo(texto, MUTED, 305, 14.5)}
    <div style="margin-top:18px; padding:12px 16px; background:#fff; border-left:3px solid {SUCCESS};
                border-radius:6px; font-family:Familjen; font-size:13px; color:{DARK_BG}; line-height:1.5;">
        {saida}
    </div>
    """


SLIDES = [
    Slide(LIGHT_BG, f"""
    {tag_label("guia rápido", BRAND_PRIMARY)}
    {titulo("5 erros que travam seu saque via Pix", 29, DARK_BG)}
    """, True, capa=True),

    Slide(DARK_BG, f"""
    {tag_label("antes da lista", "rgba(255,255,255,0.5)")}
    {titulo("O saque só sai pra chave do seu próprio CPF.", 27)}
    {subtitulo(
        "Antes de pagar, a cash-b confirma com o banco quem é o titular da "
        "chave Pix cadastrada. Os cinco itens da lista são as formas mais "
        "comuns de essa confirmação travar.",
        "rgba(255,255,255,0.7)", 305, 14.5)}
    """, False),

    Slide(LIGHT_BG, item(
        "1", "Chave Pix no nome de outra pessoa",
        "Chave do cônjuge, de um filho, de outra conta — não passa, mesmo com "
        "acesso a ela. O titular precisa ser o CPF da sua conta na cash-b.",
        "Cadastre uma chave Pix no seu nome, do seu CPF.",
    ), True),

    Slide(LIGHT_BG, item(
        "2", "Chave Pix ainda não cadastrada",
        "Sem chave cadastrada, o saque nem chega a ser solicitado.",
        "Cadastre a chave antes de pedir o saque.",
    ), True),

    Slide(LIGHT_BG, item(
        "3", "Nome abreviado diferente do banco",
        "O banco devolve o nome completo do titular. Se bater só em parte com "
        "o nome do cadastro, fica retido pra conferência manual.",
        "Não precisa fazer nada — é revisado à mão, não é um erro seu.",
    ), True),

    Slide(LIGHT_BG, item(
        "4", "Saldo abaixo do mínimo",
        "Hoje o mínimo pra sacar é R$ 20,00.",
        "Espere o saldo liberado chegar lá, ou vá juntando pra próxima vez.",
    ), True),

    Slide(LIGHT_BG, item(
        "5", "E-mail da conta não confirmado",
        "Sem confirmar o e-mail, o pedido de saque não sai do lugar.",
        "Confirme o e-mail no seu painel — é rápido.",
    ), True),

    Slide(LIGHT_BG, f"""
    {tag_label("o resumo", BRAND_PRIMARY)}
    {titulo("Três checagens resolvem quase tudo", 27, DARK_BG)}
    <div style="margin-top:10px;">
        {numbered_step("01", "Chave Pix no seu nome", "Mesmo CPF da sua conta na cash-b.")}
        {numbered_step("02", "Saldo acima do mínimo", "R$ 20,00 liberado disponível.")}
        {numbered_step("03", "E-mail confirmado", "Confirma no painel, antes de pedir o saque.")}
    </div>
    """, True),

    Slide(BRAND_GRADIENT, f"""
    {titulo("O resto é esperar o Pix cair.", 30)}
    {subtitulo("Salve pra conferir antes do próximo saque.", "rgba(255,255,255,0.9)", 300, 15)}
    {cta_pill()}
    """, False, seta=False),
]

LEGENDA = """Saldo liberado, mas o saque não sai do lugar? Veja os cinco motivos mais comuns. 📌

O saque só sai pra chave Pix cujo titular é o CPF da sua própria conta — é a trava que a cash-b confirma com o banco antes de pagar. Chave de outra pessoa, chave ainda não cadastrada, saldo abaixo do mínimo (R$ 20,00) e e-mail não confirmado são os erros que mais aparecem.

Três checagens resolvem quase tudo: chave Pix no seu nome, saldo acima do mínimo e e-mail confirmado.

Salve pra conferir antes do próximo saque.

#cashback #saquepix #shopeebrasil #dinheirodevolta #dicasdecompra"""

if __name__ == "__main__":
    import sys

    gerar("carrossel-16-erros-saque-pix", SLIDES, LEGENDA, exportar="--export" in sys.argv)
