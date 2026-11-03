"""Os avisos da Meta (webhook) das contas dos afiliados: comentário, resposta a story e DM.

O endereço do webhook é um só para o app da Meta (automacao_instagram/views.webhook_instagram). Ele
chama separar_e_processar() primeiro: os avisos de contas conectadas aqui são tratados aqui e o resto
segue para a automação da cash-b.

Regras:
- nunca reage ao que a própria conta fez (as respostas dela também chegam como aviso);
- responde cada pessoa uma vez por automação (e cada aviso uma vez só: a Meta repete avisos);
- não tem limite por mês. O Instagram aceita até 750 DMs de resposta a comentário por hora em cada conta:
  passando disso (post viralizando), as respostas entram numa fila e saem na hora seguinte, em ordem;
- respeita o plano: o Standard só responde comentários; o Premium, também stories e DMs (licencas/planos.py)."""

import logging
import random
import re
import unicodedata
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from licencas import planos

from . import api
from .models import AnuncioVisto, Automacao, AvisoRecebido, ContaInstagram, Disparo

logger = logging.getLogger(__name__)
# A Meta aceita 750 DMs de resposta a comentário por hora em cada conta. Fica uma folga; o que passar
# entra na fila e sai na hora seguinte (enviar_fila, no worker).
LIMITE_POR_HORA = 600
PRAZO_COMENTARIO = timedelta(days=7)
PRAZO_DM = timedelta(hours=24)
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


def link_da_dm(automacao: Automacao) -> str:
    """O link com o Sub ID da automação (Premium), se foi gerado; senão, o link que a pessoa colou."""
    return automacao.link_afiliado or automacao.link


def botoes_da_dm(automacao: Automacao) -> list[tuple[str, str]]:
    """Os botões da DM, na ordem: o 1º abre o link principal; o 2º e o 3º, o link de cada um."""
    if automacao.botoes < 1 or not link_da_dm(automacao):
        return []
    botoes = [((automacao.texto_botao or "Ver produto"), link_da_dm(automacao))]
    for extra in (automacao.botoes_extras or [])[: automacao.botoes - 1]:
        link = extra.get("link_afiliado") or extra.get("link")
        if link and extra.get("texto"):
            botoes.append((extra["texto"], link))
    return botoes[: Automacao.MAXIMO_BOTOES]


def texto_da_dm(automacao: Automacao, com_link: bool = True, botoes: list | None = None) -> str:
    """O texto da DM. com_link: o link vai no fim (sem botão, ou quando o Instagram não aceita os botões);
    com mais de um botão, vai cada link com o texto do seu botão."""
    texto = (automacao.texto_dm or "").strip()
    link = link_da_dm(automacao)
    if com_link and botoes and len(botoes) > 1:
        texto = f"{texto}\n\n" + "\n".join(f"{titulo}: {url}" for titulo, url in botoes)
    elif com_link and link and link not in texto:
        texto = f"{texto}\n\n{link}"
    texto = texto.strip()
    while len(texto.encode("utf-8")) > LIMITE_DM:
        texto = texto[:-10]
    return texto


def _mandar_dm(ig: ContaInstagram, d: Disparo, plano: dict) -> None:
    """A DM com os links em botões (Premium) e, se o Instagram não aceitar os botões, a mesma DM com os links no texto."""
    automacao = d.automacao
    if automacao.gatilho == Automacao.COMENTARIO:
        def manda(texto, botoes=None):
            return api.resposta_privada(ig.token, ig.ig_id, d.evento_id, texto, botoes)
    else:
        def manda(texto, botoes=None):
            return api.mensagem(ig.token, ig.ig_id, d.autor_id, texto, botoes)
    botoes = botoes_da_dm(automacao) if plano.get("botao") else []
    if botoes:
        try:
            manda(texto_da_dm(automacao, com_link=False) or "Aqui está o link:", botoes)
            return
        except api.ErroInstagram as erro:
            logger.info("Instagram: DM com botões recusada para @%s, vai em texto: %s", ig.username, erro)
    manda(texto_da_dm(automacao, botoes=botoes))


def resposta_publica(automacao: Automacao, username: str) -> str:
    opcoes = [x.strip() for x in (automacao.respostas or "").splitlines() if x.strip()]
    if not opcoes:
        return ""
    return random.choice(opcoes).replace("{nome}", f"@{username}" if username else "").strip()[:300]


def inicio_do_mes():
    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def respondidas_no_mes(conta) -> int:
    return Disparo.objects.filter(automacao__conta=conta, criado_em__gte=inicio_do_mes()).count()


