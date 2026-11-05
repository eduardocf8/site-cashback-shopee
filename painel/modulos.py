"""O que aparece no menu do painel e o estado de cada módulo para uma conta:
liberado, "Em breve" (ainda não construído no painel) ou bloqueado (o plano
não inclui - mostra cadeado e o convite para assinar)."""

from django.conf import settings
from django.urls import reverse

from licencas.models import (
    MODULO_CARROSSEIS,
    MODULO_CARROSSEIS_PREMIUM,
    MODULO_INSTAGRAM,
    MODULO_INSTAGRAM_PREMIUM,
    MODULO_NOTAS,
    MODULO_SITE,
    MODULO_WHATSAPP,
)

# Ícones de traço 24x24, mesmo estilo da proposta de design.
ICONES = {
    "inicio": "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    "whatsapp": "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z",
    "site": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "instagram": "M4 4h16v16H4zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
    "resultados": "M4 20V10M10 20V4M16 20v-7M2 20h20",
    "configuracoes": "M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4",
    "cadeado": "M6 11h12v10H6zM8 11V8a4 4 0 0 1 8 0v3",
    "check": "M5 12l4 4 10-10",
    "mais": "M12 5v14M5 12h14",
    "metas": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
    "atualizar": "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
    "baixar": "M12 4v11M7 10l5 5 5-5M5 20h14",
    "carrosseis": "M7 5h10v14H7zM3 7v10M21 7v10",
    "notas": "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
    "email": "M3 6h18v12H3zM3 7l9 6 9-6",
    "seta_cima": "M6 15l6-6 6 6",
    "seta_direita": "M9 6l6 6-6 6",
    "menu": "M4 7h16M4 12h16M4 17h16",
    "fechar": "M6 6l12 12M18 6L6 18",
    "ideia": "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
    "conversor": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "copiar": "M8 8h11v11H8zM5 16V5h11",
    "radar": "M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4",
    "enviar": "M4 12l16-8-6 16-2-7z",
    "sino": "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
    "imagens": "M7 5h10v14H7zM3 7v10M21 7v10",
    "automacoes": "M13 3L5 14h6l-1 7 8-11h-6z",
}

