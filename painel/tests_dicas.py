"""Sequência de e-mails de dicas dos novos assinantes (painel/emails_valor.py)."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core import mail
from django.test import TestCase, override_settings

from licencas.models import Assinatura, ContaAppfiliado, ProdutoZouti

from . import emails_valor
from .models import EmailValorEnviado, ResultadoDiario
from .tests import HOST

SP = ZoneInfo("America/Sao_Paulo")
COMPRA = datetime(2026, 11, 2, 15, 0, tzinfo=SP)


def dia(n, hora=10, minuto=5):
    return (COMPRA + timedelta(days=n)).replace(hour=hora, minute=minuto)


@override_settings(APPFILIADO_EMAIL_SUPORTE="contato@appfiliado.com.br",
                   APPFILIADO_EMAIL_REMETENTE="Appfiliado <contato@appfiliado.com.br>",
                   APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"],
                   APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestDicas(TestCase):
    def setUp(self):
        ProdutoZouti.objects.create(zouti_product_id="bot", nome="Bot", modulos="whatsapp")
        self.conta = ContaAppfiliado.objects.create(email="ana@exemplo.com", nome="Ana Lima")
        a = Assinatura.objects.create(conta=self.conta, zouti_subscription_id="sub1", zouti_product_ids="bot",
                                      status=Assinatura.STATUS_ATIVA)
        Assinatura.objects.filter(pk=a.pk).update(criada_em=COMPRA)

    def rodar(self, quando):
        return emails_valor.enviar_pendentes(quando)

    def test_sequencia_nos_dias_e_horario_certos(self):
        self.rodar(dia(2, 9, 30))
        self.assertEqual(len(mail.outbox), 0)  # antes das 10h
        self.rodar(dia(2))
        self.assertEqual(len(mail.outbox), 0)  # a história ainda espera o texto do Eduardo
        self.rodar(dia(4))
        self.rodar(dia(4, 15))
        self.assertEqual([m.subject for m in mail.outbox], ["O grupo que vende todo dia não é sorte"])
        email = mail.outbox[0]
        self.assertEqual(email.from_email, '"Eduardo, do Appfiliado" <contato@appfiliado.com.br>')
        self.assertEqual(email.reply_to, ["contato@appfiliado.com.br"])
        self.assertIn("List-Unsubscribe", email.extra_headers)
        html = email.alternatives[0][0]
        self.assertIn("Fala, Ana!", html)
        self.assertIn("bot-ofertas.jpg", html)  # tem o Bot: dicas do Bot
        self.assertIn("No Premium, cada grupo pode receber as ofertas do seu nicho", html)
        self.assertIn("Fala, Ana!", email.body)
        self.assertIn("Não quer mais receber estas dicas?", email.body)

        for n, assunto in [(6, "Você sabe qual grupo te dá mais comissão?"),
                           (8, "Onde achar o produto que vende antes de todo mundo"),
                           (10, "Datas duplas e Black Friday no piloto automático"),
                           (12, "Seu link na bio e seu Instagram trabalhando junto")]:
            self.rodar(dia(n))
            self.assertEqual(mail.outbox[-1].subject, assunto)
        self.assertIn("Meu site", mail.outbox[-1].alternatives[0][0])  # não tem site nem carrosséis: apresenta

        ResultadoDiario.objects.create(conta=self.conta, dia=dia(20).date(), pedidos=12, faturamento=Decimal("900"),
                                       comissao_estimada=Decimal("87.40"), comissao_validada=0)
        self.rodar(dia(21))
        self.assertEqual(mail.outbox[-1].subject, "Como estão indo as suas vendas?")
        self.assertIn("R$ 87,40 de comissão estimada", mail.outbox[-1].alternatives[0][0])
        self.rodar(dia(30))
        self.assertEqual(len(mail.outbox), 6)

    def test_servidor_fora_manda_no_dia_seguinte_e_depois_pula(self):
        self.rodar(dia(5))  # o do dia 4 sai no dia 5
        self.assertEqual(mail.outbox[-1].subject, "O grupo que vende todo dia não é sorte")
        self.rodar(dia(9))  # os dos dias 6 e... o 6 passou: pula; o 8 sai no dia 9
        self.assertEqual(mail.outbox[-1].subject, "Onde achar o produto que vende antes de todo mundo")
        self.assertTrue(EmailValorEnviado.objects.get(conta=self.conta, chave="resultados").pulado)

    def test_para_com_o_link_e_quando_cancela(self):
        resposta = self.client.get(emails_valor.link_para_parar(self.conta).split(HOST, 1)[1], HTTP_HOST=HOST)
        self.assertContains(resposta, "você não vai mais receber as dicas")
        self.rodar(dia(4))
        self.assertEqual(len(mail.outbox), 0)

        self.conta.sem_dicas_por_email = False
        self.conta.save()
        Assinatura.objects.update(status=Assinatura.STATUS_REEMBOLSADA)
        self.rodar(dia(4))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.client.get("/emails/parar-dicas/token-falso/", HTTP_HOST=HOST).status_code, 404)

    def test_quem_nao_tem_o_bot_recebe_o_conversor(self):
        ProdutoZouti.objects.filter(zouti_product_id="bot").update(modulos="site")
        self.rodar(dia(4))
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("conversor.jpg", html)
        self.assertIn("Conhecer o Bot", html)
