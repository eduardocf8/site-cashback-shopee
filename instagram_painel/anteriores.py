"""Responder quem comentou (ou mandou DM) antes de a automação estar ligada.

O botão na tela da automação cria um Repasse. O worker (publicar.rodar) busca no Instagram o que ainda
está no prazo dele para responder: comentários dos últimos 7 dias (resposta privada) e DMs das últimas
24 horas. Quem escreveu uma das palavras e ainda não recebeu desta automação entra na fila de sempre
(webhook.enviar_fila), que respeita o limite por hora do Instagram. Quem já recebeu (pelo ID da
pessoa) fica de fora, igual ao que acontece com quem comenta duas vezes."""

import logging
from datetime import datetime, timedelta
from datetime import timezone as fuso

from django.utils import timezone

from . import api
from .models import Automacao, ContaInstagram, Repasse
from .webhook import PRAZO_COMENTARIO, PRAZO_DM, _escolher, _plano_cobre, _registrar, bate, valendo

logger = logging.getLogger(__name__)

GATILHOS = (Automacao.COMENTARIO, Automacao.DIRETO)
# Não entra o que vence antes de a fila conseguir mandar (num post com muita gente, a fila leva horas).
MARGEM = timedelta(hours=2)
POSTS_EM_TODOS = 25  # "Todos os posts": os posts mais recentes do perfil
PAGINAS_POR_POST = 20  # 50 comentários por página
MAXIMO = 3000  # comentários (ou mensagens) olhados por busca
ENTRE_BUSCAS = timedelta(minutes=10)
TRAVADA_APOS = timedelta(minutes=30)  # busca que ficou "buscando" (o worker reiniciou): vira erro


class ErroAnteriores(ValueError):
    pass


def _instagram(automacao):
    return ContaInstagram.objects.filter(conta=automacao.conta).select_related("conta").first()


def motivo_para_nao_buscar(automacao, ig=None) -> str:
    """Por que o botão não vale para esta automação agora ("" = pode buscar)."""
    if automacao.gatilho not in GATILHOS:
        return "Para respostas a story ainda não dá: o Instagram só deixa responder até 24 horas depois."
    ig = ig or _instagram(automacao)
    if not ig or (automacao.ig_id and automacao.ig_id != ig.ig_id):
        return "Conecte o Instagram desta automação para buscar."
    if not automacao.ativa:
        return "Ligue a automação para buscar quem já comentou."
    if not _plano_cobre(ig, automacao.gatilho) or not valendo(ig.conta, ig.ig_id).filter(pk=automacao.pk).exists():
        return "Esta automação está parada pelo plano."
    if not automacao.enviar_dm and not (automacao.gatilho == Automacao.COMENTARIO and automacao.responder_comentario):
        return "A automação não tem resposta nem DM para mandar."
    return ""


def ultimo(automacao):
    return automacao.repasses.order_by("-pedido_em").first()


def pedir(automacao) -> Repasse:
    """O botão: cria a busca (o worker faz em seguida). Se já tem uma andando, devolve ela."""
    motivo = motivo_para_nao_buscar(automacao)
    if motivo:
        raise ErroAnteriores(motivo)
    anterior = ultimo(automacao)
    if anterior and anterior.estado in (Repasse.FILA, Repasse.BUSCANDO):
        return anterior
    if anterior and timezone.now() - anterior.pedido_em < ENTRE_BUSCAS:
        raise ErroAnteriores("Você acabou de buscar. Espere uns minutos para buscar de novo.")
    return Repasse.objects.create(automacao=automacao)


def processar() -> list[str]:
    """Worker: faz as buscas pedidas (poucas por volta, para não segurar a fila)."""
    agora = timezone.now()
    Repasse.objects.filter(estado=Repasse.BUSCANDO, pedido_em__lt=agora - TRAVADA_APOS).update(
        estado=Repasse.ERRO, terminado_em=agora, mensagem="A busca parou no meio. Tente de novo.")
    linhas = []
    for r in Repasse.objects.filter(estado=Repasse.FILA).select_related("automacao", "automacao__conta")[:3]:
        if not Repasse.objects.filter(pk=r.pk, estado=Repasse.FILA).update(estado=Repasse.BUSCANDO):
            continue  # outro worker pegou
        try:
            _rodar(r)
        except api.ErroInstagram as erro:
            r.estado, r.mensagem = Repasse.ERRO, f"O Instagram não deixou buscar agora: {erro}"[:300]
        except Exception:  # noqa: BLE001 - uma busca com problema não para o worker
            logger.exception("Instagram: erro ao buscar os anteriores da automação %s", r.automacao_id)
            r.estado, r.mensagem = Repasse.ERRO, "Erro inesperado do nosso lado. Tente de novo em alguns minutos."
        r.terminado_em = timezone.now()
        r.save()
        linhas.append(f"Automação {r.automacao_id}: {r.enfileirados} pessoa(s) de antes na fila ({r.get_estado_display()}).")
    return linhas


