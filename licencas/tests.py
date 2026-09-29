import hashlib
import hmac
import json

from django.test import Client, TestCase, override_settings

from .models import EventoWebhookKiwify, Licenca
from .services import aplicar_evento_webhook, interpretar_evento


def _payload_compra_aprovada(subscription_id="sub-123", email="cliente@exemplo.com"):
    """Formato confirmado contra um payload real de teste (ver LICENCA.md) -
    usado como base pra simular o resto do ciclo de vida da assinatura."""
    return {
        "webhook_event_type": "order_approved",
        "order_status": "paid",
        "Customer": {"email": email, "full_name": "Cliente Exemplo"},
        "Subscription": {
            "id": subscription_id,
            "status": "active",
            "plan": {"name": "Mensal"},
            "next_payment": "2026-11-25T00:00:00.000Z",
        },
    }


class TestInterpretarEvento(TestCase):
    """Testa só a lógica de decisão (sem banco) pra cada tipo de evento que a
    Kiwify pode mandar - cobre os casos que LICENCA.md marcava como "ainda
    não confirmados contra um evento real" (cancelamento, reembolso,
    chargeback, recusa, atraso)."""

    def test_compra_aprovada_libera(self):
        resultado = interpretar_evento(_payload_compra_aprovada())
        self.assertEqual(resultado["status"], Licenca.STATUS_ATIVA)
        self.assertEqual(resultado["motivo"], "")
        self.assertEqual(resultado["plano"], "Mensal")

    def test_cancelamento_bloqueia(self):
        payload = _payload_compra_aprovada()
        payload["webhook_event_type"] = "subscription_canceled"
        payload["Subscription"]["status"] = "cancelled"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_CANCELADA)
        self.assertIn("cancelada", resultado["motivo"].lower())

    def test_atraso_de_pagamento_bloqueia(self):
        payload = _payload_compra_aprovada()
        payload["Subscription"]["status"] = "late"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_ATRASADA)

    def test_reembolso_por_webhook_event_type_bloqueia(self):
        payload = _payload_compra_aprovada()
        payload["webhook_event_type"] = "order_refunded"
        payload["order_status"] = "refunded"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_REEMBOLSADA)

    def test_reembolso_por_order_status_bloqueia_mesmo_sem_webhook_event_type(self):
        payload = _payload_compra_aprovada()
        payload["webhook_event_type"] = ""
        payload["order_status"] = "refunded"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_REEMBOLSADA)

    def test_chargeback_bloqueia(self):
        payload = _payload_compra_aprovada()
        payload["webhook_event_type"] = "chargeback"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_CHARGEBACK)

    def test_pagamento_recusado_bloqueia(self):
        payload = _payload_compra_aprovada()
        payload["webhook_event_type"] = "order_refused"
        payload["order_status"] = "refused"
        del payload["Subscription"]
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_RECUSADA)

    def test_status_de_assinatura_desconhecido_bloqueia_por_padrao(self):
        """Se a Kiwify um dia mandar um Subscription.status que a gente ainda
        não mapeou, tem que bloquear (fail-safe) e não liberar "por garantia"."""
        payload = _payload_compra_aprovada()
        payload["Subscription"]["status"] = "paused_por_algum_motivo_novo"
        resultado = interpretar_evento(payload)
        self.assertEqual(resultado["status"], Licenca.STATUS_CANCELADA)
        self.assertIn("não reconhecido", resultado["motivo"])

    def test_evento_sem_nenhum_sinal_reconhecido_bloqueia_por_padrao(self):
        resultado = interpretar_evento({})
        self.assertEqual(resultado["status"], Licenca.STATUS_CANCELADA)
        self.assertIn("não reconhecido", resultado["motivo"])


