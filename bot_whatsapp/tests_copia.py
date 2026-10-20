import os
import queue
import tempfile
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from neonize.events import EVENT_TO_INT, MessageEv
from neonize.proto.Neonize_pb2 import JID
from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message

from licencas.models import ContaAppfiliado
from painel import cripto
from painel.tests import BasePainel

from . import copia, ofertas
from . import gerenciador as g
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, OfertaRecebida
from .tests import SessaoFalsa
from .tests_ofertas import AGORA, GRUPOS, link_falso, produto

TEXTO = (
    "🔥 Fone Bluetooth TWS com cancelamento de ruído\nDe R$ 199,90\nPor R$ 59,90\n"
    "👉 https://s.shopee.com.br/AbC123?utm=outro_afiliado\nCorre!"
)


def jid(usuario, servidor):
    return JID(User=usuario, Server=servidor, Device=0, RawAgent=0, Integrator=0, IsEmpty=False)


def mensagem_recebida(chat="555@g.us", texto=TEXTO, foto=False, minha=False, msg_id="ABC1"):
    ev = MessageEv()
    usuario, servidor = chat.split("@")
    ev.Info.MessageSource.Chat.CopyFrom(jid(usuario, servidor))
    ev.Info.MessageSource.Sender.CopyFrom(jid("5511999990000", "s.whatsapp.net"))
    ev.Info.MessageSource.IsFromMe = minha
    ev.Info.MessageSource.IsGroup = True
    ev.Info.ID = msg_id
    if foto:
        ev.Message.imageMessage.caption = texto
    else:
        ev.Message.conversation = texto
    return ev


class TestLeituraDaMensagem(TestCase):
    def test_links_da_shopee(self):
        texto = "Veja https://s.shopee.com.br/AbC). e https://amazon.com/x e https://shopee.com.br/p-i.1.2?x=1"
        self.assertEqual(copia.links_shopee(texto), ["https://s.shopee.com.br/AbC", "https://shopee.com.br/p-i.1.2?x=1"])
        self.assertEqual(copia.links_shopee("sem link"), [])

    def test_link_sem_https(self):
        self.assertEqual(copia.links_shopee("Corre: s.shopee.com.br/AbC123."), ["https://s.shopee.com.br/AbC123"])
        self.assertEqual(copia.links_shopee("shopee.com.br/produto-i.1.2"), ["https://shopee.com.br/produto-i.1.2"])

    def test_mensagem_embrulhada(self):
        temporaria = Message()
        temporaria.ephemeralMessage.message.imageMessage.caption = "oferta s.shopee.com.br/x"
        self.assertEqual(copia.texto_da_mensagem(temporaria), "oferta s.shopee.com.br/x")
        self.assertTrue(copia.tem_foto(temporaria))
        do_outro_aparelho = Message()
        do_outro_aparelho.deviceSentMessage.message.extendedTextMessage.text = "texto https://shope.ee/a"
        self.assertEqual(copia.texto_da_mensagem(do_outro_aparelho), "texto https://shope.ee/a")

    def test_texto_da_mensagem(self):
        self.assertEqual(copia.texto_da_mensagem(Message(conversation="oi")), "oi")
        legenda = Message()
        legenda.imageMessage.caption = "legenda"
        self.assertEqual(copia.texto_da_mensagem(legenda), "legenda")
        self.assertTrue(copia.tem_foto(legenda))
        com_previa = Message()
        com_previa.extendedTextMessage.text = "texto com prévia"
        self.assertEqual(copia.texto_da_mensagem(com_previa), "texto com prévia")

    def test_preparar_usa_o_link_limpo_do_produto(self):
        with mock.patch.object(copia, "identificar_produto", return_value="22"), \
                mock.patch.object(copia.shopee_ofertas, "buscar_produto_por_item", return_value=produto(22)):
            oferta = copia.preparar("id", "s", TEXTO)
        self.assertEqual((oferta["item_id"], oferta["link_origem"]), ("22", "https://shopee.com.br/p-i.9.22"))

        with mock.patch.object(copia, "identificar_produto", return_value=""):
            oferta = copia.preparar("id", "s", TEXTO)
        self.assertEqual(oferta["link_origem"], "https://s.shopee.com.br/AbC123?utm=outro_afiliado")
        self.assertTrue(copia.chave_do_produto("", oferta["link_origem"]).startswith("link:"))
        with self.assertRaises(ValueError):
            copia.preparar("id", "s", "sem link nenhum")