def _data(texto) -> datetime | None:
    texto = str(texto or "")
    for formato in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    try:
        quando = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return quando if quando.tzinfo else quando.replace(tzinfo=fuso.utc)


def _da_propria_conta(ig, autor_id: str, username: str) -> bool:
    return autor_id == ig.ig_id or (username and username.lower() == ig.username.lower())


def _comentarios(ig, automacao, desde):
    """Comentários de primeiro nível no prazo: do post escolhido, ou dos posts mais recentes."""
    if automacao.midia_id:
        midias = [automacao.midia_id.removeprefix("post:")]
    else:
        midias = [str(p.get("id")) for p in api.posts_recentes(ig.token, POSTS_EM_TODOS) if p.get("id")]
    vistos = 0
    for midia in midias:
        depois = ""
        for _ in range(PAGINAS_POR_POST):
            lista, depois = api.comentarios(ig.token, midia, depois)
            for c in lista:
                vistos += 1
                autor = c.get("from") or {}
                autor_id = str(autor.get("id") or "")
                username = str(autor.get("username") or c.get("username") or "")
                quando = _data(c.get("timestamp"))
                if not c.get("id") or not autor_id or _da_propria_conta(ig, autor_id, username):
                    continue  # inclusive as respostas que a própria automação publicou
                if quando and quando >= desde:
                    yield {"id": str(c["id"]), "autor_id": autor_id, "username": username, "texto": c.get("text", ""),
                           "quando": quando, "midias": {midia, f"post:{midia}"}}
                if vistos >= MAXIMO:
                    return
            if not depois:
                break


def _mensagens(ig, desde):
    """Mensagens recebidas na DM no prazo (as conversas que mexeram nas últimas 24 horas)."""
    vistas = 0
    for conversa in api.conversas_recentes(ig.token):
        mexeu = _data(conversa.get("updated_time"))
        if mexeu and mexeu < desde:
            continue
        for m in (conversa.get("messages") or {}).get("data", []):
            vistas += 1
            autor = m.get("from") or {}
            autor_id, username = str(autor.get("id") or ""), str(autor.get("username") or "")
            quando = _data(m.get("created_time"))
            if m.get("id") and autor_id and not _da_propria_conta(ig, autor_id, username) and quando and quando >= desde:
                yield {"id": str(m["id"]), "autor_id": autor_id, "username": username, "texto": m.get("message", ""),
                       "quando": quando, "midias": ""}
            if vistas >= MAXIMO:
                return


def _rodar(r: Repasse) -> None:
    a = r.automacao
    ig = _instagram(a)
    motivo = motivo_para_nao_buscar(a, ig)
    if motivo:
        r.estado, r.mensagem = Repasse.ERRO, motivo
        return
    agora = timezone.now()
    if a.gatilho == Automacao.COMENTARIO:
        eventos = _comentarios(ig, a, agora - PRAZO_COMENTARIO + MARGEM)
    else:
        eventos = _mensagens(ig, agora - PRAZO_DM + MARGEM)
    for ev in eventos:
        r.encontrados += 1
        escolhida = _escolher(ig, a.gatilho, ev["midias"], ev["texto"])
        if escolhida is None or escolhida.pk != a.pk:
            if bate(a, ev["texto"]):
                r.de_outra += 1  # bate com uma automação que vem antes (a do post específico, por exemplo)
            else:
                r.sem_palavra += 1
            continue
        d = _registrar(a, ev["id"], ev["autor_id"], ev["username"], ev["texto"])
        if d is None:  # a pessoa já recebeu desta automação (ou já está na fila)
            r.pulados += 1
            continue
        d.na_fila, d.anterior, d.evento_em = True, True, ev["quando"]
        d.save(update_fields=["na_fila", "anterior", "evento_em"])
        r.enfileirados += 1
    r.estado = Repasse.PRONTO
