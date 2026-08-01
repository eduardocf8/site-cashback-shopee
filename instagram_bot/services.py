import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from PIL import Image

from ofertas.models import Oferta

from . import conteudo, instagram_client
from .models import RegistroPublicacao
from .templates_imagem import CORES, gerar_imagem_ofertas, gerar_imagem_texto_simples

logger = logging.getLogger(__name__)

PASTA_MEDIA_BOT = Path(settings.MEDIA_ROOT) / "instagram"


def _salvar_e_montar_url(imagem, request) -> str:
    PASTA_MEDIA_BOT.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.png"
    caminho = PASTA_MEDIA_BOT / nome_arquivo
    imagem.save(caminho, "PNG")
    return request.build_absolute_uri(f"{settings.MEDIA_URL}instagram/{nome_arquivo}")


def _ja_publicado_hoje(data, conteudo_tipo: str) -> bool:
    return RegistroPublicacao.objects.filter(data=data, conteudo_tipo=conteudo_tipo, sucesso=True).exists()


def _registrar(data, tipo, conteudo_tipo, legenda, imagem_url, simulacao, sucesso, erro=""):
    return RegistroPublicacao.objects.create(
        data=data,
        tipo=tipo,
        conteudo_tipo=conteudo_tipo,
        legenda=legenda,
        imagem_url=imagem_url,
        modo_simulacao=simulacao,
        sucesso=sucesso,
        erro=erro,
    )


def _publicar_ou_simular(imagem, legenda, tipo, conteudo_tipo, data, request, story: bool) -> RegistroPublicacao:
    simulacao = not settings.INSTAGRAM_BOT_ATIVO
    imagem_url = ""
    try:
        imagem_url = _salvar_e_montar_url(imagem, request)
        if simulacao:
            logger.info(
                "[instagram_bot] modo simulação (INSTAGRAM_BOT_ATIVO=False) - geraria %s/%s: %s",
                tipo, conteudo_tipo, imagem_url,
            )
        else:
            instagram_client.publicar_imagem(imagem_url, legenda=legenda, story=story)
        return _registrar(data, tipo, conteudo_tipo, legenda, imagem_url, simulacao, sucesso=True)
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar %s/%s", tipo, conteudo_tipo)
        return _registrar(data, tipo, conteudo_tipo, legenda, imagem_url, simulacao, sucesso=False, erro=str(erro))


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
    imagem = Image.open(post["caminho"])
    return _publicar_ou_simular(
        imagem, post["legenda"], RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_INSTITUCIONAL,
        data, request, story=False,
    )


def publicar_post_ofertas_semana(data, request) -> RegistroPublicacao | None:
    ofertas = list(Oferta.objects.all()[:3])
    if not ofertas:
        logger.warning("[instagram_bot] sem ofertas sincronizadas, pulando post semanal")
        return None
    imagem = gerar_imagem_ofertas(ofertas, titulo="Top da semana", tamanho=(1080, 1080))
    legenda = (
        "As ofertas em destaque essa semana no cash-b — cashback garantido em cada uma. "
        "Link na bio pra ver todas. 🔥\n#cashback #shopee #ofertas"
    )
    return _publicar_ou_simular(
        imagem, legenda, RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA,
        data, request, story=False,
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
        if _ja_publicado_hoje(hoje, tipo):
            continue
        despachante = DESPACHANTES[tipo]
        registro = despachante(hoje, request)
        if registro:
            resultados.append({
                "conteudo_tipo": registro.conteudo_tipo,
                "sucesso": registro.sucesso,
                "simulado": registro.modo_simulacao,
            })

    return resultados