class TestCicloDeVidaDaAssinatura(TestCase):
    """Testa que o MESMO registro de Licenca é atualizado (não duplicado)
    conforme os eventos chegam pra uma assinatura - e que o e-mail com a
    chave só é enviado uma vez, na criação."""

    def test_cancelamento_apos_compra_atualiza_a_mesma_licenca(self):
        compra = _payload_compra_aprovada(subscription_id="sub-ciclo-de-vida")
        licenca1 = aplicar_evento_webhook(compra)
        self.assertEqual(licenca1.status, Licenca.STATUS_ATIVA)
        self.assertTrue(licenca1.ativa)
        chave_original = licenca1.chave

        cancelamento = _payload_compra_aprovada(subscription_id="sub-ciclo-de-vida")
        cancelamento["webhook_event_type"] = "subscription_canceled"
        cancelamento["Subscription"]["status"] = "cancelled"
        licenca2 = aplicar_evento_webhook(cancelamento)

        self.assertEqual(licenca1.pk, licenca2.pk)
        self.assertEqual(licenca2.chave, chave_original)
        self.assertEqual(licenca2.status, Licenca.STATUS_CANCELADA)
        self.assertFalse(licenca2.ativa)

    def test_reembolso_depois_de_atraso_bloqueia_com_o_motivo_do_reembolso(self):
        """Sinais fortes (reembolso/chargeback) tem prioridade sobre o status
        geral da assinatura, porque podem chegar antes da Kiwify atualizar
        Subscription.status - ver comentário em interpretar_evento."""
        compra = _payload_compra_aprovada(subscription_id="sub-prioridade")
        aplicar_evento_webhook(compra)

        atraso = _payload_compra_aprovada(subscription_id="sub-prioridade")
        atraso["Subscription"]["status"] = "late"
        aplicar_evento_webhook(atraso)

        reembolso = _payload_compra_aprovada(subscription_id="sub-prioridade")
        reembolso["webhook_event_type"] = "order_refunded"
        licenca = aplicar_evento_webhook(reembolso)

        self.assertEqual(licenca.status, Licenca.STATUS_REEMBOLSADA)

    def test_email_so_e_enviado_na_criacao_no_evento_de_cancelamento(self):
        from unittest.mock import patch

        compra = _payload_compra_aprovada(subscription_id="sub-email")
        with patch("licencas.services.enviar_email_licenca") as mock_enviar:
            aplicar_evento_webhook(compra)
            self.assertEqual(mock_enviar.call_count, 1)

            cancelamento = _payload_compra_aprovada(subscription_id="sub-email")
            cancelamento["Subscription"]["status"] = "cancelled"
            aplicar_evento_webhook(cancelamento)
            self.assertEqual(mock_enviar.call_count, 1, "não deveria reenviar e-mail numa atualização")


