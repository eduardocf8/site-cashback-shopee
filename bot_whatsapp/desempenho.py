"""Resultados das ofertas do bot (aba Resultados do Bot de WhatsApp): quanto cada oferta enviada vendeu.

Nada novo é gravado no envio: a tela cruza, no período escolhido, os envios guardados (EnvioWhatsApp)
com os itens vendidos guardados (painel.VendaItem, 13 meses).

Regra: a venda é da oferta quando é do mesmo produto e foi comprada até JANELA depois do envio (a
mesma janela de atribuição de 7 dias da Shopee). Se o produto foi enviado mais de uma vez, fica com o
envio mais recente antes da compra. Com Sub ID no grupo, só contam as vendas com aquele Sub ID (a
venda do mesmo produto vinda do Instagram ou do Meu site fica de fora); sem Sub ID, entra qualquer
venda do produto (menos preciso - a tela avisa). A venda só é separada por grupo quando o Sub ID é
só daquele grupo.

Uma "oferta" é um produto posto na fila de uma vez (um envio por grupo, criados no mesmo minuto).
Com muitos grupos são muitos envios (200 grupos x 100 ofertas por dia): as contagens saem somadas do
banco, e os envios um a um só são lidos para os produtos que venderam, nos grupos com Sub ID próprio."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Max, Min
from django.db.models.functions import TruncMinute
from django.utils import timezone

from .models import ConfiguracaoOfertas, EnvioWhatsApp

JANELA = timedelta(days=7)
ORIGENS = (EnvioWhatsApp.OFERTA, EnvioWhatsApp.ALERTA)
FAIXAS_DE_HORARIO = [(0, 7), (7, 9), (9, 12), (12, 14), (14, 18), (18, 21), (21, 24)]
MINIMO_PARA_MELHOR_HORARIO = 5  # ofertas na faixa para ela poder ser "o melhor horário"
CAMPEAS = 10
MAXIMO_DE_DIAS = 92


def _momento(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def _minuto(momento: datetime) -> datetime:
    return momento.replace(second=0, microsecond=0)


def calcular(conta, inicio: date, fim: date) -> dict:
    from painel.models import VendaItem

    de, ate = _momento(inicio), _momento(fim + timedelta(days=1))
    config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
    enviados = (EnvioWhatsApp.objects.filter(conta=conta, estado=EnvioWhatsApp.ENVIADO, origem__in=ORIGENS)
                .exclude(item_id="").order_by())

    # 1. As ofertas (somadas no banco): do período e as da semana seguinte - um envio mais novo do mesmo
    # produto "fica" com a venda.
    linhas = (enviados.filter(enviado_em__gte=de, enviado_em__lt=ate + JANELA)
              .annotate(minuto=TruncMinute("criado_em")).values("item_id", "minuto")
              .annotate(enviado_em=Min("enviado_em"), envios=Count("id"), produto=Max("produto"), imagem_url=Max("imagem_url")))
    ofertas_por_item = defaultdict(list)
    ofertas = {}
    for linha in linhas:
        chave = (linha["item_id"], _minuto(linha["minuto"]))
        oferta = {**linha, "chave": chave, "no_periodo": linha["enviado_em"] < ate}
        ofertas_por_item[linha["item_id"]].append(oferta)
        if oferta["no_periodo"]:
            ofertas[chave] = oferta
    for lista in ofertas_por_item.values():
        lista.sort(key=lambda o: o["enviado_em"])

    # 2. Os grupos do período e o Sub ID de cada um.
    grupos = {}
    for linha in (enviados.filter(enviado_em__gte=de, enviado_em__lt=ate).values("destino")
                  .annotate(envios=Count("id"), nome=Max("destino_nome"))):
        rotulo = "-".join(config.lista_sub_ids(linha["destino"])) if config else ""
        grupos[linha["destino"]] = {"jid": linha["destino"], "nome": linha["nome"] or linha["destino"],
                                    "ofertas": linha["envios"], "rotulo": rotulo, "comissao": Decimal(0), "venderam": set()}
    grupos_por_rotulo = defaultdict(set)
    for g in grupos.values():
        if g["rotulo"]:
            grupos_por_rotulo[g["rotulo"]].add(g["jid"])
    for g in grupos.values():
        g["separavel"] = bool(g["rotulo"]) and len(grupos_por_rotulo[g["rotulo"]]) == 1
    tem_grupo_sem_sub_id = any(not g["rotulo"] for g in grupos.values())

    # 3. As vendas dos produtos oferecidos.
    vendas = list(VendaItem.objects.filter(conta=conta, item_id__in=list(ofertas_por_item), comprado_em__gte=de,
                                           comprado_em__lt=ate + JANELA)
                  .exclude(situacao=VendaItem.CANCELADO)
                  .values("item_id", "pedido_id", "sub_id", "comissao", "comprado_em", "nome", "imagem_url"))

    # 4. Nos grupos com Sub ID só deles: os envios um a um, só dos produtos vendidos com aquele Sub ID.
    rotulos_vendidos = {v["sub_id"] for v in vendas}
    destinos = [g["jid"] for g in grupos.values() if g["separavel"] and g["rotulo"] in rotulos_vendidos]
    envios_por_grupo = defaultdict(list)  # (item_id, jid) -> [(enviado_em, chave da oferta)]
    if destinos:
        for e in (enviados.filter(destino__in=destinos, item_id__in={v["item_id"] for v in vendas},
                                  enviado_em__gte=de, enviado_em__lt=ate + JANELA)
                  .values("item_id", "destino", "criado_em", "enviado_em").order_by("enviado_em")):
            envios_por_grupo[(e["item_id"], e["destino"])].append((e["enviado_em"], (e["item_id"], _minuto(e["criado_em"]))))

    unico_por_rotulo = {r: next(iter(js)) for r, js in grupos_por_rotulo.items() if len(js) == 1}
    atribuidas = []
    for venda in vendas:
        comprado = venda["comprado_em"]
        grupo = unico_por_rotulo.get(venda["sub_id"])
        if grupo:
            candidatos = [c for momento, c in envios_por_grupo[(venda["item_id"], grupo)] if momento <= comprado <= momento + JANELA]
        elif venda["sub_id"] in grupos_por_rotulo or tem_grupo_sem_sub_id:
            # Sub ID de vários grupos, ou grupo sem Sub ID: a oferta certa, mas sem saber o grupo.
            grupo = None
            candidatos = [o["chave"] for o in ofertas_por_item[venda["item_id"]]
                          if o["enviado_em"] <= comprado <= o["enviado_em"] + JANELA]
        else:
            continue  # veio de outro lugar (outro Sub ID)
        if not candidatos or candidatos[-1] not in ofertas:
            continue  # sem envio antes, ou o envio mais recente é de depois do período
        atribuidas.append({**venda, "oferta": candidatos[-1], "grupo": grupo})

    vendeu = defaultdict(lambda: {"comissao": Decimal(0), "pedidos": set()})
    for v in atribuidas:
        vendeu[v["oferta"]]["comissao"] += v["comissao"]
        vendeu[v["oferta"]]["pedidos"].add(v["pedido_id"])
        if v["grupo"] in grupos:
            grupos[v["grupo"]]["comissao"] += v["comissao"]
            grupos[v["grupo"]]["venderam"].add(v["oferta"])

    comissao = sum((v["comissao"] for v in atribuidas), Decimal(0))
    total = len(ofertas)
    return {
        "inicio": inicio, "fim": fim,
        "ofertas": total,
        "envios": sum(g["ofertas"] for g in grupos.values()),
        "grupos": len(grupos),
        "venderam": len(vendeu),
        "percentual_venderam": round(len(vendeu) * 100 / total) if total else 0,
        "pedidos": len({v["pedido_id"] for v in atribuidas}),
        "comissao": comissao,
        "por_oferta": (comissao / total) if total else Decimal(0),
        "por_dia": _por_dia(inicio, fim, ofertas, vendeu),
        "campeas": _campeas(ofertas, vendeu, atribuidas),
        "por_grupo": _por_grupo(grupos),
        "por_horario": _por_horario(ofertas, vendeu),
        "sem_sub_id": tem_grupo_sem_sub_id,
        "sub_id_repetido": any(len(js) > 1 for js in grupos_por_rotulo.values()),
        "exemplo_sub_id": next((g["rotulo"] for g in grupos.values() if g["rotulo"]), ""),
    }


def _por_dia(inicio, fim, ofertas, vendeu) -> list[dict]:
    """Comissão das ofertas de cada dia (pela data do envio)."""
    somas = defaultdict(Decimal)
    for chave, oferta in ofertas.items():
        if chave in vendeu:
            somas[timezone.localtime(oferta["enviado_em"]).date()] += vendeu[chave]["comissao"]
    dias = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    maior = max([somas[d] for d in dias] + [Decimal(0)])
    return [{"dia": d, "comissao": somas[d], "altura": round(somas[d] * 100 / maior) if maior else 0} for d in dias]


def _campeas(ofertas, vendeu, atribuidas) -> list[dict]:
    por_item = {}
    for chave, oferta in ofertas.items():
        item = por_item.setdefault(oferta["item_id"], {
            "item_id": oferta["item_id"], "produto": oferta["produto"], "imagem_url": oferta["imagem_url"],
            "vezes": 0, "ultimo": oferta["enviado_em"], "comissao": Decimal(0), "pedidos": set()})
        item["vezes"] += 1
        item["ultimo"] = max(item["ultimo"], oferta["enviado_em"])
        if chave in vendeu:
            item["comissao"] += vendeu[chave]["comissao"]
            item["pedidos"] |= vendeu[chave]["pedidos"]
    for v in atribuidas:  # nome e foto que a Shopee mandou, se o envio não guardou
        item = por_item.get(v["item_id"])
        if item and not item["produto"]:
            item["produto"] = v["nome"]
        if item and not item["imagem_url"]:
            item["imagem_url"] = v["imagem_url"]
    lista = sorted((i for i in por_item.values() if i["comissao"] > 0), key=lambda i: -i["comissao"])[:CAMPEAS]
    maior = lista[0]["comissao"] if lista else 0
    for i in lista:
        i["pedidos"] = len(i["pedidos"])
        i["por_envio"] = i["comissao"] / i["vezes"]
        i["barra"] = round(i["comissao"] * 100 / maior) if maior else 0
    return lista


def _por_grupo(grupos: dict) -> list[dict]:
    lista = []
    for g in grupos.values():
        lista.append({**g, "venderam": round(len(g["venderam"]) * 100 / g["ofertas"]) if g["ofertas"] else 0,
                      "por_oferta": g["comissao"] / g["ofertas"] if g["ofertas"] else Decimal(0)})
    return sorted(lista, key=lambda g: (not g["separavel"], -g["comissao"], -g["ofertas"], str(g["nome"]).lower()))


def _por_horario(ofertas, vendeu) -> dict:
    faixas = []
    for de, ate in FAIXAS_DE_HORARIO:
        chaves = [c for c, o in ofertas.items() if de <= timezone.localtime(o["enviado_em"]).hour < ate]
        if not chaves:
            continue
        comissao = sum((vendeu[c]["comissao"] for c in chaves if c in vendeu), Decimal(0))
        faixas.append({"nome": f"{de}h–{ate}h", "ofertas": len(chaves), "comissao": comissao,
                       "por_oferta": comissao / len(chaves)})
    validas = [f for f in faixas if f["ofertas"] >= MINIMO_PARA_MELHOR_HORARIO and f["por_oferta"] > 0]
    melhor = max(validas, key=lambda f: f["por_oferta"]) if validas else None
    maior = max([f["por_oferta"] for f in faixas] + [Decimal(0)])
    for f in faixas:
        f["barra"] = round(f["por_oferta"] * 100 / maior) if maior else 0
        f["melhor"] = f is melhor
    return {"faixas": faixas, "melhor": melhor}
