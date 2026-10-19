"""Relatório diário por e-mail: resultados de ontem e do mês, Sub IDs, produtos mais
vendidos e, para quem tem o Bot de WhatsApp, as ofertas enviadas. Vai de manhã (a
Shopee libera os números de ontem ao longo da madrugada), uma vez por dia por conta."""

import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from licencas.models import MODULO_WHATSAPP

from . import resultados, telas
from .emails import url_do_painel
from .models import RelatorioEmail

logger = logging.getLogger(__name__)

HORA_DO_ENVIO = 8  # a partir das 8h (horário de Brasília)...
HORA_LIMITE_PARA_ESPERAR = 11  # ...se até 11h não teve atualização nova, vai assim mesmo
MAXIMO_EXTRAS = 3


def _ofertas_do_bot(conta, dia: date) -> dict | None:
    if MODULO_WHATSAPP not in conta.modulos_liberados():
        return None
    from bot_whatsapp.models import EnvioWhatsApp

    de, ate = resultados._limites(dia, dia)
    envios = EnvioWhatsApp.objects.filter(
        conta=conta, origem=EnvioWhatsApp.OFERTA, estado=EnvioWhatsApp.ENVIADO, criado_em__gte=de, criado_em__lt=ate,
    )
    return {"ofertas": envios.values("item_id").distinct().count(), "mensagens": envios.count()}


def montar(conta, hoje: date) -> dict:
    """Os números do e-mail (também usados no teste)."""
    ontem = hoje - timedelta(days=1)
    inicio_mes = ontem.replace(day=1)
    meta = telas.situacao_meta(conta, ontem.year, ontem.month, ontem + timedelta(days=1))
    proxima = next((f for f in meta.get("faixas_tela", []) if not f["batida"]), None)
    return {
        "conta": conta,
        "ontem": ontem,
        "nome_mes": telas.nome_mes(ontem.year, ontem.month),
        "dia_ontem": resultados.totais(conta, ontem, ontem),
        "mes": resultados.totais(conta, inicio_mes, ontem),
        "meta": meta if meta.get("faixas_tela") else None,
        "meta_proxima": proxima,
        "sub_ids": resultados.por_sub_id(conta, ontem, ontem, limite=8),
        "produtos": resultados.ranking_produtos(resultados.vendas_do_periodo(conta, ontem, ontem), limite=3),
        "bot": _ofertas_do_bot(conta, ontem),
        "url_resultados": url_do_painel("painel_resultados") + "?periodo=ontem",
        "url_configuracoes": url_do_painel("painel_configuracoes") + "#relatorio",
    }


def enviar(conta, hoje: date, destinatarios: list[str]) -> None:
    """Monta e envia. Levanta erro se o envio falhar (quem chama decide o que fazer)."""
    dados = montar(conta, hoje)
    assunto = f"Appfiliado — seus resultados de {dados['ontem']:%d/%m}"
    html = render_to_string("painel/email_relatorio.html", dados)
    texto = render_to_string("painel/email_relatorio.txt", dados)
    mensagem = EmailMultiAlternatives(
        subject=assunto, body=texto, to=destinatarios, from_email=settings.APPFILIADO_EMAIL_REMETENTE,
    )
    mensagem.attach_alternative(html, "text/html")
    mensagem.send()


def pronto_para_enviar(preferencia, agora: datetime) -> bool:
    """De manhã, depois de uma atualização com a Shopee feita hoje (os números de ontem
    já chegaram) - ou às 11h, mesmo sem ela."""
    local = timezone.localtime(agora)
    if not preferencia.ativo or preferencia.ultimo_envio_dia == local.date() or local.hour < HORA_DO_ENVIO:
        return False
    if local.hour >= HORA_LIMITE_PARA_ESPERAR:
        return True
    estado = getattr(preferencia.conta, "sincronizacao_resultados", None)
    if not estado or not estado.concluida_em or estado.erro:
        return False
    concluida = timezone.localtime(estado.concluida_em)
    return concluida.date() == local.date() and concluida.hour >= 6


def enviar_pendentes(agora: datetime | None = None) -> list[str]:
    """Chamado pelo worker a cada volta. Devolve uma linha de log por envio."""
    agora = agora or timezone.now()
    if timezone.localtime(agora).hour < HORA_DO_ENVIO:
        return []
    logs = []
    hoje = timezone.localtime(agora).date()
    preferencias = (
        RelatorioEmail.objects.filter(ativo=True, conta__shopee_validado_em__isnull=False)
        .exclude(ultimo_envio_dia=hoje).select_related("conta", "conta__sincronizacao_resultados")
    )
    for preferencia in preferencias:
        if not pronto_para_enviar(preferencia, agora):
            continue
        preferencia.ultimo_envio_dia = hoje  # uma tentativa por dia, mesmo se falhar
        try:
            enviar(preferencia.conta, hoje, preferencia.destinatarios())
            preferencia.ultimo_erro = ""
            logs.append(f"Relatório por e-mail enviado: {preferencia.conta.email}")
        except Exception as erro:  # noqa: BLE001
            logger.exception("Painel: falha no relatório por e-mail da conta %s", preferencia.conta_id)
            preferencia.ultimo_erro = str(erro)[:500]
            logs.append(f"Relatório por e-mail falhou: {preferencia.conta.email} - {erro}")
        preferencia.save(update_fields=["ultimo_envio_dia", "ultimo_erro", "atualizado_em"])
    return logs
