import io
import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ofertas.models import Oferta

from . import aprovacao, conteudo, instagram_client
from .models import RegistroPublicacao
from .templates_imagem import (
    CORES,
    gerar_imagem_oferta_carrossel,
    gerar_imagem_ofertas,
    gerar_imagem_texto_simples,
)

logger = logging.getLogger(__name__)

PASTA_MEDIA_BOT = Path(settings.MEDIA_ROOT) / "instagram"


def _salvar_e_montar_url(imagem, request) -> str:
    # JPEG, não PNG: a Instagram Graph API só aceita JPEG pra publicar imagem
    # (PNG gera o erro genérico "Only photo or video can be accepted as media type").
    PASTA_MEDIA_BOT.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    caminho = PASTA_MEDIA_BOT / nome_arquivo
    imagem.save(caminho, "JPEG", quality=90)
    return request.build_absolute_uri(f"{settings.MEDIA_URL}instagram/{nome_arquivo}")


def _bytes_jpeg(imagem) -> bytes:
    buffer = io.BytesIO()
    imagem.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _salvar_e_montar_urls(imagens, request) -> list[str]:
    return [_salvar_e_montar_url(imagem, request) for imagem in imagens]


def _ja_processado_hoje(data, conteudo_tipo: str) -> bool:
    """True se já existe um registro de hoje pra esse tipo de conteúdo que não seja
    um erro transitório - ou seja, já foi simulado, já está aguardando aprovação, já
    foi publicado ou já foi rejeitado. Só erro não bloqueia, pra permitir nova
    tentativa na próxima execução da tarefa diária."""
    return (
        RegistroPublicacao.objects.filter(data=data, conteudo_tipo=conteudo_tipo)
        .exclude(status=RegistroPublicacao.STATUS_ERRO)
        .exists()
    )


def _registrar(
    data, tipo, conteudo_tipo, legenda, imagem_url, simulacao, sucesso, status, erro="", imagem_urls=""
):
    return RegistroPublicacao.objects.create(
        data=data,
        tipo=tipo,
        conteudo_tipo=conteudo_tipo,
        legenda=legenda,
        imagem_url=imagem_url,
        imagem_urls=imagem_urls,
        modo_simulacao=simulacao,
        status=status,
        sucesso=sucesso,
        erro=erro,
    )


def _publicar_ou_simular(imagem, legenda, tipo, conteudo_tipo, data, request, story: bool) -> RegistroPublicacao:
    if not settings.INSTAGRAM_BOT_ATIVO:
        return _simular(imagem, legenda, tipo, conteudo_tipo, data, request)
    if settings.INSTAGRAM_REQUER_APROVACAO:
        return _aguardar_aprovacao(imagem, legenda, tipo, conteudo_tipo, data, request)
    return _publicar_direto(imagem, legenda, tipo, conteudo_tipo, data, request, story)


def _simular(imagem, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_url = _salvar_e_montar_url(imagem, request)
    logger.info(
        "[instagram_bot] modo simulação (INSTAGRAM_BOT_ATIVO=False) - geraria %s/%s: %s",
        tipo, conteudo_tipo, imagem_url,
    )
    return _registrar(
        data, tipo, conteudo_tipo, legenda, imagem_url,
        simulacao=True, sucesso=True, status=RegistroPublicacao.STATUS_SIMULADO,
    )


def _publicar_direto(imagem, legenda, tipo, conteudo_tipo, data, request, story: bool) -> RegistroPublicacao:
    imagem_url = ""
    try:
        imagem_url = _salvar_e_montar_url(imagem, request)
        media_id = instagram_client.publicar_imagem(imagem_url, legenda=legenda, story=story)
        registro = _registrar(
            data, tipo, conteudo_tipo, legenda, imagem_url,
            simulacao=False, sucesso=True, status=RegistroPublicacao.STATUS_PUBLICADO,
        )
        registro.instagram_media_id = media_id
        registro.save(update_fields=["instagram_media_id"])
        return registro
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar %s/%s", tipo, conteudo_tipo)
        return _registrar(
            data, tipo, conteudo_tipo, legenda, imagem_url,
            simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_ERRO, erro=str(erro),
        )


def _aguardar_aprovacao(imagem, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_url = _salvar_e_montar_url(imagem, request)
    registro = _registrar(
        data, tipo, conteudo_tipo, legenda, imagem_url,
        simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_PENDENTE_APROVACAO,
    )
    try:
        aprovacao.enviar_email_aprovacao(registro, [_bytes_jpeg(imagem)], request)
    except Exception:
        logger.exception("[instagram_bot] falha ao enviar e-mail de aprovação (registro %s)", registro.pk)
    return registro


def _publicar_ou_simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    if not settings.INSTAGRAM_BOT_ATIVO:
        return _simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)
    if settings.INSTAGRAM_REQUER_APROVACAO:
        return _aguardar_aprovacao_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)
    return _publicar_direto_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)


def _simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = _salvar_e_montar_urls(imagens, request)
    logger.info(
        "[instagram_bot] modo simulação (INSTAGRAM_BOT_ATIVO=False) - geraria carrossel %s/%s com %s imagens",
        tipo, conteudo_tipo, len(imagem_urls),
    )
    return _registrar(
        data, tipo, conteudo_tipo, legenda, "",
        simulacao=True, sucesso=True, status=RegistroPublicacao.STATUS_SIMULADO,
        imagem_urls="\n".join(imagem_urls),
    )


