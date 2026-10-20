"""Revisão do texto das ofertas com IA (Gemini), com a chave única do Appfiliado:
quem usa o painel só liga a opção, não precisa criar chave nenhuma.

Mesmas regras do app de Windows (Appfiliado/ia_revisor.py): a IA corrige o português
e, conforme o tipo, frases que não combinam com o produto ou a chamada. Se ela mexer
em link, preço ou cupom, devolver vazio, crescer demais o texto ou der erro, sai o texto
original - a oferta nunca deixa de ir por causa da IA."""

import logging
import re
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 12  # segundos por tentativa
MAXIMO_POR_DIA = 300  # revisões por conta por dia (protege a cota da chave única)
NOMES_DOS_TIPOS = {"leve": "leve", "contextual": "contextual", "criativa": "criativa"}

REGRAS = (
    "Você revisa ofertas para WhatsApp em português do Brasil.\n"
    "Regras obrigatórias:\n"
    "- Retorne somente o texto final revisado, sem explicações e sem aspas em volta.\n"
    "- Não altere links, preços, cupons, emojis, medidas, voltagem, quantidades ou nomes próprios.\n"
    "- Mantenha exatamente igual o marcador {marcador} (é onde entra o link).\n"
    "- Não invente características técnicas, descontos, frete, garantia ou informações que não estejam no texto.\n"
    "- Preserve a estrutura geral da oferta, as quebras de linha e a ordem dos links.\n"
    "- Se não tiver certeza, faça apenas correções leves de português.\n"
)
MODOS = {
    "leve": (
        "Modo: revisão leve.\n"
        "Corrija ortografia, acentuação, pontuação e pequenas falhas de clareza. "
        "Não reescreva benefícios nem mude o tom da oferta.\n"
    ),
    "contextual": (
        "Modo: revisão contextual conservadora.\n"
        "Leia o tipo de produto e identifique frases claramente estranhas ou copiadas de outro produto. "
        "Se uma frase não combina com o produto, substitua por uma frase genérica e segura que combine com a categoria. "
        "Exemplo: se o produto for utensílio de cozinha, não diga que decora o ambiente; diga que ajuda no preparo ou organização. "
        "Se o produto for roupa/calçado, foque em conforto, estilo ou uso no dia a dia. "
        "Se o produto for decoração, foque em ambiente, charme ou estilo.\n"
    ),
    "criativa": (
        "Modo: revisão criativa controlada.\n"
        "Além de corrigir português e frases incoerentes, você pode melhorar a chamada e deixar o texto mais atraente. "
        "Mesmo assim, não crie fatos novos e não aumente promessas sobre o produto.\n"
    ),
}
TEMPERATURAS = {"leve": 0.1, "contextual": 0.25, "criativa": 0.45}


def chave() -> str:
    return getattr(settings, "APPFILIADO_GEMINI_API_KEY", "") or getattr(settings, "GEMINI_API_KEY", "")


def disponivel() -> bool:
    return bool(chave())


def _modelo() -> str:
    return getattr(settings, "APPFILIADO_GEMINI_MODELO", "") or getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")


# Quando o modelo principal está sobrecarregado (o Google responde 503 em picos de uso),
# tenta de novo e depois estes, na ordem. Modelo que não existir para a chave é pulado.
MODELOS_RESERVA = ("gemini-flash-lite-latest", "gemini-2.5-flash-lite")
ESPERAS_ANTES_DE_TENTAR_DE_NOVO = (2,)  # segundos (uma nova tentativa no modelo principal)
STATUS_PASSAGEIROS = {429, 500, 502, 503, 504}  # sobrecarga ou falha momentânea


class ErroDaIA(Exception):
    def __init__(self, mensagem: str, status: int = 0):
        super().__init__(mensagem)
        self.status = status

    @property
    def passageiro(self) -> bool:
        return self.status in STATUS_PASSAGEIROS or self.status == 0

    def para_o_painel(self) -> str:
        if self.status == 503 or "high demand" in str(self).lower() or "overloaded" in str(self).lower():
            return "O Gemini estava sobrecarregado (instabilidade do Google)"
        if self.status == 429:
            return "Limite de uso da chave do Gemini atingido"
        if self.status in (400, 401, 403) and "key" in str(self).lower():
            return "A chave do Gemini foi recusada"
        if self.status == 0:
            return "Sem resposta do Gemini (tempo esgotado ou rede)"
        return f"Erro {self.status} do Gemini"


