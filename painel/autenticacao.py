"""Login do painel do Appfiliado.

É separado do login da cash-b de propósito: quem usa o painel é uma
ContaAppfiliado (licencas.models), não um usuário do site de cashback - a
mesma pessoa pode ter as duas coisas com senhas diferentes, e uma nunca dá
acesso à outra. A sessão guarda o id da conta e uma assinatura da senha: trocar
a senha derruba as outras sessões abertas (mesma ideia do Django)."""

from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.ratelimit import _incrementar_contador
from licencas.models import ContaAppfiliado

SESSAO_CONTA = "painel_conta_id"
SESSAO_VERIFICACAO = "painel_verificacao"

LIMITE_FALHAS_LOGIN = 8
JANELA_FALHAS_SEGUNDOS = 15 * 60


def _assinatura_senha(conta: ContaAppfiliado) -> str:
    return salted_hmac("painel.sessao", conta.senha, algorithm="sha256").hexdigest()


def fazer_login(request, conta: ContaAppfiliado):
    request.session.cycle_key()
    request.session[SESSAO_CONTA] = conta.pk
    request.session[SESSAO_VERIFICACAO] = _assinatura_senha(conta)
    conta.ultimo_login = timezone.now()
    conta.save(update_fields=["ultimo_login", "atualizada_em"])
    request._painel_conta = conta


def fazer_logout(request):
    request.session.flush()
    request._painel_conta = None


def conta_logada(request) -> ContaAppfiliado | None:
    if hasattr(request, "_painel_conta"):
        return request._painel_conta
    conta = None
    conta_id = request.session.get(SESSAO_CONTA)
    if conta_id:
        conta = ContaAppfiliado.objects.filter(pk=conta_id).first()
        if conta and not constant_time_compare(
            request.session.get(SESSAO_VERIFICACAO, ""), _assinatura_senha(conta)
        ):
            request.session.flush()
            conta = None
    request._painel_conta = conta
    return conta


def conta_requerida(view):
    @wraps(view)
    def interna(request, *args, **kwargs):
        if conta_logada(request) is None:
            destino = reverse("painel_entrar") + "?" + urlencode({"proximo": request.get_full_path()})
            return redirect(destino)
        return view(request, *args, **kwargs)
    return interna


def destino_seguro(request, proximo: str) -> str:
    if proximo and url_has_allowed_host_and_scheme(
        proximo, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return proximo
    return reverse("painel_inicio")


# --- Proteção contra tentativa e erro no login --------------------------------------

def _chaves_falha(ip: str, email: str) -> list[str]:
    return [f"painel_login_falha:ip:{ip}", f"painel_login_falha:email:{email.lower()}"]


def login_bloqueado(ip: str, email: str) -> bool:
    return any((cache.get(chave) or 0) >= LIMITE_FALHAS_LOGIN for chave in _chaves_falha(ip, email))


def registrar_falha_login(ip: str, email: str):
    for chave in _chaves_falha(ip, email):
        _incrementar_contador(chave, JANELA_FALHAS_SEGUNDOS)


# --- Link de definir/recuperar senha ------------------------------------------------

class TokenSenhaPainel(PasswordResetTokenGenerator):
    """Mesmo mecanismo do "esqueci a senha" do Django: o link deixa de valer
    assim que a senha muda ou a pessoa entra de novo, e expira em
    PASSWORD_RESET_TIMEOUT (3 dias)."""

    key_salt = "painel.autenticacao.TokenSenhaPainel"

    def _make_hash_value(self, conta, timestamp):
        login = "" if conta.ultimo_login is None else conta.ultimo_login.replace(microsecond=0, tzinfo=None)
        return f"{conta.pk}{conta.senha}{login}{timestamp}{conta.email}"


token_senha = TokenSenhaPainel()
