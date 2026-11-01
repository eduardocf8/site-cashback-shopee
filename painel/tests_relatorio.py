from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado

from . import relatorio, resultados
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
        # Na hora do envio o app busca as vendas na Shopee: aqui, sem internet.
        atualizar = mock.patch.object(resultados, "processar", return_value="ok")
        self.processar = atualizar.start()
        self.addCleanup(atualizar.stop)

    def test_horario_do_envio(self):
        self.assertFalse(relatorio.pronto_para_enviar(self.preferencia, as_(7, 59)))  # antes das 8h
        self.assertTrue(relatorio.pronto_para_enviar(self.preferencia, as_(8, 5)))
        self.preferencia.hora = 18
        self.assertFalse(relatorio.pronto_para_enviar(self.preferencia, as_(17, 59)))
        self.assertTrue(relatorio.pronto_para_enviar(self.preferencia, as_(18)))
        self.preferencia.save()
        self.assertEqual(relatorio.enviar_pendentes(as_(10)), [])  # ainda não deu 18h
        self.assertEqual(len(relatorio.enviar_pendentes(as_(18, 2))), 1)

    def test_numeros_de_ontem_ainda_nao_sairam(self):
        ResultadoDiario.objects.filter(dia=HOJE - timedelta(days=1)).update(pedidos=0)  # a Shopee ainda não liberou
        logs = relatorio.enviar_pendentes(as_(8, 10))
        self.processar.assert_called_once()  # foi buscar na Shopee na hora
        self.assertIn("aviso enviado", logs[0])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ainda não saíram", mail.outbox[0].subject)
        self.assertIn("a cada 30 minutos", mail.outbox[0].body)
        self.preferencia.refresh_from_db()
        self.assertEqual((self.preferencia.aviso_dia, self.preferencia.ultimo_envio_dia), (HOJE, None))
        self.assertEqual(relatorio.aviso_da_tela(self.conta) is not None, False)  # o aviso da tela é do dia de hoje (real)
        self.assertEqual(relatorio.enviar_pendentes(as_(8, 30)), [])  # espera 30 minutos para tentar de novo
        self.assertEqual(len(relatorio.enviar_pendentes(as_(8, 41))), 1)  # ainda não saiu: sem outro aviso
        self.assertEqual(len(mail.outbox), 1)
        ResultadoDiario.objects.filter(dia=HOJE - timedelta(days=1)).update(pedidos=12)  # saiu
        self.assertIn("guardada", relatorio.enviar_pendentes(as_(9, 12))[0])  # confere de novo em 10 minutos
        self.assertEqual(relatorio.enviar_pendentes(as_(9, 20)), [])
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(9, 22))[0])
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("seus resultados de 18/10", mail.outbox[1].subject)
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.ultimo_envio_dia, HOJE)

    def test_sem_numeros_o_dia_todo_desiste_as_23h(self):
        ResultadoDiario.objects.filter(dia=HOJE - timedelta(days=1)).update(pedidos=0)
        relatorio.enviar_pendentes(as_(8, 10))
        self.assertIn("não saíram hoje", relatorio.enviar_pendentes(as_(23, 5))[0])
        self.assertEqual(len(mail.outbox), 1)  # só o aviso
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.ultimo_envio_dia, HOJE)

    def test_shopee_fora_do_ar_tenta_de_novo_sem_avisar(self):
        def falhou(conta, curta=None):
            SincronizacaoResultados.objects.filter(conta=conta).update(erro="fora", concluida_em=as_(8, 10))
        self.processar.side_effect = falhou
        self.assertIn("Shopee não respondeu", relatorio.enviar_pendentes(as_(8, 10))[0])
        self.assertEqual(len(mail.outbox), 0)
        self.processar.side_effect = None
        SincronizacaoResultados.objects.filter(conta=self.conta).update(erro="")
        self.assertIn("guardada", relatorio.enviar_pendentes(as_(8, 45))[0])
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(8, 55))[0])
        self.assertEqual(len(mail.outbox), 1)

    def test_cada_conferencia_busca_na_shopee_mesmo_com_atualizacao_recente(self):
        SincronizacaoResultados.objects.filter(conta=self.conta).update(concluida_em=as_(7, 49))
        relatorio.enviar_pendentes(as_(7, 50))
        relatorio.enviar_pendentes(as_(8))
        self.assertEqual(self.processar.call_count, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_previa_10_minutos_antes_e_envio_quando_a_comissao_nao_muda(self):
        self.assertEqual(relatorio.enviar_pendentes(as_(7, 49)), [])  # ainda não é hora da prévia
        self.assertIn("prévia guardada", relatorio.enviar_pendentes(as_(7, 50))[0])
        self.processar.assert_called_once_with(self.conta, curta=True)
        self.assertEqual(relatorio.enviar_pendentes(as_(7, 55)), [])  # prévia é uma só
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.previa_comissao, Decimal("120.30"))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(8))[0])  # igual à prévia: vai
        self.assertEqual(self.processar.call_count, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_comissao_mudando_espera_10_minutos_ate_parar(self):
        ontem = HOJE - timedelta(days=1)
        valores = iter(["80", "120.30", "120.30"])  # a Shopee liberou ontem pela metade na hora do envio

        def buscar(conta, curta=None):
            ResultadoDiario.objects.filter(conta=conta, dia=ontem).update(comissao_estimada=Decimal(next(valores)))
        self.processar.side_effect = buscar
        relatorio.enviar_pendentes(as_(7, 50))  # prévia: 80
        self.assertIn("mudou", relatorio.enviar_pendentes(as_(8))[0])  # 120,30: espera
        self.assertEqual(relatorio.enviar_pendentes(as_(8, 5)), [])
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(8, 10))[0])  # 120,30 de novo: vai
        self.assertIn("R$\u00a0120,30", mail.outbox[0].alternatives[0][0])

    def test_comissao_que_nao_para_de_mudar_vai_depois_de_2_horas(self):
        ontem = HOJE - timedelta(days=1)
        valor = [Decimal("100")]

        def buscar(conta, curta=None):
            valor[0] += 1
            ResultadoDiario.objects.filter(conta=conta, dia=ontem).update(comissao_estimada=valor[0])
        self.processar.side_effect = buscar
        relatorio.enviar_pendentes(as_(7, 50))
        minuto = 0
        while not mail.outbox and minuto <= 130:
            logs = relatorio.enviar_pendentes(as_(8) + timedelta(minutes=minuto))
            minuto += 10
        self.assertEqual(minuto, 130)  # 10h00
        self.assertIn("ainda estava mudando", logs[0])

    def test_previa_atrasada_espera_um_pouco_antes_de_conferir(self):
        relatorio.enviar_pendentes(as_(7, 58))  # o worker estava ocupado
        self.assertEqual(relatorio.enviar_pendentes(as_(8)), [])
        self.assertEqual(self.processar.call_count, 1)
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(8, 3))[0])

    def test_previa_das_7h_sai_as_6h50(self):
        self.preferencia.hora = 7
        self.preferencia.save()
        self.assertEqual(relatorio.enviar_pendentes(as_(6, 49)), [])
        self.assertIn("prévia", relatorio.enviar_pendentes(as_(6, 50))[0])
        self.assertIn("enviado", relatorio.enviar_pendentes(as_(7))[0])

    def test_envia_uma_vez_por_dia_com_os_numeros(self):
        relatorio.enviar_pendentes(as_(7, 50))
        logs = relatorio.enviar_pendentes(as_(8, 10))
        self.assertEqual(len(logs), 1)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["bia@exemplo.com", "socio@exemplo.com"])
        self.assertIn("18/10", email.subject)
        html = email.alternatives[0][0]
        for trecho in ("R$ 120,30", "R$ 1.500,50", ">Pedidos<", "nowrap;\">12<", "Comissão validada", "#1F3A2E;border-radius:10px;", "R$ 2.000,50", "Site", "grupos", "faltam", "R$ 2.999,50",
                       "Bot de WhatsApp", "Nenhuma oferta enviada ontem", "periodo=ontem", "Meta de Outubro/2026", "por dia"):
            self.assertIn(trecho.replace("R$ ", "R$\u00a0"), html)  # no HTML, "R$ 1,00" não quebra a linha
        self.assertIn("R$ 120,30", email.body)  # versão em texto
        self.assertIn('src="https://app.appfiliado.com.br/static/painel/email-logo.png"', html)  # o logo de verdade, em PNG

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
        relatorio.enviar_pendentes(as_(7, 50))
        relatorio.enviar_pendentes(as_(9))
        self.assertNotIn("Bot de WhatsApp", mail.outbox[0].alternatives[0][0])