def na_fila(conta) -> int:
    return Disparo.objects.filter(automacao__conta=conta, na_fila=True).count()


def _plano_cobre(ig: ContaInstagram, gatilho: str) -> bool:
    plano = planos.automacoes(ig.conta)
    return plano["liberado"] and gatilho in plano["gatilhos"]


def _vagas_na_hora(conta, agora=None) -> int:
    """Quantas respostas ainda cabem nesta hora (o Instagram aceita 750 DMs por comentário por hora)."""
    desde = (agora or timezone.now()) - timedelta(hours=1)
    return LIMITE_POR_HORA - Disparo.objects.filter(automacao__conta=conta, enviado_em__gte=desde).count()


def do_instagram(automacoes, ig_id: str):
    """As automações do Instagram conectado (e as antigas, de antes de guardar a conta)."""
    return automacoes.filter(Q(ig_id="") | Q(ig_id=ig_id)) if ig_id else automacoes.filter(ig_id="")


def ligadas(conta, ig_id: str):
    return do_instagram(Automacao.objects.filter(conta=conta, ativa=True), ig_id)


def valendo(conta, ig_id: str, plano: dict | None = None):
    """As automações ligadas do Instagram conectado que o plano cobre: no Standard, só as mais recentes até
    o limite (quem passou para o Standard com mais ligadas fica com as últimas criadas)."""
    plano = plano or planos.automacoes(conta)
    ligadas_ = ligadas(conta, ig_id).order_by("-criada_em")
    if plano.get("ativas"):
        return ligadas_.filter(pk__in=list(ligadas_.values_list("pk", flat=True)[:plano["ativas"]]))
    return ligadas_


def _escolher(ig: ContaInstagram, gatilho: str, midia_id: str | set, texto: str, com_gerais: bool = True) -> Automacao | None:
    """A automação do post/story/anúncio específico vem antes da que vale para todos. `midia_id` pode ser
    um conjunto: uma resposta de anúncio chega com mais de um jeito de reconhecer o anúncio."""
    ids = {midia_id} if isinstance(midia_id, str) else set(midia_id)
    ids.discard("")
    ativas = valendo(ig.conta, ig.ig_id).filter(gatilho=gatilho)
    especificas = [a for a in ativas if a.midia_id and a.midia_id in ids]
    gerais = [a for a in ativas if not a.midia_id] if com_gerais else []
    return next((a for a in especificas + gerais if bate(a, texto)), None)


# --- respostas que vêm de anúncio ------------------------------------------------------------------

def do_anuncio(evento: dict) -> dict:
    """O que a mensagem traz sobre a origem: o anúncio (referral, quando a pessoa veio de um anúncio) e o
    story respondido (reply_to). Anúncio de reels que também roda nos stories não é um story do perfil:
    o Instagram só conta dele aqui, na resposta."""
    msg = evento.get("message") or {}
    ref = msg.get("referral") or evento.get("referral") or {}
    ref = ref if isinstance(ref, dict) else {}
    ctx = ref.get("ads_context_data") if isinstance(ref.get("ads_context_data"), dict) else {}
    story = (msg.get("reply_to") or {}).get("story") or {}
    story = story if isinstance(story, dict) else {}
    imagem = str(ctx.get("photo_url") or story.get("url") or "")
    return {
        "anuncio_id": str(ref.get("ad_id") or "")[:64], "post_id": str(ctx.get("post_id") or "")[:64],
        "story_id": str(story.get("id") or "")[:64], "titulo": str(ctx.get("ad_title") or "")[:200],
        "imagem": imagem[:1000] if imagem.startswith("https://") else "",
        "bruto": {k: v for k, v in (("referral", ref), ("reply_to", msg.get("reply_to"))) if v},
    }


def chave_principal(info: dict) -> str:
    if info["anuncio_id"]:
        return f"ad:{info['anuncio_id']}"
    if info["post_id"]:
        return f"post:{info['post_id']}"
    return f"story:{info['story_id']}" if info["story_id"] else ""


def chaves_da_origem(ig: ContaInstagram, info: dict) -> set[str]:
    """Todos os jeitos de reconhecer de onde veio a mensagem (o que pode estar em Automacao.midia_id)."""
    story = info["story_id"]
    # o story vale cru (escolhido na lista de stories do perfil) e com "story:" (escolhido como anúncio)
    chaves = {f"ad:{info['anuncio_id']}" if info["anuncio_id"] else "", f"post:{info['post_id']}" if info["post_id"] else "",
              story, f"story:{story}" if story else ""}
    if info["story_id"]:  # o mesmo story já chegou antes junto com o ID do anúncio
        chaves |= set(AnuncioVisto.objects.filter(ig_id=ig.ig_id, story_id=info["story_id"]).values_list("chave", flat=True))
    chaves.discard("")
    return chaves


