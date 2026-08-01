"""Backend de e-mail que usa a API HTTP do Brevo em vez de SMTP.

O Render bloqueia conexões SMTP de saída (porta 587), então o envio via
django.core.mail.backends.smtp.EmailBackend sempre dá timeout por lá. A API
HTTP do Brevo (https://api.brevo.com) roda sobre HTTPS normal, que funciona
sem problema.
"""

from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

API_URL = "https://api.brevo.com/v3/smtp/email"


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
