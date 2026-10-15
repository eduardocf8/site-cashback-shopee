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

Única exceção ao BCC em lote: o lembrete de venda indireta
(enviar_lembrete_venda_indireta_semanal), cujo conteúdo é diferente por
pessoa (produtos que ela comprou) e por isso manda 1 e-mail por usuário.
"""

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.html import escape

from links.models import Click
from pedidos.models import ItemPedido, Pedido

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

# Janela do lembrete semanal de venda indireta (ver enviar_lembrete_venda_indireta_semanal) -
# roda 1x/semana (sábado de manhã, ver README.md), olhando os pedidos dos últimos N dias.
LEMBRETE_VENDA_INDIRETA_DIAS = 7

REEL_VENDA_INDIRETA_URL = "https://www.instagram.com/reel/Ddm_ZalNGKI/"

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
        f"<p style='margin:0 0 12px;'>{_sem_quebra_no_nome(escape(p)).replace(chr(10), '<br>')}</p>"
        for p in paragrafos
    )


def _sem_quebra_no_nome(texto_escapado: str) -> str:
    """Impede a quebra de linha no hífen de "cash-b" (e de "cash-b.com"). O texto vem digitado
    no admin e o navegador quebra depois de qualquer hífen, o que partia o nome em "cash-" e "b".
    Roda DEPOIS do escape, sobre o texto já seguro, e só envolve o nome num span: o texto
    copiado continua sendo "cash-b"."""
    return texto_escapado.replace("cash-b", '<span style="white-space:nowrap;">cash-b</span>')


def _rodape_descadastro_texto(link: str) -> str:
    return (
        "\n\n---\nVocê recebeu este e-mail porque tem uma conta na cash-b.\n"
        f"Não quer mais receber e-mails de promoções? Clique aqui: {link}"
    )


def _contexto_redes_sociais() -> dict:
    """Contexto comum das redes sociais, pro rodapé de
    templates/emails/lembrete_automatico.html e lembrete_venda_indireta.html."""
    return {
        "url_instagram": settings.URL_INSTAGRAM,
        "url_whatsapp_canal": settings.URL_WHATSAPP_CANAL,
        "url_youtube": settings.URL_YOUTUBE,
    }


def _rodape_redes_sociais_texto() -> str:
    """Mesmas redes sociais de _contexto_redes_sociais(), pro rodapé da versão em
    texto puro do e-mail."""
    return (
        f"\n\nInstagram: {settings.URL_INSTAGRAM}\n"
        f"WhatsApp: {settings.URL_WHATSAPP_CANAL}\n"
        f"YouTube: {settings.URL_YOUTUBE}"
    )


def renderizar_corpo_html(
    corpo: str, ofertas, request, link_descadastro: str | None = None, banner_url: str | None = None,
    assunto: str = "",
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
            # Texto alternativo do banner: o corpo digitado, numa linha só. Quem bloqueia imagens (o
            # caso típico do Outlook) vê o HTML sem o banner, e o que aparece no lugar dele é
            # este texto - então ele precisa carregar a mensagem, não só o assunto. Quem vê a
            # imagem não vê duplicação (alt não aparece), e leitores de tela leem o texto inteiro.
            # O assunto só entra se o corpo estiver vazio.
            "banner_alt": " ".join(corpo.split()) or assunto,
            # O banner leva à vitrine (onde se compra); o "cash-b.com" do rodapé, à home.
            "link_site": request.build_absolute_uri(reverse("ofertas_lista")) + "?utm_source=email&utm_medium=comunicacao",
            "link_home": request.build_absolute_uri(reverse("home")) + "?utm_source=email&utm_medium=comunicacao",
            "link_instagram": settings.URL_INSTAGRAM,
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
        renderizar_corpo_html(
            corpo, ofertas, request, link_descadastro=link_descadastro, banner_url=banner_url, assunto=assunto
        )
        if (ofertas or banner_url) and request
        else ""
    )

    emails = list(obter_destinatarios(filtro, tipo).values_list("email", flat=True))

    total_enviados = 0
    for lote in _lotes(emails, TAMANHO_LOTE):
        try:
            mensagem = EmailMultiAlternatives(
                subject=assunto, body=corpo_enviado, to=[settings.EMAIL_BCC_PARA_PLACEHOLDER], bcc=lote
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


def enviar_lembrete_primeira_compra_7_dias(request) -> int:
    usuarios = _usuarios_sem_primeiro_pedido_cadastrados_ha(LEMBRETE_PRIMEIRA_COMPRA_7_DIAS)
    link_ofertas = request.build_absolute_uri(reverse("ofertas_lista"))
    link_descadastro = request.build_absolute_uri(reverse("preferencias_email"))
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
        + _rodape_redes_sociais_texto()
        + _rodape_descadastro_texto(link_descadastro)
    )
    corpo_html_intro = (
        "<p style='margin:0 0 12px;'>Olá!</p>"
        "<p style='margin:0 0 12px;'>Notamos que você criou sua conta na cash-b, mas "
        "ainda não fez nenhuma compra por aqui.</p>"
        "<p style='margin:0;'>É simples: você gera um link com cashback pra qualquer "
        "produto da Shopee, compra normalmente usando esse link, e uma parte do valor "
        "volta pra você em dinheiro (via Pix, depois de juntar R$ 20,00 de saldo). Não "
        "tem nenhum custo a mais nisso — você paga o mesmo preço de sempre, só que "
        "uma parte volta.</p>"
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": corpo_html_intro,
            "cta_url": link_ofertas,
            "cta_texto": "Ver ofertas",
            "link_descadastro": link_descadastro,
            **_contexto_redes_sociais(),
        },
    )
    return _mandar_lembrete_html_em_lotes(
        usuarios, "cash-b — ainda não fez seu primeiro pedido?", corpo, corpo_html
    )


def enviar_lembrete_primeira_compra_30_dias(request) -> int:
    usuarios = _usuarios_sem_primeiro_pedido_cadastrados_ha(LEMBRETE_PRIMEIRA_COMPRA_30_DIAS)
    link_ofertas = request.build_absolute_uri(reverse("ofertas_lista"))
    link_descadastro = request.build_absolute_uri(reverse("preferencias_email"))
    corpo = (
        "Olá!\n\n"
        "Faz um mês que você criou sua conta na cash-b e ainda não usou o cashback em "
        "nenhuma compra na Shopee.\n\n"
        "Não tem pegadinha nem prazo pra aproveitar: da próxima vez que for comprar na "
        "Shopee, gere o link pela cash-b antes de fechar o pedido, e uma parte do "
        "valor volta pra você — sem pagar nada a mais por isso.\n\n"
        f"Ver ofertas: {link_ofertas}\n\n"
        "Equipe cash-b"
        + _rodape_redes_sociais_texto()
        + _rodape_descadastro_texto(link_descadastro)
    )
    corpo_html_intro = (
        "<p style='margin:0 0 12px;'>Olá!</p>"
        "<p style='margin:0 0 12px;'>Faz um mês que você criou sua conta na cash-b e "
        "ainda não usou o cashback em nenhuma compra na Shopee.</p>"
        "<p style='margin:0;'>Não tem pegadinha nem prazo pra aproveitar: da próxima "
        "vez que for comprar na Shopee, gere o link pela cash-b antes de fechar o "
        "pedido, e uma parte do valor volta pra você — sem pagar nada a mais por "
        "isso.</p>"
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": corpo_html_intro,
            "cta_url": link_ofertas,
            "cta_texto": "Ver ofertas",
            "link_descadastro": link_descadastro,
            **_contexto_redes_sociais(),
        },
    )
    return _mandar_lembrete_html_em_lotes(
        usuarios, "cash-b — seu cashback ainda está te esperando", corpo, corpo_html
    )


def _itens_indiretos_por_usuario(dias: int) -> dict[int, list[ItemPedido]]:
    """Agrupa por usuário todo ItemPedido de venda indireta (clique em "Ir pra
    Shopee" OU produto comprado diferente do link que gerou o clique - ver
    ItemPedido.venda_direta) comprado nos últimos `dias` dias, de pedido não
    cancelado. Base de quem recebe o lembrete semanal E do conteúdo de cada e-mail
    (ver enviar_lembrete_venda_indireta_semanal) - diferente da versão antiga desse
    lembrete, que só checava click.tipo == TIPO_HOME e deixava passar batido quem
    converteu o link de um produto e comprou outro no lugar."""
    agora = timezone.now()
    itens = (
        ItemPedido.objects.filter(
            venda_direta=False,
            pedido__usuario_id__isnull=False,
            pedido__data_compra__gte=agora - timedelta(days=dias),
        )
        .exclude(pedido__status=Pedido.STATUS_CANCELADO)
        .select_related("pedido")
        .order_by("pedido__usuario_id", "-pedido__data_compra")
    )
    agrupado: dict[int, list[ItemPedido]] = defaultdict(list)
    for item in itens:
        agrupado[item.pedido.usuario_id].append(item)
    return agrupado


def enviar_lembrete_venda_indireta_semanal(request) -> int:
    """Lembrete semanal (Cron Job próprio, sábado de manhã - ver
    /tarefas/lembrete-venda-indireta/ em cashback_shopee/views.py e "Cron Jobs do
    Render" em marketing/instagram/README.md) pra quem comprou por venda indireta nos
    últimos 7 dias - mostra produto a produto quanto foi pago de cashback e quanto
    teria sido pago se a compra fosse direta, com a comissão real de cada item (ver
    ItemPedido.cashback_hipotetico_direto), não só o piso mínimo.

    Diferente dos outros lembretes automáticos (e da versão antiga deste): o
    conteúdo é diferente pra cada pessoa (os produtos que ela comprou), então não dá
    pra mandar em lote por BCC como o resto dos e-mails em massa deste módulo (ver
    docstring do módulo) - 1 envio por usuário, igual pedidos/notificacoes.py."""
    itens_por_usuario = _itens_indiretos_por_usuario(LEMBRETE_VENDA_INDIRETA_DIAS)
    if not itens_por_usuario:
        return 0

    usuarios = User.objects.filter(
        pk__in=itens_por_usuario.keys(), aceita_email_marketing=True
    ).exclude(email="")

    link_regras = request.build_absolute_uri(reverse("regras_cashback"))
    link_descadastro = request.build_absolute_uri(reverse("preferencias_email"))
    links_com_icone = [
        {
            "titulo": "Regras completas do cashback",
            "subtitulo": "Entenda como funciona a venda direta e a indireta",
            "url": link_regras,
            "icone_url": request.build_absolute_uri(static("images/email-icone-regras.png")),
        },
        {
            "titulo": "Assista no Instagram",
            "subtitulo": "Vídeo explicando as duas formas de comprar",
            "url": REEL_VENDA_INDIRETA_URL,
            "icone_url": request.build_absolute_uri(static("images/email-icone-instagram.png")),
        },
    ]

    corpo_html_intro = (
        "<p style='margin:0 0 12px;'>Essa semana você comprou pela cash-b usando "
        "<strong>venda indireta</strong> (clicando em “Ir pra Shopee” sem "
        "escolher um produto antes, ou comprando um produto diferente do link que "
        "você converteu) — e isso rendeu menos cashback do que podia.</p>"
    )
    corpo_html_explicacao = (
        "<p style='margin:0;'><strong>Venda direta</strong> é quando você converte "
        "o link de um produto específico (ou compra pela vitrine de ofertas) e "
        "compra exatamente esse produto — garante um cashback mínimo maior. Pra "
        "próxima, é só isso.</p>"
    )

    total_enviados = 0
    for usuario in usuarios:
        itens = itens_por_usuario[usuario.pk]
        total_pago = sum((item.cashback_pago for item in itens), Decimal("0.00"))
        total_hipotetico = sum((item.cashback_hipotetico_direto for item in itens), Decimal("0.00"))
        total_perdido = total_hipotetico - total_pago
        if total_perdido <= 0:
            # Matematicamente não deveria acontecer (o piso direto é sempre >= o
            # indireto - ver ItemPedido.cashback_perdido), mas sem nenhuma diferença
            # pra mostrar não tem o que esse e-mail diria.
            continue

        itens_contexto = [
            {
                "nome": item.nome or "Produto",
                "imagem_url": item.imagem_url,
                "cashback_pago": number_format(item.cashback_pago, decimal_pos=2),
                "cashback_hipotetico": number_format(item.cashback_hipotetico_direto, decimal_pos=2),
                "diferenca": number_format(item.cashback_perdido, decimal_pos=2),
            }
            for item in itens
        ]

        corpo_html = render_to_string(
            "emails/lembrete_venda_indireta.html",
            {
                "corpo_html_intro": corpo_html_intro,
                "corpo_html_explicacao": corpo_html_explicacao,
                "itens": itens_contexto,
                "total_pago": number_format(total_pago, decimal_pos=2),
                "total_hipotetico": number_format(total_hipotetico, decimal_pos=2),
                "total_perdido": number_format(total_perdido, decimal_pos=2),
                "links": links_com_icone,
                "link_descadastro": link_descadastro,
                **_contexto_redes_sociais(),
            },
        )

        linhas_itens_texto = "\n".join(
            f"- {item['nome']}: pago R$ {item['cashback_pago']} | se fosse direto "
            f"R$ {item['cashback_hipotetico']} (+R$ {item['diferenca']})"
            for item in itens_contexto
        )
        corpo = (
            f"Olá, {usuario.username}!\n\n"
            "Essa semana você comprou pela cash-b usando venda indireta (clicando em "
            "\"Ir pra Shopee\" sem escolher um produto antes, ou comprando um produto "
            "diferente do link que você converteu) - e isso rendeu menos cashback do "
            "que podia.\n\n"
            "Venda direta é quando você converte o link de um produto específico "
            "(ou compra pela vitrine de ofertas) e compra exatamente esse produto "
            "- garante um cashback mínimo maior. Pra próxima, é só isso.\n\n"
            f"Nessas compras, você deixou R$ {number_format(total_perdido, decimal_pos=2)} "
            "de cashback na mesa:\n\n"
            f"{linhas_itens_texto}\n\n"
            f"Total da semana: R$ {number_format(total_pago, decimal_pos=2)} -> "
            f"R$ {number_format(total_hipotetico, decimal_pos=2)}\n\n"
            f"Regras completas do cashback: {link_regras}\n"
            f"Veja no Instagram: {REEL_VENDA_INDIRETA_URL}\n\n"
            "Equipe cash-b"
            + _rodape_redes_sociais_texto()
            + _rodape_descadastro_texto(link_descadastro)
        )

        try:
            mensagem = EmailMultiAlternatives(
                subject="cash-b — quanto você deixou de ganhar essa semana",
                body=corpo,
                to=[usuario.email],
            )
            mensagem.attach_alternative(corpo_html, "text/html")
            mensagem.send()
            total_enviados += 1
        except Exception:
            logger.warning(
                "[comunicacoes] falha ao mandar lembrete de venda indireta pro usuário %s",
                usuario.pk, exc_info=True,
            )

    return total_enviados


def _mandar_lembrete_html_em_lotes(usuarios: QuerySet, assunto: str, corpo: str, corpo_html: str) -> int:
    """BCC em lotes (mesmo motivo de enviar_comunicacao, ver docstring do módulo) -
    usado pelos lembretes automáticos cujo conteúdo é igual pra todo mundo (sem token
    individual por pessoa), então BCC serve bem. Sempre manda as duas versões,
    texto (`corpo`) e HTML (`corpo_html`, via EmailMultiAlternatives)."""
    emails = list(usuarios.values_list("email", flat=True))

    total_enviados = 0
    for lote in _lotes(emails, TAMANHO_LOTE):
        try:
            mensagem = EmailMultiAlternatives(
                subject=assunto, body=corpo, to=[settings.EMAIL_BCC_PARA_PLACEHOLDER], bcc=lote
            )
            mensagem.attach_alternative(corpo_html, "text/html")
            mensagem.send()
            total_enviados += len(lote)
        except Exception:
            logger.warning(
                "[comunicacoes] falha ao mandar lote de %d e-mail(s) de lembrete automático",
                len(lote), exc_info=True,
            )
    return total_enviados
