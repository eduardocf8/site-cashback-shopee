"""E-mail da nota para o vendedor (tomador), com o PDF e o XML anexados.

Sai pelo remetente do Appfiliado, com "responder para" o e-mail do afiliado: se o
vendedor responder, a resposta vai direto para quem emitiu a nota."""

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from . import danfse

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def _brl(valor) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def conexao():
    """O serviço de e-mail das notas (NOTAS_EMAIL_PROVEDOR). Se for o mesmo do resto do
    site, usa a conexão padrão do Django."""
    if settings.NOTAS_EMAIL_PROVEDOR != settings.EMAIL_PROVEDOR:
        return get_connection(settings.NOTAS_EMAIL_BACKEND)
    return get_connection()


def montar(nota, connection=None) -> EmailMessage:
    empresa = nota.empresa
    referencia = ""
    if nota.lote_id:
        mes = nota.lote.mes_referencia
        referencia = f" das vendas concluídas em {MESES[mes.month - 1]} de {mes.year}"
    loja = f" ({nota.loja_nome})" if nota.loja_nome else ""
    corpo = (
        f"Olá, {nota.tomador_nome}!\n\n"
        f"Segue a nota fiscal de serviço (NFS-e) da comissão extra paga pela sua loja{loja} no "
        f"Programa de Afiliados da Shopee{referencia}.\n\n"
        f"Prestador: {empresa.razao_social} (CNPJ {empresa.cnpj_formatado})\n"
        f"Número da NFS-e: {nota.numero_nfse or '-'}\n"
        f"Valor: {_brl(nota.valor)}\n"
        f"Chave de acesso: {nota.chave}\n\n"
        "O PDF e o XML da nota estão em anexo. Você também pode consultar a nota em "
        "https://www.nfse.gov.br/consultapublica com a chave de acesso.\n\n"
        "Dúvidas? É só responder este e-mail.\n\n"
        f"Enviado pelo Appfiliado em nome de {empresa.razao_social}.\n"
    )
    mensagem = EmailMessage(
        subject=f"Nota fiscal de serviço nº {nota.numero_nfse or nota.numero} - {empresa.razao_social}",
        body=corpo,
        from_email=settings.NOTAS_EMAIL_REMETENTE or settings.APPFILIADO_EMAIL_REMETENTE,
        to=[nota.tomador_email],
        reply_to=[empresa.conta.email],
        connection=connection,
    )
    mensagem.attach(danfse.nome_arquivo(nota, "pdf"), danfse.pdf(nota.xml_nfse), "application/pdf")
    mensagem.attach(danfse.nome_arquivo(nota, "xml"), nota.xml_nfse.encode("utf-8"), "application/xml")
    return mensagem
