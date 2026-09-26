# -*- coding: utf-8 -*-
"""
Monta e envia por email o relatorio diario de vendas/comissao por Sub ID.

Usa smtplib/email da biblioteca padrao do Python (sem dependencias extras).
Os dados em si vem de ConversorAfiliados.obter_indicadores_por_sub_id, que
ja existe e ja e usado na aba "Indicadores" do app - aqui so reaproveitamos
esse mesmo resultado para montar o email.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def formatar_moeda(valor):
    try:
        return "R$ {:,.2f}".format(float(valor or 0)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"


MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


NOMES_STATUS_PEDIDO = {
    "COMPLETED": "Concluído",
    "PENDING": "Pendente",
    "UNPAID": "Não pago",
    "CANCELLED": "Cancelado",
    "DESCONHECIDO": "Desconhecido",
}


def montar_resumo_status_html(resumo_status):
    if not resumo_status:
        return (
            '<p style="margin:6px 0 0;color:#999;font-size:12px;">'
            "Sem detalhamento de status de pedidos disponível.</p>"
        )

    partes = []
    for status, quantidade in sorted(resumo_status.items(), key=lambda item: -item[1]):
        label = NOMES_STATUS_PEDIDO.get(status, status.title())
        partes.append(f"{label}: <strong>{quantidade}</strong>")

    return (
        '<p style="margin:6px 0 0;color:#555;font-size:12px;">'
        "Pedidos por status — " + " &nbsp;·&nbsp; ".join(partes) + "</p>"
    )


def montar_tabela_html(titulo, resumo):
    linhas = (resumo or {}).get("linhas") or []
    totais = (resumo or {}).get("totais") or {}
    resumo_status = (resumo or {}).get("resumo_status_pedidos") or {}

    if not linhas:
        corpo_linhas = (
            '<tr><td colspan="3" style="padding:10px;color:#777;">'
            "Nenhuma venda/conversão nesse período.</td></tr>"
        )
    else:
        partes = []
        for linha in linhas:
            partes.append(
                "<tr>"
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{linha.get("sub_id", "sem_subid")}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{int(linha.get("vendas") or 0)}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{formatar_moeda(linha.get("comissao"))}</td>'
                "</tr>"
            )
        corpo_linhas = "".join(partes)

    return f"""
    <h3 style="margin:24px 0 4px;font-family:Arial,sans-serif;color:#222;">{titulo}</h3>
    {montar_resumo_status_html(resumo_status)}
    <table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;margin-top:8px;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:8px 10px;text-align:left;">Sub ID</th>
          <th style="padding:8px 10px;text-align:right;">Vendas</th>
          <th style="padding:8px 10px;text-align:right;">Comissão</th>
        </tr>
      </thead>
      <tbody>{corpo_linhas}</tbody>
      <tfoot>
        <tr style="font-weight:bold;background:#fafafa;">
          <td style="padding:8px 10px;">Total</td>
          <td style="padding:8px 10px;text-align:right;">{int(totais.get("vendas") or 0)}</td>
          <td style="padding:8px 10px;text-align:right;">{formatar_moeda(totais.get("comissao"))}</td>
        </tr>
      </tfoot>
    </table>
    """


def montar_corpo_email(resumo_ontem, resumo_mes, data_referencia, titulo_mes="Mês (até ontem)"):
    tabela_ontem = montar_tabela_html("Ontem", resumo_ontem)
    tabela_mes = montar_tabela_html(titulo_mes, resumo_mes)

    return f"""
    <div style="font-family:Arial,sans-serif;color:#222;max-width:640px;">
      <h2 style="margin:0 0 4px;">Relatório de vendas/comissão — Shopee</h2>
      <p style="margin:0 0 16px;color:#666;">Gerado automaticamente em {data_referencia}</p>
      {tabela_ontem}
      {tabela_mes}
      <p style="margin-top:24px;font-size:12px;color:#999;">
        Relatório enviado automaticamente pelo bot. Os valores de comissão podem
        sofrer pequenos ajustes até serem validados/pagos pela Shopee.
      </p>
    </div>
    """


# Suporte fixo a Gmail apenas (decisao de escopo - ver app.py, aba
# "Relatorio por email"): a grande maioria usa Gmail, e documentar/testar
# outros provedores fica pra depois. Nao expor servidor/porta na tela evita
# alguem digitar um SMTP errado sem perceber por que parou de funcionar.
SMTP_SERVIDOR_GMAIL = "smtp.gmail.com"
SMTP_PORTA_GMAIL = 587


def enviar_email(settings, assunto, corpo_html, destinatarios=None):
    """
    Envia o email de relatorio usando as configuracoes salvas em settings
    (relatorio_email_remetente, relatorio_email_senha_app). Só aceita
    remetente @gmail.com - ver SMTP_SERVIDOR_GMAIL acima.

    Levanta excecao com uma mensagem legivel se algo estiver faltando ou
    o envio falhar - quem chama deve tratar/logar.
    """

    remetente = str(getattr(settings, "relatorio_email_remetente", "") or "").strip()
    senha = str(getattr(settings, "relatorio_email_senha_app", "") or "").strip()

    destinatarios = destinatarios or []
    if not destinatarios and hasattr(settings, "normalized_destinatarios_relatorio"):
        destinatarios = settings.normalized_destinatarios_relatorio()

    if not remetente:
        raise ValueError("Preencha o email remetente (Gmail) nas configurações do relatório.")
    if not remetente.lower().endswith("@gmail.com"):
        raise ValueError("O email remetente precisa ser uma conta @gmail.com - só Gmail é suportado.")
    if not senha:
        raise ValueError("Preencha a senha de app nas configurações do relatório.")
    if not destinatarios:
        raise ValueError("Preencha ao menos um destinatário do relatório.")

    mensagem = MIMEMultipart("alternative")
    mensagem["Subject"] = assunto
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(destinatarios)
    mensagem.attach(MIMEText(corpo_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_SERVIDOR_GMAIL, SMTP_PORTA_GMAIL, timeout=30) as servidor_smtp:
        servidor_smtp.ehlo()
        servidor_smtp.starttls()
        servidor_smtp.ehlo()
        servidor_smtp.login(remetente, senha)
        servidor_smtp.sendmail(remetente, destinatarios, mensagem.as_string())
