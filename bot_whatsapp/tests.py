import base64
import io
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from neonize.proto.Neonize_pb2 import JID, GroupInfo, GroupName, NewsletterMetadata
from PIL import Image

from licencas.models import ContaAppfiliado
from painel.tests import BasePainel

from . import gerenciador as g
from . import servico
from .models import ConexaoWhatsApp, EnvioWhatsApp, EventoWhatsApp


def canal(numero, nome, papel, seguidores):
    meta = NewsletterMetadata()
    meta.ID.CopyFrom(JID(User=numero, Server="newsletter", Device=0, RawAgent=0, Integrator=0, IsEmpty=False))
    meta.ThreadMeta.Name.Text = nome
    meta.ThreadMeta.SubscriberCount = seguidores
    meta.ViewerMeta.Role = meta.ViewerMeta.DESCRIPTOR.fields_by_name["Role"].enum_type.values_by_name[papel].number
    return meta


class SessaoFalsa:
    """Faz o papel da Sessao (que fala com o WhatsApp de verdade) nos testes."""

    criadas = []

    def __init__(self, fila, conta_id, jid_b64="", novo=False):
        self.fila, self.conta_id, self.jid_b64, self.novo = fila, conta_id, jid_b64, novo
        self.conectada = False
        self.paradas = 0
        self.origens = set()
        self.canais_ao_vivo = {}
        eu = SimpleNamespace(PushName="Bia", JID=JID(
            User="5511988887777", Server="s.whatsapp.net", Device=12, RawAgent=0, Integrator=0, IsEmpty=False,
        ))
        self.cliente = mock.Mock()
        self.cliente.get_me.return_value = eu
        self.cliente.get_joined_groups.return_value = [
            GroupInfo(JID=JID(User="120363001", Server="g.us"), GroupName=GroupName(Name="Ofertas VIP")),
            GroupInfo(JID=JID(User="120363002", Server="g.us"), GroupName=GroupName(Name="achadinhos")),
        ]
        self.cliente.get_subscribed_newletters.return_value = [canal("111", "Canal da Bia", "OWNER", 5400),
                                                              canal("222", "Canal que sigo", "SUBSCRIBER", 90000),
                                                              canal("333", "Canal da equipe", "ADMIN", 300)]
        SessaoFalsa.criadas.append(self)

    def iniciar(self):
        pass

    def parar(self):
        self.paradas += 1

    @property
    def viva(self):
        return True

    def avisar(self, tipo, detalhe=""):
        if tipo == "conectou":
            self.conectada = True
        if tipo in ("caiu", "deslogou", "terminou"):
            self.conectada = False
        self.fila.put((tipo, self.conta_id, detalhe, self))