@override_settings(KIWIFY_WEBHOOK_TOKEN="token-de-teste-123")
class TestWebhookEValidacaoDePontaAPonta(TestCase):
    """Simula exatamente o que a Kiwify e o bot fazem de verdade: POST no
    webhook com assinatura HMAC válida, e depois o bot chamando
    /licencas/validar/ com a chave recebida - confere a cadeia completa."""

    def _assinar(self, corpo_bytes):
        return hmac.new(b"token-de-teste-123", corpo_bytes, hashlib.sha1).hexdigest()

    def _postar_webhook(self, client, payload):
        corpo = json.dumps(payload).encode("utf-8")
        assinatura = self._assinar(corpo)
        return client.post(
            f"/licencas/webhook/kiwify/?signature={assinatura}",
            data=corpo,
            content_type="application/json",
        )

    def test_assinatura_invalida_e_recusada(self):
        client = Client()
        corpo = json.dumps(_payload_compra_aprovada()).encode("utf-8")
        resposta = client.post(
            "/licencas/webhook/kiwify/?signature=assinatura-errada",
            data=corpo,
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 403)
        evento = EventoWebhookKiwify.objects.latest("recebido_em")
        self.assertFalse(evento.assinatura_valida)
        self.assertFalse(evento.processado_com_sucesso)

    def test_fluxo_completo_compra_depois_cancelamento(self):
        client = Client()

        resposta_compra = self._postar_webhook(
            client, _payload_compra_aprovada(subscription_id="sub-e2e", email="e2e@exemplo.com")
        )
        self.assertEqual(resposta_compra.status_code, 200)

        licenca = Licenca.objects.get(kiwify_subscription_id="sub-e2e")
        self.assertEqual(licenca.status, Licenca.STATUS_ATIVA)

        resposta_validar_ok = client.post(
            "/licencas/validar/",
            data=json.dumps({"chave": licenca.chave}),
            content_type="application/json",
        )
        self.assertEqual(resposta_validar_ok.json()["valido"], True)

        cancelamento = _payload_compra_aprovada(subscription_id="sub-e2e", email="e2e@exemplo.com")
        cancelamento["webhook_event_type"] = "subscription_canceled"
        cancelamento["Subscription"]["status"] = "cancelled"
        resposta_cancelamento = self._postar_webhook(client, cancelamento)
        self.assertEqual(resposta_cancelamento.status_code, 200)

        resposta_validar_bloqueado = client.post(
            "/licencas/validar/",
            data=json.dumps({"chave": licenca.chave}),
            content_type="application/json",
        )
        corpo_validar = resposta_validar_bloqueado.json()
        self.assertEqual(corpo_validar["valido"], False)
        self.assertIn("cancelada", corpo_validar["motivo"].lower())

    def test_fluxo_completo_compra_depois_reembolso(self):
        client = Client()
        self._postar_webhook(
            client, _payload_compra_aprovada(subscription_id="sub-reembolso-e2e")
        )
        licenca = Licenca.objects.get(kiwify_subscription_id="sub-reembolso-e2e")

        reembolso = _payload_compra_aprovada(subscription_id="sub-reembolso-e2e")
        reembolso["webhook_event_type"] = "order_refunded"
        self._postar_webhook(client, reembolso)

        resposta = client.post(
            "/licencas/validar/",
            data=json.dumps({"chave": licenca.chave}),
            content_type="application/json",
        )
        corpo = resposta.json()
        self.assertEqual(corpo["valido"], False)
        self.assertIn("reembolsada", corpo["motivo"].lower())

    def test_fluxo_completo_compra_depois_chargeback(self):
        client = Client()
        self._postar_webhook(
            client, _payload_compra_aprovada(subscription_id="sub-chargeback-e2e")
        )
        licenca = Licenca.objects.get(kiwify_subscription_id="sub-chargeback-e2e")

        chargeback = _payload_compra_aprovada(subscription_id="sub-chargeback-e2e")
        chargeback["webhook_event_type"] = "chargeback"
        self._postar_webhook(client, chargeback)

        resposta = client.post(
            "/licencas/validar/",
            data=json.dumps({"chave": licenca.chave}),
            content_type="application/json",
        )
        corpo = resposta.json()
        self.assertEqual(corpo["valido"], False)
        self.assertIn("chargeback", corpo["motivo"].lower())

    def test_fluxo_completo_compra_depois_atraso_de_pagamento(self):
        client = Client()
        self._postar_webhook(
            client, _payload_compra_aprovada(subscription_id="sub-atraso-e2e")
        )
        licenca = Licenca.objects.get(kiwify_subscription_id="sub-atraso-e2e")

        atraso = _payload_compra_aprovada(subscription_id="sub-atraso-e2e")
        atraso["Subscription"]["status"] = "late"
        self._postar_webhook(client, atraso)

        resposta = client.post(
            "/licencas/validar/",
            data=json.dumps({"chave": licenca.chave}),
            content_type="application/json",
        )
        corpo = resposta.json()
        self.assertEqual(corpo["valido"], False)
        self.assertIn("atrasado", corpo["motivo"].lower())
