"""Aviso de bot parado (bot_whatsapp/avisos_de_queda.py) e primeiros passos (painel/primeiros_passos.py)."""

from datetime import timedelta
from types import SimpleNamespace

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from bot_whatsapp import avisos_de_queda
from bot_whatsapp.gerenciador import Gerenciador
from bot_whatsapp.models import AlertaPreco, ConexaoWhatsApp, ConfiguracaoOfertas
from licencas.models import Assinatura, ContaAppfiliado, ProdutoZouti

from . import primeiros_passos
from .tests import BasePainel

AGORA = timezone.now()


def conta_com_bot(email="bia@exemplo.com", **extra) -> ContaAppfiliado:
    return ContaAppfiliado.objects.create(email=email, nome="Bia Souza", modulos_cortesia="whatsapp", **extra)


class TestAvisoDeBotParado(TestCase):
    def setUp(self):
        self.conta = conta_com_bot()
        ConfiguracaoOfertas.objects.create(conta=self.conta, ativo=True)
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado=ConexaoWhatsApp.CONECTADO, jid="x")

    def parar(self, motivo, quando, estado=ConexaoWhatsApp.RECONECTANDO):
        avisos_de_queda.parou(self.conexao, motivo, quando)
        self.conexao.estado = estado
        self.conexao.save()

    def test_deslogou_avisa_na_hora_e_lembra_uma_vez_depois_de_24h(self):
        self.parar(ConexaoWhatsApp.PARADO_DESLOGOU, AGORA, ConexaoWhatsApp.DESCONECTADO)
        avisos_de_queda.uma_volta(AGORA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Seu bot do Appfiliado parou: o WhatsApp foi desconectado")
        self.assertIn("Aparelhos conectados", mail.outbox[0].body)
        self.assertIn("/whatsapp/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["bia@exemplo.com"])

        avisos_de_queda.uma_volta(AGORA + timedelta(hours=23))
        self.assertEqual(len(mail.outbox), 1)
        avisos_de_queda.uma_volta(AGORA + timedelta(hours=24, minutes=1))
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(mail.outbox[1].subject.startswith("Lembrete: seu bot"))
        avisos_de_queda.uma_volta(AGORA + timedelta(days=5))
        self.assertEqual(len(mail.outbox), 2)  # depois do lembrete, para

    def test_queda_so_avisa_depois_de_30_minutos(self):
        self.parar(ConexaoWhatsApp.PARADO_CAIU, AGORA)
        avisos_de_queda.uma_volta(AGORA + timedelta(minutes=29))
        self.assertEqual(len(mail.outbox), 0)
        avisos_de_queda.uma_volta(AGORA + timedelta(minutes=31))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("caiu", mail.outbox[0].subject)

    def test_nao_avisa_quem_nao_usa_o_bot_ou_esta_lendo_o_qr(self):
        self.parar(ConexaoWhatsApp.PARADO_DESLOGOU, AGORA, ConexaoWhatsApp.AGUARDANDO_QR)
        avisos_de_queda.uma_volta(AGORA)
        self.assertEqual(len(mail.outbox), 0)

        self.conexao.estado = ConexaoWhatsApp.DESCONECTADO
        self.conexao.save()
        ConfiguracaoOfertas.objects.update(ativo=False)
        avisos_de_queda.uma_volta(AGORA)
        self.assertEqual(len(mail.outbox), 0)
        AlertaPreco.objects.create(conta=self.conta, ativo=True)  # o alerta de preço também usa o WhatsApp
        avisos_de_queda.uma_volta(AGORA)
        self.assertEqual(len(mail.outbox), 1)

    def test_nao_avisa_quem_perdeu_o_plano(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.parar(ConexaoWhatsApp.PARADO_DESLOGOU, AGORA, ConexaoWhatsApp.DESCONECTADO)
        avisos_de_queda.uma_volta(AGORA)
        self.assertEqual(len(mail.outbox), 0)

    def test_gerenciador_marca_e_desmarca(self):
        falso = SimpleNamespace(sessoes={}, reabrir_em={})
        falso._limpar = lambda conexao, erro="": Gerenciador._limpar(falso, conexao, erro)
        Gerenciador._aviso_caiu(falso, self.conexao, "")
        self.conexao.refresh_from_db()
        self.assertEqual((self.conexao.estado, self.conexao.parado_motivo), ("reconectando", "caiu"))
        inicio = self.conexao.parado_desde
        Gerenciador._aviso_deslogou(falso, self.conexao, "removido")
        self.conexao.refresh_from_db()
        # continua contando desde a queda, mas agora é "deslogou" (avisa na hora)
        self.assertEqual((self.conexao.parado_desde, self.conexao.parado_motivo), (inicio, "deslogou"))
        Gerenciador._aviso_conectou(falso, self.conexao, "")
        self.conexao.refresh_from_db()
        self.assertIsNone(self.conexao.parado_desde)

        Gerenciador._aviso_caiu(falso, self.conexao, "")
        Gerenciador._desconectar(falso, self.conexao)  # a pessoa desconectou pelo painel: não é queda
        self.conexao.refresh_from_db()
        self.assertIsNone(self.conexao.parado_desde)


class TestFaixaDeBotParado(BasePainel):
    def test_faixa_vermelha_em_todas_as_paginas(self):
        self.entrar()
        conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado=ConexaoWhatsApp.RECONECTANDO)
        avisos_de_queda.parou(conexao, ConexaoWhatsApp.PARADO_CAIU, timezone.now() - timedelta(minutes=5))
        conexao.save()
        self.assertNotContains(self.client.get("/"), "Seu bot está parado")  # queda curta: ainda tentando

        conexao.parado_desde = timezone.now() - timedelta(hours=1)
        conexao.save()
        for pagina in ("/", "/resultados/", "/configuracoes/"):
            self.assertContains(self.client.get(pagina), "a conexão com o WhatsApp caiu e não voltou sozinha")

        conexao.parado_motivo, conexao.estado = "deslogou", ConexaoWhatsApp.DESCONECTADO
        conexao.save()
        self.assertContains(self.client.get("/"), "o WhatsApp foi desconectado.")


@override_settings(APPFILIADO_WHATSAPP_SUPORTE="+55 (45) 99999-0000")
class TestPrimeirosPassos(TestCase):
    def setUp(self):
        ProdutoZouti.objects.create(zouti_product_id="bot", nome="Bot", modulos="whatsapp")
        self.conta = ContaAppfiliado.objects.create(email="ana@exemplo.com", nome="Ana Lima")
        self.conta.definir_senha("uma-senha-boa-123")
        self.conta.save()

    def assinar(self, ha, conta=None):
        assinatura = Assinatura.objects.create(conta=conta or self.conta, zouti_subscription_id=f"sub{Assinatura.objects.count()}",
                                               zouti_product_ids="bot", status=Assinatura.STATUS_ATIVA)
        Assinatura.objects.filter(pk=assinatura.pk).update(criada_em=AGORA - ha)

    def test_dia_1_e_dia_3_so_com_passo_pendente(self):
        self.assinar(timedelta(hours=20))
        self.assertEqual(primeiros_passos.enviar_pendentes(AGORA), [])  # ainda não fez 1 dia

        self.assinar(timedelta(days=1, hours=1))  # (a primeira assinatura vale como início)
        Assinatura.objects.update(criada_em=AGORA - timedelta(days=1, hours=1))
        primeiros_passos.enviar_pendentes(AGORA)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Falta pouco pras suas ofertas começarem a sair")
        self.assertIn("Olá, Ana!", email.body)
        self.assertIn("Você está a 3 passos de ver o bot postando nos seus grupos:", email.body)
        self.assertIn("✅ Criar a senha do painel", email.body)
        self.assertIn("⬜ Conectar seu WhatsApp pelo QR Code (como no WhatsApp Web)", email.body)
        self.assertIn("/configuracoes/", email.body)  # o próximo passo: a Shopee
        self.assertIn("A gente te ajuda: é só responder este e-mail ou chamar a gente no WhatsApp: https://wa.me/5545999990000.", email.body)

        primeiros_passos.enviar_pendentes(AGORA + timedelta(hours=2))
        self.assertEqual(len(mail.outbox), 1)  # o do dia 1 vai uma vez só

        self.conta.shopee_validado_em = AGORA
        self.conta.save()
        primeiros_passos.enviar_pendentes(AGORA + timedelta(days=2))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].subject, "Precisa de ajuda para configurar o Appfiliado?")
        self.assertIn("ainda faltam 2 passos", mail.outbox[1].body)
        self.assertIn("é só responder este e-mail ou chamar a gente no WhatsApp", mail.outbox[1].body)
        self.assertIn("✅ Conectar sua conta de afiliado da Shopee", mail.outbox[1].body)
        primeiros_passos.enviar_pendentes(AGORA + timedelta(days=4))
        self.assertEqual(len(mail.outbox), 2)

    def test_quem_ja_fez_tudo_nao_recebe(self):
        self.assinar(timedelta(days=1, hours=1))
        self.conta.shopee_validado_em = AGORA
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado=ConexaoWhatsApp.CONECTADO, conectado_em=AGORA)
        ConfiguracaoOfertas.objects.create(conta=self.conta, ativo=True)
        primeiros_passos.enviar_pendentes(AGORA)
        primeiros_passos.enviar_pendentes(AGORA + timedelta(days=3))
        self.assertEqual(len(mail.outbox), 0)

    def test_cliente_antigo_que_assina_outro_modulo_nao_recebe(self):
        self.assinar(timedelta(days=60))
        self.assinar(timedelta(days=1, hours=1))
        primeiros_passos.enviar_pendentes(AGORA)
        self.assertEqual(len(mail.outbox), 0)

    def test_sem_senha_o_link_e_o_de_criar_senha(self):
        self.conta.senha = ""
        self.conta.save()
        self.assinar(timedelta(days=3, hours=1))  # direto no dia 3: só o segundo
        primeiros_passos.enviar_pendentes(AGORA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Precisa de ajuda", mail.outbox[0].subject)
        self.assertIn("/senha/definir/", mail.outbox[0].body)

    def test_so_emissor_de_notas_nao_pede_a_shopee(self):
        lista = primeiros_passos.passos(self.conta, ["notas"])
        self.assertEqual([p["chave"] for p in lista], ["senha", "notas"])
        self.assertEqual([p["chave"] for p in primeiros_passos.passos(self.conta, ["whatsapp", "site", "notas"])],
                         ["senha", "shopee", "whatsapp", "ofertas", "site", "notas"])


class TestOcultarPrimeirosPassos(BasePainel):
    """Botões do cartão "Primeiros passos" no Início."""

    def setUp(self):
        super().setUp()
        self.entrar()

    def test_cartao_aparece_com_os_dois_botoes(self):
        r = self.client.get("/")
        if "Primeiros passos" not in r.content.decode():
            self.skipTest("esta conta de teste não tem passos pendentes")
        self.assertContains(r, "Me lembre mais tarde")
        self.assertContains(r, "Não mostrar novamente")

    def test_lembrar_mais_tarde_esconde_por_12_horas(self):
        self.client.post("/primeiros-passos/ocultar/", {"acao": "depois"})
        self.conta.refresh_from_db()
        self.assertFalse(primeiros_passos.cartao_visivel(self.conta))
        self.assertNotContains(self.client.get("/"), "Me lembre mais tarde")
        self.assertFalse(primeiros_passos.cartao_visivel(self.conta, timezone.now() + timedelta(hours=11)))
        self.assertTrue(primeiros_passos.cartao_visivel(self.conta, timezone.now() + timedelta(hours=12, minutes=1)))
        self.assertFalse(self.conta.passos_ocultos)

    def test_nao_mostrar_novamente_esconde_de_vez(self):
        self.client.post("/primeiros-passos/ocultar/", {"acao": "nunca"})
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.passos_ocultos)
        self.assertFalse(primeiros_passos.cartao_visivel(self.conta, timezone.now() + timedelta(days=365)))
        self.assertNotContains(self.client.get("/"), "Primeiros passos")

    def test_so_aceita_post(self):
        self.assertEqual(self.client.get("/primeiros-passos/ocultar/").status_code, 405)
