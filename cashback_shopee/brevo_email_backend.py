"""Backend de e-mail que usa a API HTTP do Brevo em vez de SMTP.

O Render bloqueia conexões SMTP de saída (porta 587), então o envio via
django.core.mail.backends.smtp.EmailBackend sempre dá timeout por lá. A API
HTTP do Brevo (https://api.brevo.com) roda sobre HTTPS normal, que funciona
sem problema.
"""

import base64
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

API_URL = "https://api.brevo.com/v3/smtp/email"


def _anexo_para_payload(anexo: tuple) -> dict:
    """anexo é (nome, conteudo, mimetype) - o formato que EmailMessage.attach()
    guarda em message.attachments. conteudo pode ser bytes (caso comum - imagem, PDF)
    ou str (texto puro); a API do Brevo espera o conteúdo em base64 de qualquer jeito."""
    nome, conteudo, _mimetype = anexo
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    return {"name": nome, "content": base64.b64encode(dados).decode("ascii")}


class BrevoAPIEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        enviados = 0
        for message in email_messages:
            if self._enviar(message):
                enviados += 1
        return enviados

    def _enviar(self, message) -> bool:
        nome_remetente, email_remetente = parseaddr(message.from_email)
        payload = {
            "sender": {"email": email_remetente, "name": nome_remetente or None},
            "to": [{"email": destinatario} for destinatario in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        if message.cc:
            payload["cc"] = [{"email": destinatario} for destinatario in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": destinatario} for destinatario in message.bcc]
        if getattr(message, "reply_to", None):
            payload["replyTo"] = {"email": message.reply_to[0]}
        # Sem isso, EmailMessage.attach(...) era silenciosamente ignorado - a API do
        # Brevo nunca via os anexos, então nenhum e-mail com foto (aprovação de
        # story/carrossel, entre outros) chegava com imagem nenhuma, mesmo o corpo do
        # e-mail dizendo "N imagens anexadas" (bug encontrado em 2026-09-04).
        if message.attachments:
            payload["attachment"] = [_anexo_para_payload(anexo) for anexo in message.attachments]

        try:
            resposta = requests.post(
                API_URL,
                json=payload,
                headers={
                    "api-key": settings.BREVO_API_KEY,
                    "content-type": "application/json",
                    "accept": "application/json",
                },
                timeout=settings.EMAIL_TIMEOUT,
            )
            resposta.raise_for_status()
        except requests.RequestException:
            if not self.fail_silently:
                raise
            return False
        return True