def _publicar_direto_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = []
    try:
        imagem_urls = _salvar_e_montar_urls(imagens, request)
        media_id = instagram_client.publicar_carrossel(imagem_urls, legenda=legenda)
        registro = _registrar(
            data, tipo, conteudo_tipo, legenda, "",
            simulacao=False, sucesso=True, status=RegistroPublicacao.STATUS_PUBLICADO,
            imagem_urls="\n".join(imagem_urls),
        )
        registro.instagram_media_id = media_id
        registro.save(update_fields=["instagram_media_id"])
        return registro
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar carrossel %s/%s", tipo, conteudo_tipo)
        return _registrar(
            data, tipo, conteudo_tipo, legenda, "",
            simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_ERRO, erro=str(erro),
            imagem_urls="\n".join(imagem_urls),
        )


def _aguardar_aprovacao_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = _salvar_e_montar_urls(imagens, request)
    registro = _registrar(
        data, tipo, conteudo_tipo, legenda, "",
        simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_PENDENTE_APROVACAO,
        imagem_urls="\n".join(imagem_urls),
    )
    try:
        aprovacao.enviar_email_aprovacao(registro, [_bytes_jpeg(imagem) for imagem in imagens], request)
    except Exception:
        logger.exception("[instagram_bot] falha ao enviar e-mail de aprovação (registro %s)", registro.pk)
    return registro


def publicar_story_ofertas(data, request) -> RegistroPublicacao | None:
    ofertas = list(Oferta.objects.all()[:3])
    if not ofertas:
        logger.warning("[instagram_bot] sem ofertas sincronizadas, pulando story do dia")
        return None
    imagem = gerar_imagem_ofertas(ofertas, titulo="Ofertas de hoje", tamanho=(1080, 1920))
    legenda = "As melhores ofertas de hoje no cash-b. Link na bio pra ver todas. 🛍️💸"
    return _publicar_ou_simular(
        imagem, legenda, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
        data, request, story=True,
    )


def publicar_story_dica(data, request) -> RegistroPublicacao:
    texto = conteudo.escolher_dica(data)
    imagem = gerar_imagem_texto_simples(
        texto, bg=CORES["highlight"], cor_texto=CORES["ink"], tamanho=(1080, 1920),
    )
    return _publicar_ou_simular(
        imagem, texto, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_DICA,
        data, request, story=True,
    )


def publicar_story_lembrete(data, request) -> RegistroPublicacao:
    texto = conteudo.escolher_lembrete(data)
    imagem = gerar_imagem_texto_simples(
        texto, bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"], tamanho=(1080, 1920),
    )
    return _publicar_ou_simular(
        imagem, texto, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_LEMBRETE,
        data, request, story=True,
    )


def publicar_post_institucional(data, request) -> RegistroPublicacao:
    post = conteudo.escolher_post_institucional(data)
    if post["estilo"] == "brand":
        imagem = gerar_imagem_texto_simples(
            post["texto"], bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"],
        )
    else:
        imagem = gerar_imagem_texto_simples(post["texto"], bg=CORES["highlight"], cor_texto=CORES["ink"])
    return _publicar_ou_simular(
        imagem, post["legenda"], RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_INSTITUCIONAL,
        data, request, story=False,
    )


def publicar_post_ofertas_semana(data, request) -> RegistroPublicacao | None:
    """Carrossel com uma capa + 8 ofertas (uma por slide) - carrossel tende a gerar mais
    salvamentos que um post único, o que ajuda o alcance pra quem ainda não segue."""
    ofertas = list(Oferta.objects.all()[:8])
    if not ofertas:
        logger.warning("[instagram_bot] sem ofertas sincronizadas, pulando post semanal")
        return None
    # Sem emoji aqui: as fontes da marca não têm esses glifos, e o Pillow simplesmente
    # some com o caractere sem erro nenhum - o emoji fica só na legenda (o Instagram
    # renderiza a legenda com a fonte dele, aí sim com suporte a emoji).
    capa = gerar_imagem_texto_simples(
        "Top da semana no cash-b", bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"],
    )
    slides = [
        gerar_imagem_oferta_carrossel(oferta, indice, len(ofertas))
        for indice, oferta in enumerate(ofertas, start=1)
    ]
    legenda = (
        "As ofertas em destaque essa semana no cash-b — cashback garantido em cada uma. "
        "Link na bio pra ver todas. 🔥\n#cashback #shopee #ofertas"
    )
    return _publicar_ou_simular_carrossel(
        [capa, *slides], legenda, RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA,
        data, request,
    )


DESPACHANTES = {
    RegistroPublicacao.CONTEUDO_OFERTA_DIARIA: publicar_story_ofertas,
    RegistroPublicacao.CONTEUDO_DICA: publicar_story_dica,
    RegistroPublicacao.CONTEUDO_LEMBRETE: publicar_story_lembrete,
    RegistroPublicacao.CONTEUDO_INSTITUCIONAL: publicar_post_institucional,
    RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA: publicar_post_ofertas_semana,
}


def executar_publicacoes_do_dia(request) -> list[dict]:
    """Chamado a partir da tarefa diária (ver cashback_shopee/views.py). Decide o que
    precisa ser publicado hoje conforme o calendário e publica (ou simula, se
    INSTAGRAM_BOT_ATIVO=False)."""
    hoje = timezone.localdate()
    resultados = []

    for tipo in conteudo.tipo_de_conteudo_do_dia(hoje):
        if _ja_processado_hoje(hoje, tipo):
            continue
        despachante = DESPACHANTES[tipo]
        registro = despachante(hoje, request)
        if registro:
            resultados.append({
                "conteudo_tipo": registro.conteudo_tipo,
                "status": registro.status,
                "simulado": registro.modo_simulacao,
            })

    return resultados
