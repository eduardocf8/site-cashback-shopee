"""Stories de oferta do instagram_bot respondidos sem configurar nada.

Quando o bot publica um story de oferta (tem o link do produto salvo), o story ganha a própria
AutomacaoStory sozinho, no modo "link do produto". A DM usa o padrão de PadraoRespostaStory: o
texto de lá e um botão que abre o link com cashback rastreado.
"""
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.utils import timezone

from instagram_bot.models import RegistroPublicacao

from .models import AutomacaoStory, ContaInstagramConectada, PadraoRespostaStory

logger = logging.getLogger(__name__)


def conta_do_bot() -> ContaInstagramConectada | None:
    """A conta conectada que é a mesma do bot (INSTAGRAM_BUSINESS_ACCOUNT_ID): é dela que a DM sai."""
    if not settings.INSTAGRAM_BUSINESS_ACCOUNT_ID:
        return None
    return (
        ContaInstagramConectada.objects.filter(instagram_business_account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID)
        .order_by("pk")
        .first()
    )


def e_story_de_oferta(registro: RegistroPublicacao) -> bool:
    """Story publicado de verdade (não simulado nem esperando aprovação) e com o link do produto."""
    return bool(
        registro.tipo == RegistroPublicacao.TIPO_STORY
        and registro.status == RegistroPublicacao.STATUS_PUBLICADO
        and not registro.modo_simulacao
        and registro.instagram_media_id
        and registro.link_produto_original
    )


def garantir_automacao(registro: RegistroPublicacao) -> AutomacaoStory | None:
    """A automação desse story (cria se ainda não existe). None com o padrão desligado, se o story não
    é de oferta ou se a conta do bot não está em Contas conectadas."""
    if not e_story_de_oferta(registro) or not PadraoRespostaStory.carregar().ativo:
        return None
    existente = AutomacaoStory.objects.filter(instagram_story_media_id=registro.instagram_media_id).first()
    if existente:
        return existente
    conta = conta_do_bot()
    if not conta:
        logger.warning(
            "[automacao_instagram] story de oferta %s sem automação: a conta do bot (%s) não está em Contas conectadas.",
            registro.instagram_media_id, settings.INSTAGRAM_BUSINESS_ACCOUNT_ID or "sem ID",
        )
        return None
    quando = timezone.localtime(registro.criado_em) if registro.criado_em else timezone.localtime()
    nome = f"Oferta: {registro.oferta_nome or 'produto'}"[:80] + f" ({quando:%d/%m %H:%M})"
    return AutomacaoStory.objects.create(
        conta=conta, nome=nome, instagram_story_media_id=registro.instagram_media_id,
        modo_resposta=AutomacaoStory.MODO_LINK_PRODUTO, automatica=True,
    )


def mensagem_com_link(link: str) -> tuple[str, tuple[str, str]]:
    """Texto e botão (título, endereço) da DM com o link do produto."""
    padrao = PadraoRespostaStory.carregar()
    return padrao.texto, (padrao.texto_botao, link)


def _ao_salvar_registro(sender, instance, **kwargs):
    # O link e o ID do story são gravados em momentos diferentes (publicação direta ou aprovação por
    # e-mail): a cada gravação confere se o story já tem os dois. Nunca atrapalha a publicação.
    try:
        garantir_automacao(instance)
    except Exception:
        logger.exception("[automacao_instagram] falha ao criar a automação do story %s", instance.pk)


def conectar():
    post_save.connect(_ao_salvar_registro, sender=RegistroPublicacao, dispatch_uid="automacao_story_de_oferta")
