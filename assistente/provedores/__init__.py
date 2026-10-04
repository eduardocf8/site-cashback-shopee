"""Provedores de IA: cada um traduz responder() para a API de uma empresa.

Para adicionar outra empresa, crie um módulo aqui com uma classe que tenha o mesmo
método responder() de ProvedorClaude e registre-a em PROVEDORES. O nome registrado é
o valor de ASSISTENTE_IA_PROVEDOR no .env.
"""

from ..ia import IAIndisponivel
from .claude import ProvedorClaude

PROVEDORES = {
    "claude": ProvedorClaude,
}


def obter_provedor(nome: str):
    try:
        return PROVEDORES[nome]()
    except KeyError:
        raise IAIndisponivel(
            f"Provedor de IA desconhecido: {nome!r}. Opções: {', '.join(sorted(PROVEDORES))}."
        )
