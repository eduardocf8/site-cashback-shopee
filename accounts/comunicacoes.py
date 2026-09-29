"""Comunicação em massa por e-mail (ver UserAdmin em accounts/admin.py).

Manda tudo via BCC em lotes, numa única requisição síncrona do admin - o site
roda com 1 worker gunicorn só (ver README.md), então mandar 1 e-mail por
destinatário em série (dezenas/centenas de chamadas HTTP pra API do Brevo)
travaria o site inteiro por bom tempo. BCC deixa a API do Brevo mandar vários
destinatários numa chamada só; o tamanho do lote fica bem abaixo do limite
documentado da API (99 destinatários por chamada) por margem de segurança.

Quando tem ofertas escolhidas e/ou uma imagem de banner, o e-mail também sai
em HTML - banner no topo, texto, depois a vitrine de produtos (imagem + link
de cashback de cada uma) - ver templates/emails/comunicacao_vitrine.html.
"""

import logging
from datetime import timedelta
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .models import ComunicacaoEmail, User

FILTROS = dict(ComunicacaoEmail.FILTRO_CHOICES)

TAMANHO_LOTE = 50
OFERTAS_POR_LINHA = 2

# Janelas dos lembretes de primeira compra (ver enviar_lembrete_primeira_compra_7_dias/
# 30_dias) - cadastrado há N dias, ainda sem nenhum pedido. Cada janela dura 24h (N a
# N+1 dias) pra pegar cada pessoa 1 vez só, rodando o cron 1x/dia - mesmo esquema do
# lembrete de verificação de e-mail (accounts/tokens.py).
LEMBRETE_PRIMEIRA_COMPRA_7_DIAS = 7
LEMBRETE_PRIMEIRA_COMPRA_30_DIAS = 30

logger = logging.getLogger(__name__)


def obter_destinatarios(filtro: str, tipo: str = ComunicacaoEmail.TIPO_ANUNCIO) -> QuerySet:
    """Usuários com e-mail preenchido que batem no filtro escolhido. Sempre parte
    de quem tem e-mail (senão a API do Brevo recusa o endereço vazio). Anúncio/promoção
    (tipo padrão) também respeita quem desligou e-mail de marketing - comunicação geral
    não, vai pra todo mundo do filtro escolhido mesmo assim."""
    base = User.objects.exclude(email="")
    if tipo == ComunicacaoEmail.TIPO_ANUNCIO:
        base = base.filter(aceita_email_marketing=True)

    if filtro == ComunicacaoEmail.FILTRO_COM_PEDIDOS:
        return base.filter(pedidos__isnull=False).distinct()
    if filtro == ComunicacaoEmail.FILTRO_SEM_PEDIDOS:
        return base.filter(pedidos__isnull=True)
    if filtro == ComunicacaoEmail.FILTRO_EMAIL_VERIFICADO:
        return base.filter(email_verificado=True)
    if filtro == ComunicacaoEmail.FILTRO_EMAIL_NAO_VERIFICADO:
        return base.filter(email_verificado=False)
    if filtro == ComunicacaoEmail.FILTRO_JA_SACOU:
        return base.filter(saques__isnull=False).distinct()
    if filtro == ComunicacaoEmail.FILTRO_NUNCA_SACOU:
        return base.filter(saques__isnull=True)
    return base


def _lotes(itens: list, tamanho: int):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def _texto_para_html(corpo: str) -> str:
    """Cada linha em branco vira um novo parágrafo, texto sempre escapado -
    é texto puro digitado no formulário, nunca deve virar HTML de verdade."""
    paragrafos = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    return "".join(
        f"<p style='margin:0 0 12px;'>{escape(p).replace(chr(10), '<br>')}</p>" for p in paragrafos
    )


def _rodape_descadastro_texto(link: str) -> str:
    return (
        "\n\n---\nVocê recebeu este e-mail porque tem uma conta na cash-b.\n"
        f"Não quer mais receber e-mails de promoções? Clique aqui: {link}"
    )