class TestTelaDoRelatorio(BasePainel):
    # Relógio parado às 10h: mais tarde (depois do horário do envio diário escolhido no teste), o envio
    # normal do dia também sai e os testes falhavam.
    AGORA = datetime(2026, 10, 15, 10, 0, tzinfo=SP)

    def setUp(self):
        relogio = mock.patch("django.utils.timezone.now", return_value=self.AGORA)
        relogio.start()
        self.addCleanup(relogio.stop)
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
        self.assertEqual(preferencia.hora, 8)  # sem escolher: o padrão
        self.assertIn('name="hora"', self.client.get("/configuracoes/").content.decode())
        resposta = self.client.post("/configuracoes/", {"formulario": "relatorio", "ativo": "on", "hora": "19"}, follow=True)
        self.assertContains(resposta, "todo dia às 19:00")
        self.assertEqual(RelatorioEmail.objects.get(conta=self.conta).hora, 19)

        resposta = self.client.post("/configuracoes/", {"formulario": "relatorio", "ativo": "on", "acao": "testar"}, follow=True)
        self.assertContains(resposta, "Buscando os números de ontem na Shopee")
        self.assertEqual(len(mail.outbox), 0)  # quem manda é o worker, depois de buscar na Shopee
        self.assertIsNotNone(RelatorioEmail.objects.get(conta=self.conta).envio_agora_pedido_em)
        with mock.patch.object(resultados, "processar", return_value="ok"), \
                mock.patch.object(relatorio, "numeros_de_ontem_sairam", return_value=True):
            relatorio.enviar_pendentes()
            self.assertEqual(relatorio.enviar_pendentes(), [])  # o pedido é atendido uma vez só
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bia@exemplo.com"])
        self.assertIsNone(RelatorioEmail.objects.get(conta=self.conta).ultimo_envio_dia)  # teste não conta como o do dia

    def test_enviar_agora_sem_os_numeros_avisa_e_mostra_no_painel(self):
        RelatorioEmail.objects.create(conta=self.conta, ativo=True, envio_agora_pedido_em=timezone.now())
        SincronizacaoResultados.objects.create(conta=self.conta, concluida_em=timezone.now() - timedelta(hours=1))
        with mock.patch.object(resultados, "processar", return_value="ok"):
            relatorio.enviar_pendentes()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ainda não saíram", mail.outbox[0].subject)
        self.assertIn("Enviar e-mail agora", mail.outbox[0].body)
        self.assertContains(self.client.get("/"), "ainda não saíram na Shopee")
        self.assertContains(self.client.get("/resultados/"), "ainda não saíram na Shopee")

    def test_emails_extras_invalidos(self):
        resposta = self.client.post("/configuracoes/", {
            "formulario": "relatorio", "ativo": "on", "emails_extras": "a@b.com, c@d.com, e@f.com, g@h.com",
        })
        self.assertContains(resposta, "até 3 e-mails")
        resposta = self.client.post("/configuracoes/", {"formulario": "relatorio", "emails_extras": "isso-nao"})
        self.assertContains(resposta, "E-mail inválido")
