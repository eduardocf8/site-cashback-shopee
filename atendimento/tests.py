from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from neonize.events import MessageEv
from neonize.proto.Neonize_pb2 import JID

from . import agente, conhecimento, servico
from .models import Conversa, Mensagem

CONTA = 7
LIGADO = {"ATENDIMENTO_CONTA_ID": CONTA, "ANTHROPIC_API_KEY": "teste", "ATENDIMENTO_AVISAR": "5545988887777"}


def jid(usuario, servidor):
    return JID(User=usuario, Server=servidor, Device=0, RawAgent=0, Integrator=0, IsEmpty=False)


def evento(texto="Oi, quanto custa o bot?", chat="5511999990000@s.whatsapp.net", minha=False, grupo=False,
           msg_id="M1", audio=False, nome="Bia"):
    ev = MessageEv()
    usuario, servidor = chat.split("@")
    ev.Info.MessageSource.Chat.CopyFrom(jid(usuario, servidor))
    ev.Info.MessageSource.Sender.CopyFrom(jid(usuario, servidor))
    ev.Info.MessageSource.IsFromMe = minha
    ev.Info.MessageSource.IsGroup = grupo
    ev.Info.ID = msg_id
    ev.Info.Pushname = nome
    if audio:
        ev.Message.audioMessage.seconds = 3
    else:
        ev.Message.conversation = texto
    return ev


class SessaoFalsa:
    conectada = True

    def __init__(self):
        self.enviadas = []
        self.cliente = self
        self.contador = 0

    def send_message(self, destino, texto):
        self.contador += 1
        self.enviadas.append((f"{destino.User}@{destino.Server}", texto))
        return SimpleNamespace(ID=f"ENVIO{self.contador}")

    def send_chat_presence(self, *args):
        pass


def resposta_do_claude(texto="", ferramenta=None):
    conteudo = []
    if ferramenta:
        conteudo.append(SimpleNamespace(type="tool_use", id="t1", name="chamar_humano", input=ferramenta))
    if texto:
        conteudo.append(SimpleNamespace(type="text", text=texto))
    return SimpleNamespace(content=conteudo, stop_reason="tool_use" if ferramenta else "end_turn", stop_details=None)


class ClaudeFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.pedidos = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._criar))

    def _criar(self, **pedido):
        self.pedidos.append(pedido)
        return self.respostas.pop(0)


def rodar_na_hora(fn, *args):
    fn(*args)


