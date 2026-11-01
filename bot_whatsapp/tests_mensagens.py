"""Mensagens avulsas (aba Mensagens do Bot): disparo no worker e tela do painel."""

import io
from datetime import datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import conversor, cripto
from painel.tests import BasePainel

from . import mensagens, shopee_ofertas
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, MensagemAvulsa

SP = ZoneInfo("America/Sao_Paulo")
SEGUNDA_14H = datetime(2026, 10, 19, 14, 0, tzinfo=SP)
GRUPOS = [{"jid": "1@g.us", "nome": "Grupo VIP"}, {"jid": "2@g.us", "nome": "Achadinhos"}]


def link_falso(app_id, secret, url, sub_ids, ferramenta=""):
    return "https://s.shopee.com.br/afiliado-" + "-".join(sub_ids or ["sem"])


class TestDisparo(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now())
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.config = ConfiguracaoOfertas.objects.create(conta=self.conta, grupos=GRUPOS, sub_ids="grupos",
                                                         sub_ids_por_grupo={"1@g.us": "vip"})

    def criar(self, **extra):
        dados = {"conta": self.conta, "texto": "Live hoje às 20h! 🔥", "proxima_em": SEGUNDA_14H, **extra}
        return MensagemAvulsa.objects.create(**dados)

    def test_agora_vai_pra_todos_os_grupos_mesmo_com_as_ofertas_desligadas(self):
        m = self.criar()
        mensagens.uma_volta(SEGUNDA_14H)
        envios = list(EnvioWhatsApp.objects.order_by("id").values_list("destino", "texto", "origem", "estado"))
        self.assertEqual(envios, [("1@g.us", "Live hoje às 20h! 🔥", "mensagem", "pendente"),
                                  ("2@g.us", "Live hoje às 20h! 🔥", "mensagem", "pendente")])
        m.refresh_from_db()
        self.assertIsNone(m.proxima_em)  # não repete
        mensagens.uma_volta(SEGUNDA_14H + timedelta(minutes=1))
        self.assertEqual(EnvioWhatsApp.objects.count(), 2)

    @mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
    def test_links_da_shopee_viram_o_link_de_afiliado_de_cada_grupo(self, _link):
        self.criar(texto="Cupom do dia: https://shopee.com.br/produto-i.9.123 e o grupo: https://chat.whatsapp.com/abc")
        mensagens.uma_volta(SEGUNDA_14H)
        textos = dict(EnvioWhatsApp.objects.values_list("destino", "texto"))
        self.assertIn("https://s.shopee.com.br/afiliado-vip", textos["1@g.us"])
        self.assertIn("https://s.shopee.com.br/afiliado-grupos", textos["2@g.us"])
        self.assertIn("https://chat.whatsapp.com/abc", textos["1@g.us"])  # o outro link fica

    def test_semanal_agenda_a_proxima(self):
        m = self.criar(quando="semanal", dias_semana=[0, 3], hora=time(14, 0))
        mensagens.uma_volta(SEGUNDA_14H)
        m.refresh_from_db()
        self.assertEqual(timezone.localtime(m.proxima_em), datetime(2026, 10, 22, 14, 0, tzinfo=SP))  # quinta
        self.assertEqual(mensagens.descrever_quando(m), "Toda seg e qui às 14:00")

    def test_desconectado_espera_ate_1_hora_e_depois_registra_que_nao_foi(self):
        self.conexao.estado = "desconectado"
        self.conexao.save()
        m = self.criar()
        mensagens.uma_volta(SEGUNDA_14H + timedelta(minutes=50))
        self.assertEqual(EnvioWhatsApp.objects.count(), 0)
        mensagens.uma_volta(SEGUNDA_14H + timedelta(minutes=61))
        self.assertEqual(set(EnvioWhatsApp.objects.values_list("estado", flat=True)), {"erro"})
        self.assertIn("desconectado", EnvioWhatsApp.objects.first().erro)
        m.refresh_from_db()
        self.assertIsNone(m.proxima_em)

    def test_pausada_nao_sai_e_grupos_escolhidos(self):
        self.criar(pausada=True)
        self.criar(destino="grupos", grupos=["2@g.us"], texto="Só pro Achadinhos")
        mensagens.uma_volta(SEGUNDA_14H)
        self.assertEqual(list(EnvioWhatsApp.objects.values_list("destino", "texto")), [("2@g.us", "Só pro Achadinhos")])

    def test_nicho(self):
        self.config.modo_envio, self.config.nichos = "nicho", {"1@g.us": "100631"}
        self.config.save()
        self.criar(destino="nicho", nicho="100631")
        mensagens.uma_volta(SEGUNDA_14H)
        self.assertEqual(list(EnvioWhatsApp.objects.values_list("destino", flat=True)), ["1@g.us"])


