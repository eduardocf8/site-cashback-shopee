"""Textos da página de uma ferramenta fora do plano (painel/modulo.html)."""

from django import template

register = template.Library()

# Artigo de cada ferramenta (o resto é masculino singular: "o Bot de WhatsApp").
FEMININO_PLURAL = {"automacoes_instagram"}


def _com_artigo(item: dict) -> str:
    return f"{'as' if item.get('slug') in FEMININO_PLURAL else 'o'} {item['nome']}"


@register.simple_tag
def fora_do_plano(item: dict, menu: list, url_planos: str) -> dict:
    """O título dos benefícios, as ferramentas que a pessoa continua tendo e a página da ferramenta no site."""
    plural = item.get("slug") in FEMININO_PLURAL
    tem = [_com_artigo(m) for m in menu or [] if m.get("modulo") and m.get("estado") == "liberado"]
    continua = " e ".join([", ".join(tem[:-1]), tem[-1]]) if len(tem) > 1 else "".join(tem)
    url = url_planos or ""
    if item.get("pagina_site") and url.startswith("http") and "#" not in url:
        url = f"{url.rstrip('/')}/{item['pagina_site']}"
    return {
        "titulo": f"O que {_com_artigo(item)} {'fazem' if plural else 'faz'} por você",
        "continua": continua,
        "url": url,
    }