@mock.patch.object(g, "Sessao", SessaoFalsa)
class TestGerenciador(TestCase):
    def setUp(self):
        SessaoFalsa.criadas = []
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", modulos_cortesia="whatsapp")
        self.ger = g.Gerenciador()

    def conexao(self):
        return ConexaoWhatsApp.objects.get(conta=self.conta)

    def eventos(self):
        return list(EventoWhatsApp.objects.filter(conta=self.conta).order_by("id").values_list("tipo", flat=True))

    def conectar(self):
        servico.pedir_conexao(self.conta)
        self.ger.uma_volta()
        sessao = SessaoFalsa.criadas[-1]
        sessao.avisar("qr", "2@codigo1")
        self.ger.uma_volta()
        sessao.avisar("conectou")
        self.ger.uma_volta()
        return sessao

    def test_conectar_pelo_qr_guarda_numero_e_grupos(self):
        servico.pedir_conexao(self.conta)
        self.ger.uma_volta()
        sessao = SessaoFalsa.criadas[-1]
        self.assertTrue(sessao.novo)
        self.assertFalse(self.conexao().pedido_conectar)

        sessao.avisar("qr", "2@codigo1")
        self.ger.uma_volta()
        self.assertEqual((self.conexao().estado, self.conexao().qr_codigo), ("aguardando_qr", "2@codigo1"))

        sessao.avisar("conectou")
        self.ger.uma_volta()  # guarda o número e já busca os grupos
        conexao = self.conexao()
        self.assertEqual(conexao.estado, "conectado")
        self.assertEqual((conexao.numero, conexao.nome, conexao.qr_codigo), ("5511988887777", "Bia", ""))
        self.assertEqual(JID.FromString(base64.b64decode(conexao.jid)).Device, 12)
        # grupos primeiro, depois os canais; só posta onde é dono ou admin
        self.assertEqual([gr["nome"] for gr in conexao.grupos],
                         ["achadinhos", "Ofertas VIP", "Canal da Bia", "Canal da equipe", "Canal que sigo"])
        self.assertEqual(conexao.grupos[1]["jid"], "120363001@g.us")
        self.assertEqual(conexao.grupos[2], {"jid": "111@newsletter", "nome": "Canal da Bia", "participantes": 5400,
                                             "tipo": "canal", "pode_postar": True})
        self.assertFalse(conexao.grupos[4]["pode_postar"])
        self.assertFalse(conexao.pedido_grupos)
        self.assertEqual(self.eventos(), ["qr", "conectou"])

    def test_queda_e_volta_ficam_no_historico(self):
        sessao = self.conectar()
        sessao.avisar("caiu")
        self.ger.uma_volta()
        self.assertEqual(self.conexao().estado, "reconectando")
        sessao.avisar("conectou")
        self.ger.uma_volta()
        self.assertEqual(self.conexao().estado, "conectado")
        self.assertEqual(self.eventos(), ["qr", "conectou", "caiu", "reconectou"])

    def test_envia_texto_e_imagem_e_registra_erro(self):
        sessao = self.conectar()
        texto = EnvioWhatsApp.objects.create(conta=self.conta, destino="120363001@g.us", texto="Oi")
        foto = EnvioWhatsApp.objects.create(conta=self.conta, destino="120363001@g.us", texto="Oferta",
                                            imagem_url="https://exemplo.com/a.jpg")
        with mock.patch.object(g, "ESPACO_ENTRE_ENVIOS", 0):
            self.ger.uma_volta()  # uma mensagem por volta por número
            self.ger.uma_volta()
        destino = sessao.cliente.send_message.call_args.args[0]
        self.assertEqual((destino.User, destino.Server), ("120363001", "g.us"))
        sessao.cliente.send_image.assert_called_once()
        self.assertEqual(sessao.cliente.send_image.call_args.kwargs["caption"], "Oferta")
        texto.refresh_from_db()
        foto.refresh_from_db()
        self.assertEqual((texto.estado, foto.estado), ("enviado", "enviado"))

        sessao.cliente.send_message.side_effect = RuntimeError("não é participante")
        falha = EnvioWhatsApp.objects.create(conta=self.conta, destino="120363001@g.us", texto="Oi")
        with mock.patch.object(g, "ESPACO_ENTRE_ENVIOS", 0):
            self.ger.uma_volta()
        falha.refresh_from_db()
        self.assertEqual(falha.estado, "erro")
        self.assertIn("não é participante", falha.erro)

    def test_espaco_entre_mensagens_do_mesmo_numero(self):
        sessao = self.conectar()
        for _ in range(2):
            EnvioWhatsApp.objects.create(conta=self.conta, destino="120363001@g.us", texto="Oi")
        self.ger.uma_volta()
        self.ger.uma_volta()  # menos de 3 s depois: a segunda espera
        self.assertEqual(sessao.cliente.send_message.call_count, 1)
        self.ger.ultimo_envio[self.conta.pk] -= g.ESPACO_ENTRE_ENVIOS
        self.ger.uma_volta()
        self.assertEqual(sessao.cliente.send_message.call_count, 2)

    def test_previa_grande_em_grupo_e_canal(self):
        sessao = self.conectar()
        sessao.cliente.upload.return_value = mock.Mock(
            DirectPath="/v/t/abc", FileSHA256=b"s", FileEncSHA256=b"e", MediaKey=b"k",
        )
        for destino in ("120363001@g.us", "111@newsletter"):
            EnvioWhatsApp.objects.create(
                conta=self.conta, destino=destino, texto="Oferta boa\nhttps://s.shopee.com.br/abc", formato="previa",
                imagem_url="https://cf.shopee.com.br/file/1", produto="Fone Bluetooth", link_afiliado="https://s.shopee.com.br/abc",
            )
        quadrada = io.BytesIO()
        Image.new("RGB", (500, 500), "#c33").save(quadrada, "JPEG")
        resposta = mock.Mock(content=quadrada.getvalue())
        with mock.patch.object(g, "ESPACO_ENTRE_ENVIOS", 0), mock.patch("requests.get", return_value=resposta):
            self.ger.uma_volta()
            self.ger.uma_volta()
        sessao.cliente.send_image.assert_not_called()  # só o cartão, sem foto separada
        self.assertEqual(sessao.cliente.send_message.call_count, 2)
        for chamada in sessao.cliente.send_message.call_args_list:
            destino, mensagem = chamada.args
            previa = mensagem.extendedTextMessage
            self.assertEqual((previa.matchedText, previa.title), ("https://s.shopee.com.br/abc", "Fone Bluetooth"))
            self.assertEqual((previa.thumbnailWidth, previa.thumbnailHeight), (1200, 630))  # larga: cartão grande
            self.assertTrue(previa.JPEGThumbnail)
            if destino.Server == "newsletter":
                # canal não abre a imagem enviada à parte: só a miniatura (maior) dentro da mensagem
                self.assertEqual((previa.thumbnailDirectPath, previa.mediaKey), ("", b""))
                self.assertGreater(len(previa.JPEGThumbnail), 3000)
            else:
                self.assertEqual((previa.thumbnailDirectPath, previa.mediaKey), ("/v/t/abc", b"k"))
        self.assertEqual(sessao.cliente.upload.call_count, 1)  # só o grupo sobe a imagem
        self.assertEqual(list(EnvioWhatsApp.objects.values_list("estado", flat=True)), ["enviado", "enviado"])

    def test_previa_grande_sem_foto_ou_com_upload_falhando_ainda_envia(self):
        sessao = self.conectar()
        EnvioWhatsApp.objects.create(
            conta=self.conta, destino="120363001@g.us", texto="Oferta\nhttps://s.shopee.com.br/abc", formato="previa",
            produto="Fone", link_afiliado="https://s.shopee.com.br/abc",  # sem foto
        )
        self.ger.uma_volta()
        previa = sessao.cliente.send_message.call_args.args[1].extendedTextMessage
        self.assertEqual(previa.matchedText, "https://s.shopee.com.br/abc")  # prévia pequena, sem imagem
        self.assertEqual(previa.thumbnailWidth, 0)

        sessao.cliente.upload.side_effect = RuntimeError("sem rede")
        quadrada = io.BytesIO()
        Image.new("RGB", (300, 300), "#33c").save(quadrada, "JPEG")
        envio = EnvioWhatsApp.objects.create(
            conta=self.conta, destino="120363001@g.us", texto="Oferta 2\nhttps://s.shopee.com.br/xyz", formato="previa",
            produto="Tênis", link_afiliado="https://s.shopee.com.br/xyz", imagem_url="https://cf.shopee.com.br/file/2",
        )
        self.ger.ultimo_envio[self.conta.pk] -= g.ESPACO_ENTRE_ENVIOS
        with mock.patch("requests.get", return_value=mock.Mock(content=quadrada.getvalue())):
            self.ger.uma_volta()
        previa = sessao.cliente.send_message.call_args.args[1].extendedTextMessage
        self.assertEqual((previa.thumbnailWidth, previa.thumbnailDirectPath), (1200, ""))  # só a miniatura
        envio.refresh_from_db()
        self.assertEqual(envio.estado, "enviado")

    def test_canal_recebe_texto_com_previa_do_link(self):
        sessao = self.conectar()
        envio = EnvioWhatsApp.objects.create(
            conta=self.conta, destino="111@newsletter", texto="Oferta boa\n🛒 Compre aqui:\nhttps://s.shopee.com.br/abc",
            imagem_url="https://cf.shopee.com.br/file/1", produto="Fone Bluetooth", link_afiliado="https://s.shopee.com.br/abc",
        )
        with mock.patch.object(g, "miniatura", return_value=b"jpeg") as foto:
            self.ger.uma_volta()
        foto.assert_called_once_with("https://cf.shopee.com.br/file/1")
        sessao.cliente.send_image.assert_not_called()
        destino, mensagem = sessao.cliente.send_message.call_args.args
        self.assertEqual((destino.User, destino.Server), ("111", "newsletter"))
        previa = mensagem.extendedTextMessage
        self.assertEqual((previa.matchedText, previa.title, previa.JPEGThumbnail), ("https://s.shopee.com.br/abc", "Fone Bluetooth", b"jpeg"))
        self.assertIn("Oferta boa", previa.text)
        envio.refresh_from_db()
        self.assertEqual(envio.estado, "enviado")

    def test_previa_sem_link_vira_texto_simples(self):
        envio = EnvioWhatsApp(texto="Só um aviso", destino="1@newsletter")
        self.assertEqual(g.mensagem_com_previa(envio).conversation, "Só um aviso")

    def test_envio_desiste_se_ficar_muito_tempo_sem_conexao(self):
        envio = EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", texto="Oi")
        self.ger.uma_volta()
        envio.refresh_from_db()
        self.assertEqual(envio.estado, "pendente")
        EnvioWhatsApp.objects.filter(pk=envio.pk).update(criado_em=timezone.now() - timedelta(minutes=11))
        self.ger.uma_volta()
        envio.refresh_from_db()
        self.assertEqual(envio.estado, "erro")

    def test_desconectar_pelo_painel_faz_logout(self):
        sessao = self.conectar()
        servico.pedir_desconexao(self.conta)
        self.ger.uma_volta()
        sessao.cliente.logout.assert_called_once()
        conexao = self.conexao()
        self.assertEqual((conexao.estado, conexao.jid, conexao.grupos), ("desconectado", "", []))
        self.assertNotIn(self.conta.pk, self.ger.sessoes)

    def test_desconectado_pelo_celular(self):
        sessao = self.conectar()
        sessao.avisar("deslogou", "401")
        self.ger.uma_volta()
        conexao = self.conexao()
        self.assertEqual((conexao.estado, conexao.jid), ("desconectado", ""))
        self.assertIn("desconectou este aparelho", conexao.erro)

    def test_qr_que_expira_volta_para_desconectado(self):
        servico.pedir_conexao(self.conta)
        self.ger.uma_volta()
        SessaoFalsa.criadas[-1].avisar("terminou")
        self.ger.uma_volta()
        conexao = self.conexao()
        self.assertEqual(conexao.estado, "desconectado")
        self.assertIn("expirou", conexao.erro)

    def test_sessao_que_para_sozinha_e_reaberta(self):
        sessao = self.conectar()
        sessao.avisar("terminou", "websocket fechado")
        self.ger.uma_volta()
        self.assertEqual(self.conexao().estado, "reconectando")
        self.assertEqual(len(SessaoFalsa.criadas), 1)
        self.ger.reabrir_em[self.conta.pk] = 0  # passou o tempo de espera
        self.ger.uma_volta()
        reaberta = SessaoFalsa.criadas[-1]
        self.assertIsNot(reaberta, sessao)
        self.assertEqual(reaberta.jid_b64, self.conexao().jid)
        self.assertFalse(reaberta.novo)

    def test_aviso_de_sessao_antiga_e_ignorado(self):
        antiga = self.conectar()
        servico.pedir_conexao(self.conta)  # gerou outro QR: a sessão antiga é trocada
        self.ger.uma_volta()
        self.assertEqual(antiga.paradas, 1)
        antiga.avisar("deslogou")
        self.ger.uma_volta()
        self.assertEqual(self.conexao().estado, "aguardando_qr")

    def test_ao_reiniciar_o_worker_retoma_as_sessoes(self):
        self.conectar()
        outra = ContaAppfiliado.objects.create(email="outra@exemplo.com")
        ConexaoWhatsApp.objects.create(conta=outra, estado="aguardando_qr", qr_codigo="2@velho")
        novo = g.Gerenciador()  # worker reiniciado (deploy)
        novo.retomar()
        retomada = SessaoFalsa.criadas[-1]
        self.assertEqual((retomada.conta_id, retomada.novo), (self.conta.pk, False))
        self.assertEqual(self.conexao().estado, "reconectando")
        self.assertEqual(ConexaoWhatsApp.objects.get(conta=outra).estado, "desconectado")

    def test_pede_o_minimo_de_historico_ao_conectar(self):
        props = g.propriedades_do_aparelho()
        self.assertEqual(props.os, "Appfiliado")
        self.assertFalse(props.requireFullSync)
        self.assertEqual(props.historySyncConfig.fullSyncDaysLimit, 1)
        self.assertEqual(props.historySyncConfig.recentSyncDaysLimit, 1)

    def test_limite_de_memoria_reinicia_o_processo_so_quando_falta(self):
        with mock.patch.dict("os.environ", {"GOMEMLIMIT": "300MiB"}), mock.patch("os.execve") as execve:
            g.garantir_limite_de_memoria(["manage.py", "sincronizar_painel", "--loop"])
        execve.assert_not_called()
        with mock.patch.dict("os.environ", {"GOMEMLIMIT": ""}), mock.patch("os.execve") as execve:
            g.garantir_limite_de_memoria(["manage.py", "sincronizar_painel", "--loop"])
        argv, ambiente = execve.call_args.args[1], execve.call_args.args[2]
        self.assertEqual(argv[1:], ["manage.py", "sincronizar_painel", "--loop"])
        self.assertEqual(ambiente["GOMEMLIMIT"], g.LIMITE_DE_MEMORIA_GO)

    def test_banco_da_sessao(self):
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://u:s@host/db"}, clear=False):
            self.assertEqual(g.endereco_do_banco(), "postgresql://u:s@host/db")
        with mock.patch.dict("os.environ", {"DATABASE_URL": "sqlite:///db.sqlite3", "WHATSAPP_DATABASE_URL": ""}):
            self.assertTrue(g.endereco_do_banco().endswith("whatsapp_sessoes.sqlite3"))


