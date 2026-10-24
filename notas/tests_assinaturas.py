"""Notas fiscais das assinaturas do Appfiliado (Zouti -> NFS-e): notas/assinaturas.py."""
import copy
import datetime as dt
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from licencas.models import Assinatura
from licencas.services import processar_evento

from . import assinaturas, certificado, dps, servicos
from . import email as email_notas
from .models import AMBIENTE_PRODUCAO, NotaFiscal
from .sefin import Resposta
from .tests import ClienteFalso, autorizada, criar_conta, criar_empresa, gerar_pfx, xml_nfse

# Como chega da Zouti (o evento de assinatura ativada, com dados fictícios).
ATIVADA = {
    "id": "sub_teste123", "order_id": "ord_teste123", "status": "ACTIVE",
    "customer": {"id": "cus_1", "name": "Carla Souza", "email": "Carla@Exemplo.com", "document": "123.456.789-09",
                 "phone": "5511999990000"},
    "plan": {"id": "plan_1", "name": "teste", "amount": 4990, "currency": "BRL", "interval": "MONTHLY"},
    "payment_method": "PIX", "current_period_start": "2026-10-21T02:09:59.120Z",
    "current_period_end": "2026-11-21T03:00:00.000Z", "next_payment_date": "2026-11-21T03:00:00.000Z",
    "line_items": [{"name": "Bot de WhatsApp Standard", "amount": 4990, "product_id": "prod_bot"}],
    "billing_cycle_count": 1, "created_at": "2026-10-21T02:09:59.123Z", "updated_at": "2026-10-21T02:10:31.932Z",
}


def evento(**mudancas):
    payload = copy.deepcopy(ATIVADA)
    payload.update(mudancas)
    return payload


class BaseAssinaturas(TestCase):
    def setUp(self):
        cache.clear()
        self.conta = criar_conta(email="dono@appfiliado.com.br", modulos="notas_ilimitado")
        self.empresa = criar_empresa(self.conta, regime="simples")
        certificado.guardar(self.empresa, gerar_pfx(), "senha-do-pfx")
        ajuste = override_settings(NOTAS_ASSINATURAS_CONTA_ID=self.conta.pk, NOTAS_ASSINATURAS_AMBIENTE="1")
        ajuste.enable()
        self.addCleanup(ajuste.disable)


class TestRegistro(BaseAssinaturas):
    def test_pagamento_confirmado_vira_nota_na_fila_com_o_servico_das_assinaturas(self):
        resumo = assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        self.assertIn("na fila", resumo)
        nota = NotaFiscal.objects.get()
        self.assertEqual((nota.tipo, nota.situacao, nota.ambiente), (NotaFiscal.TIPO_ASSINATURA, NotaFiscal.FILA, AMBIENTE_PRODUCAO))
        self.assertEqual((nota.tomador_tipo, nota.tomador_documento, nota.tomador_nome, nota.tomador_email),
                         ("cpf", "12345678909", "Carla Souza", "carla@exemplo.com"))
        self.assertEqual(nota.valor, Decimal("49.90"))
        self.assertEqual((nota.servico_codigo, nota.servico_nbs), ("010501", "111032200"))
        self.assertEqual(nota.servico_descricao, "Assinatura Appfiliado - Bot de WhatsApp Standard (ref. 10/2026)")
        self.assertEqual(nota.email_situacao, NotaFiscal.EMAIL_PENDENTE)
        self.assertEqual(nota.referencia, "zouti:sub_teste123:2026-10-21")

    def test_mesmo_periodo_nao_duplica_e_renovacao_gera_outra(self):
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        self.assertIn("já registrada", assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento()))
        assinaturas.registrar_pagamento("SUBSCRIPTION_RENEWED", evento(current_period_start="2026-11-21T03:00:00.000Z",
                                                                      billing_cycle_count=2))
        self.assertEqual(NotaFiscal.objects.count(), 2)

    def test_sem_pagamento_ou_sem_dados_nao_emite(self):
        self.assertEqual(assinaturas.registrar_pagamento("SUBSCRIPTION_CREATED", evento(status="INCOMPLETE")), "")
        self.assertIn("status", assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento(status="INCOMPLETE")))
        sem_doc = evento(customer={**ATIVADA["customer"], "document": ""})
        self.assertIn("CPF/CNPJ", assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", sem_doc))
        self.assertFalse(NotaFiscal.objects.exists())
        with override_settings(NOTAS_ASSINATURAS_CONTA_ID=0):
            self.assertEqual(assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento()), "")

    def test_ambiente_de_testes_nao_manda_email_pro_cliente(self):
        with override_settings(NOTAS_ASSINATURAS_AMBIENTE="2"):
            assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        self.assertEqual(NotaFiscal.objects.get().email_situacao, NotaFiscal.EMAIL_NAO)

    def test_webhook_libera_a_assinatura_e_poe_a_nota_na_fila(self):
        resultado = processar_evento("SUBSCRIPTION_ACTIVATED", "Subscription", evento())
        self.assertTrue(Assinatura.objects.filter(zouti_subscription_id="sub_teste123").exists())
        self.assertTrue(resultado.startswith("Nota: na fila"))
        self.assertEqual(NotaFiscal.objects.count(), 1)

    def test_nao_ocupa_o_plano_de_notas(self):
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        self.assertEqual(servicos.uso_do_plano(self.empresa)["usadas"], 0)