def _chamar_modelo(modelo: str, prompt: str, temperatura: float, max_tokens: int = 1200, json_saida: bool = False,
                   timeout: int = TIMEOUT) -> str:
    """json_saida pede a resposta em JSON (usado pelo gerador de carrosséis)."""
    url = f"{settings.GEMINI_API_URL}/models/{modelo}:generateContent"
    config = {"temperature": temperatura, "maxOutputTokens": max_tokens}
    if json_saida:
        config["responseMimeType"] = "application/json"
    try:
        resposta = requests.post(
            url,
            headers={"x-goog-api-key": chave(), "Content-Type": "application/json"},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": config,
            },
            timeout=timeout,
        )
    except requests.RequestException as erro:
        raise ErroDaIA(str(erro)[:200]) from erro
    try:
        dados = resposta.json() if resposta.content else {}
    except ValueError:
        dados = {}
    if resposta.status_code >= 400 or "error" in dados:
        erro = (dados.get("error") or {}).get("message") or f"HTTP {resposta.status_code}"
        raise ErroDaIA(erro[:200], resposta.status_code)
    partes = ((dados.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "\n".join(p.get("text", "") for p in partes if not p.get("thought")).strip()


def _chamar(prompt: str, temperatura: float, esperar=time.sleep, **opcoes) -> str:
    """Modelo principal (com uma nova tentativa se for falha passageira) e, se ele
    continuar sobrecarregado, os modelos reserva. Levanta o último ErroDaIA."""
    principal = _modelo()
    tentativas = [principal] * (1 + len(ESPERAS_ANTES_DE_TENTAR_DE_NOVO))
    tentativas += [m for m in MODELOS_RESERVA if m != principal]
    ultimo = None
    for i, modelo in enumerate(tentativas):
        if 0 < i <= len(ESPERAS_ANTES_DE_TENTAR_DE_NOVO):
            esperar(ESPERAS_ANTES_DE_TENTAR_DE_NOVO[i - 1])
        try:
            return _chamar_modelo(modelo, prompt, temperatura, **opcoes)
        except ErroDaIA as erro:
            ultimo = erro
            if modelo == principal and not erro.passageiro:
                raise  # chave recusada, pedido inválido...: tentar de novo não resolve
            logger.warning("IA: %s falhou (%s %s)", modelo, erro.status, erro)
    raise ultimo


def _links(texto: str) -> list[str]:
    """Tudo que vira link no WhatsApp (com ou sem http, ex: "bit.ly/x"): a IA não pode
    tirar, trocar nem pôr nenhum."""
    from .formatador import PADRAO_LINK_QUALQUER

    return [link.rstrip(").,;!?").lower() for link in PADRAO_LINK_QUALQUER.findall(texto or "")]


def _precos(texto: str) -> list[str]:
    return [re.sub(r"\s+", "", p) for p in re.findall(r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}", texto or "")]


def _cupons(texto: str) -> list[str]:
    """Códigos em maiúsculas com número (ex: CUPOM10, SHOPEE15OFF) - não podem mudar."""
    return sorted(set(re.findall(r"\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{5,}\b", texto or "")))


def problema_na_resposta(original: str, revisado: str, marcador: str) -> str:
    """"" se a resposta pode ser usada; senão, o motivo para manter o original."""
    if not revisado:
        return "A IA não devolveu texto."
    if marcador and revisado.count(marcador) != original.count(marcador):
        return "A IA mexeu no lugar do link."
    if _links(original) != _links(revisado):
        return "A IA mexeu nos links."
    if _precos(original) != _precos(revisado):
        return "A IA mexeu em algum preço."
    if _cupons(original) != _cupons(revisado):
        return "A IA mexeu no cupom."
    if len(revisado) > max(600, len(original) * 2.2):
        return "A IA aumentou demais o texto."
    return ""


def revisar(texto: str, tipo: str, marcador: str = "") -> tuple[str, bool, str]:
    """(texto final, se foi revisado, mensagem para o painel). Nunca levanta erro."""
    if not disponivel():
        return texto, False, "Revisão com IA indisponível no momento - foi o texto original."
    tipo = tipo if tipo in MODOS else "contextual"
    prompt = f"{REGRAS.format(marcador=marcador or '(sem marcador)')}\n{MODOS[tipo]}\nTexto da oferta:\n{texto}"
    try:
        revisado = _chamar(prompt, TEMPERATURAS[tipo]).strip().strip('"').strip()
    except ErroDaIA as erro:
        logger.warning("IA: falha ao revisar oferta: %s", erro)
        return texto, False, f"{erro.para_o_painel()} - foi o texto original."
    except Exception as erro:  # noqa: BLE001 - resposta estranha etc.
        logger.warning("IA: falha ao revisar oferta: %s", erro)
        return texto, False, "A IA não respondeu - foi o texto original."
    motivo = problema_na_resposta(texto, revisado, marcador)
    if motivo:
        return texto, False, f"{motivo} Foi o texto original, por segurança."
    return revisado, True, f"Última oferta revisada pela IA ({NOMES_DOS_TIPOS[tipo]})."