class TestServico(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com", modulos_cortesia="whatsapp")

    def conectada(self):
        conexao = servico.conexao_da(self.conta)
        conexao.estado = ConexaoWhatsApp.CONECTADO
        conexao.grupos = [{"jid": "1@g.us", "nome": "Ofertas"}]
        conexao.save()

    def test_enfileirar_valida_grupo_texto_e_limite(self):
        self.assertIsNone(servico.enfileirar_envio(self.conta, "1@g.us", "Oi")[0])  # desconectado
        self.conectada()
        self.assertEqual(servico.enfileirar_envio(self.conta, "2@g.us", "Oi")[1], "Escolha um dos seus grupos.")
        self.assertEqual(servico.enfileirar_envio(self.conta, "1@g.us", "  ")[1], "Escreva a mensagem.")
        for _ in range(servico.MAXIMO_NA_FILA):
            self.assertIsNotNone(servico.enfileirar_envio(self.conta, "1@g.us", "Oi")[0])
        self.assertIn("fila", servico.enfileirar_envio(self.conta, "1@g.us", "Oi")[1])
        self.assertEqual(EnvioWhatsApp.objects.first().destino_nome, "Ofertas")

    def test_qr_vira_svg_e_detecta_worker_parado(self):
        svg = servico.qr_svg("2@" + "A" * 230)  # o código de verdade é grande assim
        self.assertTrue(svg.startswith("<svg viewBox="))  # sem viewBox o navegador cortava o QR
        self.assertNotIn("width=", svg.split(">")[0])
        conexao = servico.pedir_conexao(self.conta)
        self.assertFalse(servico.worker_sem_resposta(conexao))
        conexao.qr_em = timezone.now() - timedelta(minutes=3)
        self.assertTrue(servico.worker_sem_resposta(conexao))


class TestTelaDoWhatsApp(BasePainel):
    def setUp(self):
        super().setUp()  # a conta de teste tem o módulo whatsapp de cortesia
        self.entrar()

    def test_menu_e_tela_desconectada(self):
        html = self.client.get("/").content.decode()
        self.assertIn('href="/whatsapp/"', html)
        self.assertIn("Conectar seu WhatsApp pelo QR Code", html)
        self.assertContains(self.client.get("/whatsapp/"), "Conectar WhatsApp")

    def test_conectar_mostra_o_qr(self):
        resposta = self.client.post("/whatsapp/conectar/")
        self.assertRedirects(resposta, "/whatsapp/", fetch_redirect_response=False)
        conexao = ConexaoWhatsApp.objects.get(conta=self.conta)
        self.assertTrue(conexao.pedido_conectar)
        self.assertContains(self.client.get("/whatsapp/"), "Gerando o QR Code")

        conexao.qr_codigo = "2@abc"
        conexao.save()
        self.assertContains(self.client.get("/whatsapp/"), "<svg")
        dados = self.client.get("/whatsapp/estado/").json()
        self.assertEqual(dados["estado"], "aguardando_qr")
        self.assertTrue(dados["qr"].startswith("<svg"))

    def test_conectado_mostra_numero_grupos_e_envia_teste(self):
        ConexaoWhatsApp.objects.create(
            conta=self.conta, estado="conectado", numero="5511988887777", conectado_em=timezone.now(),
            grupos=[{"jid": "1@g.us", "nome": "Ofertas VIP", "participantes": 3}],
        )
        html = self.client.get("/whatsapp/").content.decode()
        self.assertIn("+55 (11) 98888-7777", html)
        self.assertIn("Ofertas VIP (3 pessoas)", html)
        self.client.post("/whatsapp/enviar/", {"destino": "1@g.us", "texto": "Teste"})
        self.assertEqual(EnvioWhatsApp.objects.get().destino_nome, "Ofertas VIP")
        self.client.post("/whatsapp/desconectar/")
        self.assertTrue(ConexaoWhatsApp.objects.get(conta=self.conta).pedido_desconectar)
        html = self.client.get("/whatsapp/").content.decode()
        self.assertIn("Desconectando…", html)
        self.assertIn('data-desconectando="1"', html)  # a tela fica conferindo e recarrega sozinha
        self.assertTrue(self.client.get("/whatsapp/estado/").json()["desconectando"])

    def test_conta_sem_o_modulo_ve_o_convite(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertContains(self.client.get("/whatsapp/"), "Não incluso no seu plano")
        self.client.post("/whatsapp/conectar/")
        self.assertFalse(ConexaoWhatsApp.objects.exists())
        self.assertEqual(self.client.get("/whatsapp/estado/").status_code, 403)