@mock.patch.object(ofertas.shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
@mock.patch.object(copia, "identificar_produto", return_value="22")
@mock.patch.object(copia.shopee_ofertas, "buscar_produto_por_item", return_value=produto(22, nome="Fone TWS"))
class TestMotorCopiando(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp_premium", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, modo="copiar", origens=[{"jid": "555@g.us", "nome": "Ofertas do Zé"}],
            grupos=GRUPOS, intervalo_minutos=0, sub_ids="copia",
        )
        self.motor = ofertas.Motor()

    def receber(self, **campos):
        dados = {"conta": self.conta, "mensagem_id": f"m{OfertaRecebida.objects.count()}", "origem": "555@g.us",
                 "origem_nome": "Ofertas do Zé", "texto": TEXTO}
        dados.update(campos)
        recebida = OfertaRecebida.objects.create(**dados)
        # A mensagem chegou um minuto antes da volta do motor (senão já estaria vencida).
        OfertaRecebida.objects.filter(pk=recebida.pk).update(recebida_em=AGORA - timedelta(minutes=1))
        recebida.refresh_from_db()
        return recebida

    def rodar(self, agora=AGORA):
        self.motor.uma_volta(agora)
        self.config.refresh_from_db()

    def test_repassa_com_o_link_da_conta(self, *_):
        recebida = self.receber(imagem_arquivo="/tmp/foto.jpg")
        self.rodar()
        envios = list(EnvioWhatsApp.objects.order_by("destino"))
        self.assertEqual([e.destino for e in envios], ["1@g.us", "2@g.us"])
        envio = envios[0]
        self.assertEqual(envio.link_afiliado, "https://s.shopee.com.br/2-copia")  # gerado do link limpo do produto
        self.assertIn("🛒 Compre aqui:\nhttps://s.shopee.com.br/2-copia", envio.texto)
        self.assertNotIn("outro_afiliado", envio.texto)  # o link de quem postou sai do texto
        self.assertEqual((envio.imagem_arquivo, envio.imagem_url, envio.item_id), ("/tmp/foto.jpg", "", "22"))
        recebida.refresh_from_db()
        self.assertEqual((recebida.estado, recebida.produto), ("enviada", "Fone TWS"))
        self.assertEqual(self.config.proximo_envio_em, AGORA)  # intervalo 0: a próxima pode sair já

    def test_mensagem_que_outro_processo_ja_pegou_nao_e_repassada_de_novo(self, *_):
        recebida = self.receber()
        OfertaRecebida.objects.filter(pk=recebida.pk).update(processada_em=AGORA)  # o outro worker pegou
        self.rodar()
        self.assertEqual(EnvioWhatsApp.objects.count(), 0)
        recebida.refresh_from_db()
        self.assertEqual(recebida.estado, "pendente")
        self.rodar(AGORA + timedelta(minutes=70))  # se o outro travou, vence como as demais
        recebida.refresh_from_db()
        self.assertEqual(recebida.estado, "ignorada")

    def test_sem_foto_na_mensagem_usa_a_do_produto(self, *_):
        self.receber()
        self.rodar()
        self.assertEqual(EnvioWhatsApp.objects.first().imagem_url, "https://cf.shopee.com.br/file/22")

    def test_nao_repete_o_mesmo_produto(self, *_):
        self.receber()
        self.rodar()
        segunda = self.receber()
        self.rodar(AGORA + timedelta(minutes=1))
        segunda.refresh_from_db()
        self.assertEqual(segunda.estado, "ignorada")
        self.assertIn("Já foi para todos os grupos", segunda.motivo)
        self.assertEqual(EnvioWhatsApp.objects.count(), 2)

    def test_intervalo_e_oferta_velha(self, *_):
        self.config.intervalo_minutos = 10
        self.config.save()
        self.receber()
        self.rodar()
        espera = self.receber()
        self.rodar(AGORA + timedelta(minutes=5))  # antes do intervalo: fica na fila
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "pendente")
        self.rodar(AGORA + timedelta(minutes=70))  # passou de 1 hora na fila
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "ignorada")

    def test_erro_numa_mensagem_nao_trava_a_fila(self, buscar, identificar, link):
        ruim = self.receber(texto="sem link da shopee aqui")
        self.rodar()
        ruim.refresh_from_db()
        self.assertEqual(ruim.estado, "erro")
        boa = self.receber()
        self.rodar()
        boa.refresh_from_db()
        self.assertEqual(boa.estado, "enviada")

    def test_sem_mensagens_espera(self, *_):
        self.rodar()
        self.assertEqual(self.config.situacao, "Esperando ofertas nos grupos e canais de origem.")


