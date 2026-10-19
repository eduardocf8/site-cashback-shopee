"""Contas de cor do Meu site: a pessoa pode escolher qualquer cor, então o texto por
cima dela (branco ou escuro) e o tom usado em preços sobre fundo branco são calculados
para continuarem legíveis. A prévia do editor repete estas contas em meusite.js."""

import re

PADRAO_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
TINTA_ESCURA = "#1C2B23"
ESCURO_DO_FUNDO = "#1A1A1A"
PESO_DO_FUNDO = 0.78  # fundo colorido = 78% da cor + 22% de quase preto


def valida(cor: str) -> bool:
    return bool(PADRAO_HEX.match(cor or ""))


def _rgb(cor: str) -> tuple[int, int, int]:
    return int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)


def misturar(cor: str, outra: str, peso: float) -> str:
    """peso da primeira cor (0 a 1)."""
    a, b = _rgb(cor), _rgb(outra)
    return "#" + "".join(f"{round(x * peso + y * (1 - peso)):02X}" for x, y in zip(a, b))


def luminancia(cor: str) -> float:
    def canal(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in _rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def clara(cor: str) -> bool:
    """Texto escuro fica mais legível que branco (ponto em que os dois empatam)."""
    return luminancia(cor) > 0.22


def tinta_sobre(cor: str) -> str:
    return TINTA_ESCURA if clara(cor) else "#FFFFFF"


def para_texto(cor: str) -> str:
    """A cor, escurecida se preciso, para usar como texto sobre fundo branco."""
    while luminancia(cor) > 0.3:
        cor = misturar(cor, "#000000", 0.85)
    return cor


def tema(cor: str) -> dict:
    """Variáveis CSS do site para uma cor."""
    if not valida(cor):
        cor = "#E8541E"
    fundo = misturar(cor, ESCURO_DO_FUNDO, PESO_DO_FUNDO)
    escuro = clara(fundo)
    return {
        "cor": cor,
        "fundo": fundo,
        "tinta": TINTA_ESCURA if escuro else "#FFFFFF",
        "tinta_suave": "rgba(28,43,35,.75)" if escuro else "rgba(255,255,255,.82)",
        "vidro": "rgba(0,0,0,.08)" if escuro else "rgba(255,255,255,.16)",
        "sobre_cor": tinta_sobre(cor),
        "cor_texto": para_texto(cor),
    }
