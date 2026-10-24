"""Backend de e-mail pelo Amazon SES (API v2, por HTTPS).

Por que não SMTP: o Render bloqueia SMTP de saída (ver brevo_email_backend.py).
Por que não boto3: é uma chamada só (SendEmail com a mensagem pronta, anexos inclusos);
assinar a requisição (AWS Signature V4) são poucas linhas e o worker tem limite de memória.

Configuração (variáveis de ambiente, ver settings.py): AWS_SES_REGIAO,
AWS_SES_ACCESS_KEY_ID, AWS_SES_SECRET_ACCESS_KEY e, opcional, AWS_SES_CONFIGURATION_SET.
O usuário da AWS só precisa da permissão ses:SendEmail (e ses:SendRawEmail)."""

import base64
import datetime
import hashlib
import hmac
import json
import logging
from urllib.parse import quote, urlsplit

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class LimiteDeEnvio(Exception):
    """O serviço de e-mail pediu para ir mais devagar (cota por segundo ou por dia).
    Quem chama deve parar e tentar de novo mais tarde, sem marcar o e-mail como falho."""


def _hmac(chave: bytes, texto: str) -> bytes:
    return hmac.new(chave, texto.encode("utf-8"), hashlib.sha256).digest()


def assinar_v4(metodo: str, url: str, cabecalhos: dict, corpo: bytes, *, regiao: str, servico: str,
               access_key: str, secret_key: str, agora: datetime.datetime | None = None) -> dict:
    """Devolve os cabeçalhos com a assinatura AWS Signature Version 4."""
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    amz_data, dia = agora.strftime("%Y%m%dT%H%M%SZ"), agora.strftime("%Y%m%d")
    partes = urlsplit(url)
    cabecalhos = {**cabecalhos, "host": partes.netloc, "x-amz-date": amz_data}
    normalizados = {k.lower().strip(): " ".join(str(v).split()) for k, v in cabecalhos.items()}
    nomes = sorted(normalizados)
    consulta = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
        for k, v in sorted(p.split("=", 1) if "=" in p else (p, "") for p in partes.query.split("&") if p)
    )
    pedido_canonico = "\n".join([
        metodo, quote(partes.path or "/", safe="/-_.~"), consulta,
        "".join(f"{n}:{normalizados[n]}\n" for n in nomes), ";".join(nomes),
        hashlib.sha256(corpo).hexdigest(),
    ])
    escopo = f"{dia}/{regiao}/{servico}/aws4_request"
    texto = "\n".join(["AWS4-HMAC-SHA256", amz_data, escopo, hashlib.sha256(pedido_canonico.encode()).hexdigest()])
    chave = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret_key).encode(), dia), regiao), servico), "aws4_request")
    assinatura = hmac.new(chave, texto.encode(), hashlib.sha256).hexdigest()
    cabecalhos["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{escopo}, "
                                   f"SignedHeaders={';'.join(nomes)}, Signature={assinatura}")
    return cabecalhos


class SESEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.regiao = settings.AWS_SES_REGIAO
        self.url = f"https://email.{self.regiao}.amazonaws.com/v2/email/outbound-emails"
        self.sessao = requests.Session()

    def send_messages(self, email_messages):
        return sum(1 for mensagem in email_messages or [] if self._enviar(mensagem))

    def _enviar(self, message) -> bool:
        destinos = {"ToAddresses": list(message.to)}
        if message.cc:
            destinos["CcAddresses"] = list(message.cc)
        if message.bcc:
            destinos["BccAddresses"] = list(message.bcc)
        pedido = {
            "FromEmailAddress": message.from_email,
            "Destination": destinos,
            # A mensagem MIME pronta do Django (com anexos, reply-to e versão HTML).
            "Content": {"Raw": {"Data": base64.b64encode(message.message().as_bytes(linesep="\r\n")).decode()}},
        }
        if getattr(message, "reply_to", None):
            pedido["ReplyToAddresses"] = list(message.reply_to)
        if settings.AWS_SES_CONFIGURATION_SET:
            pedido["ConfigurationSetName"] = settings.AWS_SES_CONFIGURATION_SET
        corpo = json.dumps(pedido).encode()
        cabecalhos = assinar_v4("POST", self.url, {"content-type": "application/json"}, corpo,
                                regiao=self.regiao, servico="ses", access_key=settings.AWS_SES_ACCESS_KEY_ID,
                                secret_key=settings.AWS_SES_SECRET_ACCESS_KEY)
        try:
            resposta = self.sessao.post(self.url, data=corpo, headers=cabecalhos, timeout=settings.EMAIL_TIMEOUT)
        except requests.RequestException:
            if not self.fail_silently:
                raise
            return False
        if resposta.status_code == 200:
            return True
        detalhe = resposta.text[:500]
        if resposta.status_code == 429 or "Throttl" in detalhe or "LimitExceeded" in detalhe or "SendingPaused" in detalhe:
            raise LimiteDeEnvio(f"Amazon SES: limite de envio atingido ({resposta.status_code}).")
        if not self.fail_silently:
            raise requests.HTTPError(f"Amazon SES recusou o e-mail ({resposta.status_code}): {detalhe}", response=resposta)
        return False
