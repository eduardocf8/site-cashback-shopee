"""Alerta de preço: regra da queda, conferência no worker, e-mail e postagem nos grupos."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import cripto

from . import alertas, shopee_ofertas
from .models import AlertaDisparado, AlertaPreco, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, ProdutoAcompanhado
from .tests_ofertas import GRUPOS, SP, link_falso, produto

AGORA = datetime(2026, 10, 21, 10, 0, tzinfo=SP)


def criar_conta(modulos="whatsapp_premium"):
    return ContaAppfiliado.objects.create(
        email="bia@exemplo.com", modulos_cortesia=modulos, shopee_app_id="123",
        shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
    )


class TestRegraDaQueda(TestCase):
    def setUp(self):
        self.conta = criar_conta()
        self.produto, _ = alertas.adicionar(self.conta, produto(1, preco=100.0))

    def preco(self, valor, queda_minima=10):
        return alertas.registrar_preco(self.produto, Decimal(str(valor)), AGORA, queda_minima)

    def test_avisa_so_quando_chega_na_queda_minima_e_nao_repete(self):
        self.assertIsNone(self.preco(95))  # caiu 5%: ainda não
        alerta = self.preco(89.9)  # 10,1% abaixo dos 100
        self.assertEqual((alerta.preco_antes, alerta.preco_agora, alerta.queda), (Decimal("100.00"), Decimal("89.90"), Decimal("10.1")))
        self.assertIsNone(self.preco(85))  # só 5% abaixo do último alerta
        self.assertIsNotNone(self.preco(80))  # 11% abaixo dos 89,90

    def test_preco_que_sobe_vira_a_nova_referencia(self):
        self.preco(120)
        self.assertEqual(self.produto.referencia, Decimal("120.00"))
        self.assertIsNotNone(self.preco(105))  # 12,5% abaixo do pico (mas acima dos 100 iniciais)

    def test_historico_e_menor_preco(self):
        self.preco(95)
        self.preco(95)
        self.preco(99)
        self.assertEqual([p for _, p in self.produto.historico], [100.0, 95.0, 99.0])  # só as mudanças
        self.assertEqual(self.produto.menor_preco, Decimal("95.00"))
        self.assertEqual(self.produto.variacao, -1.0)

    def test_limite_do_plano(self):
        conta = ContaAppfiliado.objects.create(email="std@x.com", modulos_cortesia="whatsapp")
        for i in range(10):
            alertas.adicionar(conta, produto(100 + i))
        with self.assertRaisesMessage(alertas.LimiteDoPlano, "até 10 produtos"):
            alertas.adicionar(conta, produto(999))
        self.assertFalse(alertas.adicionar(conta, produto(100))[1])  # o mesmo produto não conta de novo

    def test_mensagem_com_os_campos(self):
        texto = alertas.montar_mensagem("{produto}: {preco_antes} → {preco_agora} (-{queda})", "Fone", 129.9, 99.9, 23.1, "L")
        self.assertEqual(texto, "Fone: R$ 129,90 → R$ 99,90 (-23,1%)\n\nL")  # sem {link}, o link vai no fim
        self.assertIn("📉 BAIXOU DE PREÇO!", alertas.montar_mensagem("", "Fone", 10, 9, 10, "L"))


class TestAvisoPorProduto(TestCase):
    """Cada produto pode trocar a queda padrão por uma queda própria em % ou por um preço em R$."""

    def setUp(self):
        self.conta = criar_conta()
        self.produto, _ = alertas.adicionar(self.conta, produto(1, preco=100.0))

    def preco(self, valor, queda_minima=10):
        return alertas.registrar_preco(self.produto, Decimal(str(valor)), AGORA, queda_minima)

    def test_queda_propria_em_porcentagem(self):
        self.assertEqual(alertas.definir_aviso(self.produto, "pct", "20"), "")
        self.assertIsNone(self.preco(85))  # caiu 15%: o padrão (10%) avisaria, mas este pede 20%
        self.assertIsNotNone(self.preco(79.9))
        self.assertIn("Digite uma queda", alertas.definir_aviso(self.produto, "pct", "95"))
        self.assertIn("Digite uma queda", alertas.definir_aviso(self.produto, "pct", "abc"))

    def test_preco_em_reais_avisa_uma_vez_e_de_novo_so_depois_de_subir(self):
        self.assertEqual(alertas.definir_aviso(self.produto, "reais", "89,90"), "")
        self.assertEqual(self.produto.preco_alvo, Decimal("89.90"))
        self.assertIsNone(self.preco(92))  # caiu 8%, mas não chegou nos 89,90
        alerta = self.preco(89.9)
        self.assertEqual((alerta.preco_alvo, alerta.preco_antes, alerta.preco_agora), (Decimal("89.90"), Decimal("100.00"), Decimal("89.90")))
        self.assertIsNone(self.preco(85))  # continua abaixo: não repete
        self.assertIsNone(self.preco(95))  # subiu acima do alvo: rearma
        self.assertIsNotNone(self.preco(88))
        resumo = alertas.resumo_do_aviso(self.produto, 10)
        self.assertEqual(resumo["tipo"], "chegou")
        self.assertIn("seu preço: R$ 89,90", resumo["texto"])

    def test_alvo_que_o_preco_ja_atingiu_avisa_na_proxima_conferencia(self):
        self.preco(70)  # padrão 10%: avisa e a referência vira 70
        alertas.definir_aviso(self.produto, "reais", "75")
        self.assertIsNotNone(self.preco(70))
        self.assertIsNone(self.preco(70))

    def test_resumo_e_volta_ao_padrao(self):
        self.assertEqual(alertas.resumo_do_aviso(self.produto, 10)["texto"], "📉 Avisa com queda de 10%")
        self.assertIn("padrão · R$ 90,00 ou menos", alertas.resumo_do_aviso(self.produto, 10)["detalhe"])
        alertas.definir_aviso(self.produto, "reais", "79,90")
        resumo = alertas.resumo_do_aviso(self.produto, 10)
        self.assertEqual((resumo["texto"], resumo["detalhe"]), ("🎯 Avisa quando chegar a R$ 79,90", "faltam R$ 20,10 (20%)"))
        self.assertIn("Digite o preço", alertas.definir_aviso(self.produto, "reais", "0"))
        alertas.definir_aviso(self.produto, "padrao", "")
        self.assertEqual(self.produto.tipo_aviso, "padrao")
        self.assertIsNotNone(self.preco(89))  # de volta aos 10%


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotorDeAlertas(TestCase):
    def setUp(self):
        self.conta = criar_conta()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.alerta = AlertaPreco.objects.create(conta=self.conta, ativo=True, intervalo_minutos=15, queda_minima=10)
        self.motor = alertas.Motor()
        alertas.adicionar(self.conta, produto(1, preco=100.0, nome="Fone"))
        alertas.adicionar(self.conta, produto(2, preco=50.0, nome="Mouse"))

    def rodar(self, precos, agora=AGORA):
        def buscar(app_id, secret, item_id):
            preco = precos.get(str(item_id))
            return None if preco is None else produto(item_id, preco=preco, nome={"1": "Fone", "2": "Mouse"}[str(item_id)])
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", side_effect=buscar) as consultas:
            self.motor.uma_volta(agora)
        self.alerta.refresh_from_db()
        return consultas

    def test_queda_avisa_no_painel_e_por_email(self, _link):
        self.rodar({"1": 80.0, "2": 49.0})
        disparado = AlertaDisparado.objects.get()
        self.assertEqual((disparado.nome, disparado.queda, disparado.enviado_email), ("Fone", Decimal("20.0"), True))
        self.assertEqual(disparado.link_afiliado, "https://s.shopee.com.br/1-alerta")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bia@exemplo.com"])
        self.assertIn("Fone baixou 20%", mail.outbox[0].subject)
        self.assertIn("R$ 80,00", mail.outbox[0].alternatives[0][0])
        self.assertEqual(self.alerta.proxima_conferencia_em, AGORA + timedelta(minutes=15))
        self.assertFalse(EnvioWhatsApp.objects.exists())  # postar nos grupos está desligado

    def test_preco_em_reais_no_email(self, _link):
        fone = ProdutoAcompanhado.objects.get(item_id="1")
        alertas.definir_aviso(fone, "reais", "85")
        self.rodar({"1": 84.0, "2": 50.0})
        disparado = AlertaDisparado.objects.get()
        self.assertEqual(disparado.preco_alvo, Decimal("85.00"))
        self.assertIn("Fone chegou a R$ 84,00", mail.outbox[0].subject)
        self.assertIn("Chegou ao seu preço de R$\xa085,00", mail.outbox[0].alternatives[0][0])

    def test_espera_o_intervalo_e_respeita_o_minimo_do_plano(self, _link):
        self.rodar({"1": 100.0, "2": 50.0})
        consultas = self.rodar({"1": 100.0, "2": 50.0}, AGORA + timedelta(minutes=10))
        self.assertEqual(consultas.call_count, 0)
        self.conta.modulos_cortesia = "whatsapp"  # Standard: a partir de 1 hora
        self.conta.save()
        self.rodar({"1": 100.0, "2": 50.0}, AGORA + timedelta(minutes=15))
        self.assertEqual(self.alerta.proxima_conferencia_em, AGORA + timedelta(minutes=75))

    def test_posta_nos_grupos_com_o_modelo(self, _link):
        AlertaPreco.objects.filter(pk=self.alerta.pk).update(enviar_grupos=True, avisar_email=False,
                                                             modelo_mensagem="Baixou! {produto} por {preco_agora}\n{link}")
        ConfiguracaoOfertas.objects.create(conta=self.conta, sub_ids="grupos", grupos=[GRUPOS[0]])  # os grupos da Automação
        self.rodar({"1": 80.0, "2": 50.0})
        envio = EnvioWhatsApp.objects.get()
        self.assertEqual((envio.origem, envio.destino, envio.estado), ("alerta", "1@g.us", "pendente"))
        self.assertEqual(envio.texto, "Baixou! Fone por R$ 80,00\nhttps://s.shopee.com.br/1-grupos")
        self.assertTrue(AlertaDisparado.objects.get().postado_grupos)
        self.assertEqual(len(mail.outbox), 0)

    def test_sem_grupos_na_automacao_avisa_o_motivo(self, _link):
        AlertaPreco.objects.filter(pk=self.alerta.pk).update(enviar_grupos=True)
        self.rodar({"1": 80.0, "2": 50.0})
        self.assertFalse(EnvioWhatsApp.objects.exists())
        self.assertIn("escolha os grupos na aba Automação", self.alerta.ultimo_erro)

    def test_sem_whatsapp_conectado_avisa_o_motivo(self, _link):
        AlertaPreco.objects.filter(pk=self.alerta.pk).update(enviar_grupos=True)
        ConexaoWhatsApp.objects.update(estado="desconectado")
        self.rodar({"1": 80.0, "2": 50.0})
        self.assertFalse(EnvioWhatsApp.objects.exists())
        self.assertIn("conecte o WhatsApp", self.alerta.ultimo_erro)
        self.assertEqual(len(mail.outbox), 1)  # o e-mail vai mesmo assim

    def test_produto_que_sumiu_fica_indisponivel(self, _link):
        self.rodar({"2": 50.0})
        self.assertTrue(ProdutoAcompanhado.objects.get(item_id="1").indisponivel)

    def test_pausado_nao_confere_mas_conferir_agora_sim(self, _link):
        AlertaPreco.objects.filter(pk=self.alerta.pk).update(ativo=False)
        self.assertEqual(self.rodar({"1": 80.0, "2": 50.0}).call_count, 0)
        AlertaPreco.objects.filter(pk=self.alerta.pk).update(pedido_conferir_em=AGORA)
        self.assertEqual(self.rodar({"1": 80.0, "2": 50.0}).call_count, 2)
        self.assertIsNone(self.alerta.pedido_conferir_em)

    def test_sem_o_bot_no_plano_para(self, _link):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertEqual(self.rodar({"1": 80.0, "2": 50.0}).call_count, 0)
        self.assertIn("Renove a assinatura", self.alerta.ultimo_erro)
