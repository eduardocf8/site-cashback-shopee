"""Radar de ofertas: busca no catálogo da cash-b (ofertas/catalogo.py)."""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from bot_whatsapp import shopee_ofertas
from bot_whatsapp.models import ConexaoWhatsApp, EnvioWhatsApp, ProdutoAcompanhado
from bot_whatsapp.tests_ofertas import GRUPOS, produto
from ofertas.models import Oferta, SincronizacaoCatalogo

from . import radar
from .cripto import cifrar
from .tests import BasePainel

BELEZA, AUDIO = 100630, 100535


def oferta(item_id, nome, preco, comissao, extra=0, desconto=0, vendas=100, categoria=AUDIO, avaliacao="4.8"):
    return Oferta.objects.create(
        item_id=item_id, nome=nome, nome_curto=nome, preco_min=Decimal(str(preco)), preco_max=Decimal(str(preco)),
        percentual_comissao=Decimal(str(comissao)), percentual_comissao_extra=Decimal(str(extra)),
        percentual_desconto=desconto, vendas=vendas, categoria_id=categoria, categoria_nome="x",
        avaliacao=Decimal(avaliacao), loja_nome="Loja", product_link=f"https://shopee.com.br/p-i.1.{item_id}",
        imagem_url=f"https://cf.shopee.com.br/file/{item_id}", visto_em=timezone.now(),
    )


class TestFiltros(BasePainel):
    def test_le_os_filtros_e_ignora_lixo(self):
        f = radar.filtros_da_requisicao({"ordem": "maior_comissao", "preco_min": "R$ 1.234,50", "preco_max": "abc",
                                         "comissao_min": "200", "so_extra": "1", "categoria": "999"})
        self.assertEqual((f["ordem"], str(f["preco_min"]), f["preco_max"], f["comissao_min"], f["so_extra"], f["categoria"]),
                         ("maior_comissao", "1234.50", None, None, True, ""))
        self.assertEqual(radar.filtros_da_requisicao({"ordem": "x"})["ordem"], "mais_vendidos")
        self.assertEqual(radar.filtros_da_requisicao({"categoria": str(AUDIO)})["categoria"], AUDIO)


