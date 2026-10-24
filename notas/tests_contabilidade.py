"""Envio mensal das notas pra contabilidade (notas/contabilidade.py e a tela do Emissor)."""
import datetime as dt
import io
import zipfile
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import contabilidade, receita
from .models import AMBIENTE_PRODUCAO, AMBIENTE_TESTE, NotaFiscal
from .tests import CNPJ, HOST, SENHA, criar_conta, criar_empresa, xml_nfse


def nota(empresa, competencia, situacao=NotaFiscal.AUTORIZADA, ambiente=AMBIENTE_PRODUCAO, numero=1, valor="10.00"):
    return NotaFiscal.objects.create(
        empresa=empresa, ambiente=ambiente, tipo=NotaFiscal.TIPO_VENDEDOR, competencia=competencia, situacao=situacao,
        tomador_tipo="cnpj", tomador_documento="11222333000181", tomador_nome="LOJA X LTDA", valor=valor,
        serie="1", numero=numero, numero_nfse=str(numero), chave=f"C{numero}".ljust(50, "0"), xml_nfse=xml_nfse(str(numero)),
        cancelada_em=timezone.now() if situacao == NotaFiscal.CANCELADA else None,
        xml_cancelamento="<evento/>" if situacao == NotaFiscal.CANCELADA else "")


class TestContabilidade(TestCase):
    def setUp(self):
        self.conta = criar_conta(email="dono@empresa.com")
        self.empresa = criar_empresa(self.conta, contabilidade_email="fiscal@contabil.com")
        nota(self.empresa, dt.date(2026, 9, 3), numero=1, valor="100.00")
        nota(self.empresa, dt.date(2026, 9, 20), situacao=NotaFiscal.CANCELADA, numero=2, valor="50.00")
        nota(self.empresa, dt.date(2026, 10, 1), numero=3)  # outro mês
        nota(self.empresa, dt.date(2026, 9, 5), ambiente=AMBIENTE_TESTE, numero=1)  # teste: fica de fora
        nota(self.empresa, dt.date(2026, 9, 6), situacao=NotaFiscal.RECUSADA, numero=4)  # recusada: fica de fora

    def test_zip_com_xmls_cancelamentos_e_planilha_do_mes(self):
        conteudo, totais = contabilidade.montar_zip(self.empresa, dt.date(2026, 9, 1))
        self.assertEqual((totais["notas"], totais["canceladas"], str(totais["valor"])), (2, 1, "100.00"))
        nomes = zipfile.ZipFile(io.BytesIO(conteudo)).namelist()
        self.assertEqual(len([n for n in nomes if n.startswith("xml/")]), 2)
        self.assertEqual(len([n for n in nomes if n.startswith("cancelamentos/")]), 1)
        self.assertIn("resumo.csv", nomes)

    def test_dia_1_manda_o_mes_anterior_uma_vez_so(self):
        enviados = contabilidade.enviar_mes_anterior(dt.date(2026, 10, 1))
        self.assertEqual(enviados, 1)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual((email.to, email.cc), (["fiscal@contabil.com"], ["dono@empresa.com"]))
        self.assertIn("setembro de 2026", email.subject)
        self.assertIn("Notas: 2 (das quais 1 cancelada)", email.body)
        self.assertTrue(email.attachments[0][0].endswith("2026-09.zip"))
        self.assertEqual(contabilidade.enviar_mes_anterior(dt.date(2026, 10, 2)), 0)  # já foi
        self.assertEqual(len(mail.outbox), 1)

    def test_espera_as_notas_do_mes_sairem_da_fila(self):
        nota(self.empresa, dt.date(2026, 9, 30), situacao=NotaFiscal.FILA, numero=9)
        self.assertEqual(contabilidade.enviar_mes_anterior(dt.date(2026, 10, 1)), 0)
        NotaFiscal.objects.filter(numero=9).update(situacao=NotaFiscal.AUTORIZADA)
        self.assertEqual(contabilidade.enviar_mes_anterior(dt.date(2026, 10, 1)), 1)

    def test_sem_email_nao_manda(self):
        self.empresa.contabilidade_email = ""
        self.empresa.save()
        self.assertEqual(contabilidade.enviar_mes_anterior(dt.date(2026, 10, 1)), 0)


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestTelaContabilidade(TestCase):
    def setUp(self):
        cache.clear()
        receita_falsa = mock.patch.object(receita, "consultar", return_value={"regime": "mei"})
        receita_falsa.start()
        self.addCleanup(receita_falsa.stop)
        self.conta = criar_conta()
        self.empresa = criar_empresa(self.conta)
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})

    def test_salva_o_email_e_manda_na_hora(self):
        self.assertContains(self.client.get("/notas/"), "Notas pra contabilidade")
        self.client.post("/notas/", {"acao": "contabilidade", "email": "Fiscal@Contabil.com"})
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.contabilidade_email, "fiscal@contabil.com")
        # O automático começa no próximo mês: o que já passou não sai sozinho.
        self.assertEqual(self.empresa.contabilidade_enviado_mes, contabilidade.mes_anterior())
        mes = contabilidade.mes_anterior()
        resposta = self.client.post("/notas/", {"acao": "contabilidade_enviar", "mes": f"{mes:%Y-%m}"}, follow=True)
        self.assertContains(resposta, "Enviado pra fiscal@contabil.com")
        self.assertEqual(mail.outbox[0].to, ["fiscal@contabil.com"])

    def test_mes_fora_da_lista_e_recusado(self):
        self.client.post("/notas/", {"acao": "contabilidade", "email": "fiscal@contabil.com"})
        resposta = self.client.post("/notas/", {"acao": "contabilidade_enviar", "mes": "2019-01"}, follow=True)
        self.assertContains(resposta, "Escolha um mês da lista")
        self.assertEqual(len(mail.outbox), 0)
