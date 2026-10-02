from django import template

from pedidos.models import CampanhaCashback

register = template.Library()


@register.inclusion_tag("_faixa_campanha.html")
def faixa_campanha():
    """Faixa no topo da página avisando da campanha de cashback (ou de que ela vem aí).

    É um template tag e não um context processor de propósito: o context processor roda
    em TODA renderização (admin, 404, e-mail), e a consulta só faz sentido nas poucas
    páginas que mostram a faixa. A tabela tem poucas linhas, então é uma consulta barata
    por página vista - e sem cache, para a faixa aparecer e sumir no mesmo instante em que
    os cards de oferta mudam de valor (eles usam o mesmo multiplicador_atual)."""
    return {"faixa": CampanhaCashback.para_faixa()}
