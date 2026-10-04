"""Preço por token de cada modelo, para calcular quanto cada resposta custou.

É a base do teto diário de gasto (quando o bot existir) e do relatório de comparação
entre modelos. Os valores são os da tabela pública da API (US$ por 1 milhão de tokens)
e precisam ser revistos se a Anthropic mudar o preço - confira em
https://platform.claude.com/docs/en/about-claude/pricing antes de mexer.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Preco:
    entrada: Decimal  # US$ por 1 milhão de tokens de entrada sem cache
    saida: Decimal  # US$ por 1 milhão de tokens de saída (inclui o raciocínio do modelo)

    # Na API da Claude, gravar no cache custa 1,25x a entrada (cache de 5 minutos) e
    # ler do cache custa 0,1x - é o que deixa barato mandar a base inteira toda vez.
    @property
    def cache_escrita(self) -> Decimal:
        return self.entrada * Decimal("1.25")

    @property
    def cache_leitura(self) -> Decimal:
        return self.entrada * Decimal("0.1")


PRECOS = {
    "claude-sonnet-5-5": Preco(entrada=Decimal("2"), saida=Decimal("10")),
    "claude-haiku-4-5": Preco(entrada=Decimal("1"), saida=Decimal("5")),
}


def calcular_custo_usd(
    modelo: str, entrada: int, saida: int, cache_escrita: int = 0, cache_leitura: int = 0
) -> Decimal | None:
    """Custo em US$ de uma chamada, ou None se o modelo não está na tabela (aí quem chama
    decide o que fazer - o teto de gasto, por exemplo, deve tratar como desconhecido em
    vez de contar zero)."""
    preco = PRECOS.get(modelo)
    if preco is None:
        return None
    total = (
        entrada * preco.entrada
        + saida * preco.saida
        + cache_escrita * preco.cache_escrita
        + cache_leitura * preco.cache_leitura
    )
    return total / Decimal("1000000")
