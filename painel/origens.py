"""De onde veio cada venda: Bot de WhatsApp, Meu site, Conversor de links, outras ferramentas do
Appfiliado (Radar, Alerta de preço, Carrosséis, Instagram) ou fora do Appfiliado.

A Shopee não diz a origem da venda, só devolve os Sub IDs do link. Por isso todo link que o
Appfiliado gera leva uma MARCA de origem num dos 5 Sub IDs (o último livre; se a pessoa já usa os
5, vai sem marca). A marca some do Sub ID mostrado nas telas (resultados.sub_id) e vira o campo
VendaItem.origem.

Venda de link sem a marca (links antigos, ou com os 5 Sub IDs ocupados): a origem é deduzida pelo
Sub ID - os da Automação do bot (padrão e de cada grupo), os do Meu site, o padrão do conversor e os
fixos das outras ferramentas. O resto (inclusive sem Sub ID) é "fora do Appfiliado"."""

BOT, SITE, CONVERSOR, OUTRAS, FORA = "bot", "site", "conversor", "outras", "fora"
NOMES = {BOT: "Bot de WhatsApp", SITE: "Meu site", CONVERSOR: "Conversor de links", OUTRAS: "Outras ferramentas",
         FORA: "Fora do Appfiliado"}
NOMES_CURTOS = {**NOMES, CONVERSOR: "Conversor"}
CORES = {BOT: "#1F3A2E", SITE: "#E8A317", CONVERSOR: "#5B8C74", OUTRAS: "#A9C7B5", FORA: "#CFC6B8"}
ORDEM = [BOT, SITE, CONVERSOR, OUTRAS, FORA]

# Ferramenta que gera o link -> marca no Sub ID (só letras e números, como a Shopee exige).
MARCAS = {"bot": "apbot", "site": "apsite", "conversor": "apconv", "radar": "apradar", "alerta": "apalerta",
          "carrossel": "apcarr", "instagram": "apinsta"}
ORIGEM_DA_MARCA = {"apbot": BOT, "apsite": SITE, "apconv": CONVERSOR, "apradar": OUTRAS, "apalerta": OUTRAS,
                   "apcarr": OUTRAS, "apinsta": OUTRAS}
MAXIMO_SUB_IDS = 5
# Sub IDs fixos das ferramentas (para as vendas de links sem marca).
SUB_IDS_DO_CONVERSOR = {"conversor"}
SUB_IDS_DE_OUTRAS = {"radar", "alerta", "instagram"}


def com_marca(sub_ids, ferramenta: str) -> list[str]:
    """Os Sub IDs do link com a marca da ferramenta no fim (se couber)."""
    lista = list(sub_ids or [])
    marca = MARCAS.get(ferramenta)
    if marca and len(lista) < MAXIMO_SUB_IDS and marca not in lista:
        lista.append(marca)
    return lista


def separar_marca(partes: list[str]) -> tuple[list[str], str]:
    """(Sub IDs sem as marcas, origem da marca ou "")."""
    origem = next((ORIGEM_DA_MARCA[p.lower()] for p in partes if p.lower() in ORIGEM_DA_MARCA), "")
    return [p for p in partes if p.lower() not in ORIGEM_DA_MARCA], origem


class Classificador:
    """Origem de uma venda pela marca ou, sem ela, pelo Sub ID (rótulo "a-b" como em VendaItem.sub_id)."""

    def __init__(self, rotulos_do_bot=(), rotulos_do_site=()):
        self.bot = {r.lower() for r in rotulos_do_bot if r}
        self.site = {r.lower() for r in rotulos_do_site if r}

    def origem(self, rotulo: str, marca: str = "") -> str:
        if marca:
            return marca
        rotulo = (rotulo or "").lower()
        if rotulo in self.bot:
            return BOT
        if rotulo in self.site:
            return SITE
        if rotulo in SUB_IDS_DO_CONVERSOR:
            return CONVERSOR
        if rotulo in SUB_IDS_DE_OUTRAS:
            return OUTRAS
        return FORA


def rotulos_do_bot(config) -> set[str]:
    """Os rótulos dos links do bot: o padrão da Automação e o de cada grupo."""
    if not config:
        return set()
    listas = [config.sub_ids, *(config.sub_ids_por_grupo or {}).values()]
    return {"-".join(s.strip() for s in str(texto or "").split(",") if s.strip())[:120] for texto in listas} - {""}


def classificador_da_conta(conta) -> Classificador:
    from bot_whatsapp.models import ConfiguracaoOfertas
    from meusite.models import SiteAfiliado

    config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
    site = SiteAfiliado.objects.filter(conta=conta).first()
    return Classificador(rotulos_do_bot(config), [site.sub_id, site.sub_id_vitrine] if site else [])