def foto_png() -> bytes:
    from PIL import Image

    saida = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(saida, "PNG")
    return saida.getvalue()


class TestTelaDeMensagens(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        ConfiguracaoOfertas.objects.create(conta=self.conta, grupos=GRUPOS)

    def dados(self, **extra):
        return {"acao": "salvar", "texto": "Live hoje às 20h!", "destino": "todos", "quando": "agora", **extra}

    def test_aba_e_envio_agora_com_foto(self):
        html = self.client.get("/whatsapp/mensagens/").content.decode()
        self.assertIn(">Mensagens</a>", html)
        self.assertIn("Agendadas <span class=\"suave pequeno\">(0 de 20)</span>", html)
        self.assertNotIn('value="nicho"', html)  # sem envio por nicho na Automação

        resposta = self.client.post("/whatsapp/mensagens/", self.dados(
            foto_nova=SimpleUploadedFile("foto.png", foto_png(), content_type="image/png")))
        self.assertRedirects(resposta, "/whatsapp/mensagens/", fetch_redirect_response=False)
        m = MensagemAvulsa.objects.get()
        self.assertTrue(bytes(m.foto).startswith(b"\xff\xd8"))  # virou JPEG
        self.assertIsNotNone(m.proxima_em)
        self.assertEqual(self.client.get(f"/whatsapp/mensagens/{m.pk}/foto/")["Content-Type"], "image/jpeg")

    def test_agendar_semanal_editar_pausar_e_excluir(self):
        self.client.post("/whatsapp/mensagens/", self.dados(quando="semanal", dias_semana=["1", "3"], hora="20:00"))
        m = MensagemAvulsa.objects.get()
        self.assertEqual((m.dias_semana, m.hora), ([1, 3], time(20, 0)))
        html = self.client.get("/whatsapp/mensagens/").content.decode()
        self.assertIn("Toda ter e qui às 20:00 · Todos os grupos do bot (2 grupos)", html)

        self.client.post("/whatsapp/mensagens/", self.dados(pk=m.pk, texto="Texto novo", quando="semanal",
                                                             dias_semana=["1"], hora="21:00"))
        m.refresh_from_db()
        self.assertEqual((m.texto, m.dias_semana, MensagemAvulsa.objects.count()), ("Texto novo", [1], 1))

        self.client.post("/whatsapp/mensagens/", {"acao": "pausar", "pk": m.pk})
        m.refresh_from_db()
        self.assertTrue(m.pausada)
        self.client.post("/whatsapp/mensagens/", {"acao": "excluir", "pk": m.pk})
        self.assertFalse(MensagemAvulsa.objects.exists())

    def test_validacoes_e_limite_do_plano(self):
        resposta = self.client.post("/whatsapp/mensagens/", self.dados(quando="agendar", data="2020-01-01", hora_agendada="10:00"))
        self.assertContains(resposta, "Esse horário já passou.")
        resposta = self.client.post("/whatsapp/mensagens/", self.dados(destino="grupos"))
        self.assertContains(resposta, "Escolha pelo menos um grupo.")
        resposta = self.client.post("/whatsapp/mensagens/", self.dados(texto="  "))
        self.assertContains(resposta, "Escreva a mensagem.")

        for i in range(20):
            MensagemAvulsa.objects.create(conta=self.conta, texto=f"m{i}", quando="semanal", dias_semana=[1],
                                          hora=time(9, 0), proxima_em=timezone.now() + timedelta(days=1))
        resposta = self.client.post("/whatsapp/mensagens/", self.dados(), follow=True)
        self.assertContains(resposta, "o máximo do seu plano")
        self.assertEqual(MensagemAvulsa.objects.count(), 20)

    def test_nao_mexe_na_mensagem_de_outra_conta(self):
        outra = ContaAppfiliado.objects.create(email="outra@exemplo.com")
        m = MensagemAvulsa.objects.create(conta=outra, texto="dela", proxima_em=timezone.now() + timedelta(days=1))
        self.client.post("/whatsapp/mensagens/", {"acao": "excluir", "pk": m.pk})
        self.assertTrue(MensagemAvulsa.objects.filter(pk=m.pk).exists())
        self.assertEqual(self.client.get(f"/whatsapp/mensagens/{m.pk}/foto/").status_code, 404)
