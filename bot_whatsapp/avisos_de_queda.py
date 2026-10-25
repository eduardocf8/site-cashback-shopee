"""Aviso de bot parado: quando o WhatsApp da conta para sem a pessoa ter pedido, o bot deixa de
postar em silêncio. Aqui a gente avisa por e-mail (e o painel mostra uma faixa vermelha).

- "deslogou": o WhatsApp tirou o aparelho (removido no celular, troca de celular, sessão
  encerrada). Não volta sozinho: avisa na hora.
- "caiu": a conexão caiu e o worker tenta reconectar sozinho. Só avisa se continuar fora
  depois de ESPERA_DA_QUEDA (quedas curtas voltam sozinhas).

Um e-mail por queda e, se continuar parado, um lembrete depois de LEMBRETE_APOS; depois disso
para. Só pra quem tem o Bot no plano e está usando (ofertas ligadas ou alerta de preço ligado).
O gerenciador marca e desmarca a queda (parou/voltou); o worker chama uma_volta()."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import AlertaPreco, ConexaoWhatsApp, ConfiguracaoOfertas

logger = logging.getLogger(__name__)

ESPERA_DA_QUEDA = timedelta(minutes=30)
LEMBRETE_APOS = timedelta(hours=24)
MAXIMO_DE_AVISOS = 2
CAMPOS = ["parado_desde", "parado_motivo", "parado_avisos", "parado_avisado_em"]


def parou(conexao, motivo: str, agora=None) -> None:
    """Marca a queda (quem chama salva os CAMPOS). "deslogou" vale mais que "caiu": se já
    estava caído e o WhatsApp tirou o aparelho, o motivo muda (e o aviso sai na hora)."""
    if not conexao.parado_desde:
        conexao.parado_desde, conexao.parado_motivo = agora or timezone.now(), motivo
        conexao.parado_avisos, conexao.parado_avisado_em = 0, None
    elif motivo == ConexaoWhatsApp.PARADO_DESLOGOU:
        conexao.parado_motivo = motivo


def voltou(conexao) -> None:
    conexao.parado_desde, conexao.parado_motivo = None, ""
    conexao.parado_avisos, conexao.parado_avisado_em = 0, None


def esta_parado(conexao, agora=None) -> bool:
    """Parado de um jeito que merece aviso (e-mail e faixa no painel). Enquanto a pessoa está
    lendo o QR Code de novo, não."""
    if not conexao or not conexao.parado_desde or conexao.estado in (ConexaoWhatsApp.CONECTADO,
                                                                     ConexaoWhatsApp.AGUARDANDO_QR):
        return False
    if conexao.parado_motivo == ConexaoWhatsApp.PARADO_DESLOGOU:
        return True
    return (agora or timezone.now()) - conexao.parado_desde >= ESPERA_DA_QUEDA


def _usa_o_bot(conta) -> bool:
    from licencas.models import MODULO_WHATSAPP

    if MODULO_WHATSAPP not in conta.modulos_liberados():
        return False  # assinatura vencida ou cancelada: o bot parar é o esperado
    return (ConfiguracaoOfertas.objects.filter(conta=conta, ativo=True).exists()
            or AlertaPreco.objects.filter(conta=conta, ativo=True).exists())


def uma_volta(agora=None) -> list[str]:
    agora = agora or timezone.now()
    linhas = []
    paradas = (ConexaoWhatsApp.objects.filter(parado_desde__isnull=False, parado_avisos__lt=MAXIMO_DE_AVISOS)
               .exclude(estado__in=[ConexaoWhatsApp.CONECTADO, ConexaoWhatsApp.AGUARDANDO_QR])
               .select_related("conta"))
    for conexao in paradas:
        if not esta_parado(conexao, agora):
            continue
        if conexao.parado_avisos and agora - conexao.parado_avisado_em < LEMBRETE_APOS:
            continue
        if not _usa_o_bot(conexao.conta):
            continue
        # Marca antes de mandar: se dois processos rodarem juntos, só um manda.
        marcou = ConexaoWhatsApp.objects.filter(pk=conexao.pk, parado_avisos=conexao.parado_avisos).update(
            parado_avisos=conexao.parado_avisos + 1, parado_avisado_em=agora)
        if not marcou:
            continue
        lembrete = conexao.parado_avisos > 0
        if enviar_email(conexao, lembrete):
            linhas.append(f"Bot parado: avisei {conexao.conta.email} ({conexao.parado_motivo}{', lembrete' if lembrete else ''}).")
    return linhas


def enviar_email(conexao, lembrete: bool = False) -> bool:
    from painel.emails import url_do_painel

    conta = conexao.conta
    quando = timezone.localtime(conexao.parado_desde)
    hoje = timezone.localdate()
    dia = "hoje" if quando.date() == hoje else "ontem" if quando.date() == hoje - timedelta(days=1) else \
        f"em {quando:%d/%m}"
    hora = f"{quando:%H}h{quando:%M}"
    if conexao.parado_motivo == ConexaoWhatsApp.PARADO_DESLOGOU:
        assunto = "Seu bot do Appfiliado parou: o WhatsApp foi desconectado"
        explicacao = (f"O WhatsApp desconectou o Appfiliado às {hora} de {dia}. Isso acontece quando o aparelho "
                      "é removido em \"Aparelhos conectados\", quando você troca de celular ou quando o WhatsApp "
                      "encerra a sessão.")
        como_voltar = ("Para voltar, leva menos de um minuto: abra o painel, clique em Conectar e leia o QR Code "
                       "com o celular.")
    else:
        assunto = "Seu bot do Appfiliado parou: a conexão com o WhatsApp caiu"
        explicacao = f"A conexão com o seu WhatsApp caiu às {hora} de {dia} e não voltou sozinha."
        como_voltar = ("Para voltar, abra o painel e clique em Conectar. Se pedir, leia o QR Code com o celular. "
                       "Confira também se o celular está com internet.")
    if lembrete:
        assunto = "Lembrete: " + assunto[0].lower() + assunto[1:]
    corpo = (
        f"Olá{', ' + conta.nome.split(' ')[0] if conta.nome else ''}!\n\n"
        f"{explicacao}\n\n"
        "Enquanto isso, as ofertas não estão saindo nos seus grupos.\n\n"
        f"{como_voltar}\n\n"
        f"Reconectar agora: {url_do_painel('painel_whatsapp')}\n\n"
        "Qualquer dúvida, é só responder este e-mail.\n\n"
        "Equipe Appfiliado"
    )
    try:
        EmailMessage(subject=assunto, body=corpo, to=[conta.email],
                     from_email=settings.APPFILIADO_EMAIL_REMETENTE).send()
    except Exception:  # noqa: BLE001
        logger.exception("Bot parado: falha ao mandar o aviso pra conta %s", conta.pk)
        return False
    return True