def renderizar_corpo_html(
    corpo: str, ofertas, request, link_descadastro: str | None = None, banner_url: str | None = None
) -> str:
    """request é necessário pra montar o link absoluto (https://cash-b.com/...) de
    cada oferta - fora de uma view não tem como saber o domínio."""
    itens = [
        {"oferta": oferta, "link": request.build_absolute_uri(reverse("ofertas_ir", args=[oferta.id]))}
        for oferta in ofertas
    ]
    linhas = [itens[i : i + OFERTAS_POR_LINHA] for i in range(0, len(itens), OFERTAS_POR_LINHA)]
    return render_to_string(
        "emails/comunicacao_vitrine.html",
        {
            "corpo_html_intro": _texto_para_html(corpo),
            "ofertas": itens,
            "ofertas_em_linhas": linhas,
            "link_descadastro": link_descadastro,
            "banner_url": banner_url,
        },
    )


def enviar_comunicacao(
    *,
    assunto: str,
    corpo: str,
    filtro: str,
    tipo: str = ComunicacaoEmail.TIPO_ANUNCIO,
    ofertas=None,
    banner=None,
    enviado_por,
    request=None,
) -> ComunicacaoEmail:
    if filtro not in FILTROS:
        filtro = ComunicacaoEmail.FILTRO_TODOS
    if tipo not in dict(ComunicacaoEmail.TIPO_CHOICES):
        tipo = ComunicacaoEmail.TIPO_ANUNCIO

    eh_anuncio = tipo == ComunicacaoEmail.TIPO_ANUNCIO
    # Sem request não dá pra montar um link absoluto (precisa saber o domínio) - nesse
    # caso raro (só acontece se alguém chamar essa função fora da view do admin) o
    # anúncio sai sem o rodapé de descadastro em vez de quebrar o envio inteiro.
    link_descadastro = request.build_absolute_uri(reverse("preferencias_email")) if eh_anuncio and request else None

    ofertas = list(ofertas or [])

    # Cria e salva primeiro (isso já grava o arquivo do banner no storage e gera a URL
    # dele) - só depois dá pra montar o HTML que referencia essa URL. total_destinatarios
    # e total_enviados ficam provisórios aqui, atualizados no final depois do envio de
    # verdade.
    comunicacao = ComunicacaoEmail(assunto=assunto, corpo=corpo, filtro=filtro, tipo=tipo, enviado_por=enviado_por)
    if banner:
        comunicacao.banner = banner
    comunicacao.save()

    banner_url = request.build_absolute_uri(comunicacao.banner.url) if comunicacao.banner and request else None
    corpo_enviado = corpo + (_rodape_descadastro_texto(link_descadastro) if link_descadastro else "")
    corpo_html = (
        renderizar_corpo_html(corpo, ofertas, request, link_descadastro=link_descadastro, banner_url=banner_url)
        if (ofertas or banner_url) and request
        else ""
    )

    emails = list(obter_destinatarios(filtro, tipo).values_list("email", flat=True))
    _, endereco_remetente = parseaddr(settings.DEFAULT_FROM_EMAIL)

    total_enviados = 0
    for lote in _lotes(emails, TAMANHO_LOTE):
        try:
            mensagem = EmailMultiAlternatives(
                subject=assunto, body=corpo_enviado, to=[endereco_remetente], bcc=lote
            )
            if corpo_html:
                mensagem.attach_alternative(corpo_html, "text/html")
            mensagem.send()
            total_enviados += len(lote)
        except Exception:
            logger.warning("[comunicacoes] falha ao mandar lote de %d e-mail(s)", len(lote), exc_info=True)

    comunicacao.corpo_html = corpo_html
    comunicacao.total_destinatarios = len(emails)
    comunicacao.total_enviados = total_enviados
    comunicacao.save(update_fields=["corpo_html", "total_destinatarios", "total_enviados"])
    if ofertas:
        comunicacao.ofertas.set(ofertas)
    return comunicacao


