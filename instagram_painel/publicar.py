"""Publicar no Instagram os posts do Estúdio: agora ou num horário marcado.

O navegador desenha cada slide em JPEG (1080 px de largura) e manda para agendar(). As imagens ficam
no banco até a publicação. Uma thread do worker do painel (sincronizar_painel --loop) confere a fila
a cada 15 segundos e publica pela API: um container por imagem (e um a mais juntando o carrossel),
espera a Meta processar e chama media_publish. Stories saem um por um.

A Meta baixa cada imagem por um endereço público (/instagram/midia/<token>.jpg, no domínio do
painel). O token não dá para adivinhar e o endereço some depois da publicação."""

import io
import logging
import secrets
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from . import api
from .models import ContaInstagram, ImagemPublicacao, Publicacao

logger = logging.getLogger(__name__)

MAX_IMAGENS = 10
MAX_BYTES = 8 * 1024 * 1024  # limite da Meta por imagem
MAX_PENDENTES = 30
ANTECEDENCIA_MAXIMA = timedelta(days=60)
PRESA = timedelta(minutes=15)  # "publicando" há mais tempo que isso: o worker caiu no meio
MAX_TENTATIVAS = 3
INTERVALO = 15  # segundos entre uma conferência da fila e outra
ESPERA_CONTAINER = 90  # segundos esperando a Meta processar cada imagem
GUARDA_ERRO = timedelta(days=7)  # imagens das que deram erro (para "Tentar de novo")
dormir = time.sleep  # os testes trocam


class ErroPublicacao(Exception):
    """Mensagem pronta para mostrar à pessoa."""


def tipo_do_post(post) -> str:
    return Publicacao.STORY if post.formato == "story" else Publicacao.FEED


def _jpeg(arquivo) -> tuple[bytes, bytes]:
    """Confere a imagem que veio do navegador e devolve (JPEG final, miniatura)."""
    from PIL import Image

    if arquivo.size > MAX_BYTES:
        raise ErroPublicacao("Uma das imagens passou de 8 MB.")
    try:
        imagem = Image.open(arquivo)
        if imagem.format not in ("JPEG", "PNG"):
            raise ErroPublicacao("As imagens precisam ser JPEG.")
        if not (320 <= imagem.size[0] <= 1440) or imagem.size[1] > 2600:
            raise ErroPublicacao("O tamanho de uma das imagens não serve para o Instagram.")
        imagem.load()
    except ErroPublicacao:
        raise
    except Exception as erro:  # Pillow levanta vários tipos para arquivo quebrado
        raise ErroPublicacao("Uma das imagens veio quebrada. Tente de novo.") from erro
    imagem = imagem.convert("RGB")
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=92)
    imagem.thumbnail((360, 640))
    mini = io.BytesIO()
    imagem.save(mini, "JPEG", quality=80)
    return saida.getvalue(), mini.getvalue()


def quando_de(texto: str, agora=None):
    """Data e hora do navegador -> datetime com fuso. Vem com fuso ('2026-10-27T21:30:00.000Z', o
    navegador converte o horário de quem agendou); sem fuso, vale o horário de Brasília."""
    from datetime import datetime

    agora = agora or timezone.now()
    try:
        quando = datetime.fromisoformat(str(texto or "").strip()[:40])
        if timezone.is_naive(quando):
            quando = timezone.make_aware(quando)
    except (ValueError, TypeError) as erro:
        raise ErroPublicacao("Escolha o dia e a hora da publicação.") from erro
    if quando < agora + timedelta(minutes=5):
        raise ErroPublicacao("Escolha um horário daqui a pelo menos 5 minutos (ou publique agora).")
    if quando > agora + ANTECEDENCIA_MAXIMA:
        raise ErroPublicacao("Dá para agendar até 60 dias para frente.")
    return quando


