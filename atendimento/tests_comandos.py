from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from bot_whatsapp.models import ConexaoWhatsApp
from licencas.models import ContaAppfiliado
from painel.models import MetaMensal, ResultadoDiario, SincronizacaoResultados, VendaItem

from . import comandos, servico
from .models import CodigoVinculo, Conversa, Mensagem
from .tests import CONTA, LIGADO, SessaoFalsa, evento

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"
FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 10, 28, 15, 0, tzinfo=FUSO)  # ontem = 27/10
CHAT = "5511999990000@s.whatsapp.net"


@override_settings(**LIGADO, APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"],
                   APPFILIADO_PAINEL_URL=f"https://{HOST}", APPFILIADO_WHATSAPP_SUPORTE="+55 (45) 99999-0000")
class BaseComandos(TestCase):
    def setUp(self):
        cache.clear()
        relogio = mock.patch("django.utils.timezone.now", return_value=AGORA)
        relogio.start()
        self.addCleanup(relogio.stop)
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", nome="Bia Souza", modulos_cortesia="whatsapp",
                                                    shopee_validado_em=AGORA)
        self.conta.definir_senha(SENHA)
        self.conta.save()

    def chegou(self, texto, msg_id=None, chat=CHAT):
        self.contador = getattr(self, "contador", 0) + 1
        ev = evento(texto, chat=chat, msg_id=msg_id or f"M{self.contador}")
        servico.registrar(ev, texto, False)
        return Mensagem.objects.filter(conversa__chat=chat).order_by("id").last()

    def resposta(self, texto, chat=CHAT) -> str:
        """O texto que vai sair pela próxima volta (ou "" se o comando não respondeu nada)."""
        ultima = self.chegou(texto, chat=chat)
        return ultima.texto if ultima.autor == Mensagem.AGENTE else ""

    def vincular(self, chat=CHAT):
        codigo = comandos.gerar_codigo(self.conta)
        return self.resposta(f"VINCULAR {codigo.codigo}", chat=chat)


class TestIdentificar(TestCase):
    def test_so_a_mensagem_inteira_vira_comando(self):
        self.assertEqual(comandos.identificar("/Resultados!"), ("resultados", ""))
        self.assertEqual(comandos.identificar(" Métas "), ("metas", ""))
        self.assertEqual(comandos.identificar("mais vendidos"), ("top", ""))
        self.assertEqual(comandos.identificar("Vincular 123456"), ("vincular", "123456"))
        self.assertEqual(comandos.identificar("VINCULAR123456"), ("vincular", "123456"))
        self.assertEqual(comandos.identificar("vincular"), ("vincular", ""))
        self.assertIsNone(comandos.identificar("quero ver os resultados do bot"))
        self.assertIsNone(comandos.identificar("vincular 12345"))
        self.assertIsNone(comandos.identificar(""))


class TestSemVinculo(BaseComandos):
    def test_comando_sem_vinculo_explica_como_vincular_sem_chamar_o_agente(self):
        texto = self.resposta("resultados")
        self.assertIn("vincule este número", texto)
        self.assertIn(f"https://{HOST}/configuracoes/#whatsapp", texto)
        self.assertFalse(Mensagem.objects.filter(autor=Mensagem.CLIENTE, respondida=False).exists())

    def test_conversa_e_menu_seguem_pro_agente(self):
        for texto in ("Oi, quanto custa o bot?", "menu", "ajuda"):
            ultima = self.chegou(texto)
            self.assertEqual((ultima.autor, ultima.respondida), (Mensagem.CLIENTE, False))
        self.assertIn("vincule", self.resposta("comandos"))

    def test_codigo_errado_conta_tentativa_e_bloqueia_no_dia(self):
        for _ in range(comandos.TENTATIVAS_DE_VINCULO_POR_DIA):
            self.assertIn("Esse código não vale", self.resposta("VINCULAR 000000"))
        self.assertIn("Muitas tentativas", self.resposta("VINCULAR 000000"))
        codigo = comandos.gerar_codigo(self.conta).codigo
        self.assertIn("Muitas tentativas", self.resposta(f"VINCULAR {codigo}"))  # nem o certo passa hoje
        self.assertIsNone(Conversa.objects.get().conta)

    def test_codigo_vencido_nao_vale(self):
        codigo = comandos.gerar_codigo(self.conta)
        CodigoVinculo.objects.filter(pk=codigo.pk).update(criado_em=AGORA - timedelta(minutes=31))
        self.assertIn("Esse código não vale", self.resposta(f"VINCULAR {codigo.codigo}"))


