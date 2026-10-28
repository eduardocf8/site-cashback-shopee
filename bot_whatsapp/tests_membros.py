from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from neonize.proto.Neonize_pb2 import JID, GroupInfo, GroupName, GroupParticipant

from licencas.models import ContaAppfiliado
from painel.models import ResultadoSubIdDiario
from painel.tests import BasePainel

from . import gerenciador as g
from . import membros
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, DiaMembros, GrupoMonitorado, LeituraMembros
from .tests import SessaoFalsa

AGORA = datetime(2026, 10, 28, 15, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
HOJE = date(2026, 10, 28)
GRUPOS = [
    {"jid": "1@g.us", "nome": "Achadinhos 1", "participantes": 1000, "tipo": "grupo", "admin": True},
    {"jid": "2@g.us", "nome": "Achadinhos 2", "participantes": 300, "tipo": "grupo"},
    {"jid": "9@newsletter", "nome": "Canal", "participantes": 5000, "tipo": "canal"},
]


def jid(usuario, servidor="g.us"):
    return JID(User=usuario, Server=servidor, Device=0, RawAgent=0, Integrator=0, IsEmpty=False)


def grupo_do_whatsapp(numero, nome, participantes, admin_numero=""):
    pessoas = [GroupParticipant(JID=jid(f"55119{i:08d}", "s.whatsapp.net")) for i in range(participantes)]
    if admin_numero:  # grupo com LID: o número do bot aparece no PhoneNumber
        pessoas.append(GroupParticipant(JID=jid("99", "lid"), PhoneNumber=jid(admin_numero, "s.whatsapp.net"), IsAdmin=True))
    return GroupInfo(JID=jid(numero), GroupName=GroupName(Name=nome), Participants=pessoas)


class TestMembros(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", modulos_cortesia="whatsapp")
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)

    def test_escolher_so_grupos_da_conexao_e_ate_500(self):
        self.assertEqual(membros.escolher(self.conta, ["1@g.us", "9@newsletter", "x@g.us", "1@g.us"], self.conexao), 1)
        grupo = GrupoMonitorado.objects.get()
        self.assertEqual((grupo.jid, grupo.nome, grupo.membros, grupo.admin, grupo.lido_em), ("1@g.us", "Achadinhos 1", 1000, True, None))
        self.assertEqual(membros.contas_para_ler(AGORA), [self.conta.pk])  # recém-escolhido: lê já

        membros.escolher(self.conta, ["2@g.us"], self.conexao)
        self.assertEqual(list(GrupoMonitorado.objects.values_list("jid", flat=True)), ["2@g.us"])

        muitos = [{"jid": f"{i}@g.us", "nome": f"G{i}", "participantes": 10, "tipo": "grupo"} for i in range(600)]
        self.conexao.grupos = muitos
        self.assertEqual(membros.escolher(self.conta, [m["jid"] for m in muitos], self.conexao), 500)

    def test_leitura_por_hora_e_entradas_e_saidas(self):
        membros.escolher(self.conta, ["1@g.us", "2@g.us"], self.conexao)
        membros.atualizar(self.conta.pk, {"1@g.us": {"membros": 1001, "nome": "Achadinhos 1", "admin": True}}, AGORA)
        um, dois = GrupoMonitorado.objects.get(jid="1@g.us"), GrupoMonitorado.objects.get(jid="2@g.us")
        self.assertEqual((um.membros, um.lido_em), (1001, AGORA))
        self.assertFalse(dois.no_grupo)  # não veio na leitura: o bot saiu do grupo
        self.assertEqual(LeituraMembros.objects.filter(grupo=um).count(), 1)
        self.assertEqual(DiaMembros.objects.get(grupo=um, dia=HOJE).membros, 1001)
        self.assertEqual(membros.contas_para_ler(AGORA + timedelta(minutes=30)), [])
        self.assertEqual(membros.contas_para_ler(AGORA + timedelta(minutes=61)), [self.conta.pk])

        membros.registrar_mudanca(self.conta.pk, "1@g.us", 3, 1, AGORA)
        membros.registrar_mudanca(self.conta.pk, "1@g.us", 0, 2, AGORA)
        membros.registrar_mudanca(self.conta.pk, "outro@g.us", 5, 0, AGORA)  # não monitorado: ignora
        dia = DiaMembros.objects.get(grupo=um, dia=HOJE)
        self.assertEqual((dia.entradas, dia.saidas, dia.membros), (3, 3, 1001))

        LeituraMembros.objects.update(em=AGORA - timedelta(days=3))
        membros.limpar(AGORA)
        self.assertFalse(LeituraMembros.objects.exists())

    def test_painel_variacao_lotacao_e_comissao_por_sub_id(self):
        membros.escolher(self.conta, ["1@g.us", "2@g.us"], self.conexao)
        um, dois = GrupoMonitorado.objects.get(jid="1@g.us"), GrupoMonitorado.objects.get(jid="2@g.us")
        GrupoMonitorado.objects.update(criado_em=AGORA - timedelta(days=40))
        LeituraMembros.objects.create(grupo=um, em=AGORA - timedelta(hours=25), membros=980)
        DiaMembros.objects.create(grupo=um, dia=HOJE - timedelta(days=8), membros=900)
        DiaMembros.objects.create(grupo=um, dia=HOJE, membros=1000, entradas=25, saidas=5)
        DiaMembros.objects.create(grupo=dois, dia=HOJE - timedelta(days=31), membros=350)
        ConfiguracaoOfertas.objects.create(conta=self.conta, sub_ids="grupos", sub_ids_por_grupo={"1@g.us": "vip"})
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=HOJE - timedelta(days=2), sub_id="vip", vendas=4,
                                            comissao_estimada=Decimal("50"))
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=HOJE - timedelta(days=40), sub_id="vip", vendas=1,
                                            comissao_estimada=Decimal("99"))  # mês passado: não conta

        dados = membros.painel(self.conta, AGORA)
        primeiro, segundo = dados["linhas"]
        self.assertEqual(primeiro["grupo"], um)  # o maior primeiro
        self.assertEqual((primeiro["var_24h"], primeiro["var_7d"], primeiro["var_30d"]), (20, 100, None))
        self.assertEqual((primeiro["entradas"], primeiro["saidas"]), (25, 5))
        self.assertEqual((primeiro["lotacao"], primeiro["quase_cheio"]), (98, True))
        self.assertEqual((primeiro["comissao"], primeiro["por_membro"]), (Decimal("50"), Decimal("0.05")))
        self.assertEqual((segundo["var_30d"], segundo["comissao"]), (-50, None))  # sem Sub ID próprio
        self.assertEqual((dados["total"], dados["var_24h"], dados["quase_cheios"], dados["tem_comissao"]), (1300, 20, 1, True))
        self.assertEqual(dados["serie"][-1], {"dia": HOJE, "membros": 1300})