def _story_do_perfil(ig: ContaInstagram, story_id: str) -> bool:
    try:
        return any(str(m.get("id")) == story_id for m in api.stories_no_ar(ig.token))
    except api.ErroInstagram:
        return False


def registrar_anuncio(ig: ContaInstagram, info: dict, texto: str) -> None:
    """Guarda o anúncio (ou o story fora do perfil) de onde veio a resposta, para a opção "Um anúncio"."""
    chave = chave_principal(info)
    if not chave:
        return
    visto = AnuncioVisto.objects.filter(ig_id=ig.ig_id, chave=chave).first()
    if not visto:
        so_story = not (info["anuncio_id"] or info["post_id"])
        try:
            with transaction.atomic():
                visto = AnuncioVisto.objects.create(
                    ig_id=ig.ig_id, chave=chave, anuncio_id=info["anuncio_id"], post_id=info["post_id"], story_id=info["story_id"],
                    do_perfil=so_story and _story_do_perfil(ig, info["story_id"]))
        except IntegrityError:  # chegou junto com outro aviso do mesmo anúncio
            visto = AnuncioVisto.objects.get(ig_id=ig.ig_id, chave=chave)
    for campo in ("titulo", "imagem", "story_id", "post_id"):
        if info[campo] and (campo in ("titulo", "imagem") or not getattr(visto, campo)):
            setattr(visto, campo, info[campo])
    visto.respostas += 1
    visto.ultimo_texto = str(texto or "")[:200]
    visto.bruto = info["bruto"]
    visto.save()


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


def enviar(ig: ContaInstagram, d: Disparo) -> None:
    """Manda a resposta (comentário e/ou DM) de um registro e guarda o resultado."""
    automacao, erros, plano = d.automacao, [], planos.automacoes(ig.conta)
    if automacao.gatilho == Automacao.COMENTARIO and automacao.responder_comentario:
        if (texto := resposta_publica(automacao, d.autor_username)):
            try:
                api.responder_comentario(ig.token, d.evento_id, texto)
                d.resposta_ok = True
            except api.ErroInstagram as erro:
                erros.append(f"Resposta: {erro}")
    if automacao.enviar_dm and texto_da_dm(automacao):
        try:
            _mandar_dm(ig, d, plano)
            d.dm_ok = True
        except api.ErroInstagram as erro:
            erros.append(f"DM: {erro}")
    d.erro, d.na_fila, d.enviado_em = " · ".join(erros)[:400], False, timezone.now()
    d.save(update_fields=["resposta_ok", "dm_ok", "erro", "na_fila", "enviado_em"])


def _responder_ou_enfileirar(ig: ContaInstagram, d: Disparo) -> None:
    if _vagas_na_hora(ig.conta) > 0 and not na_fila(ig.conta):
        enviar(ig, d)
    else:  # passou do limite da hora (ou já tem gente esperando): entra no fim da fila
        d.na_fila = True
        d.save(update_fields=["na_fila"])


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
    if not automacao or not _plano_cobre(ig, Automacao.COMENTARIO):
        return
    if (d := _registrar(automacao, comentario_id, autor_id, username, valor.get("text", ""))):
        _responder_ou_enfileirar(ig, d)


def _mensagem(ig: ContaInstagram, evento: dict) -> None:
    msg = evento.get("message") or {}
    if not msg or msg.get("is_echo") or msg.get("is_deleted") or msg.get("is_self"):
        return
    autor_id = str((evento.get("sender") or {}).get("id") or "")
    mid = str(msg.get("mid") or "")
    if not autor_id or autor_id == ig.ig_id or not mid:
        return
    texto = msg.get("text", "")
    info = do_anuncio(evento)
    try:
        registrar_anuncio(ig, info, texto)
    except Exception:  # guardar a origem nunca impede a resposta
        logger.exception("Instagram: falha ao guardar o anúncio de @%s", ig.username)
    automacao = None
    if (chaves := chaves_da_origem(ig, info)):
        # Resposta a story ou mensagem de anúncio: primeiro a automação daquele anúncio/story; as de
        # "Todos os stories" só valem para resposta a story mesmo.
        automacao = _escolher(ig, Automacao.STORY, chaves, texto, com_gerais=bool(info["story_id"]))
    if not automacao and not info["story_id"]:
        automacao = _escolher(ig, Automacao.DIRETO, "", texto)
    if not automacao or not automacao.enviar_dm or not _plano_cobre(ig, automacao.gatilho):
        return
    if (d := _registrar(automacao, mid, autor_id, "", msg.get("text", ""))):
        _responder_ou_enfileirar(ig, d)