# slug -> configuração. "modulo": código da licença que libera (None = todos
# têm). "pronto": já existe no painel. "teste": já funciona, mas em versão de teste. "so_em_breve": ainda não dá para vender
# para ninguém (ex: Instagram, esperando a Meta). "grupo": título do bloco no menu ("" = sem título; "conta" = vai
# pro rodapé do menu, junto da conta). Nas ferramentas do plano: "resumo" (uma linha, nos cartões do Início),
# "frase" (subtítulo da página da ferramenta), "beneficios" e "exemplo" (o que ela faz, na página de quem não tem),
# "ao_assinar" e "pagina_site" (a página dela em appfiliado.com.br).
MODULOS_DO_MENU = [
    {"slug": "inicio", "nome": "Início", "icone": "inicio", "modulo": None, "pronto": True, "grupo": ""},
    {"slug": "resultados", "nome": "Resultados", "icone": "resultados", "modulo": None, "pronto": True, "grupo": "Seus números"},
    {"slug": "metas", "nome": "Metas", "icone": "metas", "modulo": None, "pronto": True, "grupo": "Seus números"},
    {"slug": "radar", "nome": "Radar de ofertas", "icone": "radar", "modulo": None, "pronto": True, "grupo": "Ofertas"},
    {"slug": "conversor", "nome": "Conversor de links", "icone": "conversor", "modulo": None, "pronto": True, "grupo": "Ofertas"},
    {
        "slug": "whatsapp", "nome": "Bot de WhatsApp", "icone": "whatsapp", "modulo": MODULO_WHATSAPP,
        "pronto": True, "grupo": "Divulgação",
        "resumo": "Ofertas no automático nos seus grupos.",
        "frase": "Ofertas da Shopee com o seu link de afiliado nos seus grupos e canais no automático.",
        "texto_bloqueado": "Envie ofertas com seu link de afiliado nos seus grupos e canais do WhatsApp "
                           "no automático.",
        "beneficios": [
            ("Ofertas no automático", "O bot busca na Shopee por palavra-chave, loja ou categoria e manda com o seu link."),
            ("Do seu jeito", "Você escolhe os grupos, os horários e quantas ofertas saem por dia."),
            ("Datas da Shopee", "Modo campanha pro 11.11 e pras outras datas, com o cupom e a frase da campanha."),
            ("Alerta de preço", "Confere os preços dos produtos que você escolher e avisa quando algum baixar."),
            ("Gestão dos grupos", "Os membros que cada grupo ganhou ou perdeu, os que estão perto de lotar e o "
                                  "próximo grupo criado pelo painel."),
            ("Link de entrada", "Um link só no anúncio, na bio ou no story, que manda cada pessoa pro grupo que "
                                "ainda tem vaga."),
        ],
        "exemplo": "Exemplo de oferta no grupo",
        "ao_assinar": "Ao assinar, o bot é liberado nesta mesma conta.",
        "pagina_site": "bot-de-whatsapp/",
    },
    {
        "slug": "site", "nome": "Meu site", "icone": "site", "modulo": MODULO_SITE, "pronto": True, "grupo": "Divulgação",
        "resumo": "Seu link na bio com conversor e vitrine.",
        "frase": "Seu link na bio com vitrine de ofertas e conversor de links.",
        "texto_em_breve": "Você vai editar aqui o seu site com conversor de links e vitrine "
                          "de produtos no endereço seunome.appfiliado.com.br.",
        "texto_bloqueado": "Tenha seu próprio site com conversor de links e vitrine de produtos, pronto "
                           "para usar como link na bio.",
        "beneficios": [
            ("Seu endereço", "Um site seu em seunome.appfiliado.com.br para colocar na bio do Instagram e do TikTok."),
            ("Botões e redes", "Os seus links em botões e as suas redes sociais, com os cliques de cada um."),
            ("Vitrine de ofertas", "As ofertas da Shopee com foto, preço e desconto, todas com o seu link de afiliado."),
            ("Conversor de links", "Quem visita cola o link de um produto da Shopee e compra pelo seu link."),
        ],
        "exemplo": "Exemplo de site",
        "ao_assinar": "Ao assinar, o site é liberado nesta mesma conta.",
        "pagina_site": "meu-site/",
    },
    {
        # O antigo gerador saiu do produto: os mesmos códigos de licença liberam o Estúdio Instagram, que toma o
        # lugar dele em todas as listas. A página e os carrosséis já salvos continuam em /carrosseis/.
        "slug": "carrosseis", "nome": "Carrosséis", "icone": "carrosseis", "modulo": MODULO_CARROSSEIS,
        "fora_das_listas": True,
        # o premium libera o gerador inteiro, sem precisar do básico junto
        "modulos_que_liberam": [MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM], "pronto": True,
        "texto_bloqueado": "Cole o link de um produto da Shopee e receba um carrossel pronto pro "
                           "Instagram com textos feitos por IA e o seu link de afiliado.",
    },
    {
        # Em construção: só abre para contas com a chave "beta" ligada no admin, até o lançamento. Antes dele,
        # quem já tem os códigos (os mesmos do antigo gerador) vê o Estúdio como "Em breve" ("breve_para_quem_tem").
        "slug": "estudio_instagram", "nome": "Estúdio Instagram", "icone": "instagram", "modulo": MODULO_CARROSSEIS,
        "modulos_que_liberam": [MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM], "pronto": True,
        "beta": "beta_estudio_instagram", "breve_para_quem_tem": True, "grupo": "Divulgação",
        "resumo": "Posts e stories com o seu link.",
        "frase": "Posts e stories com o seu link de afiliado, publicados direto no seu Instagram.",
        "texto_bloqueado": "Crie posts e stories com a sua marca e publique direto no seu Instagram.",
        "texto_em_breve": "O Estúdio Instagram já faz parte do seu plano e é liberado nesta conta assim que chegar.",
        "beneficios": [
            ("Do link ao post", "Cole o link de um produto da Shopee e a IA monta o post com a foto, o preço e a legenda."),
            ("Posts e stories", "Carrossel, post de uma imagem e sequência de stories no tamanho certo do Instagram."),
            ("Do seu jeito", "Troque os textos e as fotos no editor. No Premium, também as cores, os fundos e a sua marca."),
            ("Publicar ou agendar", "Publique no feed ou nos stories na hora ou no dia e na hora que você escolher."),
        ],
        "exemplo": "Exemplo de post",
        "ao_assinar": "Ao assinar, o Estúdio é liberado nesta mesma conta.",
        "pagina_site": "estudio-instagram/",
    },
    {
        "slug": "automacoes_instagram", "nome": "Automações Instagram", "icone": "automacoes", "modulo": MODULO_INSTAGRAM,
        "modulos_que_liberam": [MODULO_INSTAGRAM, MODULO_INSTAGRAM_PREMIUM], "pronto": True,
        "beta": "beta_estudio_instagram", "grupo": "Divulgação",
        "resumo": "Link por DM para quem comentar.",
        "frase": "Quem comentar a palavra certa no seu post recebe o seu link de afiliado por DM.",
        "texto_bloqueado": "Quem comentar a palavra certa no seu post recebe o seu link de afiliado por DM, na hora.",
        "beneficios": [
            ("Comentou, recebeu", "Quem comentar a palavra certa, como QUERO, recebe o seu link por DM na hora."),
            ("Posts e anúncios", "Vale para um post, para todos os posts ou para os comentários de um anúncio."),
            ("Stories e DMs", "No Premium, também quem responder o seu story ou mandar a palavra por DM."),
            ("Histórico", "Quem foi respondido, o que a pessoa escreveu e se a resposta e a DM saíram."),
        ],
        "exemplo": "Exemplo de resposta",
        "ao_assinar": "Ao assinar, as automações são liberadas nesta mesma conta.",
        "pagina_site": "automacoes-instagram/",
    },
    {
        "slug": "notas", "nome": "Emissor NFS-e", "icone": "notas", "modulo": MODULO_NOTAS, "pronto": True, "grupo": "Empresa",
        "resumo": "Notas da Shopee e dos vendedores.",
        "frase": "As notas fiscais das suas comissões direto do relatório da Shopee. Para afiliados pessoa jurídica.",
        "texto_bloqueado": "Emita no automático a nota da Shopee e as notas de cada vendedor que pagou "
                           "comissão extra e mande cada uma por e-mail pro vendedor.",
        "beneficios": [
            ("Sem digitar nada", "Envie o relatório mensal da Shopee e o Appfiliado emite uma nota por loja e a da Shopee."),
            ("Emissor Nacional", "As notas saem direto no Emissor Nacional do governo, no CNPJ da sua empresa."),
            ("E-mail pro vendedor", "Cada vendedor recebe a nota por e-mail com o PDF e o XML."),
            ("Teste antes", "Ensaie no ambiente de testes do governo, sem valor fiscal e sem contar no seu plano."),
        ],
        "exemplo": "Exemplo de lote emitido",
        "ao_assinar": "Ao assinar, o Emissor é liberado nesta mesma conta.",
        "pagina_site": "emissao-de-notas/",
    },
    {"slug": "configuracoes", "nome": "Configurações", "icone": "configuracoes", "modulo": None, "pronto": True, "grupo": "conta"},
    {"slug": "sugestoes", "nome": "Sugerir melhoria", "icone": "ideia", "modulo": None, "pronto": True, "grupo": "conta"},
]

