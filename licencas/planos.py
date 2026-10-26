"""O que cada plano libera dentro dos módulos (limites do Standard e do Premium).

Os códigos vêm de ContaAppfiliado.modulos_liberados(); um plano maior já inclui o básico
(licencas.models.INCLUI). Mudar um número aqui vale para todo mundo na hora."""

from .models import (
    MODULO_CARROSSEIS_PREMIUM, MODULO_INSTAGRAM, MODULO_INSTAGRAM_PREMIUM, MODULO_NOTAS, MODULO_NOTAS_500, MODULO_NOTAS_2000, MODULO_NOTAS_5000,
    MODULO_NOTAS_10000, MODULO_NOTAS_ILIMITADO,
    MODULO_SITE_SEM_MARCA, MODULO_WHATSAPP_PREMIUM,
)

# Gerador de carrosséis: por dia.
CARROSSEIS = {
    False: {"geracoes": 3, "reescritas": 15},
    True: {"geracoes": 10, "reescritas": 40},
}

# Automações do Instagram: quais gatilhos e quantas pessoas respondidas por mês (cada pessoa conta
# uma vez por automação, como no histórico).
AUTOMACOES = {
    False: {"gatilhos": ("comentario",), "pessoas_por_mes": 1000},
    True: {"gatilhos": ("comentario", "story", "direto"), "pessoas_por_mes": 10000},
}

# Bot de WhatsApp.
BOT = {
    False: {"grupos": 10, "ofertas_por_grupo_dia": 60, "intervalo_minimo": 15, "copiar": False, "ia": False, "nicho": False, "mensagens_agendadas": 20,
            "alerta_produtos": 10, "alerta_intervalo_minimo": 60},
    True: {"grupos": 50, "ofertas_por_grupo_dia": 300, "intervalo_minimo": 3, "copiar": True, "ia": True, "nicho": True, "mensagens_agendadas": 50,
           "alerta_produtos": 50, "alerta_intervalo_minimo": 15},
}

# Meu site.
SITE = {
    False: {"botoes": 3, "produtos_escolhidos": False},
    True: {"botoes": 10, "produtos_escolhidos": True},
}

# Emissor NFS-e: notas de verdade por mês (None = sem limite). Vale o maior plano que a conta tiver.
NOTAS_POR_MES = [
    (MODULO_NOTAS_ILIMITADO, None), (MODULO_NOTAS_10000, 10000), (MODULO_NOTAS_5000, 5000),
    (MODULO_NOTAS_2000, 2000), (MODULO_NOTAS_500, 500), (MODULO_NOTAS, 100),
]


def _liberados(conta_ou_lista) -> list[str]:
    if isinstance(conta_ou_lista, (list, tuple, set)):
        return list(conta_ou_lista)
    return conta_ou_lista.modulos_liberados()


def carrosseis(conta) -> dict:
    return CARROSSEIS[MODULO_CARROSSEIS_PREMIUM in _liberados(conta)]


def automacoes(conta) -> dict:
    liberados = _liberados(conta)
    premium = MODULO_INSTAGRAM_PREMIUM in liberados
    return {**AUTOMACOES[premium], "premium": premium, "liberado": premium or MODULO_INSTAGRAM in liberados}


def bot_premium(conta) -> bool:
    return MODULO_WHATSAPP_PREMIUM in _liberados(conta)


def bot(conta) -> dict:
    return {**BOT[bot_premium(conta)], "premium": bot_premium(conta)}


def site_premium(conta) -> bool:
    return MODULO_SITE_SEM_MARCA in _liberados(conta)


def site(conta) -> dict:
    return {**SITE[site_premium(conta)], "premium": site_premium(conta)}


def notas_por_mes(conta) -> int | None:
    """Quantas notas de verdade a conta pode emitir no mês (None = sem limite; 0 = sem o módulo)."""
    liberados = _liberados(conta)
    for codigo, limite in NOTAS_POR_MES:
        if codigo in liberados:
            return limite
    return 0
