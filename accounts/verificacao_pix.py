"""Verificação da titularidade da chave Pix na Asaas (ROADMAP Fase 61).

A validação do CPF no cadastro só confere os dígitos verificadores - CPF tirado de
gerador passa. A trava real é aqui: o CPF do titular da chave Pix (que a Asaas devolve
mascarado, "***.202.745-**") tem que bater com o CPF da conta. CPF de gerador não é
titular de chave nenhuma, e saque pra chave de outra pessoa não passa.

O nome do titular também é comparado com o nome completo do cadastro, mas só marca
para conferência manual (chave_pix_nome_confere=False): bancos abreviam nomes.
"""
import logging
import unicodedata

from django.utils import timezone

from accounts.ratelimit import _incrementar_contador
from saques.asaas_client import AsaasAPIError, AsaasConfigError, AsaasIndisponivelError, consultar_chave_pix

logger = logging.getLogger(__name__)

# Consulta de chave inexistente custa 15 das 300 fichas da conta na Asaas - sem um
# limite por pessoa, ~20 tentativas erradas travariam a verificação pra todo mundo.
TENTATIVAS_POR_DIA = 3
CAMPOS_VERIFICACAO = [
    "chave_pix_status", "chave_pix_titular_nome", "chave_pix_titular_documento",
    "chave_pix_verificada_em", "chave_pix_nome_confere",
]


class LimiteDeTentativasError(Exception):
    pass


def _normalizar_nome(nome: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return [parte for parte in sem_acento.lower().split() if parte not in ("de", "da", "do", "das", "dos", "e")]


def nomes_conferem(nome_cadastro: str, nome_titular: str) -> bool | None:
    """Primeiro nome e último sobrenome iguais (sem acento, sem "de/da/dos").
    None quando falta um dos dois - não dá pra afirmar nada."""
    a, b = _normalizar_nome(nome_cadastro), _normalizar_nome(nome_titular)
    if not a or not b:
        return None
    return a[0] == b[0] and a[-1] == b[-1]


def cpf_confere(cpf_conta: str, documento_mascarado: str) -> bool:
    """Compara só as posições visíveis: "***.202.745-**" -> "***202745**" contra os 11
    dígitos da conta. Documento de 14 posições (CNPJ) ou sem nenhum dígito visível
    nunca confere - a conta é de pessoa física."""
    mascara = "".join(c for c in documento_mascarado or "" if c.isdigit() or c == "*")
    if len(mascara) != 11 or len(cpf_conta or "") != 11 or not any(c.isdigit() for c in mascara):
        return False
    return all(m == "*" or m == c for m, c in zip(mascara, cpf_conta))


def _aplicar(usuario, status, nome="", documento="", nome_confere=None):
    usuario.chave_pix_status = status
    usuario.chave_pix_titular_nome = nome
    usuario.chave_pix_titular_documento = documento
    usuario.chave_pix_nome_confere = nome_confere
    usuario.chave_pix_verificada_em = timezone.now() if status == usuario.PIX_VERIFICADA else None


def verificar_chave_pix(usuario, salvar=True, contar_tentativa=True) -> str:
    """Consulta a chave atual do usuário na Asaas e grava o resultado. Devolve o status:
    verificada / recusada / pendente (Asaas indisponível - tentar de novo depois).

    contar_tentativa=False só para a tarefa diária de pendentes (accounts/tasks), que
    já é limitada por execução."""
    if not usuario.chave_pix or not usuario.tipo_chave_pix:
        _aplicar(usuario, usuario.PIX_NAO_VERIFICADA)
    else:
        if contar_tentativa and _incrementar_contador(f"verificacao_pix:{usuario.pk}", 24 * 60 * 60) > TENTATIVAS_POR_DIA:
            raise LimiteDeTentativasError(
                "Você atingiu o limite de verificações de chave Pix por hoje. Tente de novo amanhã."
            )
        try:
            dados = consultar_chave_pix(usuario.tipo_chave_pix, usuario.chave_pix)
        except (AsaasIndisponivelError, AsaasConfigError) as erro:
            logger.warning("[pix] verificação pendente para %s: %s", usuario.pk, erro)
            _aplicar(usuario, usuario.PIX_PENDENTE)
        except AsaasAPIError as erro:
            logger.info("[pix] chave recusada para %s: %s", usuario.pk, erro)
            _aplicar(usuario, usuario.PIX_RECUSADA)
        else:
            titular = dados.get("owner") or {}
            nome, documento = titular.get("name", ""), titular.get("cpfCnpj", "")
            status = usuario.PIX_VERIFICADA if cpf_confere(usuario.cpf, documento) else usuario.PIX_RECUSADA
            _aplicar(usuario, status, nome, documento, nomes_conferem(usuario.nome_completo, nome))
    if salvar:
        usuario.save(update_fields=CAMPOS_VERIFICACAO)
    return usuario.chave_pix_status


def verificar_pendentes(limite: int = 4) -> dict:
    """Tarefa diária: tenta de novo as verificações pendentes e verifica aos poucos as
    chaves antigas (cadastradas antes da verificação existir). Prioriza quem tem
    indicação esperando o bônus. limite baixo de propósito: a Asaas aceita 5
    consultas/minuto por conta."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    usuarios = (
        get_user_model().objects
        .exclude(chave_pix="")
        .filter(chave_pix_status__in=[get_user_model().PIX_PENDENTE, get_user_model().PIX_NAO_VERIFICADA])
        .order_by("-chave_pix_status")  # "pendente" antes de "" (não verificada)
    )
    com_indicacao = usuarios.filter(Q(indicacoes_feitas__isnull=False) | Q(indicacao_recebida__isnull=False)).distinct()
    escolhidos = list(com_indicacao[:limite])
    if len(escolhidos) < limite:
        ids = [u.pk for u in escolhidos]
        escolhidos += list(usuarios.exclude(pk__in=ids)[: limite - len(escolhidos)])

    resultado = {"verificadas": 0, "recusadas": 0, "pendentes": 0}
    for usuario in escolhidos:
        status = verificar_chave_pix(usuario, contar_tentativa=False)
        chave = {"verificada": "verificadas", "recusada": "recusadas"}.get(status, "pendentes")
        resultado[chave] += 1
    return resultado
