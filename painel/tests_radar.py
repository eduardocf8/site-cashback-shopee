"""Radar de ofertas."""

from unittest import mock

from django.core.cache import cache
from django.utils import timezone

from bot_whatsapp import shopee_ofertas
from bot_whatsapp.models import ConexaoWhatsApp, EnvioWhatsApp, ProdutoAcompanhado
from bot_whatsapp.tests_ofertas import GRUPOS, produto

from . import radar
from .cripto import cifrar
from .tests import BasePainel

PRODUTOS = [
    produto(1, nome="Fone Bluetooth", preco=100.0, comissao=10.0, comissao_extra=4.0, desconto=30.0),
    produto(2, nome="Air Fryer 4L", preco=300.0, comissao=5.0, comissao_extra=0.0, desconto=10.0),
    produto(3, nome="Caneca térmica", preco=40.0, comissao=12.0, comissao_extra=0.0, desconto=50.0),
]


class TestFiltros(BasePainel):
    def test_le_os_filtros_e_ignora_lixo(self):
        f = radar.filtros_da_requisicao({"ordem": "maior_comissao", "preco_min": "R$ 1.234,50", "preco_max": "abc",
                                         "comissao_min": "200", "so_extra": "1", "categoria": "nao-existe"})
        self.assertEqual((f["ordem"], str(f["preco_min"]), f["preco_max"], f["comissao_min"], f["so_extra"], f["categoria"]),
                         ("maior_comissao", "1234.50", None, None, True, ""))
        self.assertEqual(radar.filtros_da_requisicao({"ordem": "x"})["ordem"], "mais_vendidos")


@mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=(list(PRODUTOS), True))
class TestTelaDoRadar(BasePainel):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.conta.shopee_app_id, self.conta.shopee_secret_cifrado = "123", cifrar("s")
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        self.entrar()

    def test_mostra_os_produtos_com_comissao_estimada(self, buscar):
        resposta = self.client.get("/radar/")
        self.assertContains(resposta, "Fone Bluetooth")
        self.assertContains(resposta, "~R$ 10,00")  # 10% de R$ 100,00
        self.assertContains(resposta, "+4% extra")
        self.assertContains(resposta, "Próxima ›")
        self.assertContains(resposta, 'href="/radar/"')  # no menu
        self.client.get("/radar/")
        self.assertEqual(buscar.call_count, 1)  # a mesma busca fica guardada

    def test_filtros(self, buscar):
        resposta = self.client.get("/radar/?so_extra=1")
        self.assertContains(resposta, "Fone Bluetooth")
        self.assertNotContains(resposta, "Air Fryer 4L")
        resposta = self.client.get("/radar/?desconto_min=40&ordem=maior_desconto&palavra=caneca")
        self.assertContains(resposta, "Caneca térmica")
        self.assertNotContains(resposta, "Fone Bluetooth")
        busca = buscar.call_args.args[2]
        self.assertEqual((busca.tipo_busca, busca.palavra_chave, busca.ordenacao), ("palavra_chave", "caneca", "maior_desconto"))

    def test_botoes_conforme_o_plano(self, _):
        resposta = self.client.get("/radar/")  # tem o Bot (sem WhatsApp conectado), não tem Carrosséis
        self.assertContains(resposta, "Conecte o WhatsApp para mandar daqui")
        self.assertContains(resposta, "Alerta</button>")
        self.assertContains(resposta, 'title="Gerar carrossel: dos Carrosséis"')
        self.conta.modulos_cortesia = "carrosseis"
        self.conta.save()
        resposta = self.client.get("/radar/")
        self.assertContains(resposta, 'title="Mandar no grupo: do Bot de WhatsApp"')
        self.assertContains(resposta, "Carrossel</button>")

    def test_copiar_link(self, _):
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x") as gerar:
            resposta = self.client.post("/radar/link/", {"link": "https://shopee.com.br/p-i.9.1"})
        self.assertEqual(resposta.json(), {"link": "https://s.shopee.com.br/x"})
        self.assertEqual(gerar.call_args.args[3], ["radar"])
        self.assertEqual(self.client.post("/radar/link/", {"link": "https://golpe.com/x"}).status_code, 400)

    def test_mandar_no_grupo_e_acompanhar(self, _):
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.assertContains(self.client.get("/radar/"), "Ofertas VIP")
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=PRODUTOS[0]), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x"):
            resposta = self.client.post("/radar/enviar/", {"item_id": "1", "destino": "1@g.us", "voltar": "/radar/?pagina=2"})
            self.assertEqual(resposta["Location"], "/radar/?pagina=2")
            self.client.post("/radar/acompanhar/", {"item_id": "1", "voltar": "https://golpe.com"})
        envio = EnvioWhatsApp.objects.get()
        self.assertEqual((envio.destino, envio.item_id, envio.origem), ("1@g.us", "1", "oferta"))
        self.assertIn("Fone Bluetooth", envio.texto)
        self.assertTrue(ProdutoAcompanhado.objects.filter(conta=self.conta, item_id="1").exists())
        self.assertContains(self.client.get("/radar/"), "✓ No alerta")

    def test_sem_o_bot_nao_manda(self, _):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.client.post("/radar/enviar/", {"item_id": "1", "destino": "1@g.us"})
        self.client.post("/radar/acompanhar/", {"item_id": "1"})
        self.assertFalse(EnvioWhatsApp.objects.exists())
        self.assertFalse(ProdutoAcompanhado.objects.exists())

    def test_sem_shopee_pede_para_conectar(self, buscar):
        self.conta.shopee_app_id = ""
        self.conta.save()
        self.assertContains(self.client.get("/radar/"), "Conecte sua conta da Shopee")
        buscar.assert_not_called()
