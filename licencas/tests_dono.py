"""Painel do dono (licencas/dono.py): valores das assinaturas, números, página no admin e resumo semanal."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from . import dono
from .models import Assinatura, ContaAppfiliado, ProdutoZouti, ResumoSemanalDono
from .services import valor_e_ciclo
from .tests import PRODUTO_BOT, BaseZouti, _assinatura_payload

SP = ZoneInfo("America/Sao_Paulo")
DOMINGO_9H = datetime(2026, 10, 25, 9, 5, tzinfo=SP)


class TestValorDaAssinatura(BaseZouti):
    def test_webhook_guarda_valor_ciclo_e_encerramento(self):
        payload = _assinatura_payload()
        payload["line_items"][0]["amount"] = 4990
        self.enviar("SUBSCRIPTION_ACTIVATED", payload)
        a = Assinatura.objects.get()
        self.assertEqual((a.valor, a.meses_por_ciclo, a.encerrada_em), (Decimal("49.90"), 1, None))

        cancelada = {**payload, "status": "CANCELED", "updated_at": "2026-10-05T10:00:00.000Z"}
        self.enviar("SUBSCRIPTION_CANCELED", cancelada)
        a.refresh_from_db()
        self.assertEqual(timezone.localtime(a.encerrada_em).date().isoformat(), "2026-10-05")

    def test_valor_e_ciclo(self):
        anual = {"plan": {"interval": "YEARLY"}, "line_items": [{"amount": 49900}]}
        self.assertEqual(valor_e_ciclo(anual), (Decimal("499.00"), 12))
        self.assertEqual(valor_e_ciclo({}), (None, None))


def assinar(conta, valor, meses=1, status=Assinatura.STATUS_ATIVA, criada=None, encerrada=None, produto=PRODUTO_BOT):
    a = Assinatura.objects.create(conta=conta, zouti_subscription_id=f"sub{Assinatura.objects.count()}",
                                  zouti_product_ids=produto, status=status, valor=valor, meses_por_ciclo=meses,
                                  encerrada_em=encerrada)
    if criada:
        Assinatura.objects.filter(pk=a.pk).update(criada_em=criada)
    return a


@override_settings(APPFILIADO_EMAIL_SUPORTE="dono@appfiliado.com.br")
class TestNumeros(TestCase):
    def setUp(self):
        ProdutoZouti.objects.create(zouti_product_id=PRODUTO_BOT, nome="Bot Standard", modulos="whatsapp")
        self.ana = ContaAppfiliado.objects.create(email="ana@exemplo.com", ultimo_acesso_em=DOMINGO_9H)
        self.bia = ContaAppfiliado.objects.create(email="bia@exemplo.com")
        ContaAppfiliado.objects.filter(pk=self.bia.pk).update(criada_em=DOMINGO_9H - timedelta(days=40))
        self.bia.refresh_from_db()
        assinar(self.ana, Decimal("49.90"), criada=DOMINGO_9H - timedelta(days=3))  # nova na semana
        assinar(self.bia, Decimal("499.00"), meses=12, criada=DOMINGO_9H - timedelta(days=40))
        assinar(self.bia, Decimal("49.90"), status=Assinatura.STATUS_CANCELADA, criada=DOMINGO_9H - timedelta(days=60),
                encerrada=DOMINGO_9H - timedelta(days=2))

    def test_receita_assinantes_e_produtos(self):
        n = dono.numeros(DOMINGO_9H)
        self.assertEqual(n["receita"], Decimal("49.90") + Decimal("41.58"))  # anual / 12
        self.assertEqual((n["contas"], n["assinaturas"]), (2, 2))
        self.assertEqual(n["por_produto"][0]["produto"], "Bot Standard")
        self.assertEqual((n["por_produto"][0]["mensais"], n["por_produto"][0]["anuais"]), (1, 1))
        self.assertEqual([s["conta"].email for s in n["uso"]["sem_uso"]], ["bia@exemplo.com"])  # nunca entrou
        self.assertEqual(n["evolucao"][-1]["saidas"], 1)

    def test_resumo_semanal_so_no_domingo_depois_das_9h_e_uma_vez(self):
        self.assertEqual(dono.enviar_resumo_semanal(DOMINGO_9H - timedelta(hours=1)), [])  # 8h
        self.assertEqual(dono.enviar_resumo_semanal(DOMINGO_9H - timedelta(days=1)), [])  # sábado
        dono.enviar_resumo_semanal(DOMINGO_9H)
        dono.enviar_resumo_semanal(DOMINGO_9H + timedelta(hours=3))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["dono@appfiliado.com.br"])
        self.assertEqual(email.subject, "Appfiliado: resumo da semana de 18/10 a 24/10")
        self.assertIn("Novas assinaturas na semana: 1", email.body)
        self.assertIn("ana@exemplo.com · Bot Standard · R$ 49,90/mês", email.body)
        self.assertIn("Saídas na semana: 1 (1 cancelada(s)", email.body)
        self.assertIn("Receita recorrente mensal no fim da semana: R$ 91,48 (+R$ 0,00 na semana)", email.body)  # entrou 49,90 e saiu 49,90
        self.assertEqual(ResumoSemanalDono.objects.get().semana.isoformat(), "2026-10-18")

    def test_pagina_no_admin(self):
        usuario = get_user_model().objects.create_superuser("dono", "dono@exemplo.com", "senha-forte-123")
        self.client.force_login(usuario)
        resposta = self.client.get("/admin/licencas/contaappfiliado/painel-do-dono/")
        self.assertContains(resposta, "Receita recorrente mensal")
        self.assertContains(resposta, "Bot Standard")
        self.assertContains(self.client.get("/admin/"), "Painel do dono")
        self.client.logout()
        self.assertEqual(self.client.get("/admin/licencas/contaappfiliado/painel-do-dono/").status_code, 302)
