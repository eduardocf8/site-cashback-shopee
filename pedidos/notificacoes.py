import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.formats import number_format
from django.utils.html import escape

from accounts.push import enviar_push

logger = logging.getLogger(__name__)


def _contexto_redes_sociais() -> dict:
    """Mesmo rodapé de redes sociais do accounts/comunicacoes.py (duplicado aqui de
    propósito - são só 3 leituras de settings, não vale acoplar os dois módulos por
    isso) - ver templates/emails/lembrete_automatico.html."""
    return {
        "url_instagram": settings.URL_INSTAGRAM,
        "url_whatsapp_canal": settings.URL_WHATSAPP_CANAL,
        "url_youtube": settings.URL_YOUTUBE,
    }


def _rodape_redes_sociais_texto() -> str:
    return (
        f"\n\nInstagram: {settings.URL_INSTAGRAM}\n"
        f"WhatsApp: {settings.URL_WHATSAPP_CANAL}\n"
        f"YouTube: {settings.URL_YOUTUBE}"
    )


def _enviar(usuario, assunto, corpo, corpo_html):
    if not usuario or not usuario.email:
        return
    try:
        mensagem = EmailMultiAlternatives(subject=assunto, body=corpo, to=[usuario.email])
        mensagem.attach_alternative(corpo_html, "text/html")
        mensagem.send()
    except Exception:
        logger.exception("Falha ao enviar e-mail de notificação de pedido pro usuário %s", usuario.pk)


def notificar_pedido_validado(pedido):
    produto = pedido.produto_nome or f"pedido {pedido.order_id}"
    valor = number_format(pedido.valor_cashback, decimal_pos=2)
    prazo = (
        pedido.data_prevista_liberacao.strftime("%d/%m/%Y")
        if pedido.data_prevista_liberacao
        else "em breve"
    )
    corpo = (
        f"Olá, {pedido.usuario.username}!\n\n"
        f'Seu pedido "{produto}" foi validado pela Shopee.\n'
        f"Cashback: R$ {valor}\n\n"
        f"Esse saldo fica disponível para saque a partir de {prazo}.\n\n"
        "Equipe cash-b"
        + _rodape_redes_sociais_texto()
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": (
                f"<p style='margin:0 0 12px;'>Olá, {pedido.usuario.username}!</p>"
                f"<p style='margin:0;'>Seu pedido “{produto}” foi validado "
                "pela Shopee.</p>"
            ),
            "destaque_valor": f"R$ {valor}",
            "corpo_html_depois": (
                f"<p style='margin:0;'>Esse saldo fica disponível para saque a partir "
                f"de {prazo}.</p>"
            ),
            **_contexto_redes_sociais(),
        },
    )
    _enviar(pedido.usuario, "cash-b — seu pedido foi validado", corpo, corpo_html)
    enviar_push(
        pedido.usuario,
        "Pedido validado!",
        f'"{produto}" — R$ {valor} de cashback, liberado para saque em {prazo}.',
        url="/dashboard/#pedidos",
    )


def notificar_pedido_liberado(pedido):
    produto = pedido.produto_nome or f"pedido {pedido.order_id}"
    valor = number_format(pedido.valor_cashback, decimal_pos=2)
    corpo = (
        f"Olá, {pedido.usuario.username}!\n\n"
        f'O cashback de "{produto}" (R$ {valor}) já está liberado e pode ser '
        "sacado via Pix no seu painel.\n\n"
        "Equipe cash-b"
        + _rodape_redes_sociais_texto()
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": (
                f"<p style='margin:0 0 12px;'>Olá, {pedido.usuario.username}!</p>"
                f"<p style='margin:0;'>O cashback de “{produto}” já está "
                "liberado e pode ser sacado via Pix no seu painel.</p>"
            ),
            "destaque_valor": f"R$ {valor}",
            **_contexto_redes_sociais(),
        },
    )
    _enviar(pedido.usuario, "cash-b — cashback liberado para saque", corpo, corpo_html)
    enviar_push(
        pedido.usuario,
        "Cashback liberado!",
        f'R$ {valor} de "{produto}" já pode ser sacado via Pix.',
        url="/dashboard/#saques",
    )