class TestGerenciadorCopiando(TestCase):
    def setUp(self):
        patcher = mock.patch.object(g, "Sessao", SessaoFalsa)
        patcher.start()
        self.addCleanup(patcher.stop)
        SessaoFalsa.criadas = []
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", modulos_cortesia="whatsapp")
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado")
        ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, modo="copiar", origens=[{"jid": "555@g.us", "nome": "Ofertas do Zé"}],
        )
        self.ger = g.Gerenciador()
        self.sessao = self.ger.abrir(self.conta.pk, novo=True)
        self.pasta = tempfile.mkdtemp()

    def test_ouve_as_origens_e_guarda_a_oferta_com_a_foto(self):
        self.ger.uma_volta()
        self.assertEqual(self.sessao.origens, {"555@g.us"})
        self.sessao.cliente.download_any.return_value = b"jpeg-da-mensagem"
        with mock.patch.object(g, "PASTA_DAS_FOTOS", g.Path(self.pasta)):
            self.sessao.avisar("mensagem", mensagem_recebida(foto=True))
            self.sessao.avisar("mensagem", mensagem_recebida(foto=True))  # repetida: uma só
            self.ger.uma_volta()
        recebida = OfertaRecebida.objects.get()
        self.assertEqual((recebida.origem, recebida.origem_nome, recebida.estado), ("555@g.us", "Ofertas do Zé", "pendente"))
        self.assertIn("Fone Bluetooth", recebida.texto)
        with open(recebida.imagem_arquivo, "rb") as arquivo:
            self.assertEqual(arquivo.read(), b"jpeg-da-mensagem")

    def test_envia_a_foto_da_mensagem(self):
        caminho = os.path.join(self.pasta, "foto.jpg")
        with open(caminho, "wb") as arquivo:
            arquivo.write(b"jpeg")
        self.sessao.conectada = True
        EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", texto="Oferta", imagem_arquivo=caminho)
        self.ger.uma_volta()
        destino, foto = self.sessao.cliente.send_image.call_args.args
        self.assertEqual(foto, b"jpeg")

    def test_mensagem_sem_link_da_shopee_fica_como_ignorada(self):
        self.ger.uma_volta()
        self.sessao.avisar("mensagem", mensagem_recebida(texto="olha https://amazon.com.br/x", msg_id="Z1"))
        self.ger.uma_volta()
        recebida = OfertaRecebida.objects.get()
        self.assertEqual((recebida.estado, recebida.motivo), ("ignorada", "Sem link da Shopee na mensagem."))

    def test_acompanha_os_canais_de_origem_ao_vivo(self):
        ConfiguracaoOfertas.objects.update(origens=[{"jid": "555@g.us"}, {"jid": "88@newsletter"}])
        self.sessao.conectada = True
        self.sessao.cliente.newsletter_subscribe_live_updates.return_value = 300
        self.ger.uma_volta()
        self.assertEqual(self.sessao.cliente.newsletter_subscribe_live_updates.call_count, 1)
        jid = self.sessao.cliente.newsletter_subscribe_live_updates.call_args.args[0]
        self.assertEqual((jid.User, jid.Server), ("88", "newsletter"))
        self.ger.proxima_atualizacao_das_origens = 0
        self.ger.uma_volta()  # ainda vale: não pede de novo
        self.assertEqual(self.sessao.cliente.newsletter_subscribe_live_updates.call_count, 1)

    def test_desligar_o_modo_copiar_para_de_ouvir(self):
        self.ger.uma_volta()
        ConfiguracaoOfertas.objects.update(modo="shopee")
        self.ger.proxima_atualizacao_das_origens = 0
        self.ger.uma_volta()
        self.assertEqual(self.sessao.origens, set())


