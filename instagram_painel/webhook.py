"""Os avisos da Meta (webhook) das contas dos afiliados: comentário, resposta a story e DM.

O endereço do webhook é um só para o app da Meta (automacao_instagram/views.webhook_instagram). Ele
chama separar_e_processar() primeiro: os avisos de contas conectadas aqui são tratados aqui e o resto
segue para a automação da cash-b.

Regras:
- nunca reage ao que a própria conta fez (as respostas dela também chegam como aviso);
- responde cada pessoa uma vez por automação (e cada aviso uma vez só: a Meta repete avisos);
- respeita um limite por hora por conta, para não cair nas regras de spam do Instagram."""

import logging
import random
import re
import unicodedata
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import api
from .models import Automacao, ContaInstagram, Disparo

logger = logging.getLogger(__name__)
LIMITE_POR_HORA = 150
LIMITE_DM = 1000  # bytes, regra do Instagram


def _normal(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def palavras(automacao: Automacao) -> list[str]:
    return [p for p in (_normal(x).strip() for x in re.split(r"[\n,;]+", automacao.palavras or "")) if p]


def bate(automacao: Automacao, texto: str) -> bool:
    """Sem palavras: qualquer texto (menos na DM). Com palavras: alguma delas aparece como palavra inteira."""
    lista = palavras(automacao)
    if not lista:
        return automacao.gatilho != Automacao.DIRETO
    alvo = _normal(texto)
    return any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", alvo) for p in lista)


def texto_da_dm(automacao: Automacao) -> str:
    texto = (automacao.texto_dm or "").strip()
    if automacao.link and automacao.link not in texto:
        texto = f"{texto}\n\n{automacao.link}".strip()
    while len(texto.encode("utf-8")) > LIMITE_DM:
        texto = texto[:-10]
    return texto


def resposta_publica(automacao: Automacao, username: str) -> str:
    opcoes = [x.strip() for x in (automacao.respostas or "").splitlines() if x.strip()]
    if not opcoes:
        return ""
    return random.choice(opcoes).replace("{nome}", f"@{username}" if username else "").strip()[:300]


def _no_limite(ig: ContaInstagram) -> bool:
    desde = timezone.now() - timedelta(hours=1)
    return Disparo.objects.filter(automacao__conta=ig.conta, criado_em__gte=desde).count() >= LIMITE_POR_HORA


def _escolher(ig: ContaInstagram, gatilho: str, midia_id: str, texto: str) -> Automacao | None:
    """A automação do post/story específico vem antes da que vale para todos."""
    ativas = Automacao.objects.filter(conta=ig.conta, gatilho=gatilho, ativa=True)
    especificas = [a for a in ativas if midia_id and a.midia_id == midia_id]
    gerais = [a for a in ativas if not a.midia_id]
    return next((a for a in especificas + gerais if bate(a, texto)), None)


def _registrar(automacao: Automacao, evento_id: str, autor_id: str, username: str, texto: str) -> Disparo | None:
    """Cria o registro antes de responder: se a Meta repetir o aviso, ou a pessoa já foi respondida, não sai de novo."""
    if automacao.disparos.filter(autor_id=autor_id).exists():
        return None
    try:
        with transaction.atomic():
            return Disparo.objects.create(automacao=automacao, evento_id=evento_id[:200], autor_id=autor_id[:64],
                                          autor_username=username[:64], texto=str(texto or "")[:2000])
    except IntegrityError:
        return None


def _comentario(ig: ContaInstagram, valor: dict) -> None:
    autor = valor.get("from") or {}
    autor_id, username = str(autor.get("id") or ""), str(autor.get("username") or "")
    comentario_id = str(valor.get("id") or "")
    if not comentario_id or not autor_id or autor_id == ig.ig_id or username.lower() == ig.username.lower():
        return  # sem dados ou é a própria conta (inclusive as respostas que a automação publica)
    if valor.get("parent_id"):
        return  # resposta dentro de outro comentário: fica de fora, como no ManyChat
    midia_id = str((valor.get("media") or {}).get("id") or "")
    automacao = _escolher(ig, Automacao.COMENTARIO, midia_id, valor.get("text", ""))
    if not automacao or _no_limite(ig):
        return
    d = _registrar(automacao, comentario_id, autor_id, username, valor.get("text", ""))
    if not d:
        return
    erros = []
    token = ig.token
    if automacao.responder_comentario and (texto := resposta_publica(automacao, username)):
        try:
            api.responder_comentario(token, comentario_id, texto)
            d.resposta_ok = True
        except api.ErroInstagram as erro:
            erros.append(f"Resposta: {erro}")
    if automacao.enviar_dm and (texto := texto_da_dm(automacao)):
        try:
            api.resposta_privada(token, ig.ig_id, comentario_id, texto)
            d.dm_ok = True
        except api.ErroInstagram as erro:
            erros.append(f"DM: {erro}")
    d.erro = " · ".join(erros)[:400]
    d.save(update_fields=["resposta_ok", "dm_ok", "erro"])


def _mensagem(ig: ContaInstagram, evento: dict) -> None:
    msg = evento.get("message") or {}
    if not msg or msg.get("is_echo") or msg.get("is_deleted") or msg.get("is_self"):
        return
    autor_id = str((evento.get("sender") or {}).get("id") or "")
    mid = str(msg.get("mid") or "")
    if not autor_id or autor_id == ig.ig_id or not mid:
        return
    story = (msg.get("reply_to") or {}).get("story") or {}
    if story.get("id"):
        automacao = _escolher(ig, Automacao.STORY, str(story["id"]), msg.get("text", ""))
    else:
        automacao = _escolher(ig, Automacao.DIRETO, "", msg.get("text", ""))
    if not automacao or not automacao.enviar_dm or _no_limite(ig):
        return
    d = _registrar(automacao, mid, autor_id, "", msg.get("text", ""))
    if not d:
        return
    try:
        api.mensagem(ig.token, ig.ig_id, autor_id, texto_da_dm(automacao))
        d.dm_ok = True
    except api.ErroInstagram as erro:
        d.erro = f"DM: {erro}"[:400]
    d.save(update_fields=["dm_ok", "erro"])


def separar_e_processar(payload: dict) -> dict:
    """Trata os avisos das contas conectadas no Appfiliado e devolve o payload para a automação da cash-b.

    Os avisos de uma conta conectada também seguem para a cash-b: a mesma conta (a @usecashb, por
    exemplo) pode estar nos dois lugares, e cada lado só responde onde tem automação configurada."""
    entradas = payload.get("entry") or []
    ids = {str(e.get("id")) for e in entradas if isinstance(e, dict)}
    contas = {ig.ig_id: ig for ig in ContaInstagram.objects.filter(ig_id__in=ids).select_related("conta")}
    for entrada in entradas:
        ig = contas.get(str(entrada.get("id"))) if isinstance(entrada, dict) else None
        if not ig:
            continue
        for change in entrada.get("changes") or []:
            try:
                if change.get("field") == "comments" and isinstance(change.get("value"), dict):
                    _comentario(ig, change["value"])
                elif change.get("field") == "messages" and isinstance(change.get("value"), dict):
                    _mensagem(ig, change["value"])
            except Exception:
                logger.exception("Instagram: falha ao tratar aviso de @%s", ig.username)
        for evento in entrada.get("messaging") or []:
            try:
                _mensagem(ig, evento)
            except Exception:
                logger.exception("Instagram: falha ao tratar mensagem de @%s", ig.username)
    return payload