@override_settings(**LIGADO)
class TestAtendimento(TestCase):
    def setUp(self):
        self.sessao = SessaoFalsa()
        patcher = mock.patch.object(servico._executor, "submit", side_effect=rodar_na_hora)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _chegou(self, *args, **kwargs):
        ev = evento(*args, **kwargs)
        self.assertTrue(servico.deve_ouvir(CONTA, ev))
        servico.registrar(ev, ev.Message.conversation, kwargs.get("audio", False))

    def _passar_a_espera(self):
        Conversa.objects.update(ultima_recebida_em=timezone.now() - timedelta(seconds=30))

    def test_so_ouve_conversa_privada_do_numero_de_vendas(self):
        self.assertFalse(servico.deve_ouvir(CONTA, evento(grupo=True, chat="123@g.us")))
        self.assertFalse(servico.deve_ouvir(99, evento()))
        self.assertFalse(servico.deve_ouvir(CONTA, evento(chat="123@newsletter")))
        self.assertTrue(servico.deve_ouvir(CONTA, evento(chat="98765@lid")))
        with override_settings(ANTHROPIC_API_KEY=""):
            self.assertFalse(servico.deve_ouvir(CONTA, evento()))

    def test_responde_depois_da_espera_juntando_as_mensagens(self):
        self._chegou("Oi", msg_id="A")
        self._chegou("quanto custa o bot?", msg_id="B")
        claude = ClaudeFalso(resposta_do_claude("O Bot Standard sai R$ 49,90/mês. Quantos grupos você tem?"))
        with mock.patch.object(agente, "_cliente", return_value=claude):
            servico.uma_volta({CONTA: self.sessao})
            self.assertEqual(self.sessao.enviadas, [])  # ainda dentro da espera
            self._passar_a_espera()
            servico.uma_volta({CONTA: self.sessao})
        self.assertEqual(self.sessao.enviadas, [("5511999990000@s.whatsapp.net",
                                                 "O Bot Standard sai R$ 49,90/mês. Quantos grupos você tem?")])
        mensagens = claude.pedidos[0]["messages"]
        self.assertEqual(mensagens[0], {"role": "user", "content": "Oi\n\nquanto custa o bot?"})
        self.assertEqual(mensagens[-1]["role"], "system")  # contexto do dia e do nome, fora do cache
        self.assertEqual(claude.pedidos[0]["system"][0]["cache_control"]["type"], "ephemeral")
        conversa = Conversa.objects.get()
        self.assertEqual((conversa.nome, conversa.telefone), ("Bia", "5511999990000"))
        self.assertFalse(conversa.mensagens.filter(autor=Mensagem.CLIENTE, respondida=False).exists())
        # O eco da própria resposta não conta como mensagem sua.
        servico.registrar(evento("O Bot Standard sai R$ 49,90/mês. Quantos grupos você tem?", minha=True, msg_id="ENVIO1"),
                          "O Bot Standard sai R$ 49,90/mês. Quantos grupos você tem?", False)
        self.assertEqual(Conversa.objects.get().estado, Conversa.IA)

    def test_chamar_humano_pausa_e_avisa_voce(self):
        self._chegou("Quero falar com uma pessoa sobre um reembolso")
        self._passar_a_espera()
        claude = ClaudeFalso(
            resposta_do_claude(ferramenta={"motivo": "Pedido de reembolso", "resumo": "Comprou ontem e quer reembolso."}),
            resposta_do_claude("Claro! O time do Appfiliado vai continuar o atendimento por aqui."),
        )
        with mock.patch.object(agente, "_cliente", return_value=claude):
            servico.uma_volta({CONTA: self.sessao})
        conversa = Conversa.objects.get()
        self.assertEqual(conversa.estado, Conversa.HUMANO)
        self.assertEqual(conversa.motivo_humano, "Pedido de reembolso")
        destinos = [d for d, _ in self.sessao.enviadas]
        self.assertEqual(destinos, ["5511999990000@s.whatsapp.net", "5545988887777@s.whatsapp.net"])
        self.assertIn("wa.me/5511999990000", self.sessao.enviadas[1][1])
        self.assertIn("Comprou ontem", self.sessao.enviadas[1][1])
        # Com a conversa pausada, a pessoa escreve de novo e o agente não responde.
        self._chegou("Alô?", msg_id="M2")
        self._passar_a_espera()
        servico.uma_volta({CONTA: self.sessao})
        self.assertEqual(len(self.sessao.enviadas), 2)

    def test_voce_responde_pelo_celular_e_devolve_com_o_comando(self):
        self._chegou("Oi")
        servico.registrar(evento("Oi, aqui é o Eduardo!", minha=True, msg_id="EU1"), "Oi, aqui é o Eduardo!", False)
        conversa = Conversa.objects.get()
        self.assertEqual(conversa.estado, Conversa.HUMANO)
        self.assertTrue(conversa.mensagens.filter(autor=Mensagem.VOCE).exists())
        self._chegou("Obrigado!", msg_id="M2")  # chegou enquanto você atendia
        servico.registrar(evento("#ia", minha=True, msg_id="EU2"), "#ia", False)
        self.assertEqual(Conversa.objects.get().estado, Conversa.IA)
        # Ao voltar, o agente não responde o que chegou enquanto você atendia...
        self._passar_a_espera()
        with mock.patch.object(agente, "_cliente") as cliente:
            servico.uma_volta({CONTA: self.sessao})
        cliente.assert_not_called()
        # ...só a próxima mensagem, e na hora (depois da espera de digitação).
        self._chegou("E o plano anual?", msg_id="M3")
        self._passar_a_espera()
        claude = ClaudeFalso(resposta_do_claude("O anual sai com 17% de desconto."))
        with mock.patch.object(agente, "_cliente", return_value=claude):
            servico.uma_volta({CONTA: self.sessao})
        self.assertEqual(self.sessao.enviadas[-1][1], "O anual sai com 17% de desconto.")

    def test_pausa_antiga_volta_pro_agente(self):
        Conversa.objects.create(chat="1@s.whatsapp.net", estado=Conversa.HUMANO,
                                humano_desde=timezone.now() - timedelta(hours=13))
        servico.uma_volta({CONTA: self.sessao})
        self.assertEqual(Conversa.objects.get().estado, Conversa.IA)

    def test_audio_recebe_aviso_sem_chamar_a_ia(self):
        self._chegou(audio=True)
        with mock.patch.object(agente, "_cliente") as cliente:
            servico.uma_volta({CONTA: self.sessao})
        cliente.assert_not_called()
        self.assertEqual(self.sessao.enviadas[0][1], servico.AVISO_SO_TEXTO)

    def test_falha_da_ia_nao_deixa_a_pessoa_sem_resposta(self):
        self._chegou("Oi")
        self._passar_a_espera()
        with mock.patch.object(agente, "_cliente", side_effect=RuntimeError("fora do ar")):
            servico.uma_volta({CONTA: self.sessao})
        self.assertEqual(self.sessao.enviadas[0][1], agente.RESPOSTA_DE_FALHA)
        self.assertEqual(Conversa.objects.get().estado, Conversa.HUMANO)

    def test_limite_de_respostas_no_dia(self):
        self._chegou("Oi")
        self._passar_a_espera()
        Conversa.objects.update(dia_das_respostas=timezone.localdate(), respostas_no_dia=servico.RESPOSTAS_POR_DIA)
        with mock.patch.object(agente, "_cliente") as cliente:
            servico.uma_volta({CONTA: self.sessao})
        cliente.assert_not_called()
        self.assertEqual(Conversa.objects.get().estado, Conversa.HUMANO)


class TestBaseDeConhecimento(TestCase):
    def test_tem_precos_links_e_a_api_da_shopee(self):
        texto = conhecimento.texto()
        for trecho in ("R$ 49,90", "R$ 89,90", "https://pay.zouti.com.br/checkout?poi=", "Quero ativar a API",
                       "affiliate.shopee.com.br/open_api", "Emissor NFS-e", "garantia" if "garantia" in texto else "7 dias"):
            self.assertIn(trecho, texto)