class TestComVinculo(BaseComandos):
    def setUp(self):
        super().setUp()
        self.assertIn("Pronto! Este número está ligado à sua conta do Appfiliado (bia@exemplo.com)", self.vincular())
        SincronizacaoResultados.objects.create(conta=self.conta, concluida_em=AGORA - timedelta(minutes=20))

    def test_vincular_liga_a_conta_e_apaga_o_codigo(self):
        conversa = Conversa.objects.get()
        self.assertEqual(conversa.conta, self.conta)
        self.assertFalse(CodigoVinculo.objects.exists())
        self.assertIn("*resultados*", self.resposta("comandos"))

    def test_ate_2_numeros_por_conta(self):
        segundo, terceiro = "5511888880000@s.whatsapp.net", "5511777770000@s.whatsapp.net"
        self.assertIn("Pronto!", self.vincular(chat=segundo))
        self.assertEqual(Conversa.objects.filter(conta=self.conta).count(), 2)
        self.assertIn("Pedidos:", self.resposta("resultados"))  # o primeiro continua vinculado
        self.assertIn("Pedidos:", self.resposta("resultados", chat=segundo))
        self.assertIn("já tem 2 números vinculados", self.vincular(chat=terceiro))
        self.assertTrue(CodigoVinculo.objects.exists())  # o código continua valendo
        self.assertIsNone(Conversa.objects.get(chat=terceiro).conta)
        self.assertIn("Pronto!", self.vincular())  # o mesmo número de novo não conta como outro

    def test_resultados_de_ontem_7_dias_e_mes(self):
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 27), pedidos=12, faturamento=Decimal("1234.56"),
                                       comissao_estimada=Decimal("98.76"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 22), pedidos=3, faturamento=Decimal("100"),
                                       comissao_estimada=Decimal("10"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 2), pedidos=1, faturamento=Decimal("50"),
                                       comissao_estimada=Decimal("5"), comissao_validada=Decimal("40"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 28), pedidos=9, faturamento=Decimal("999"))
        texto = self.resposta("Resultados")
        self.assertIn("*Ontem (27/10)*\nPedidos: 12\nFaturamento: R$ 1.234,56\nComissão estimada: R$ 98,76\n"
                      "Comissão validada: R$ 0,00", texto)
        self.assertIn("*Últimos 7 dias (21/10 a 27/10)*\nPedidos: 15\nFaturamento: R$ 1.334,56", texto)
        self.assertIn("*Outubro/2026 até ontem*\nPedidos: 16\nFaturamento: R$ 1.384,56", texto)
        self.assertIn("Comissão estimada: R$ 108,76\nComissão validada: R$ 0,00\n\n*Outubro", texto)  # 7 dias
        self.assertIn("Comissão validada: R$ 40,00", texto)
        self.assertIn("Atualizado às 14:40.", texto)
        self.assertIn(f"https://{HOST}/resultados/", texto)
        self.assertNotIn("ainda aparece zerado", texto)  # já passou do meio-dia

    def test_de_manha_avisa_que_ontem_ainda_nao_saiu(self):
        with mock.patch("django.utils.timezone.now", return_value=AGORA.replace(hour=7)):
            self.assertIn("Ontem ainda aparece zerado?", self.resposta("resultados"))
            ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 27), pedidos=2)
            self.assertNotIn("Ontem ainda aparece zerado?", self.resposta("resultados"))

    def test_metas_com_faixas(self):
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=[
            {"percentual": 100, "faturamento": 3000, "bonus": 100},
            {"percentual": 125, "faturamento": 3750, "bonus": 200},
        ])
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 20), faturamento=Decimal("3200"))
        texto = self.resposta("metas")
        self.assertIn("🎯 *Meta de Outubro/2026*\nFaturamento até ontem: R$ 3.200,00", texto)
        self.assertIn("✅ 100% (R$ 3.000,00, bônus de R$ 100,00): batida", texto)
        self.assertIn("⬜ 125% (R$ 3.750,00, bônus de R$ 200,00): faltam R$ 550,00", texto)
        self.assertIn("Para a próxima faixa: R$ 137,50 por dia nos 4 dias que faltam.", texto)
        self.assertIn("Bônus garantido: R$ 100,00", texto)

    def test_metas_sem_cadastro_manda_pro_painel(self):
        texto = self.resposta("meta")
        self.assertIn("ainda não cadastrou a meta de Outubro/2026", texto)
        self.assertIn(f"https://{HOST}/metas/", texto)

    def test_vendas_de_ontem_e_top_da_semana(self):
        def item(nome, pedido, quando, comissao, situacao=VendaItem.CONCLUIDO, qtd=1):
            return VendaItem.objects.create(
                conta=self.conta, conversao_id=pedido, pedido_id=pedido, item_id=nome, nome=nome, quantidade=qtd,
                valor=Decimal("50") * qtd, comissao=Decimal(comissao), situacao=situacao, comprado_em=quando)

        item("Fone Bluetooth", "P1", datetime(2026, 10, 27, 14, 32, tzinfo=FUSO), "4.50", qtd=2)
        item("Garrafa térmica", "P2", datetime(2026, 10, 27, 9, 5, tzinfo=FUSO), "3", situacao=VendaItem.CANCELADO)
        item("Fone Bluetooth", "P3", datetime(2026, 10, 23, 10, 0, tzinfo=FUSO), "2.25")
        item("Hoje não entra", "P4", datetime(2026, 10, 28, 8, 0, tzinfo=FUSO), "1")

        texto = self.resposta("vendas")
        self.assertIn("🛒 *Vendas de ontem (27/10)*\n1 produto vendido, comissão de R$ 4,50", texto)
        self.assertIn("• 14:32 2x Fone Bluetooth: R$ 100,00, comissão R$ 4,50", texto)
        self.assertIn("• 09:05 Garrafa térmica: R$ 50,00, comissão R$ 3,00 ❌ cancelado", texto)
        self.assertNotIn("Hoje não entra", texto)
        self.assertIn("?periodo=ontem", texto)

        texto = self.resposta("top")
        self.assertIn("1. Fone Bluetooth: 3 unidades, comissão R$ 6,75", texto)
        self.assertNotIn("Garrafa", texto)

    def test_sem_shopee_ou_sem_plano_avisa(self):
        ContaAppfiliado.objects.filter(pk=self.conta.pk).update(shopee_validado_em=None)
        self.assertIn("Shopee ainda não está conectada", self.resposta("resultados"))
        ContaAppfiliado.objects.filter(pk=self.conta.pk).update(modulos_cortesia="")
        self.assertIn("assinatura do Appfiliado não está ativa", self.resposta("resultados"))

    def test_limite_de_comandos_no_dia(self):
        Conversa.objects.update(comandos_no_dia=comandos.COMANDOS_POR_DIA)
        self.assertIn("limite de 30 comandos", self.resposta("top"))
        self.assertEqual(self.resposta("top"), "")  # depois do aviso, nada
        self.assertFalse(Mensagem.objects.filter(autor=Mensagem.CLIENTE, respondida=False).exists())

    def volta(self, quando):
        sessao = SessaoFalsa()
        with mock.patch("django.utils.timezone.now", return_value=quando), \
                mock.patch.object(servico.agente, "responder") as agente:
            servico.uma_volta({CONTA: sessao})
        agente.assert_not_called()
        return [texto for _, texto in sessao.enviadas]

    def test_validada_com_busca_recente_responde_na_hora(self):
        SincronizacaoResultados.objects.filter(conta=self.conta).update(concluida_em=AGORA - timedelta(minutes=5))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 28), comissao_validada=Decimal("55.50"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 27), comissao_validada=Decimal("40"))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 9, 30), comissao_validada=Decimal("999"))
        texto = self.resposta("Comissão validada")
        self.assertIn("✅ *Comissão validada hoje (28/10)*\nR$ 55,50", texto)
        self.assertIn("Ontem (27/10): R$ 40,00", texto)
        self.assertIn("Outubro/2026 até agora: R$ 95,50", texto)
        self.assertIn("Atualizado às 14:55.", texto)
        self.assertNotIn("ainda aparece zerado", texto)
        self.assertFalse(SincronizacaoResultados.objects.get(conta=self.conta).aguardando)

    def test_validada_pede_a_busca_e_responde_quando_termina(self):
        self.assertIn("Buscando a comissão validada de hoje na Shopee", self.resposta("validada"))
        estado = SincronizacaoResultados.objects.get(conta=self.conta)
        self.assertTrue(estado.aguardando)
        self.assertFalse(estado.pedido_curto)  # a de 30 dias: pega validação de compra antiga
        self.assertIn("Buscando", self.resposta("hoje"))  # pediu de novo: uma resposta só no fim

        enviadas = self.volta(AGORA + timedelta(seconds=20))
        self.assertFalse(any("✅" in t for t in enviadas))  # a busca ainda não terminou

        # O worker do painel busca na Shopee.
        SincronizacaoResultados.objects.filter(conta=self.conta).update(
            iniciada_em=AGORA + timedelta(seconds=30), concluida_em=AGORA + timedelta(seconds=50))
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 28), comissao_validada=Decimal("12.30"))
        enviadas = self.volta(AGORA + timedelta(minutes=1))
        validadas = [t for t in enviadas if "✅" in t]
        self.assertEqual(len(validadas), 1)
        self.assertIn("R$ 12,30", validadas[0])
        self.assertNotIn("não respondeu", validadas[0])
        self.assertIsNone(Conversa.objects.get().validada_pedida_em)
        self.assertEqual([t for t in self.volta(AGORA + timedelta(minutes=2)) if "✅" in t], [])

    def test_validada_sem_resposta_da_shopee_manda_o_que_tem(self):
        SincronizacaoResultados.objects.filter(conta=self.conta).update(pedido_em=AGORA - timedelta(minutes=1),
                                                                         pedido_curto=True)
        self.resposta("validada")
        self.assertFalse(SincronizacaoResultados.objects.get(conta=self.conta).pedido_curto)  # virou a de 30 dias
        self.assertEqual([t for t in self.volta(AGORA + timedelta(minutes=4)) if "✅" in t], [])
        validadas = [t for t in self.volta(AGORA + timedelta(minutes=6)) if "✅" in t]
        self.assertEqual(len(validadas), 1)
        self.assertIn("A Shopee não respondeu agora", validadas[0])

    def test_atualizar_pede_a_busca_e_avisa_quando_termina(self):
        self.assertIn("Atualizando seus dados com a Shopee", self.resposta("Atualizar"))
        estado = SincronizacaoResultados.objects.get(conta=self.conta)
        self.assertTrue(estado.aguardando)
        self.assertFalse(estado.pedido_curto)  # a de 30 dias, como o botão do painel
        self.assertEqual([t for t in self.volta(AGORA + timedelta(seconds=20)) if "✅ Pronto" in t], [])
        SincronizacaoResultados.objects.filter(conta=self.conta).update(
            iniciada_em=AGORA + timedelta(seconds=30), concluida_em=AGORA + timedelta(seconds=50))
        prontas = [t for t in self.volta(AGORA + timedelta(minutes=1)) if "✅ Pronto" in t]
        self.assertEqual(prontas, ["✅ Pronto! Seus dados foram atualizados com a Shopee às 15:00. Mande *resultados*, "
                                   "*vendas*, *top*, *metas* ou *validada* para ver os números."])
        self.assertIsNone(Conversa.objects.get().atualizacao_pedida_em)
        # Logo depois, não pede outra busca.
        with mock.patch("django.utils.timezone.now", return_value=AGORA + timedelta(minutes=1)):
            self.assertIn("já estão atualizados com a Shopee (às 15:00)", self.resposta("atualizar"))

    def test_atualizar_com_erro_ou_demora_da_shopee(self):
        self.resposta("atualizar")
        SincronizacaoResultados.objects.filter(conta=self.conta).update(
            iniciada_em=AGORA + timedelta(seconds=30), concluida_em=AGORA + timedelta(seconds=50), erro="fora")
        self.assertIn("Não consegui atualizar com a Shopee agora", "".join(self.volta(AGORA + timedelta(minutes=1))))
        SincronizacaoResultados.objects.filter(conta=self.conta).update(erro="", iniciada_em=None)
        with mock.patch("django.utils.timezone.now", return_value=AGORA + timedelta(minutes=2)):
            self.resposta("atualizar")
        self.assertNotIn("demorando", "".join(self.volta(AGORA + timedelta(minutes=5))))
        self.assertIn("A Shopee está demorando", "".join(self.volta(AGORA + timedelta(minutes=8))))

    def test_desvincular(self):
        self.assertIn("não está mais ligado", self.resposta("desvincular"))
        self.assertIsNone(Conversa.objects.get().conta)

    def test_resposta_sai_na_volta_seguinte(self):
        self.resposta("ajuda")
        sessao = SessaoFalsa()
        with mock.patch.object(servico.agente, "responder") as agente:
            servico.uma_volta({CONTA: sessao})
        agente.assert_not_called()
        self.assertEqual(sessao.enviadas[-1][0], CHAT)
        self.assertIn("Oi, Bia! Comandos que eu entendo por aqui", sessao.enviadas[-1][1])


