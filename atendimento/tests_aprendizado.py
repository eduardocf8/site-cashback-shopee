"""O agente aprende com as suas respostas, com a sua aprovação (atendimento/aprendizado.py)."""

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from . import agente, aprendizado, servico
from .models import Conversa, Mensagem, RespostaAprendida
from .tests import CONTA, LIGADO, ClaudeFalso, SessaoFalsa, evento, rodar_na_hora

DONO = "5545988887777@s.whatsapp.net"


def sugestao(aprender=True, pergunta="Dá pra usar dois números de WhatsApp no mesmo bot?",
             resposta="Não, cada conta conecta um número. Pra dois números, são duas assinaturas do Bot."):
    entrada = {"aprender": aprender, "pergunta": pergunta if aprender else "", "resposta": resposta if aprender else ""}
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id="t1", name="registrar_aprendizado", input=entrada)],
                           stop_reason="tool_use")


@override_settings(**LIGADO)
class TestAprendizado(TestCase):
    def setUp(self):
        self.sessao = SessaoFalsa()
        patcher = mock.patch.object(servico._executor, "submit", side_effect=rodar_na_hora)
        patcher.start()
        self.addCleanup(patcher.stop)

    def conversa_atendida_por_voce(self, ha=timedelta(minutes=31)):
        servico.registrar(evento("Dá pra usar dois números no mesmo bot?", msg_id="C1"), "Dá pra usar dois números no mesmo bot?", False)
        servico.registrar(evento("Não, cada conta é um número.", minha=True, msg_id="V1"), "Não, cada conta é um número.", False)
        Mensagem.objects.update(criada_em=timezone.now() - ha)
        return Conversa.objects.get()

    def volta(self, *respostas):
        claude = ClaudeFalso(*respostas)
        with mock.patch.object(agente, "_cliente", return_value=claude):
            servico.uma_volta({CONTA: self.sessao})
        return claude

    def dono_responde(self, texto, msg_id, citada=""):
        ev = evento(texto, chat=DONO, msg_id=msg_id, nome="Eduardo")
        if citada:
            ev.Message.ClearField("conversation")
            ev.Message.extendedTextMessage.text = texto
            ev.Message.extendedTextMessage.contextInfo.stanzaID = citada
        servico.registrar(ev, texto, False)

    def test_sugere_30_min_depois_e_voce_aprova_com_1(self):
        self.conversa_atendida_por_voce(ha=timedelta(minutes=20))
        claude = self.volta()
        self.assertEqual(claude.pedidos, [])  # ainda não deu 30 minutos
        Mensagem.objects.update(criada_em=timezone.now() - timedelta(minutes=31))
        claude = self.volta(sugestao())
        self.assertIn("Você (dono): Não, cada conta é um número.", claude.pedidos[0]["messages"][0]["content"])
        r = RespostaAprendida.objects.get()
        self.assertEqual(r.estado, RespostaAprendida.SUGERIDA)

        self.volta()  # manda a sugestão pro seu WhatsApp (e não analisa a mesma conversa de novo)
        self.assertEqual(self.sessao.enviadas[-1][0], DONO)
        self.assertIn("Aprender esta resposta?", self.sessao.enviadas[-1][1])

        self.dono_responde("1", "D1")
        r.refresh_from_db()
        self.assertEqual(r.estado, RespostaAprendida.APROVADA)
        self.volta()  # a confirmação sai pro seu WhatsApp
        self.assertTrue(self.sessao.enviadas[-1][1].startswith("✅ Aprendido!"))
        self.assertIn("dois números", agente.respostas_aprovadas())
        # A aprovada entra no que o agente sabe, num bloco à parte do cache.
        self.assertEqual(len(agente._sistema()), 2)

    def test_resposta_citando_a_sugestao_troca_o_texto(self):
        self.conversa_atendida_por_voce()
        self.volta(sugestao())
        self.volta()
        r = RespostaAprendida.objects.get()
        self.dono_responde("Não. Cada assinatura do Bot conecta um número só.", "D1", citada=r.whatsapp_id)
        r.refresh_from_db()
        self.assertEqual((r.estado, r.resposta), (RespostaAprendida.APROVADA, "Não. Cada assinatura do Bot conecta um número só."))

    def test_2_descarta_e_mensagem_comum_do_dono_segue_como_conversa(self):
        self.conversa_atendida_por_voce()
        self.volta(sugestao())
        self.volta()
        self.dono_responde("Oi, quanto custa o site?", "D0")  # você testando o agente: vira conversa normal
        self.assertTrue(Mensagem.objects.filter(texto="Oi, quanto custa o site?", autor=Mensagem.CLIENTE).exists())
        self.dono_responde("2", "D1")
        self.assertEqual(RespostaAprendida.objects.get().estado, RespostaAprendida.DESCARTADA)

    def test_caso_pessoal_nao_vira_sugestao(self):
        self.conversa_atendida_por_voce()
        self.volta(sugestao(aprender=False))
        self.assertFalse(RespostaAprendida.objects.exists())
        self.assertIsNotNone(Conversa.objects.get().aprendizado_em)
        claude = self.volta()
        self.assertEqual(claude.pedidos, [])  # não analisa de novo sem resposta nova sua
