"""Provedor da Claude (API da Anthropic), pelo SDK oficial."""

import json
import logging

import anthropic
from django.conf import settings

from ..ia import (
    MENSAGEM_PASSAR_PARA_HUMANO,
    PAPEL_ASSISTENTE,
    IAIndisponivel,
    Mensagem,
    RespostaIA,
)
from ..instrucoes import FORMATO_RESPOSTA
from ..precos import calcular_custo_usd

logger = logging.getLogger(__name__)

# Folga generosa: a resposta em si é curta, mas no Sonnet o raciocínio do modelo
# também conta aqui. Cortar no meio sairia mais caro (a conversa iria para uma pessoa)
# do que os poucos tokens a mais.
MAX_TOKENS = 4096

# Esforço de raciocínio. "low" é o indicado para conversa: responde rápido e gasta
# menos, e dúvidas de FAQ não precisam de mais. O Haiku 4.5 não aceita o parâmetro.
ESFORCO = {"claude-sonnet-5-5": "low"}

# No Sonnet 5.5, se o filtro de segurança da Anthropic recusar uma mensagem por
# engano, a própria API tenta de novo num modelo alternativo em vez de devolver a
# recusa ("default" = a Anthropic escolhe o modelo pela categoria da recusa).
# O Haiku 4.5 não tem esse filtro, então não precisa.
MODELOS_COM_ALTERNATIVO_EM_RECUSA = {"claude-sonnet-5-5"}
BETA_ALTERNATIVO_EM_RECUSA = "server-side-fallback-2026-07-01"


class ProvedorClaude:
    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise IAIndisponivel("Configure ANTHROPIC_API_KEY no .env.")
        # max_retries: o SDK já repete sozinho erros temporários (limite de uso,
        # instabilidade) com espera crescente. timeout curto porque a pessoa está
        # esperando a resposta no WhatsApp.
        self.cliente = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60, max_retries=2)

    def responder(
        self, sistema_fixo: str, sistema_do_momento: str, historico: list[Mensagem], modelo: str
    ) -> RespostaIA:
        parametros = {
            "model": modelo,
            "max_tokens": MAX_TOKENS,
            "system": [
                # O cache vale até aqui: tudo o que vem antes desta marca (instruções +
                # páginas) é cobrado a 10% do preço nas mensagens seguintes.
                {"type": "text", "text": sistema_fixo, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": sistema_do_momento},
            ],
            "messages": _mensagens_para_api(historico),
            "output_config": {"format": {"type": "json_schema", "schema": FORMATO_RESPOSTA}},
        }
        if modelo in ESFORCO:
            parametros["output_config"]["effort"] = ESFORCO[modelo]
        if modelo in MODELOS_COM_ALTERNATIVO_EM_RECUSA:
            parametros["betas"] = [BETA_ALTERNATIVO_EM_RECUSA]
            parametros["fallbacks"] = "default"

        try:
            resposta = self.cliente.beta.messages.create(**parametros)
        except anthropic.APIError as erro:
            raise IAIndisponivel(f"Erro na API da Claude: {erro}") from erro

        return _interpretar(resposta, modelo)


def _mensagens_para_api(historico: list[Mensagem]) -> list[dict]:
    mensagens = [
        {"role": "assistant" if m.papel == PAPEL_ASSISTENTE else "user", "content": m.texto}
        for m in historico
        if m.texto.strip()
    ]
    # A API exige que a conversa comece pela pessoa. Uma mensagem do bot antes da
    # primeira mensagem da pessoa (ex.: boas-vindas) não acrescenta nada à resposta.
    while mensagens and mensagens[0]["role"] == "assistant":
        mensagens.pop(0)
    if not mensagens:
        raise ValueError("O histórico precisa ter ao menos uma mensagem da pessoa.")
    return mensagens


def _interpretar(resposta, modelo_pedido: str) -> RespostaIA:
    uso = resposta.usage
    # Se a API usou o modelo alternativo (ver MODELOS_COM_ALTERNATIVO_EM_RECUSA),
    # resposta.model é ele - e é o preço dele que vale.
    modelo = resposta.model or modelo_pedido
    tokens = {
        "tokens_entrada": uso.input_tokens or 0,
        "tokens_saida": uso.output_tokens or 0,
        "tokens_cache_escrita": uso.cache_creation_input_tokens or 0,
        "tokens_cache_leitura": uso.cache_read_input_tokens or 0,
    }
    custo = calcular_custo_usd(
        modelo, tokens["tokens_entrada"], tokens["tokens_saida"],
        tokens["tokens_cache_escrita"], tokens["tokens_cache_leitura"],
    )
    if custo is None and modelo != modelo_pedido:
        # Modelo alternativo fora da tabela de preços: estima pelo modelo pedido em vez
        # de deixar o gasto do dia sem essa resposta.
        custo = calcular_custo_usd(
            modelo_pedido, tokens["tokens_entrada"], tokens["tokens_saida"],
            tokens["tokens_cache_escrita"], tokens["tokens_cache_leitura"],
        )

    def falha(motivo: str) -> RespostaIA:
        logger.warning("[assistente] resposta descartada (%s), modelo %s", motivo, modelo)
        return RespostaIA(
            texto=MENSAGEM_PASSAR_PARA_HUMANO, passar_para_humano=True, modelo=modelo,
            custo_usd=custo, motivo_falha=motivo, **tokens,
        )

    if resposta.stop_reason == "refusal":
        return falha("recusa")
    if resposta.stop_reason == "max_tokens":
        return falha("resposta_cortada")

    texto_json = next((bloco.text for bloco in resposta.content if bloco.type == "text"), "")
    try:
        dados = json.loads(texto_json)
        texto = str(dados["resposta"]).strip()
        passar_para_humano = bool(dados["passar_para_humano"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return falha("formato_invalido")
    if not texto:
        return falha("formato_invalido")

    return RespostaIA(
        texto=texto, passar_para_humano=passar_para_humano, modelo=modelo, custo_usd=custo, **tokens
    )
