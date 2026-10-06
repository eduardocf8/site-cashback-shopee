from django import template

from pedidos.models import CampanhaCashback
from pedidos.previa import campanha_da_previa

register = template.Library()


@register.inclusion_tag("_faixa_campanha.html")
def faixa_campanha():
    """Faixa no topo da página avisando da campanha de cashback (ou de que ela vem aí).

    É um template tag e não um context processor de propósito: o context processor roda
    em TODA renderização (admin, 404, e-mail), e a consulta só faz sentido nas poucas
    páginas que mostram a faixa. A tabela tem poucas linhas, então é uma consulta barata
    por página vista - e sem cache, para a faixa aparecer e sumir no mesmo instante em que
    os cards de oferta mudam de valor (eles usam o mesmo multiplicador_atual)."""
    return {"faixa": CampanhaCashback.para_faixa(), "previa": campanha_da_previa() is not None}


@register.inclusion_tag("_barra_campanha_card.html", takes_context=True)
def barra_campanha_card(context):
    """Barra "10.10: 50% a mais de cashback" no topo do card de oferta, enquanto a campanha está no ar.

    O card já mostra o valor com o extra; a barra diz POR QUE ele é maior (quem não viu a faixa
    ou o Instagram vê um 6,3% e não sabe que o normal é 4,2%). Só aparece com a campanha de fato
    ativa (ou na prévia do administrador), nunca no aviso prévio: antes do dia os valores do
    card ainda são os normais.

    A campanha é consultada uma vez por requisição e guardada nela: uma página tem dezenas de
    cards, e uma consulta por card seria desperdício."""
    request = context.get("request")
    if request is not None and hasattr(request, "_campanha_barra_card"):
        campanha = request._campanha_barra_card
    else:
        campanha = CampanhaCashback.ativa_agora()
        if request is not None:
            request._campanha_barra_card = campanha
    return {"campanha": campanha}