def agendar(post, arquivos: list, quando=None) -> Publicacao:
    """Cria a publicação do post (já salvo). quando=None: publica assim que o worker pegar."""
    conta = post.conta
    if not ContaInstagram.objects.filter(conta=conta).exists():
        raise ErroPublicacao("Conecte o seu Instagram para publicar.")
    if not arquivos:
        raise ErroPublicacao("Nenhuma imagem chegou. Tente de novo.")
    tipo = tipo_do_post(post)
    if len(arquivos) > MAX_IMAGENS:
        raise ErroPublicacao(f"O Instagram aceita até {MAX_IMAGENS} imagens por vez.")
    if len(arquivos) != len(post.slides or []):
        raise ErroPublicacao("As imagens não batem com os slides do post. Salve e tente de novo.")
    if tipo == Publicacao.FEED and len(post.legenda or "") > 2200:
        raise ErroPublicacao("A legenda passou de 2.200 caracteres.")
    if Publicacao.objects.filter(conta=conta, estado=Publicacao.PENDENTE).count() >= MAX_PENDENTES:
        raise ErroPublicacao(f"Você já tem {MAX_PENDENTES} publicações agendadas. Espere algumas saírem.")
    imagens = [_jpeg(a) for a in arquivos]
    agora = timezone.now()
    with transaction.atomic():
        pub = Publicacao.objects.create(
            conta=conta, post=post, nome=post.nome[:120], tipo=tipo,
            legenda=post.legenda if tipo == Publicacao.FEED else "",
            agendada_para=quando or agora, agora=quando is None, miniatura=imagens[0][1])
        ImagemPublicacao.objects.bulk_create([
            ImagemPublicacao(publicacao=pub, ordem=i, dados=jpeg, token=secrets.token_urlsafe(32))
            for i, (jpeg, _) in enumerate(imagens)])
    atualizar_post(post)
    return pub


def cancelar(pub: Publicacao) -> bool:
    if not Publicacao.objects.filter(pk=pub.pk, estado=Publicacao.PENDENTE).update(estado=Publicacao.CANCELADA):
        return False
    ImagemPublicacao.objects.filter(publicacao=pub).delete()
    if pub.post_id:
        atualizar_post(pub.post)
    return True


def tentar_de_novo(pub: Publicacao) -> bool:
    if pub.estado != Publicacao.ERRO or not pub.imagens.exists():
        return False
    Publicacao.objects.filter(pk=pub.pk, estado=Publicacao.ERRO).update(
        estado=Publicacao.PENDENTE, agendada_para=timezone.now(), agora=True, tentativas=0, erro="")
    if pub.post_id:
        atualizar_post(pub.post)
    return True


def atualizar_post(post) -> None:
    """O selo do post no Estúdio segue a publicação mais recente dele."""
    pubs = list(Publicacao.objects.filter(post=post).exclude(estado=Publicacao.CANCELADA).order_by("-criada_em")[:20])
    if any(p.ativa for p in pubs):
        estado = "agendado"
    elif pubs and pubs[0].estado == Publicacao.PUBLICADA:
        estado = "publicado"
    elif pubs and pubs[0].estado == Publicacao.ERRO:
        estado = "erro"
    elif any(p.estado == Publicacao.PUBLICADA for p in pubs):
        estado = "publicado"
    else:
        estado = "rascunho"
    if post.estado != estado:
        type(post).objects.filter(pk=post.pk).update(estado=estado)
        post.estado = estado


# --- o worker -----------------------------------------------------------------------------------

def url_publica(imagem: ImagemPublicacao) -> str:
    caminho = reverse("painel_instagram_midia", args=[imagem.token], urlconf="painel.urls_dominio")
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + caminho


def _esperar(token: str, container: str) -> None:
    fim = time.monotonic() + ESPERA_CONTAINER
    pausa = 1.5
    while True:
        estado = api.estado_container(token, container)
        if estado in ("FINISHED", "PUBLISHED"):
            return
        if estado in ("ERROR", "EXPIRED"):
            raise api.ErroInstagram("O Instagram não aceitou uma das imagens.")
        if time.monotonic() > fim:
            raise api.ErroInstagram("O Instagram demorou demais para processar as imagens.")
        dormir(pausa)
        pausa = min(pausa * 1.5, 6)


def _publicar_feed(ig, pub, urls) -> list[str]:
    token = ig.token
    if len(urls) == 1:
        container = api.criar_container(token, ig.ig_id, image_url=urls[0], caption=pub.legenda)
    else:
        filhos = [api.criar_container(token, ig.ig_id, image_url=u, is_carousel_item=True) for u in urls]
        for filho in filhos:
            _esperar(token, filho)
        container = api.criar_container(token, ig.ig_id, media_type="CAROUSEL", children=",".join(filhos), caption=pub.legenda)
    _esperar(token, container)
    return [api.publicar_container(token, ig.ig_id, container)]


