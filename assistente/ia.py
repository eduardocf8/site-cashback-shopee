"""Ponto único de contato do resto do sistema com a IA.

O bot (webhook do WhatsApp, worker, admin) só conhece responder() e os tipos daqui -
nunca o SDK de uma empresa específica. Assim, trocar de modelo é só mudar
ASSISTENTE_IA_MODELO, e trocar de empresa (OpenAI, Google...) é escrever um provedor
novo em assistente/provedores/ e registrá-lo em PROVEDORES, sem mexer no bot.

Quem chama responder() precisa tratar IAIndisponivel (sem chave, fora do ar, limite
de uso): o bot deve mandar uma mensagem fixa e passar a conversa para uma pessoa.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from .base_conhecimento import dados_do_momento, montar_base
from .instrucoes import montar_instrucoes

PAPEL_PESSOA = "pessoa"
PAPEL_ASSISTENTE = "assistente"

# Usada quando a IA não consegue dar uma resposta confiável (recusou, cortou a
# resposta no meio, devolveu algo fora do formato). Na dúvida, uma pessoa assume.
MENSAGEM_PASSAR_PARA_HUMANO = (
    "Vou chamar uma pessoa da equipe para continuar seu atendimento por aqui."
)


@dataclass
class Mensagem:
    papel: str  # PAPEL_PESSOA ou PAPEL_ASSISTENTE
    texto: str


@dataclass
class RespostaIA:
    texto: str
    passar_para_humano: bool
    modelo: str  # o modelo que de fato respondeu (pode diferir do pedido, ver provedores)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_cache_escrita: int = 0
    tokens_cache_leitura: int = 0
    custo_usd: Decimal | None = None
    # Por que a resposta é a mensagem padrão em vez da do modelo: "recusa",
    # "resposta_cortada" ou "formato_invalido". None quando a resposta é do modelo.
    motivo_falha: str | None = None


class IAIndisponivel(Exception):
    """A IA não pôde ser chamada: chave ausente ou inválida, serviço fora do ar, limite
    de uso atingido. A mensagem diz o motivo (vai para o log, não para o usuário)."""


def montar_sistema() -> tuple[str, str]:
    """As duas partes do prompt de sistema: (fixa, do momento).

    A parte fixa (instruções + páginas do site) é grande e muda raramente - o provedor
    a manda em cache. A do momento (data, campanha) muda a cada minuto e vai depois,
    para não invalidar o cache."""
    fixa = f"{montar_instrucoes()}\n<base_de_conhecimento>\n{montar_base()}\n</base_de_conhecimento>"
    do_momento = f"<dados_do_momento>\n{dados_do_momento()}\n</dados_do_momento>"
    return fixa, do_momento


def responder(historico: list[Mensagem], modelo: str | None = None) -> RespostaIA:
    """Resposta do assistente para a conversa até aqui (a última mensagem é a da
    pessoa). `modelo` sobrescreve ASSISTENTE_IA_MODELO - usado na comparação entre
    modelos; o bot em si não precisa passar."""
    from .provedores import obter_provedor

    sistema_fixo, sistema_do_momento = montar_sistema()
    provedor = obter_provedor(settings.ASSISTENTE_IA_PROVEDOR)
    return provedor.responder(
        sistema_fixo=sistema_fixo,
        sistema_do_momento=sistema_do_momento,
        historico=historico,
        modelo=modelo or settings.ASSISTENTE_IA_MODELO,
    )
