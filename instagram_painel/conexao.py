"""Conectar, manter e desconectar o Instagram do afiliado."""

import base64
import hashlib
import hmac
import json
import logging
from datetime import timedelta

from django.utils import timezone

from painel import cripto

from . import api
from .models import Automacao, ContaInstagram

logger = logging.getLogger(__name__)
RENOVAR_ANTES = timedelta(days=20)  # o token vale 60 dias; renova com folga
RENOVAR_POR_VOLTA = 20


class ErroConexao(Exception):
    """Mensagem pronta para mostrar à pessoa."""


def conectar(conta, codigo: str, redirect_uri: str) -> ContaInstagram:
    """Volta do login do Instagram: troca o código pelo token de 60 dias, lê o perfil e liga os avisos."""
    try:
        curto = api.trocar_codigo(codigo, redirect_uri)
        longo = api.token_longo(curto["access_token"])
        token = longo["access_token"]
        p = api.perfil(token)
    except (api.ErroInstagram, KeyError) as erro:
        logger.warning("Instagram: falha ao conectar a conta %s: %s", conta.pk, erro)
        raise ErroConexao("Não consegui conectar o seu Instagram agora. Tente de novo em instantes.") from erro
    ig_id = str(p.get("user_id") or curto.get("user_id") or "")
    if not ig_id:
        raise ErroConexao("O Instagram não informou qual é a sua conta. Tente de novo.")
    outra = ContaInstagram.objects.filter(ig_id=ig_id).exclude(conta=conta).first()
    if outra:
        raise ErroConexao(f"O @{outra.username} já está conectado em outra conta do Appfiliado.")
    agora = timezone.now()
    ig, _ = ContaInstagram.objects.update_or_create(conta=conta, defaults={
        "ig_id": ig_id, "app_user_id": str(p.get("id") or curto.get("user_id") or "")[:64], "username": str(p.get("username") or "")[:64], "nome": str(p.get("name") or "")[:150],
        "foto": str(p.get("profile_picture_url") or "")[:1000], "token_cifrado": cripto.cifrar(token),
        "token_expira_em": agora + timedelta(seconds=int(longo.get("expires_in") or 60 * 86400)),
        "token_renovado_em": agora, "permissoes": str(curto.get("permissions") or "")[:500], "erro": "",
    })
    try:
        api.ligar_avisos(token)
        ig.avisos_ligados = True
    except api.ErroInstagram as erro:
        logger.warning("Instagram: não liguei os avisos de @%s: %s", ig.username, erro)
        ig.avisos_ligados, ig.erro = False, f"Avisos desligados: {erro}"[:300]
    ig.save(update_fields=["avisos_ligados", "erro", "atualizada_em"])
    return ig


def desconectar(conta) -> None:
    ContaInstagram.objects.filter(conta=conta).delete()
    Automacao.objects.filter(conta=conta, ativa=True).update(ativa=False)


def renovar_tokens(agora=None) -> list[str]:
    """Chamado pelo worker do painel: renova os tokens que vencem nos próximos 20 dias."""
    agora = agora or timezone.now()
    linhas = []
    vencendo = ContaInstagram.objects.filter(token_expira_em__lt=agora + RENOVAR_ANTES,
                                             token_renovado_em__lt=agora - timedelta(hours=24))
    for ig in vencendo[:RENOVAR_POR_VOLTA]:
        try:
            novo = api.renovar_token(ig.token)
            ig.token_cifrado = cripto.cifrar(novo["access_token"])
            ig.token_expira_em = agora + timedelta(seconds=int(novo.get("expires_in") or 60 * 86400))
            ig.erro = ""
            linhas.append(f"Instagram: token de @{ig.username} renovado.")
        except (api.ErroInstagram, KeyError) as erro:
            ig.erro = f"Não deu para renovar o acesso: {erro}"[:300]
            linhas.append(f"Instagram: falha ao renovar @{ig.username}: {erro}")
        ig.token_renovado_em = agora  # tenta de novo só no dia seguinte
        ig.save(update_fields=["token_cifrado", "token_expira_em", "token_renovado_em", "erro", "atualizada_em"])
    return linhas


# --- avisos da Meta quando a pessoa tira o app do Instagram ou pede para apagar os dados -----------

def ler_signed_request(valor: str) -> dict | None:
    """Confere a assinatura do signed_request (HMAC-SHA256 com o segredo do app) e devolve o conteúdo."""
    try:
        assinatura, corpo = valor.split(".", 1)
        def b64(s):
            return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        esperado = hmac.new(api.app_secret().encode(), corpo.encode(), hashlib.sha256).digest()
        if not api.app_secret() or not hmac.compare_digest(esperado, b64(assinatura)):
            return None
        return json.loads(b64(corpo))
    except (ValueError, TypeError):
        return None


def apagar_por_usuario(user_id: str) -> int:
    """Apaga a conexão (e desliga as automações) do usuário do Instagram que saiu do app."""
    apagadas = 0
    from django.db.models import Q

    for ig in ContaInstagram.objects.filter(Q(ig_id=str(user_id)) | Q(app_user_id=str(user_id))):
        desconectar(ig.conta)
        apagadas += 1
    return apagadas
