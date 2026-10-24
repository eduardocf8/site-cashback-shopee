"""Sincronização do catálogo (ofertas/catalogo.py): guardar e atualizar por categoria,
rodada diária curta e semanal completa, remoção de quem sumiu e teto de produtos."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings

from links.shopee_client import ShopeeAPIError

from . import catalogo
from .models import BuscaCatalogo, CashbackMaximoCache, NomeCurtoCache, Oferta, SincronizacaoCatalogo
from .services import encurtar_nomes_pendentes

SP = ZoneInfo("America/Sao_Paulo")
TERCA = datetime(2026, 10, 20, 10, 0, tzinfo=SP)
CATEGORIAS = {100: "Beleza", 200: "Áudio"}
CREDENCIAIS = {"SHOPEE_AFFILIATE_APP_ID": "app", "SHOPEE_AFFILIATE_SECRET": "segredo"}


def node(item_id, preco="10.00", comissao="0.05", vendas=100, nome=None, categoria=100, extra="0"):
    return {"itemId": item_id, "productName": nome or f"Produto {item_id}", "priceMin": preco, "priceMax": preco,
            "commissionRate": comissao, "sellerCommissionRate": extra, "sales": vendas, "productCatIds": [categoria] if categoria else [],
            "productLink": f"https://shopee.com.br/p-i.1.{item_id}", "imageUrl": "", "shopName": "Loja"}


class FalsaShopee:
    """Feed geral: itens 1-3 (1 página). Categoria 100: 2 páginas (10-11, 12). Categoria 200: 20-21."""

    def __init__(self, falhar_em=None):
        self.chamadas = []
        self.falhar_em = falhar_em

    def __call__(self, pagina, limite=50, categoria=None):
        self.chamadas.append((categoria, pagina))
        if self.falhar_em is not None and categoria == self.falhar_em:
            raise ShopeeAPIError("fora do ar")
        paginas = {None: [[1, 2, 3]], 100: [[10, 11], [12]], 200: [[20, 21]]}[categoria]
        itens = paginas[pagina - 1] if pagina <= len(paginas) else []
        return {"nodes": [node(i, categoria=categoria or 100, vendas=1000 - i) for i in itens],
                "pageInfo": {"hasNextPage": pagina < len(paginas)}}


@override_settings(**CREDENCIAIS)
@mock.patch("ofertas.services.carregar_categorias_nivel1", return_value=CATEGORIAS)
class TestRodada(TestCase):
    def rodar(self, agora, shopee=None, voltas=10):
        shopee = shopee or FalsaShopee()
        with mock.patch.object(catalogo, "buscar_ofertas_produtos", side_effect=shopee):
            for _ in range(voltas):
                catalogo.avancar(agora)
        return shopee

    def test_primeira_rodada_e_completa_e_traz_todas_as_buscas(self, _):
        shopee = self.rodar(TERCA)
        estado = SincronizacaoCatalogo.objects.get()
        self.assertTrue(estado.completa)
        self.assertIsNotNone(estado.finalizada_em)
        self.assertEqual(sorted(Oferta.objects.values_list("item_id", flat=True)), [1, 2, 3, 10, 11, 12, 20, 21])
        self.assertEqual(shopee.chamadas, [(None, 1), (100, 1), (100, 2), (200, 1)])  # para no hasNextPage
        self.assertEqual(estado.ultima_completa, TERCA.date())
        self.assertEqual(Oferta.objects.get(item_id=20).categoria_nome, "Áudio")
        self.assertIsNotNone(CashbackMaximoCache.obter())

    def test_rodada_diaria_so_as_primeiras_paginas_e_so_depois_das_3h(self, _):
        self.rodar(TERCA)
        with mock.patch.object(catalogo, "PAGINAS_DIARIAS", 1):
            shopee = self.rodar(TERCA + timedelta(hours=15))  # 1h da manhã de quarta: ainda não
            self.assertEqual(shopee.chamadas, [])
            shopee = self.rodar(TERCA.replace(day=21, hour=3, minute=5))
        estado = SincronizacaoCatalogo.objects.get()
        self.assertFalse(estado.completa)
        self.assertEqual(shopee.chamadas, [(None, 1), (100, 1), (200, 1)])  # só a 1ª página de cada

    def test_segunda_feira_e_completa(self, _):
        self.rodar(TERCA)
        with mock.patch.object(catalogo, "PAGINAS_DIARIAS", 1):
            self.rodar(TERCA.replace(day=26, hour=4))  # segunda-feira
        self.assertTrue(SincronizacaoCatalogo.objects.get().completa)

    def test_atualiza_sem_trocar_o_id_e_tira_quem_sumiu(self, _):
        self.rodar(TERCA)
        fone = Oferta.objects.get(item_id=10)
        Oferta.objects.filter(item_id=20).update(visto_em=TERCA - timedelta(days=10))  # não veio há 10 dias
        Oferta.objects.create(item_id=999, nome="Da sincronização antiga", categoria_id=100, product_link="https://x.com")
        catalogo.finalizar_rodada(SincronizacaoCatalogo.objects.get(), TERCA)
        self.assertFalse(Oferta.objects.filter(item_id__in=[20, 999]).exists())  # 999: sem visto_em, na completa
        self.assertEqual(Oferta.objects.get(item_id=10).pk, fone.pk)

    def test_shopee_fora_do_ar_tenta_de_novo_e_nao_apaga_ninguem(self, _):
        Oferta.objects.create(item_id=999, nome="Antiga", categoria_id=100, product_link="https://x.com",
                              visto_em=TERCA - timedelta(days=30))
        shopee = self.rodar(TERCA, FalsaShopee(falhar_em=200), voltas=10)
        busca = BuscaCatalogo.objects.get(categoria_id=200)
        self.assertEqual((busca.falhas, busca.terminada), (3, True))
        self.assertEqual(shopee.chamadas.count((200, 1)), 3)
        self.assertIn("fora do ar", SincronizacaoCatalogo.objects.get().ultimo_erro)
        self.assertTrue(Oferta.objects.filter(item_id=999).exists())  # com falha, ninguém some por engano

    def test_teto_de_produtos_fica_com_os_mais_vendidos(self, _):
        with mock.patch.object(catalogo, "MAXIMO_OFERTAS", 5):
            self.rodar(TERCA)
        self.assertEqual(Oferta.objects.count(), 5)
        self.assertFalse(Oferta.objects.filter(item_id__in=[20, 21, 12]).exists())  # os de menos vendas

    @override_settings(SHOPEE_AFFILIATE_APP_ID="")
    def test_sem_credenciais_fica_parada_e_avisa(self, _):
        shopee = self.rodar(TERCA)
        self.assertEqual(shopee.chamadas, [])
        self.assertIn("SHOPEE_AFFILIATE_APP_ID", SincronizacaoCatalogo.objects.get().ultimo_erro)


class TestGuardarPagina(TestCase):
    @mock.patch("ofertas.services.carregar_categorias_nivel1", return_value=CATEGORIAS)
    def test_cria_atualiza_e_reaproveita_nome_curto(self, _):
        NomeCurtoCache.objects.create(item_id=1, nome_original="Fone Bluetooth Super Completo", nome_curto="Fone BT")
        catalogo.guardar_pagina([node(1, nome="Fone Bluetooth Super Completo"), node(2, categoria=None)], TERCA,
                                categoria_padrao=200)
        fone = Oferta.objects.get(item_id=1)
        self.assertEqual((fone.nome_curto, fone.preco_min, fone.visto_em), ("Fone BT", Decimal("10.00"), TERCA))
        self.assertEqual(Oferta.objects.get(item_id=2).categoria_nome, "Áudio")  # sem categoria: a da busca
        Oferta.objects.filter(item_id=2).update(nome_curto="Curto antigo")
        depois = TERCA + timedelta(days=1)
        catalogo.guardar_pagina([node(1, preco="8.00", nome="Fone Bluetooth Super Completo"),
                                 node(2, nome="Nome novo")], depois)
        fone.refresh_from_db()
        self.assertEqual((fone.preco_min, fone.nome_curto, fone.visto_em), (Decimal("8.00"), "Fone BT", depois))
        self.assertEqual(Oferta.objects.get(item_id=2).nome_curto, "Nome novo")  # nome mudou: curto refeito depois

    @mock.patch("ofertas.services.carregar_categorias_nivel1", return_value=CATEGORIAS)
    def test_guarda_a_comissao_extra_do_vendedor_e_atualiza(self, _):
        catalogo.guardar_pagina([node(1, comissao="0.10", extra="0.04"), node(2)], TERCA)
        self.assertEqual(Oferta.objects.get(item_id=1).percentual_comissao_extra, Decimal("0.04"))
        self.assertEqual(Oferta.objects.get(item_id=2).percentual_comissao_extra, 0)
        catalogo.guardar_pagina([node(1, comissao="0.10", extra="0")], TERCA + timedelta(days=1))  # a campanha acabou
        self.assertEqual(Oferta.objects.get(item_id=1).percentual_comissao_extra, 0)


class TestNomesCurtos(TestCase):
    def test_pega_os_mais_vendidos_pendentes_e_pula_quem_ja_tem_cache(self):
        for item_id, vendas in ((1, 10), (2, 500), (3, 300)):
            Oferta.objects.create(item_id=item_id, nome=f"Nome {item_id}", nome_curto=f"Nome {item_id}", vendas=vendas,
                                  categoria_id=1, product_link="https://x.com")
        NomeCurtoCache.objects.create(item_id=2, nome_original="Nome 2", nome_curto="Nome 2")  # Gemini devolveu igual
        with mock.patch("ofertas.gemini_client.encurtar_nomes", side_effect=lambda nomes: [f"Curto {n}" for n in nomes]) as gemini, \
                mock.patch("ofertas.services.TAMANHO_LOTE_GEMINI", 1):
            resultado = encurtar_nomes_pendentes(limite_lotes=1)
        self.assertEqual(resultado, {"pendentes_nesta_vez": 1})
        gemini.assert_called_once_with(["Nome 3"])  # o mais vendido que ainda falta
        self.assertEqual(Oferta.objects.get(item_id=3).nome_curto, "Curto Nome 3")
