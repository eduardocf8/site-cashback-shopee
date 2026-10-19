from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado

from . import relatorio
from .models import MetaMensal, RegraSubId, RelatorioEmail, ResultadoDiario, ResultadoSubIdDiario, SincronizacaoResultados
from .tests import SP, BasePainel

HOJE = date(2026, 10, 19)


def as_(hora, minuto=0, dia=HOJE):
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=SP)


class TestRelatorioDiario(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", shopee_app_id="1", shopee_validado_em=timezone.now(), modulos_cortesia="whatsapp",
        )
        self.preferencia = RelatorioEmail.objects.create(conta=self.conta, ativo=True, emails_extras="socio@exemplo.com")
        ontem = HOJE - timedelta(days=1)
        ResultadoDiario.objects.create(conta=self.conta, dia=ontem, pedidos=12, faturamento=Decimal("1500.50"),
                                       comissao_estimada=Decimal("120.30"), comissao_validada=Decimal("40"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 1), pedidos=3, faturamento=Decimal("500"),
                                       comissao_estimada=Decimal("30"))
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=ontem, sub_id="user123", vendas=5, comissao_estimada=Decimal("50"))
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=ontem, sub_id="grupos", vendas=7, comissao_estimada=Decimal("70.30"))
        RegraSubId.objects.create(conta=self.conta, operador="comeca", texto="user", nome="Site")
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=[{"percentual": 100, "faturamento": 5000, "bonus": 100}])
        self.estado = SincronizacaoResultados.objects.create(conta=self.conta, concluida_em=as_(7, 30))

    def test_horario_do_envio(self):
        self.assertFalse(relatorio.pronto_para_enviar(self.preferencia, as_(7, 59)))  # antes das 8h
        self.assertTrue(relatorio.pronto_para_enviar(self.preferencia, as_(8, 5)))  # atualizou hoje às 7h30
        self.estado.concluida_em = as_(23, dia=HOJE - timedelta(days=1))
        self.estado.save()
        self.preferencia.conta.refresh_from_db()
        self.preferencia = RelatorioEmail.objects.select_related("conta__sincronizacao_resultados").get()
        self.assertFalse(relatorio.pronto_para_enviar(self.preferencia, as_(9)))  # ainda sem os números de ontem
        self.assertTrue(relatorio.pronto_para_enviar(self.preferencia, as_(11)))  # 11h: vai assim mesmo

    def test_envia_uma_vez_por_dia_com_os_numeros(self):
        logs = relatorio.enviar_pendentes(as_(8, 10))
        self.assertEqual(len(logs), 1)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["bia@exemplo.com", "socio@exemplo.com"])
        self.assertIn("18/10", email.subject)
        html = email.alternatives[0][0]
        for trecho in ("R$ 120,30", "R$ 1.500,50", ">Pedidos<", "nowrap;\">12<", "Comissão validada", "#1F3A2E;border-radius:10px;", "R$ 2.000,50", "Site", "grupos", "faltam", "R$ 2.999,50",
                       "Bot de WhatsApp", "Nenhuma oferta enviada ontem", "periodo=ontem", "Meta de Outubro/2026", "por dia"):
            self.assertIn(trecho, html)
        self.assertIn("R$ 120,30", email.body)  # versão em texto

        self.assertEqual(relatorio.enviar_pendentes(as_(9)), [])  # já foi hoje
        self.assertEqual(len(mail.outbox), 1)
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.ultimo_envio_dia, HOJE)

    def test_desligado_ou_sem_shopee_nao_envia(self):
        self.preferencia.ativo = False
        self.preferencia.save()
        self.assertEqual(relatorio.enviar_pendentes(as_(9)), [])
        self.assertEqual(len(mail.outbox), 0)

    def test_sem_bot_nao_mostra_o_bloco_do_bot(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        relatorio.enviar_pendentes(as_(9))
        self.assertNotIn("Bot de WhatsApp", mail.outbox[0].alternatives[0][0])


class TestTelaDoRelatorio(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()

    def test_ligar_com_emails_extras_e_enviar_um_agora(self):
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("Relatório diário por e-mail", html)
        resposta = self.client.post("/configuracoes/", {
            "formulario": "relatorio", "ativo": "on", "emails_extras": "Socio@Exemplo.com; outro@exemplo.com",
        })
        self.assertRedirects(resposta, "/configuracoes/#relatorio", fetch_redirect_response=False)
        preferencia = RelatorioEmail.objects.get(conta=self.conta)
        self.assertEqual((preferencia.ativo, preferencia.emails_extras), (True, "socio@exemplo.com, outro@exemplo.com"))

        self.client.post("/configuracoes/", {"formulario": "relatorio", "ativo": "on", "acao": "testar"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bia@exemplo.com"])
        self.assertIsNone(RelatorioEmail.objects.get(conta=self.conta).ultimo_envio_dia)  # teste não conta como o do dia

    def test_emails_extras_invalidos(self):
        resposta = self.client.post("/configuracoes/", {
            "formulario": "relatorio", "ativo": "on", "emails_extras": "a@b.com, c@d.com, e@f.com, g@h.com",
        })
        self.assertContains(resposta, "até 3 e-mails")
        resposta = self.client.post("/configuracoes/", {"formulario": "relatorio", "emails_extras": "isso-nao"})
        self.assertContains(resposta, "E-mail inválido")
