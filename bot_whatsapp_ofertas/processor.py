from parser import extrair_links, extrair_links_shopee
from formatador import formatar_texto_oferta
from oferta import Oferta

try:
    from config import PROCESSAR_APENAS_SHOPEE
except Exception:
    PROCESSAR_APENAS_SHOPEE = True


def processar_mensagem(msg, conversor):
    texto_original = msg.get("texto") or ""

    if PROCESSAR_APENAS_SHOPEE:
        links = extrair_links_shopee(texto_original)
    else:
        links = extrair_links(texto_original)

    if not links:
        return None

    texto_processado = texto_original
    links_convertidos = {}

    for link in links:
        novo_link = conversor.converter_link(link)
        links_convertidos[link] = novo_link
        texto_processado = texto_processado.replace(link, novo_link)

    primeiro_link = links[0]
    link_final = links_convertidos[primeiro_link]

    texto_formatado = formatar_texto_oferta(
        texto_processado,
        link_final
    )

    return Oferta(
        autor=msg.get("autor"),
        texto_original=texto_original,
        links=links,
        link_original=primeiro_link,
        link_afiliado=link_final,
        texto_final=texto_formatado,
        tem_imagem=msg.get("tem_imagem", False),
        id_mensagem=msg.get("id_mensagem")
    )