class TestPainel(BaseComandos):
    def setUp(self):
        super().setUp()
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})

    def test_gera_codigo_mostra_link_e_desvincula(self):
        agente = ContaAppfiliado.objects.create(email="vendas@appfiliado.com.br")
        ConexaoWhatsApp.objects.create(conta=agente, numero="5545988880000")
        with override_settings(ATENDIMENTO_CONTA_ID=agente.pk):
            self._gera_codigo_mostra_link_e_desvincula()

    def _gera_codigo_mostra_link_e_desvincula(self):
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("Resultados no WhatsApp", html)
        self.assertIn("+55 (45) 98888-0000", html)
        self.assertIn("Vincular meu WhatsApp", html)

        resposta = self.client.post("/configuracoes/", {"formulario": "whatsapp_codigo"})
        self.assertRedirects(resposta, "/configuracoes/#whatsapp", fetch_redirect_response=False)
        codigo = CodigoVinculo.objects.get(conta=self.conta).codigo
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn(f"https://wa.me/5545988880000?text=VINCULAR%20{codigo}", html)
        self.assertIn("vale até 15:30", html)

        self.resposta(f"VINCULAR {codigo}")
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("+55 (11) 99999-0000", html)
        self.assertIn("Números vinculados (1 de 2)", html)
        self.assertIn("Vincular outro número", html)

        # Segundo número: chega no limite.
        self.client.post("/configuracoes/", {"formulario": "whatsapp_codigo"})
        self.resposta(f"VINCULAR {CodigoVinculo.objects.get(conta=self.conta).codigo}", chat="5511888880000@s.whatsapp.net")
        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("Números vinculados (2 de 2)", html)
        self.assertIn("+55 (11) 88888-0000", html)
        self.assertIn("já tem 2 números vinculados, o máximo", html)
        self.assertNotIn("Vincular outro número", html)
        self.client.post("/configuracoes/", {"formulario": "whatsapp_codigo"})
        self.assertFalse(CodigoVinculo.objects.filter(conta=self.conta).exists())  # no limite, não gera código

        # Desvincula só o escolhido (e só da própria conta).
        primeiro = Conversa.objects.get(chat=CHAT)
        outra = ContaAppfiliado.objects.create(email="outra@exemplo.com")
        alheia = Conversa.objects.create(chat="5511666660000@s.whatsapp.net", conta=outra)
        self.client.post("/configuracoes/", {"formulario": "whatsapp_desvincular", "conversa": alheia.pk})
        self.client.post("/configuracoes/", {"formulario": "whatsapp_desvincular", "conversa": "x"})
        self.assertEqual(Conversa.objects.get(pk=alheia.pk).conta, outra)
        self.client.post("/configuracoes/", {"formulario": "whatsapp_desvincular", "conversa": primeiro.pk})
        self.assertEqual(list(Conversa.objects.filter(conta=self.conta).values_list("chat", flat=True)),
                         ["5511888880000@s.whatsapp.net"])

    def test_cartao_so_precisa_do_numero(self):
        # No web, o agente (conta e chave da IA) pode não estar configurado: quem responde é o worker.
        with override_settings(ANTHROPIC_API_KEY="", ATENDIMENTO_CONTA_ID=0):
            html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("Resultados no WhatsApp", html)
        self.assertIn("+55 (45) 99999-0000", html)  # sem a conexão do agente, usa o número de suporte
        with override_settings(APPFILIADO_WHATSAPP_SUPORTE="", ATENDIMENTO_CONTA_ID=0):
            html = self.client.get("/configuracoes/").content.decode()
        self.assertNotIn("Resultados no WhatsApp", html)
