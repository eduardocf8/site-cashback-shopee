"""O que cada plano libera dentro dos módulos (limites do Standard e do Premium).

Os códigos vêm de ContaAppfiliado.modulos_liberados(); um plano maior já inclui o básico
(licencas.models.INCLUI). Mudar um número aqui vale para todo mundo na hora."""

from .models import (
    MODULO_CARROSSEIS_PREMIUM, MODULO_NOTAS, MODULO_NOTAS_1000, MODULO_NOTAS_5000, MODULO_NOTAS_ILIMITADO,
    MODULO_SITE_SEM_MARCA, MODULO_WHATSAPP_PREMIUM,
)

# Gerador de carrosséis: por dia.
CARROSSEIS = {
    False: {"geracoes": 3, "reescritas": 15},
    True: {"geracoes": 10, "reescritas": 40},
}

# Bot de WhatsApp.
BOT = {
    False: {"grupos": 3, "ofertas_por_grupo_dia": 30, "intervalo_minimo": 15, "copiar": False, "ia": False},
    True: {"grupos": 20, "ofertas_por_grupo_dia": 100, "intervalo_minimo": 3, "copiar": True, "ia": True},
}

# Meu site.
SITE = {
    False: {"botoes": 3, "produtos_escolhidos": False},
    True: {"botoes": 10, "produtos_escolhidos": True},
}

# Emissão NFS-e: notas de verdade por mês (None = sem limite). Vale o maior plano que a conta tiver.
NOTAS_POR_MES = [(MODULO_NOTAS_ILIMITADO, None), (MODULO_NOTAS_5000, 5000), (MODULO_NOTAS_1000, 1000), (MODULO_NOTAS, 100)]


def _liberados(conta_ou_lista) -> list[str]:
    if isinstance(conta_ou_lista, (list, tuple, set)):
        return list(conta_ou_lista)
    return conta_ou_lista.modulos_liberados()


def carrosseis(conta) -> dict:
    return CARROSSEIS[MODULO_CARROSSEIS_PREMIUM in _liberados(conta)]


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