def enviar_fila(agora=None) -> list[str]:
    """Worker: manda o que ficou na fila, por ordem de chegada, até o limite da hora de cada conta.
    Passou do prazo do Instagram (7 dias depois do comentário, 24 horas depois da DM), não sai mais."""
    agora = agora or timezone.now()
    linhas = []
    contas = (Disparo.objects.filter(na_fila=True).values_list("automacao__conta_id", flat=True).distinct())
    for conta_id in list(contas)[:50]:
        ig = ContaInstagram.objects.filter(conta_id=conta_id).select_related("conta").first()
        fila = Disparo.objects.filter(automacao__conta_id=conta_id, na_fila=True).select_related("automacao").order_by("criado_em")
        if not ig:
            fila.update(na_fila=False, erro="Não enviada: o Instagram foi desconectado.")
            continue
        enviadas = 0
        for d in fila[:max(0, _vagas_na_hora(ig.conta, agora))]:
            prazo = PRAZO_COMENTARIO if d.automacao.gatilho == Automacao.COMENTARIO else PRAZO_DM
            if agora - d.criado_em > prazo:
                Disparo.objects.filter(pk=d.pk).update(na_fila=False, erro="Não enviada: passou do prazo do Instagram para responder.")
                continue
            if d.automacao.ig_id and d.automacao.ig_id != ig.ig_id:
                Disparo.objects.filter(pk=d.pk).update(na_fila=False, erro="Não enviada: o Instagram conectado mudou.")
                continue
            if not d.automacao.ativa or not _plano_cobre(ig, d.automacao.gatilho):
                Disparo.objects.filter(pk=d.pk).update(na_fila=False, erro="Não enviada: a automação foi pausada ou saiu do plano.")
                continue
            enviar(ig, d)
            enviadas += 1
        if enviadas:
            linhas.append(f"Instagram @{ig.username}: {enviadas} resposta(s) da fila enviada(s).")
    return linhas


GUARDAR_AVISOS_POR = timedelta(days=7)


def _resumo(campo: str, valor: dict) -> str:
    if campo == "comments":
        return f"@{(valor.get('from') or {}).get('username', '?')} comentou: {str(valor.get('text', ''))[:200]}"
    msg = valor.get("message") or {}
    if msg.get("is_echo"):
        return "Mensagem enviada pela própria conta"
    if (ref := msg.get("referral") or valor.get("referral")) and isinstance(ref, dict) and ref.get("ad_id"):
        return f"Mensagem de anúncio ({ref['ad_id']}): {str(msg.get('text', ''))[:200]}"
    if (msg.get("reply_to") or {}).get("story"):
        return f"Resposta a story: {str(msg.get('text', ''))[:200]}"
    if msg:
        return f"DM: {str(msg.get('text', ''))[:200]}"
    return api.corpo_json(valor)[:300]


def registrar_avisos(payload: dict) -> None:
    """Guarda um resumo de cada aviso que chegou (de qualquer conta), para a tela de teste."""
    try:
        novos = []
        for entrada in payload.get("entry") or []:
            if not isinstance(entrada, dict):
                continue
            ig_id = str(entrada.get("id") or "")[:64]
            for change in entrada.get("changes") or []:
                valor = change.get("value") if isinstance(change.get("value"), dict) else {}
                novos.append(AvisoRecebido(ig_id=ig_id, campo=str(change.get("field") or "?")[:40], resumo=_resumo(change.get("field"), valor)))
            for evento in entrada.get("messaging") or []:
                novos.append(AvisoRecebido(ig_id=ig_id, campo="messaging", resumo=_resumo("messages", evento)))
        AvisoRecebido.objects.bulk_create(novos)
        AvisoRecebido.objects.filter(recebido_em__lt=timezone.now() - GUARDAR_AVISOS_POR).delete()
    except Exception:
        logger.exception("Instagram: falha ao registrar avisos")


def separar_e_processar(payload: dict) -> dict:
    """Trata os avisos das contas conectadas no Appfiliado e devolve o payload para a automação da cash-b.

    Os avisos de uma conta conectada também seguem para a cash-b: a mesma conta (a @usecashb, por
    exemplo) pode estar nos dois lugares, e cada lado só responde onde tem automação configurada."""
    registrar_avisos(payload)
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