class TestFiltroDaSessaoDeVerdade(TestCase):
    """O filtro roda na thread da biblioteca para TODA mensagem: tem de ser rápido e só
    deixar passar as das origens com link ou foto (inclusive as do próprio número)."""

    def test_filtro(self):
        with mock.patch.object(g, "endereco_do_banco", return_value=os.path.join(tempfile.mkdtemp(), "s.sqlite3")):
            fila = queue.Queue()
            sessao = g.Sessao(fila, 1, novo=True)
        tratar = sessao.cliente.event.list_func[EVENT_TO_INT[MessageEv]]
        tratar(sessao.cliente, mensagem_recebida())  # ainda sem origens
        sessao.origens = {"555@g.us"}
        tratar(sessao.cliente, mensagem_recebida(chat="999@g.us"))  # outro grupo
        tratar(sessao.cliente, mensagem_recebida(texto="bom dia, grupo!"))  # conversa, sem link
        self.assertTrue(fila.empty())
        tratar(sessao.cliente, mensagem_recebida())
        tratar(sessao.cliente, mensagem_recebida(minha=True))  # postada pelo próprio número: vale
        tratar(sessao.cliente, mensagem_recebida(texto="olha https://amazon.com.br/x"))  # vai como ignorada
        self.assertEqual([fila.get_nowait()[0] for _ in range(3)], ["mensagem"] * 3)


class TestTelaCopiando(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.modulos_cortesia = "whatsapp_premium"  # os limites do Standard têm testes próprios
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS + [
            {"jid": "555@g.us", "nome": "Ofertas do Zé", "tipo": "grupo"},
            {"jid": "88@newsletter", "nome": "Canal que sigo", "tipo": "canal", "pode_postar": False},
        ])

    def dados(self, **extra):
        base = {
            "modo": "copiar", "origens": ["555@g.us", "88@newsletter"], "tipo_busca": "geral", "ordenacao": "mais_vendidos",
            "grupos": ["1@g.us"], "intervalo_minutos": "0", "horario_inicio": "07:00", "horario_fim": "23:00",
            "dias_semana": ["0", "1", "2", "3", "4", "5", "6"], "repetir_apos_dias": "7",
        }
        base.update(extra)
        return base

    def test_salvar_e_ligar_no_modo_copiar(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("Copiar de grupos e canais", html)
        self.assertIn('id="lista-origens"', html)
        self.assertNotIn('value="88@newsletter" id="id_grupos', html)  # canal só seguido não é destino

        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertRedirects(resposta, "/whatsapp/ofertas/", fetch_redirect_response=False)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((config.modo, config.intervalo_minutos), ("copiar", 0))
        self.assertEqual([o["nome"] for o in config.origens], ["Ofertas do Zé", "Canal que sigo"])
        self.client.post("/whatsapp/ofertas/ligar/")
        config.refresh_from_db()
        self.assertTrue(config.ativo)
        self.assertContains(self.client.get("/whatsapp/ofertas/"), "Ofertas recebidas")

    def test_validacoes(self):
        html = self.client.post("/whatsapp/ofertas/", self.dados(origens=[])).content.decode()
        self.assertIn("Escolha pelo menos um grupo ou canal para copiar.", html)
        html = self.client.post("/whatsapp/ofertas/", self.dados(origens=["1@g.us"])).content.decode()
        self.assertIn("não pode ser origem e destino ao mesmo tempo", html)
        html = self.client.post("/whatsapp/ofertas/", self.dados(modo="shopee")).content.decode()
        self.assertIn("o intervalo mínimo é 1 minuto", html)
        self.assertFalse(ConfiguracaoOfertas.objects.filter(conta=self.conta, modo="copiar").exists())
