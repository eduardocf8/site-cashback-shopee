"""O que aparece no menu do painel e o estado de cada módulo para uma conta:
liberado, "Em breve" (ainda não construído no painel) ou bloqueado (o plano
não inclui - mostra cadeado e o convite para assinar)."""

from django.urls import reverse

from licencas.models import (
    MODULO_CARROSSEIS,
    MODULO_CARROSSEIS_PREMIUM,
    MODULO_INSTAGRAM,
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
    "conversor": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    "copiar": "M8 8h11v11H8zM5 16V5h11",
    "radar": "M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 12l6-6M17 3v4h4",
    "enviar": "M4 12l16-8-6 16-2-7z",
    "sino": "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0",
    "imagens": "M7 5h10v14H7zM3 7v10M21 7v10",
}

# slug -> configuração. "modulo": código da licença que libera (None = todos
# têm). "pronto": já existe no painel. "teste": já funciona, mas em versão de teste. "so_em_breve": ainda não dá para vender
# para ninguém (ex: Instagram, esperando a Meta).
MODULOS_DO_MENU = [
    {"slug": "inicio", "nome": "Início", "icone": "inicio", "modulo": None, "pronto": True},
    {"slug": "resultados", "nome": "Resultados", "icone": "resultados", "modulo": None, "pronto": True},
    {"slug": "metas", "nome": "Metas", "icone": "metas", "modulo": None, "pronto": True},
    {"slug": "radar", "nome": "Radar de ofertas", "icone": "radar", "modulo": None, "pronto": True},
    {"slug": "conversor", "nome": "Conversor de links", "icone": "conversor", "modulo": None, "pronto": True},
    {
        "slug": "whatsapp", "nome": "Bot de WhatsApp", "icone": "whatsapp", "modulo": MODULO_WHATSAPP,
        "pronto": True, "teste": True,
        "texto_bloqueado": "Envie ofertas com seu link de afiliado nos seus grupos e canais do WhatsApp, "
                           "no automático.",
    },
    {
        "slug": "site", "nome": "Meu site", "icone": "site", "modulo": MODULO_SITE, "pronto": True,
        "texto_em_breve": "Você vai editar aqui o seu site com conversor de links e vitrine "
                          "de produtos, no endereço seunome.appfiliado.com.br.",
        "texto_bloqueado": "Tenha seu próprio site com conversor de links e vitrine de produtos, pronto "
                           "para usar como link na bio.",
    },
    {
        "slug": "carrosseis", "nome": "Carrosséis", "icone": "carrosseis", "modulo": MODULO_CARROSSEIS,
        # o premium libera o gerador inteiro, sem precisar do básico junto
        "modulos_que_liberam": [MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM], "pronto": True,
        "texto_bloqueado": "Cole o link de um produto da Shopee e receba um carrossel pronto para o "
                           "Instagram, com textos feitos por IA e o seu link de afiliado.",
    },
    {
        "slug": "notas", "nome": "Emissão NFS-e", "icone": "notas", "modulo": MODULO_NOTAS, "pronto": True,
        "teste": True,
        "texto_bloqueado": "Emita no automático a nota da Shopee e as notas de cada vendedor que pagou "
                           "comissão extra, e mande cada uma por e-mail para o vendedor.",
    },
    {
        "slug": "instagram", "nome": "Instagram", "icone": "instagram", "modulo": MODULO_INSTAGRAM,
        "pronto": False, "so_em_breve": True,
        "texto_em_breve": "Responda comentários e mande o link por mensagem direta, no automático.",
    },
    {"slug": "configuracoes", "nome": "Configurações", "icone": "configuracoes", "modulo": None, "pronto": True},
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
    "notas": "painel_notas",
    "configuracoes": "painel_configuracoes",
}


def estado(item: dict, liberados: list[str]) -> str:
    """"liberado", "em_breve" ou "bloqueado"."""
    if item.get("so_em_breve"):
        return "em_breve"
    if item["modulo"] and not set(item.get("modulos_que_liberam") or [item["modulo"]]) & set(liberados):
        return "bloqueado"
    return "liberado" if item["pronto"] else "em_breve"


def menu(liberados: list[str], ativo: str) -> list[dict]:
    itens = []
    for item in MODULOS_DO_MENU:
        situacao = estado(item, liberados)
        url_name = URL_DE_SLUG.get(item["slug"])
        href = reverse(url_name) if url_name else reverse("painel_modulo", args=[item["slug"]])
        selo = {"bloqueado": ("Desbloquear", "bloqueado"), "em_breve": ("Em breve", "breve")}.get(situacao)
        if situacao == "liberado" and item.get("teste"):
            selo = ("Teste", "breve")
        itens.append({
            **item,
            "href": href,
            "ativo": item["slug"] == ativo,
            "estado": situacao,
            "selo_texto": selo[0] if selo else "",
            "selo_tipo": selo[1] if selo else "",
            "icone_path": ICONES[item["icone"]],
        })
    return itens
