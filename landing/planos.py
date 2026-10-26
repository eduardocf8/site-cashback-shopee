"""Planos e preços da página de vendas (appfiliado.com.br). Os mesmos valores do guia da Zouti
(marketing/appfiliado/gerar_guia_zouti.py) e os links de checkout de cada produto cadastrado
lá (marketing/appfiliado/links-checkout.md). Mudou preço? Muda lá, na Zouti e aqui."""

import itertools
import math

from django.conf import settings

# Planos de antes do lançamento do Instagram: 3 módulos e combos com desconto por quantidade.
MODULOS = ("bot", "site", "carrosseis")
# Planos do lançamento (settings.APPFILIADO_LANCAMENTO_INSTAGRAM): 4 módulos avulsos e 3 pacotes.
MODULOS_LANCAMENTO = ("bot", "site", "estudio", "automacoes")
NOMES = {"bot": "Bot de WhatsApp", "site": "Meu site", "carrosseis": "Gerador de carrosséis",
         "estudio": "Estúdio Instagram", "automacoes": "Automações do Instagram"}
NIVEIS = ("Standard", "Premium")
PRECOS = {"bot": (49.90, 89.90), "site": (22.90, 35.90), "carrosseis": (19.90, 35.90),  # mensal (Standard, Premium)
          "estudio": (29.90, 49.90), "automacoes": (29.90, 54.90)}
# Pacotes do lançamento: (código, nome, frase, módulos, fator do desconto). Todos os módulos no mesmo nível.
PACOTES = [
    ("ofertas", "Pacote Ofertas", "As suas ofertas no automático nos grupos e no seu link na bio.", ("bot", "site"), 0.90),
    ("instagram", "Pacote Instagram", "Crie, publique e responda no Instagram com o seu link de afiliado.", ("estudio", "automacoes"), 0.90),
    ("completo", "Pacote Completo", "Os 4 módulos, do WhatsApp ao Instagram, numa assinatura só.", MODULOS_LANCAMENTO, 0.85),
]
# Módulos da licença que cada produto libera (cadastro dos produtos no admin, ProdutoZouti).
CODIGOS_LICENCA = {"bot": ("whatsapp", "whatsapp_premium"), "site": ("site", "site_sem_marca"),
                   "carrosseis": ("carrosseis", "carrosseis_premium"), "estudio": ("carrosseis", "carrosseis_premium"),
                   "automacoes": ("instagram", "instagram_premium")}


def lancado() -> bool:
    return settings.APPFILIADO_LANCAMENTO_INSTAGRAM


def modulos() -> tuple:
    """Os módulos vendidos agora no site."""
    return MODULOS_LANCAMENTO if lancado() else MODULOS
DESCONTO_COMBO = {1: 1.0, 2: 0.90, 3: 0.80}  # 2 módulos: 10% a menos; 3 módulos: 20% a menos
NOTAS = [("Até 100 notas", 17.90), ("Até 500 notas", 49.90), ("Até 2.000 notas", 89.90),
         ("Até 5.000 notas", 129.90), ("Até 10.000 notas", 169.90), ("Notas ilimitadas", 229.90)]

LINKS = {
    "bot0": "https://pay.zouti.com.br/checkout?poi=prod_offer_p9rg1fgcszk7s4tzktp1av",
    "bot1": "https://pay.zouti.com.br/checkout?poi=prod_offer_54rjxzp2rqw3gn4q88p6tu",
    "site0": "https://pay.zouti.com.br/checkout?poi=prod_offer_5vymcbejsauhlc5cojz4qu",
    "site1": "https://pay.zouti.com.br/checkout?poi=prod_offer_z3dctjra387vn4pbhvvgta",
    "carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_3letx6aafxi39lmk0pwqow",
    "carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_x5nzlufsqtqaalk7jwh737",
    "bot0+site0+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_cp1st4s9ispqvesph3icsd",
    "bot1+site1+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_hgzr6nb9ofyw0fba33zrli",
    "bot0+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_4ykf3sjuyfbwt8p0vmvhl3",
    "bot0+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_11zh0j24yx65sfhsbsyluh",
    "bot1+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_smgdfbjf0hz1421u7imj6a",
    "bot1+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_55t1h7vjlmowhf6j8rpidl",
    "bot1+site0": "https://pay.zouti.com.br/checkout?poi=prod_offer_r3eecav6ws3vxdqewfl156",
    "site0+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_f38y2tssutfsfavswxwy9p",
    "site1+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_at0acntr656wz296f87i6y",
    "bot1+site1+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_dmlt8axrcic6pz7aliri8b",
    "bot0+site0": "https://pay.zouti.com.br/checkout?poi=prod_offer_t4k6zflv0kk48mflxww6vi",
    "bot0+site1": "https://pay.zouti.com.br/checkout?poi=prod_offer_agmsf88a798q6yenb91aem",
    "bot1+site1": "https://pay.zouti.com.br/checkout?poi=prod_offer_ly16x42fignxdvpr3u439n",
    "site0+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_mzs2aupdzsatwkya77vljg",
    "site1+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_txj4s7foncmv2w5hb6gz8m",
    "bot0+site0+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_pi7gczh9q0buh4caau56qv",
    "bot0+site1+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_1bxw18xl81m9xtc6j2vv3s",
    "bot0+site1+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_fg07qptvkrtqiv9r1bg9sp",
    "bot1+site0+carrosseis0": "https://pay.zouti.com.br/checkout?poi=prod_offer_ykiqiyboifv2mgi362ou16",
    "bot1+site0+carrosseis1": "https://pay.zouti.com.br/checkout?poi=prod_offer_csofwqn9hr7l9ig34qfg2v",
    # Lançamento do Instagram: Bot e Meu site seguem com os produtos de cima. Os outros entram aqui
    # quando forem criados na Zouti (vazio: o botão aparece como "Em breve").
    "estudio0": "",
    "estudio1": "",
    "automacoes0": "",
    "automacoes1": "",
    "pacote-ofertas0": "",
    "pacote-ofertas1": "",
    "pacote-instagram0": "",
    "pacote-instagram1": "",
    "pacote-completo0": "",
    "pacote-completo1": "",
}