def _usuarios_sem_primeiro_pedido_cadastrados_ha(dias: int) -> QuerySet:
    """Quem se cadastrou entre `dias` e `dias + 1` atrás, ainda sem nenhum pedido, com
    e-mail e sem ter desligado e-mail de marketing - usado pelos lembretes de primeira
    compra (ver enviar_lembrete_primeira_compra_7_dias/30_dias)."""
    agora = timezone.now()
    return (
        User.objects.exclude(email="")
        .filter(aceita_email_marketing=True, pedidos__isnull=True)
        .filter(date_joined__lt=agora - timedelta(days=dias), date_joined__gte=agora - timedelta(days=dias + 1))
    )


def _mandar_lembrete_em_lotes(usuarios: QuerySet, request, assunto: str, corpo: str) -> int:
    """BCC em lotes, mesmo motivo de enviar_comunicacao (ver docstring do módulo) - o
    conteúdo é igual pra todo mundo do lembrete (sem token individual por pessoa),
    então BCC serve bem aqui também. Sempre leva o rodapé de descadastro - é um
    lembrete promocional ("venha comprar"), respeita o mesmo opt-out dos e-mails da
    tela de comunicação do admin."""
    link_descadastro = request.build_absolute_uri(reverse("preferencias_email")) if request else None
    corpo_completo = corpo + (_rodape_descadastro_texto(link_descadastro) if link_descadastro else "")
    emails = list(usuarios.values_list("email", flat=True))
    _, endereco_remetente = parseaddr(settings.DEFAULT_FROM_EMAIL)

    total_enviados = 0
    for lote in _lotes(emails, TAMANHO_LOTE):
        try:
            EmailMessage(subject=assunto, body=corpo_completo, to=[endereco_remetente], bcc=lote).send()
            total_enviados += len(lote)
        except Exception:
            logger.warning(
                "[comunicacoes] falha ao mandar lote de %d e-mail(s) (lembrete de primeira compra)",
                len(lote), exc_info=True,
            )
    return total_enviados


def enviar_lembrete_primeira_compra_7_dias(request) -> int:
    usuarios = _usuarios_sem_primeiro_pedido_cadastrados_ha(LEMBRETE_PRIMEIRA_COMPRA_7_DIAS)
    link_ofertas = request.build_absolute_uri(reverse("ofertas_lista"))
    corpo = (
        "Olá!\n\n"
        "Notamos que você criou sua conta na cash-b, mas ainda não fez nenhuma compra "
        "por aqui.\n\n"
        "É simples: você gera um link com cashback pra qualquer produto da Shopee, "
        "compra normalmente usando esse link, e uma parte do valor volta pra você em "
        "dinheiro (via Pix, depois de juntar R$ 20,00 de saldo). Não tem nenhum custo "
        "a mais nisso — você paga o mesmo preço de sempre, só que uma parte volta.\n\n"
        f"Dá uma olhada nas ofertas: {link_ofertas}\n\n"
        "Equipe cash-b"
    )
    return _mandar_lembrete_em_lotes(usuarios, request, "cash-b — ainda não fez seu primeiro pedido?", corpo)


def enviar_lembrete_primeira_compra_30_dias(request) -> int:
    usuarios = _usuarios_sem_primeiro_pedido_cadastrados_ha(LEMBRETE_PRIMEIRA_COMPRA_30_DIAS)
    link_ofertas = request.build_absolute_uri(reverse("ofertas_lista"))
    corpo = (
        "Olá!\n\n"
        "Faz um mês que você criou sua conta na cash-b e ainda não usou o cashback em "
        "nenhuma compra na Shopee.\n\n"
        "Não tem pegadinha nem prazo pra aproveitar: da próxima vez que for comprar na "
        "Shopee, gere o link pela cash-b antes de fechar o pedido, e uma parte do "
        "valor volta pra você — sem pagar nada a mais por isso.\n\n"
        f"Ver ofertas: {link_ofertas}\n\n"
        "Equipe cash-b"
    )
    return _mandar_lembrete_em_lotes(
        usuarios, request, "cash-b — seu cashback ainda está te esperando", corpo
    )