class TestEmissao(BaseAssinaturas):
    def test_dps_sai_com_o_servico_proprio_e_consumidor_final(self):
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        nota = NotaFiscal.objects.get()
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso), \
                mock.patch.object(servicos, "campos_novos", return_value=frozenset({"IBSCBS", "IBSCBS.indFinal"})):
            servicos.processar(nota)
        xml = falso.emitidas[0].decode()
        self.assertIn("<cTribNac>010501</cTribNac>", xml)
        self.assertIn("Assinatura Appfiliado - Bot de WhatsApp Standard", xml)
        self.assertIn("<cNBS>111032200</cNBS>", xml)
        # Com IBS/CBS o endereço do tomador é obrigatório e a Zouti não manda: pessoa física vai como
        # tomador não identificado (consumidor final), e o e-mail continua indo pra ela.
        self.assertNotIn("<toma>", xml)
        self.assertIn("<indFinal>1</indFinal>", xml)
        nota = NotaFiscal.objects.get()
        self.assertEqual((nota.situacao, nota.tomador_email), (NotaFiscal.AUTORIZADA, "carla@exemplo.com"))

    def test_sem_ibscbs_o_cliente_vai_identificado(self):
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        falso = ClienteFalso(emitir=autorizada())
        with mock.patch.object(servicos, "ClienteSefin", falso), mock.patch.object(servicos, "campos_novos", return_value=frozenset()):
            servicos.processar(NotaFiscal.objects.get())
        xml = falso.emitidas[0].decode()
        self.assertIn("<toma><CPF>12345678909</CPF><xNome>Carla Souza</xNome><email>carla@exemplo.com</email></toma>", xml)

    def test_cliente_empresa_vai_identificado_com_o_endereco_da_receita(self):
        cnpj = evento(customer={**ATIVADA["customer"], "document": "11.222.333/0001-81", "name": "Loja da Carla Ltda"})
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", cnpj)
        falso = ClienteFalso(emitir=autorizada())
        endereco = {"municipio_ibge": "3550308", "cep": "01001000", "logradouro": "Praça da Sé", "numero": "1", "bairro": "Sé"}
        with mock.patch.object(servicos, "ClienteSefin", falso), \
                mock.patch.object(servicos, "campos_novos", return_value=frozenset({"IBSCBS", "IBSCBS.indFinal"})), \
                mock.patch.object(servicos, "_endereco_da_receita", return_value=endereco):
            servicos.processar(NotaFiscal.objects.get())
        xml = falso.emitidas[0].decode()
        self.assertIn("<CNPJ>11222333000181</CNPJ>", xml)
        self.assertIn("<CEP>01001000</CEP>", xml)
        self.assertIn("<indFinal>0</indFinal>", xml)

    def test_email_proprio_pro_cliente(self):
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        nota = NotaFiscal.objects.get()
        nota.situacao, nota.numero_nfse, nota.xml_nfse, nota.chave = NotaFiscal.AUTORIZADA, "42", xml_nfse(), "C" * 50
        with mock.patch.object(email_notas.danfse, "pdf", return_value=b"%PDF"):
            mensagem = email_notas.montar(nota)
        self.assertIn("assinatura do Appfiliado", mensagem.subject)
        self.assertIn("pagamento da sua assinatura", mensagem.body)
        self.assertNotIn("comissão extra", mensagem.body)
        self.assertEqual(mensagem.to, ["carla@exemplo.com"])


class TestRecusaDoGoverno(BaseAssinaturas):
    def test_recusa_por_endereco_mostra_o_motivo_do_governo(self):
        """Sem endereço não há outro a tentar: a nota guarda a mensagem do governo, e não a nossa."""
        assinaturas.registrar_pagamento("SUBSCRIPTION_ACTIVATED", evento())
        recusa = Resposta(400, {"erros": [{"codigo": "E0239", "descricao": "Endereço do tomador obrigatório"}]})
        with mock.patch.object(servicos, "ClienteSefin", ClienteFalso(emitir=recusa)), \
                mock.patch.object(servicos, "campos_novos", return_value=frozenset({"IBSCBS"})):
            servicos.processar(NotaFiscal.objects.get())
        nota = NotaFiscal.objects.get()
        self.assertEqual(nota.situacao, NotaFiscal.RECUSADA)
        self.assertEqual(nota.mensagens[0]["codigo"], "E0239")


class TestEstorno(BaseAssinaturas):
    def setUp(self):
        super().setUp()
        processar_evento("SUBSCRIPTION_ACTIVATED", "Subscription", evento())

    def test_nota_que_nao_saiu_sai_da_fila(self):
        resultado = processar_evento("PAYMENT_REFUNDED", "Payment",
                                     {"status": "REFUNDED", "subscription_id": "sub_teste123", "order_id": "ord_teste123"})
        self.assertIn("tirada da fila", resultado)
        self.assertFalse(NotaFiscal.objects.exists())

    def test_nota_autorizada_e_cancelada(self):
        NotaFiscal.objects.update(situacao=NotaFiscal.AUTORIZADA, chave="C" * 50, numero_nfse="42")
        with mock.patch.object(servicos, "cancelar") as cancelar:
            resultado = processar_evento("ORDER_DISPUTED", "Order", {"id": "ord_teste123", "status": "DISPUTED"})
        cancelar.assert_called_once()
        self.assertEqual(cancelar.call_args.args[1], "2")
        self.assertIn("cancelada", resultado)

    def test_falha_no_cancelamento_nao_quebra_o_webhook(self):
        NotaFiscal.objects.update(situacao=NotaFiscal.AUTORIZADA, chave="C" * 50)
        with mock.patch.object(servicos, "cancelar", side_effect=servicos.ErroNotas("prazo encerrado")):
            resultado = processar_evento("PAYMENT_REFUNDED", "Payment", {"status": "REFUNDED", "subscription_id": "sub_teste123"})
        self.assertIn("cancelar à mão", resultado)
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_REEMBOLSADA)
