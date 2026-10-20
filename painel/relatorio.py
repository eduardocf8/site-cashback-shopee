"""Relatório diário por e-mail: resultados de ontem e do mês, Sub IDs, produtos mais
vendidos e, para quem tem o Bot de WhatsApp, as ofertas enviadas. Vai uma vez por dia
por conta, no horário que a pessoa escolheu - mas só depois que a Shopee libera os números de
ontem (costuma ser entre 7h e 8h). Na hora do envio o app busca as vendas na Shopee: se ontem
ainda não apareceu, manda um aviso e tenta de novo a cada 30 minutos."""

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

HORA_MAIS_CEDO = 7  # o horário de envio é escolhido pela pessoa (RelatorioEmail.hora), das 7h às 22h
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
    return {
        "conta": conta,
        "ontem": ontem,
        "nome_mes": telas.nome_mes(ontem.year, ontem.month),
        "dia_ontem": resultados.totais(conta, ontem, ontem),
        "mes": resultados.totais(conta, inicio_mes, ontem),
        "meta": meta if meta.get("faixas_tela") else None,
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


INTERVALO_ENTRE_TENTATIVAS = timedelta(minutes=30)
HORA_DE_DESISTIR = 23  # se os números de ontem não saírem até aqui, o relatório do dia não vai
ATUALIZACAO_RECENTE = timedelta(minutes=10)  # atualização com a Shopee mais nova que isso não é refeita


def pronto_para_enviar(preferencia, agora: datetime) -> bool:
    """No horário escolhido (ou depois, se ainda não foi hoje), respeitando o intervalo entre
    tentativas quando os números de ontem ainda não tinham saído."""
    local = timezone.localtime(agora)
    if not preferencia.ativo or preferencia.ultimo_envio_dia == local.date() or local.hour < preferencia.hora:
        return False
    return not preferencia.proxima_tentativa_em or preferencia.proxima_tentativa_em <= agora


def numeros_de_ontem_sairam(conta, hoje: date) -> bool:
    """A Shopee libera os pedidos do dia anterior de manhã, de uma vez: enquanto não libera,
    ontem aparece sem nenhum pedido."""
    from .models import ResultadoDiario

    return ResultadoDiario.objects.filter(conta=conta, dia=hoje - timedelta(days=1), pedidos__gt=0).exists()


def atualizar_e_conferir(conta, hoje: date, agora: datetime) -> bool | None:
    """Busca as vendas na Shopee agora (se a última atualização não for de poucos minutos atrás)
    e diz se os números de ontem já saíram. None = não consegui falar com a Shopee."""
    from .models import SincronizacaoResultados

    estado = SincronizacaoResultados.objects.filter(conta=conta).first()
    recente = estado and estado.concluida_em and not estado.erro and agora - estado.concluida_em < ATUALIZACAO_RECENTE
    if not recente:
        resultados.processar(conta)
        estado = SincronizacaoResultados.objects.filter(conta=conta).first()
        if not estado or estado.erro:
            return None
    return numeros_de_ontem_sairam(conta, hoje)


def enviar_aviso(conta, hoje: date, destinatarios: list[str], agora: datetime, motivo: str = "nao_saiu",
                 automatico: bool = True) -> None:
    """E-mail curto avisando que o relatório não foi (os números de ontem ainda não saíram, ou a
    Shopee não respondeu)."""
    ontem = hoje - timedelta(days=1)
    dados = {"ontem": ontem, "hora": timezone.localtime(agora), "motivo": motivo, "automatico": automatico,
             "hora_de_desistir": HORA_DE_DESISTIR, "url_resultados": url_do_painel("painel_resultados"),
             "url_configuracoes": url_do_painel("painel_configuracoes") + "#relatorio"}
    assunto = (f"Appfiliado — seus números de {ontem:%d/%m} ainda não saíram na Shopee" if motivo == "nao_saiu"
               else "Appfiliado — não consegui buscar seus resultados na Shopee")
    texto = render_to_string("painel/email_relatorio_aviso.txt", dados)
    mensagem = EmailMultiAlternatives(subject=assunto, body=texto, to=destinatarios,
                                      from_email=settings.APPFILIADO_EMAIL_REMETENTE)
    mensagem.attach_alternative(render_to_string("painel/email_relatorio_aviso.html", dados), "text/html")
    mensagem.send()


def _enviar_agora_pedidos(agora: datetime, hoje: date) -> list[str]:
    """Botão "Enviar e-mail agora": atualiza com a Shopee e manda o relatório (ou o aviso).
    Não conta como o relatório do dia."""
    from .models import RelatorioEmail

    logs = []
    for preferencia in RelatorioEmail.objects.filter(envio_agora_pedido_em__isnull=False).select_related("conta"):
        # Só um processo atende o pedido (num deploy, o worker antigo e o novo rodam juntos).
        if not RelatorioEmail.objects.filter(pk=preferencia.pk, envio_agora_pedido_em__isnull=False).update(
                envio_agora_pedido_em=None):
            continue
        conta = preferencia.conta
        if not conta.shopee_validado_em:
            continue
        try:
            saiu = atualizar_e_conferir(conta, hoje, agora)
            if saiu:
                enviar(conta, hoje, preferencia.destinatarios())
                logs.append(f"Relatório por e-mail (pedido agora) enviado: {conta.email}")
            else:
                enviar_aviso(conta, hoje, preferencia.destinatarios(), agora,
                             "nao_saiu" if saiu is False else "shopee_fora", automatico=False)
                if saiu is False:
                    RelatorioEmail.objects.filter(pk=preferencia.pk).update(aviso_dia=hoje)
                logs.append(f"Relatório por e-mail (pedido agora): aviso enviado para {conta.email}")
        except Exception as erro:  # noqa: BLE001
            logger.exception("Painel: falha no relatório pedido agora da conta %s", conta.pk)
            RelatorioEmail.objects.filter(pk=preferencia.pk).update(ultimo_erro=str(erro)[:500])
            logs.append(f"Relatório por e-mail (pedido agora) falhou: {conta.email} - {erro}")
    return logs


def enviar_pendentes(agora: datetime | None = None) -> list[str]:
    """Chamado pelo worker a cada volta. Devolve uma linha de log por envio."""
    from django.db.models import Q

    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    hoje = local.date()
    logs = _enviar_agora_pedidos(agora, hoje)
    if local.hour < HORA_MAIS_CEDO:
        return logs
    preferencias = (
        RelatorioEmail.objects.filter(ativo=True, conta__shopee_validado_em__isnull=False, hora__lte=local.hour)
        .exclude(ultimo_envio_dia=hoje).select_related("conta")
    )
    for preferencia in preferencias:
        if not pronto_para_enviar(preferencia, agora):
            continue
        if local.hour >= HORA_DE_DESISTIR:
            # Os números de ontem não saíram o dia todo (ou não teve venda): o dia fica sem relatório.
            RelatorioEmail.objects.filter(pk=preferencia.pk).update(ultimo_envio_dia=hoje, proxima_tentativa_em=None)
            logs.append(f"Relatório por e-mail: os números de ontem não saíram hoje para {preferencia.conta.email}")
            continue
        # Uma tentativa por vez - e só um processo tenta (vale quem marcar a próxima primeiro).
        livre = Q(proxima_tentativa_em__isnull=True) | Q(proxima_tentativa_em__lte=agora)
        if not RelatorioEmail.objects.filter(livre, pk=preferencia.pk).exclude(ultimo_envio_dia=hoje).update(
                proxima_tentativa_em=agora + INTERVALO_ENTRE_TENTATIVAS):
            continue
        conta = preferencia.conta
        try:
            saiu = atualizar_e_conferir(conta, hoje, agora)
            if saiu:
                enviar(conta, hoje, preferencia.destinatarios())
                RelatorioEmail.objects.filter(pk=preferencia.pk).update(
                    ultimo_envio_dia=hoje, proxima_tentativa_em=None, ultimo_erro="")
                logs.append(f"Relatório por e-mail enviado: {conta.email}")
            elif saiu is False and preferencia.aviso_dia != hoje:
                enviar_aviso(conta, hoje, preferencia.destinatarios(), agora)
                RelatorioEmail.objects.filter(pk=preferencia.pk).update(aviso_dia=hoje)
                logs.append(f"Relatório por e-mail: números de ontem ainda não saíram, aviso enviado para {conta.email}")
            else:
                logs.append(f"Relatório por e-mail: {conta.email} - "
                            f"{'ainda sem os números de ontem' if saiu is False else 'Shopee não respondeu'}, tento de novo")
        except Exception as erro:  # noqa: BLE001 - tenta de novo na próxima vez
            logger.exception("Painel: falha no relatório por e-mail da conta %s", conta.pk)
            RelatorioEmail.objects.filter(pk=preferencia.pk).update(ultimo_erro=str(erro)[:500])
            logs.append(f"Relatório por e-mail falhou: {conta.email} - {erro}")
    return logs


def aviso_da_tela(conta) -> dict | None:
    """Aviso para o painel: hoje o relatório ainda não foi porque os números de ontem não saíram."""
    from .models import RelatorioEmail

    hoje = timezone.localdate()
    preferencia = RelatorioEmail.objects.filter(conta=conta, aviso_dia=hoje).exclude(ultimo_envio_dia=hoje).first()
    if not preferencia:
        return None
    return {"ontem": hoje - timedelta(days=1), "automatico": preferencia.ativo}