LINKS_NOTAS = {
    "até 100 notas": "https://pay.zouti.com.br/checkout?poi=prod_offer_qw00waurucori6nmj9bm03",
    "até 500 notas": "https://pay.zouti.com.br/checkout?poi=prod_offer_bpkrexnbwksfmla48ph8pt",
    "até 2.000 notas": "https://pay.zouti.com.br/checkout?poi=prod_offer_30z5hdrchz6v5bl8ylntd4",
    "até 5.000 notas": "https://pay.zouti.com.br/checkout?poi=prod_offer_s2hzwsbvv7iizpjbfqa6qc",
    "até 10.000 notas": "https://pay.zouti.com.br/checkout?poi=prod_offer_ot6it88kl80smidjda0lh1",
    "ilimitada": "https://pay.zouti.com.br/checkout?poi=prod_offer_l8mbdn05eneb5ofreq1csf",
}


def brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preco_do_combo(total: float, n_modulos: int) -> float:
    """Desconto do combo arredondado para baixo, sempre terminando em ,90 (como na Zouti)."""
    if n_modulos == 1:
        return round(total, 2)
    return math.floor(total * DESCONTO_COMBO[n_modulos] - 0.90 + 1e-9) + 0.90


def chave(escolha: dict) -> str:
    """{'bot': 1, 'site': 0} -> 'bot1+site0' (módulos na ordem fixa, nível 0 = Standard, 1 = Premium)."""
    return "+".join(f"{m}{escolha[m]}" for m in MODULOS if m in escolha)


def nome_do_combo(escolha: dict) -> str:
    return " + ".join(f"{NOMES[m]} {NIVEIS[escolha[m]]}" for m in MODULOS if m in escolha)


def todos_os_combos() -> dict:
    """Todas as combinações vendáveis (26): chave -> nome, preço, soma dos preços separados e link."""
    saida = {}
    for n in (1, 2, 3):
        for modulos in itertools.combinations(MODULOS, n):
            for niveis in itertools.product((0, 1), repeat=n):
                escolha = dict(zip(modulos, niveis))
                separado = sum(PRECOS[m][nv] for m, nv in escolha.items())
                saida[chave(escolha)] = {
                    "nome": nome_do_combo(escolha), "preco": preco_do_combo(separado, n),
                    "separado": round(separado, 2), "link": LINKS[chave(escolha)],
                }
    return saida


def preco_do_pacote(modulos_do_pacote, nivel: int, fator: float) -> tuple[float, float]:
    """(preço do pacote, soma dos avulsos), com o desconto arredondado para baixo até terminar em ,90."""
    separado = round(sum(PRECOS[m][nivel] for m in modulos_do_pacote), 2)
    return math.floor(separado * fator - 0.90 + 1e-9) + 0.90, separado


def anual(mensal: float) -> float:
    """12 meses pelo preço de 10 (~17% de desconto), como na Zouti."""
    return round(mensal * 10, 2)


def pacotes() -> list[dict]:
    saida = []
    for codigo, nome, frase, mods, fator in PACOTES:
        niveis = []
        for nivel in (0, 1):
            preco, separado = preco_do_pacote(mods, nivel, fator)
            niveis.append({"nivel": NIVEIS[nivel], "preco": preco, "separado": separado,
                           "desconto": round((1 - preco / separado) * 100), "link": LINKS[f"pacote-{codigo}{nivel}"]})
        saida.append({"codigo": codigo, "nome": nome, "frase": frase, "modulos": [NOMES[m] for m in mods],
                      "desconto": round((1 - fator) * 100), "niveis": niveis})
    return saida


def produtos_do_lancamento() -> list[dict]:
    """Os 14 produtos da Zouti depois do lançamento: nome, mensal, anual, módulos da licença e link."""
    lista = []
    for m in MODULOS_LANCAMENTO:
        for nivel in (0, 1):
            mensal = PRECOS[m][nivel]
            lista.append({"nome": f"{NOMES[m]} {NIVEIS[nivel]}", "mensal": mensal, "anual": anual(mensal),
                          "licenca": CODIGOS_LICENCA[m][nivel], "link": LINKS[f"{m}{nivel}"], "novo": m in ("estudio", "automacoes")})
    for codigo, nome, _, mods, fator in PACOTES:
        for nivel in (0, 1):
            mensal, _ = preco_do_pacote(mods, nivel, fator)
            lista.append({"nome": f"{nome} {NIVEIS[nivel]}", "mensal": mensal, "anual": anual(mensal),
                          "licenca": ", ".join(CODIGOS_LICENCA[m][nivel] for m in mods), "link": LINKS[f"pacote-{codigo}{nivel}"],
                          "novo": True})
    return lista