def notificar_indicador_bonus_pendente(indicacao):
    """Avisa quem indicou que a 1ª compra do indicado acabou de validar - o próximo
    pedido validado do indicador vem com o dobro de cashback (ver
    services.py::_selecionar_bonus_indicacao). Dispara só uma vez, no momento em que
    esse vínculo é decidido pela primeira vez - não a cada resync do mesmo pedido."""
    indicador = indicacao.indicador
    corpo = (
        f"Olá, {indicador.username}!\n\n"
        f"A pessoa que você indicou (@{indicacao.indicado.username}) teve a 1ª compra "
        "validada! 🎉\n\n"
        "Isso significa que o SEU próximo pedido validado vai vir com o dobro de "
        "cashback. Aproveite!\n\n"
        "Se estiver rolando uma campanha de cashback extra, seu pedido já vem com o "
        "valor aumentado da campanha e o bônus da indicação fica guardado pro "
        "pedido seguinte, depois que ela terminar.\n\n"
        "Equipe cash-b"
        + _rodape_redes_sociais_texto()
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": (
                f"<p style='margin:0 0 12px;'>Olá, {indicador.username}!</p>"
                f"<p style='margin:0 0 12px;'>A pessoa que você indicou "
                f"(@{indicacao.indicado.username}) teve a 1ª compra validada! \U0001F389</p>"
                "<p style='margin:0 0 12px;'>Isso significa que o <strong>seu próximo "
                "pedido validado</strong> vai vir com o dobro de cashback. Aproveite!</p>"
                "<p style='margin:0;'>Se estiver rolando uma campanha de cashback extra, "
                "seu pedido já vem com o valor aumentado da campanha e o bônus da "
                "indicação fica guardado pro pedido seguinte, depois que ela "
                "terminar.</p>"
            ),
            **_contexto_redes_sociais(),
        },
    )
    _enviar(
        indicador, "cash-b — sua indicação validou! seu próximo pedido vem em dobro", corpo, corpo_html
    )
    enviar_push(
        indicador,
        "Sua indicação validou!",
        f"@{indicacao.indicado.username} teve a 1ª compra validada — seu próximo pedido vem em dobro.",
        url="/dashboard/#indicacoes",
    )


def _notificar_simples(usuario, assunto, linhas, titulo_push, texto_push):
    """E-mail + push com o mesmo layout dos avisos de pedido, para textos curtos."""
    corpo = (
        f"Olá, {usuario.username}!\n\n" + "\n\n".join(linhas) + "\n\nEquipe cash-b" + _rodape_redes_sociais_texto()
    )
    corpo_html = render_to_string(
        "emails/lembrete_automatico.html",
        {
            "corpo_html_intro": (
                f"<p style='margin:0 0 12px;'>Olá, {escape(usuario.username)}!</p>"
                + "".join(f"<p style='margin:0 0 12px;'>{escape(linha)}</p>" for linha in linhas)
            ),
            **_contexto_redes_sociais(),
        },
    )
    _enviar(usuario, assunto, corpo, corpo_html)
    enviar_push(usuario, titulo_push, texto_push, url="/dashboard/#pedidos")


def notificar_reclamacao_vinculada(reclamacao):
    pedido = reclamacao.pedido
    valor = number_format(pedido.valor_cashback, decimal_pos=2)
    _notificar_simples(
        reclamacao.usuario,
        "cash-b — encontramos sua compra",
        [
            f"Encontramos o pedido {reclamacao.order_id} e ele já está na sua conta, em Meus pedidos.",
            f"Cashback: R$ {valor}. Ele segue os prazos normais: validado depois da entrega e do "
            "prazo de devolução, e liberado no dia 1º do segundo mês após a validação.",
        ],
        "Encontramos sua compra!",
        f"O pedido {reclamacao.order_id} foi adicionado à sua conta (R$ {valor} de cashback).",
    )


def notificar_reclamacao_encerrada(reclamacao):
    _notificar_simples(
        reclamacao.usuario,
        "cash-b — sobre a compra que você nos avisou",
        [
            f"Conferimos o pedido {reclamacao.order_id} e não foi possível adicioná-lo à sua conta.",
            reclamacao.resposta,
            "Na próxima compra, abra o link da cash-b e finalize a compra sem abrir outros links "
            "no caminho. Qualquer dúvida, fale com a gente pelo Fale conosco no site.",
        ],
        "Sobre a compra que você nos avisou",
        f"Não foi possível adicionar o pedido {reclamacao.order_id}. Veja o motivo no seu painel.",
    )