POR_SLUG = {item["slug"]: item for item in MODULOS_DO_MENU}
URL_DE_SLUG = {
    "inicio": "painel_inicio",
    "resultados": "painel_resultados",
    "metas": "painel_metas",
    "radar": "painel_radar",
    "conversor": "painel_conversor",
    "whatsapp": "painel_whatsapp",
    "site": "painel_meu_site",
    "carrosseis": "painel_carrosseis",
    "estudio_instagram": "painel_estudio",
    "automacoes_instagram": "painel_estudio_automacoes",
    "notas": "painel_notas",
    "sugestoes": "painel_sugestoes",
    "configuracoes": "painel_configuracoes",
}


def estado(item: dict, liberados: list[str]) -> str:
    """"liberado", "em_breve" ou "bloqueado"."""
    if item.get("so_em_breve"):
        return "em_breve"
    if item["modulo"] and not set(item.get("modulos_que_liberam") or [item["modulo"]]) & set(liberados):
        return "bloqueado"
    return "liberado" if item["pronto"] else "em_breve"


def lancado() -> bool:
    return settings.APPFILIADO_LANCAMENTO_INSTAGRAM


def ve_beta(item: dict, conta) -> bool:
    """A página do item abre para a conta? O que está em construção ("beta") só abre para a conta com a chave
    ligada, até o lançamento. O que saiu das listas (o antigo Carrosséis) não aparece mais em lugar nenhum."""
    if item.get("fora_das_listas"):
        return False
    return not item.get("beta") or lancado() or bool(getattr(conta, item["beta"], False))


def situacao(item: dict, liberados: list[str], conta) -> str | None:
    """Como o item aparece nas listas do painel (menu, Início, Plano): "liberado", "bloqueado", "em_breve" ou
    None (não aparece). Antes do lançamento, quem tem os códigos do Estúdio sem a chave de teste vê "Em breve"."""
    if item.get("fora_das_listas"):
        return None
    if ve_beta(item, conta):
        return estado(item, liberados)
    if item.get("breve_para_quem_tem") and estado(item, liberados) == "liberado":
        return "em_breve"
    return None


def menu(liberados: list[str], ativo: str, conta=None) -> list[dict]:
    itens = []
    grupo_anterior = ""
    for item in MODULOS_DO_MENU:
        situacao_item = situacao(item, liberados, conta)
        if situacao_item is None:
            continue
        url_name = URL_DE_SLUG.get(item["slug"])
        href = reverse(url_name) if url_name and ve_beta(item, conta) else reverse("painel_modulo", args=[item["slug"]])
        selo = {"bloqueado": ("Desbloquear", "bloqueado"), "em_breve": ("Em breve", "breve")}.get(situacao_item)
        if situacao_item == "liberado" and item.get("teste"):
            selo = ("Teste", "breve")
        grupo = item.get("grupo", "")
        itens.append({
            **item,
            "href": href,
            "ativo": item["slug"] == ativo,
            "estado": situacao_item,
            "selo_texto": selo[0] if selo else "",
            "selo_tipo": selo[1] if selo else "",
            "icone_path": ICONES[item["icone"]],
            # Título do bloco no menu, só no primeiro item de cada grupo.
            "secao": grupo if grupo not in ("", "conta") and grupo != grupo_anterior else "",
        })
        grupo_anterior = grupo
    return itens


def ferramentas(itens: list[dict]) -> dict:
    """Quantas ferramentas do plano (as que pedem licença) a conta tem liberadas, pro cartão "Seu plano"."""
    do_plano = [i for i in itens if i["modulo"] and i["estado"] != "em_breve"]
    return {"liberadas": sum(i["estado"] == "liberado" for i in do_plano), "total": len(do_plano)}