def _publicar_stories(ig, pub, urls) -> list[str]:
    token, feitos = ig.token, list(pub.midias or [])
    for url in urls[len(feitos):]:  # numa nova tentativa, pula os stories que já saíram
        container = api.criar_container(token, ig.ig_id, image_url=url, media_type="STORIES")
        _esperar(token, container)
        feitos.append(api.publicar_container(token, ig.ig_id, container))
        Publicacao.objects.filter(pk=pub.pk).update(midias=feitos)
    return feitos


def _erro(pub, mensagem: str) -> str:
    Publicacao.objects.filter(pk=pub.pk).update(estado=Publicacao.ERRO, erro=mensagem[:400])
    if pub.post_id:
        atualizar_post(pub.post)
    return f"Publicação {pub.pk}: {mensagem}"


def publicar(pub: Publicacao) -> str:
    """Publica de fato (a publicação já foi pega por este processo em pegar())."""
    from painel import modulos as mod

    ig = ContaInstagram.objects.filter(conta=pub.conta).first()
    if not ig:
        return _erro(pub, "O Instagram foi desconectado antes da publicação.")
    if mod.estado(mod.POR_SLUG["estudio_instagram"], pub.conta.modulos_liberados()) != "liberado":
        return _erro(pub, "O Estúdio Instagram não está mais no seu plano.")
    if pub.tipo == Publicacao.FEED and pub.midias:  # já tinha saído antes de o worker cair
        urls, midias = [], list(pub.midias)
    else:
        urls = [url_publica(im) for im in pub.imagens.all()]
        if not urls:
            return _erro(pub, "As imagens da publicação sumiram. Publique de novo pelo editor.")
        midias = None
    try:
        if midias is None:
            midias = _publicar_stories(ig, pub, urls) if pub.tipo == Publicacao.STORY else _publicar_feed(ig, pub, urls)
    except api.ErroInstagram as erro:
        logger.warning("Instagram: publicação %s de @%s falhou: %s", pub.pk, ig.username, erro)
        return _erro(pub, f"O Instagram recusou: {erro}")
    try:
        link = api.link_da_midia(ig.token, midias[0]) if pub.tipo == Publicacao.FEED else ""
    except api.ErroInstagram:
        link = ""
    Publicacao.objects.filter(pk=pub.pk).update(estado=Publicacao.PUBLICADA, publicada_em=timezone.now(),
                                                midias=midias, permalink=link[:600], erro="")
    ImagemPublicacao.objects.filter(publicacao=pub).delete()
    if pub.post_id:
        atualizar_post(pub.post)
    return f"Publicação {pub.pk} de @{ig.username}: publicada ({len(midias)} mídia(s))."


def pegar(pub: Publicacao, agora) -> bool:
    """Só um processo publica cada uma: quem conseguir trocar o estado primeiro."""
    return bool(Publicacao.objects.filter(pk=pub.pk, estado=pub.estado, iniciada_em=pub.iniciada_em).update(
        estado=Publicacao.PUBLICANDO, iniciada_em=agora, tentativas=F("tentativas") + 1))


def uma_volta(agora=None) -> list[str]:
    agora = agora or timezone.now()
    linhas = []
    fila = (Publicacao.objects
            .filter(Q(estado=Publicacao.PENDENTE, agendada_para__lte=agora)
                    | Q(estado=Publicacao.PUBLICANDO, iniciada_em__lt=agora - PRESA))
            .select_related("conta", "post").order_by("agendada_para")[:10])
    for pub in fila:
        if pub.estado == Publicacao.PUBLICANDO and pub.tentativas >= MAX_TENTATIVAS:
            linhas.append(_erro(pub, "Não deu para publicar depois de várias tentativas."))
            continue
        if not pegar(pub, agora):
            continue
        try:
            linhas.append(publicar(pub))
        except Exception:  # noqa: BLE001 - uma publicação com problema não trava as outras
            logger.exception("Instagram: erro ao publicar %s", pub.pk)
            linhas.append(_erro(pub, "Erro inesperado ao publicar. Tente de novo."))
    # Imagens das que deram erro há mais de uma semana não servem mais.
    ImagemPublicacao.objects.filter(publicacao__estado=Publicacao.ERRO,
                                    publicacao__agendada_para__lt=agora - GUARDA_ERRO).delete()
    return linhas


def rodar():
    while True:
        close_old_connections()
        try:
            for linha in uma_volta():
                logger.info(linha)
        except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
            logger.exception("Instagram: erro na fila de publicações")
        time.sleep(INTERVALO)


def iniciar_em_segundo_plano():
    threading.Thread(target=rodar, name="publicacoes-instagram", daemon=True).start()