@mock.patch.object(g, "Sessao", SessaoFalsa)
class TestGerenciadorLeMembros(TestCase):
    def setUp(self):
        SessaoFalsa.criadas = []
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", modulos_cortesia="whatsapp")
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", numero="5511988887777", grupos=GRUPOS)
        self.ger = g.Gerenciador()
        self.sessao = SessaoFalsa(self.ger.fila, self.conta.pk)
        self.sessao.conectada = True
        self.ger.sessoes[self.conta.pk] = self.sessao
        self.sessao.cliente.get_joined_groups.return_value = [
            grupo_do_whatsapp("1", "Achadinhos 1", 40, admin_numero="5511988887777"),
            grupo_do_whatsapp("2", "Achadinhos 2", 7),
        ]

    def test_le_uma_vez_por_hora_marca_admin_e_conta_quem_entrou(self):
        membros.escolher(self.conta, ["1@g.us", "2@g.us"], ConexaoWhatsApp.objects.get(conta=self.conta))
        self.ger.uma_volta()
        um = GrupoMonitorado.objects.get(jid="1@g.us")
        self.assertEqual((um.membros, um.admin), (41, True))
        self.assertEqual((GrupoMonitorado.objects.get(jid="2@g.us").admin), False)
        self.assertEqual(self.sessao.monitorados, {"1@g.us", "2@g.us"})
        self.ger.proxima_leitura_de_membros = 0.0
        self.ger.uma_volta()
        self.assertEqual(self.sessao.cliente.get_joined_groups.call_count, 1)  # já leu nesta hora

        self.ger.fila.put(("membros", self.conta.pk, ("1@g.us", 2, 1), self.sessao))
        self.ger.uma_volta()
        dia = DiaMembros.objects.get(grupo=um)
        self.assertEqual((dia.entradas, dia.saidas, dia.membros), (2, 1, 42))


class TestTelaDeMembros(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)

    def test_escolher_e_ver_os_grupos(self):
        html = self.client.get("/whatsapp/membros/").content.decode()
        self.assertIn("Escolha os grupos para acompanhar", html)
        self.assertIn('data-maximo="500"', html)
        self.assertIn("Achadinhos 1", html)
        self.assertNotIn("9@newsletter", html)  # canal não entra

        resposta = self.client.post("/whatsapp/membros/", {"grupos": ["1@g.us", "2@g.us"]})
        self.assertRedirects(resposta, "/whatsapp/membros/", fetch_redirect_response=False)
        html = self.client.get("/whatsapp/membros/").content.decode()
        self.assertIn("em 2 grupos", html)
        self.assertIn("1.300", html)
        self.assertIn("A primeira leitura sai em até 1 minuto.", html)
        self.assertIn("Dê um Sub ID próprio a ele", html)
        self.assertIn('href="/whatsapp/membros/"', html)  # a aba

        html = self.client.get("/whatsapp/membros/?escolher=1").content.decode()
        self.assertIn('value="1@g.us" checked', html)

    def test_sem_o_modulo_bloqueia(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertNotContains(self.client.get("/whatsapp/membros/"), "Escolha os grupos para acompanhar")