class TestTelaDoRadar(BasePainel):
    def setUp(self):
        super().setUp()
        self.conta.shopee_app_id, self.conta.shopee_secret_cifrado = "123", cifrar("s")
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        oferta(1, "Fone Bluetooth JBL", 100, "0.1000", extra="0.0400", desconto=30, vendas=500)
        oferta(2, "Air Fryer 4L", 300, "0.0500", desconto=10, vendas=900, categoria=BELEZA)
        oferta(3, "Caneca térmica", 40, "0.1200", desconto=50, vendas=50, avaliacao="4.0")
        oferta(4, "Sem preço", 0, "0.2000")
        SincronizacaoCatalogo.objects.create(rodada=timezone.localdate(), finalizada_em=timezone.now())
        self.entrar()

    def nomes(self, consulta=""):
        html = self.client.get("/radar/" + consulta).content.decode()
        return [n for n in ("Fone Bluetooth JBL", "Air Fryer 4L", "Caneca térmica", "Sem preço") if n in html]

    def test_mostra_so_produtos_com_preco_com_comissao_de_referencia(self):
        resposta = self.client.get("/radar/")
        self.assertContains(resposta, "Comissão de referência 10%")
        self.assertContains(resposta, "~R$ 10,00")  # 10% de R$ 100,00
        self.assertContains(resposta, "+4% extra")
        self.assertContains(resposta, 'href="/radar/"')  # no menu
        self.assertEqual(self.nomes(), ["Fone Bluetooth JBL", "Air Fryer 4L", "Caneca térmica"])  # mais vendidos primeiro? ver ordem
        self.assertNotContains(resposta, "atrasada")
        self.assertContains(resposta, "3 produtos da Shopee")

    def test_ordens(self):
        def ordem(consulta):
            html = self.client.get("/radar/" + consulta).content.decode()
            return sorted(("Fone Bluetooth JBL", "Air Fryer 4L", "Caneca térmica"), key=html.index)
        self.assertEqual(ordem(""), ["Air Fryer 4L", "Fone Bluetooth JBL", "Caneca térmica"])  # vendas
        self.assertEqual(ordem("?ordem=maior_comissao"), ["Caneca térmica", "Fone Bluetooth JBL", "Air Fryer 4L"])
        self.assertEqual(ordem("?ordem=maior_desconto"), ["Caneca térmica", "Fone Bluetooth JBL", "Air Fryer 4L"])

    def test_filtros(self):
        self.assertEqual(self.nomes("?so_extra=1"), ["Fone Bluetooth JBL"])
        self.assertEqual(self.nomes("?palavra=caneca"), ["Caneca térmica"])
        self.assertEqual(self.nomes("?palavra=fone+bluetooth"), ["Fone Bluetooth JBL"])  # todas as palavras, em qualquer ordem
        self.assertEqual(self.nomes(f"?categoria={BELEZA}"), ["Air Fryer 4L"])
        self.assertEqual(self.nomes("?comissao_min=10"), ["Fone Bluetooth JBL", "Caneca térmica"])
        self.assertEqual(self.nomes("?desconto_min=40"), ["Caneca térmica"])
        self.assertEqual(self.nomes("?preco_min=50&preco_max=200"), ["Fone Bluetooth JBL"])
        self.assertEqual(self.nomes("?avaliacao_min=4,5"), ["Fone Bluetooth JBL", "Air Fryer 4L"])
        self.assertContains(self.client.get("/radar/?palavra=nada-disso"), "Nenhum produto encontrado")

    def test_vinte_e_quatro_por_pagina_com_numeracao(self):
        for i in range(10, 60):
            oferta(i, f"Produto {i}", 10, "0.0500", vendas=1000 + i)
        resposta = self.client.get("/radar/")
        self.assertContains(resposta, "Mostrando 1–24 de 53")
        resposta = self.client.get("/radar/?pagina=3")
        self.assertContains(resposta, "Mostrando 49–53 de 53")
        self.assertContains(resposta, 'aria-label="Página anterior"')
        self.assertEqual(self.client.get("/radar/?pagina=99").status_code, 200)  # página fora do fim vira a última

    def test_avisa_quando_o_catalogo_esta_atrasado(self):
        SincronizacaoCatalogo.objects.update(finalizada_em=timezone.now() - timedelta(days=3))
        self.assertContains(self.client.get("/radar/"), "A atualização dos produtos está atrasada")

    def test_botoes_conforme_o_plano(self):
        resposta = self.client.get("/radar/")  # tem o Bot (sem WhatsApp conectado), não tem Carrosséis
        self.assertContains(resposta, "Conecte o WhatsApp para mandar daqui")
        self.assertContains(resposta, "Alerta</button>")
        self.assertContains(resposta, 'title="Gerar carrossel: dos Carrosséis"')
        self.conta.modulos_cortesia = "carrosseis"
        self.conta.save()
        resposta = self.client.get("/radar/")
        self.assertContains(resposta, 'title="Mandar no grupo: do Bot de WhatsApp"')
        self.assertContains(resposta, "Carrossel</button>")

    def test_depois_do_lancamento_o_botao_cria_o_post_no_estudio(self):
        self.conta.modulos_cortesia = "carrosseis"
        self.conta.save()
        with self.settings(APPFILIADO_LANCAMENTO_INSTAGRAM=True):
            resposta = self.client.get("/radar/")
        self.assertContains(resposta, 'action="/estudio/novo/"')
        self.assertContains(resposta, 'name="como" value="produto"')
        self.assertContains(resposta, "Post</button>")
        self.assertNotContains(resposta, "Carrossel</button>")
        self.conta.modulos_cortesia = ""
        self.conta.save()
        with self.settings(APPFILIADO_LANCAMENTO_INSTAGRAM=True):
            self.assertContains(self.client.get("/radar/"), 'title="Criar post: do Estúdio Instagram"')

    def test_copiar_link(self):
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x") as gerar:
            resposta = self.client.post("/radar/link/", {"link": "https://shopee.com.br/p-i.9.1"})
        self.assertEqual(resposta.json(), {"link": "https://s.shopee.com.br/x"})
        self.assertEqual(gerar.call_args.args[3], ["radar"])
        self.assertEqual(self.client.post("/radar/link/", {"link": "https://golpe.com/x"}).status_code, 400)

    def test_mandar_no_grupo_e_acompanhar_consultam_o_preco_de_agora(self):
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.assertContains(self.client.get("/radar/"), "Ofertas VIP")
        agora = produto(1, nome="Fone Bluetooth JBL", preco=89.9)  # a Shopee já está com outro preço
        with mock.patch.object(shopee_ofertas, "buscar_produto_por_item", return_value=agora), \
                mock.patch.object(shopee_ofertas, "gerar_link_afiliado", return_value="https://s.shopee.com.br/x"):
            resposta = self.client.post("/radar/enviar/", {"item_id": "1", "destino": "1@g.us", "voltar": "/radar/?pagina=2"})
            self.assertEqual(resposta["Location"], "/radar/?pagina=2")
            self.client.post("/radar/acompanhar/", {"item_id": "1", "voltar": "https://golpe.com"})
        envio = EnvioWhatsApp.objects.get()
        self.assertEqual((envio.destino, envio.item_id, envio.origem), ("1@g.us", "1", "oferta"))
        self.assertIn("R$ 89,90", envio.texto)
        self.assertEqual(ProdutoAcompanhado.objects.get(conta=self.conta, item_id="1").preco_inicial, Decimal("89.90"))
        self.assertContains(self.client.get("/radar/"), "✓ No alerta")

    def test_sem_o_bot_nao_manda(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.client.post("/radar/enviar/", {"item_id": "1", "destino": "1@g.us"})
        self.client.post("/radar/acompanhar/", {"item_id": "1"})
        self.assertFalse(EnvioWhatsApp.objects.exists())
        self.assertFalse(ProdutoAcompanhado.objects.exists())

    def test_sem_shopee_pede_para_conectar(self):
        self.conta.shopee_app_id = ""
        self.conta.save()
        self.assertContains(self.client.get("/radar/"), "Conecte sua conta da Shopee")
