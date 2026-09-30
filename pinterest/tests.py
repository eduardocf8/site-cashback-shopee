import csv
import io
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from ofertas.models import Oferta

from . import services, views
from .imagem import TAMANHO_PIN, gerar_imagem_pin_categoria

from ofertas.services import carregar_categorias_nivel1


def _criar_oferta(item_id, categoria_id, categoria_nome, vendas, nome=None):
    return Oferta.objects.create(
        item_id=item_id,
        nome=nome or f"Produto {item_id}",
        imagem_url=f"https://cf.shopee.com.br/file/{item_id}",
        preco_min=Decimal("10"),
        preco_max=Decimal("10"),
        percentual_comissao=Decimal("0.05"),
        vendas=vendas,
        categoria_id=categoria_id,
        categoria_nome=categoria_nome,
        product_link=f"https://shopee.com.br/produto-i.1.{item_id}",
    )


@override_settings(
    PINTEREST_SITE_URL="https://cash-b.com",
    PINTEREST_NOME_BOARD="Ofertas de {categoria} na Shopee",
    RENDER_EXTERNAL_HOSTNAME="cash-b.onrender.com",
)
class PlanilhaTests(TestCase):
    def setUp(self):
        _criar_oferta(1, 100, "Beleza", vendas=900)
        _criar_oferta(2, 200, "Casa e Decoração", vendas=500)
        _criar_oferta(3, 0, "", vendas=9999)  # sem categoria: nunca vira Pin

    def test_uma_linha_por_categoria_mais_vendida_primeiro(self):
        linhas = services.montar_linhas(quantidade=14, hoje=date(2026, 10, 1))
        self.assertEqual([l["Pinterest board"] for l in linhas], [
            "Ofertas de Beleza na Shopee", "Ofertas de Casa e Decoração na Shopee",
        ])

    def test_link_vai_pro_dominio_proprio_com_utm(self):
        linha = services.montar_linhas(hoje=date(2026, 10, 1))[0]
        link = urlparse(linha["Link"])
        self.assertEqual(link.netloc, "cash-b.com")
        self.assertEqual(link.path, reverse("ofertas_lista"))
        parametros = parse_qs(link.query)
        self.assertEqual(parametros["categoria"], ["100"])
        self.assertEqual(parametros["utm_source"], ["pinterest"])
        self.assertEqual(parametros["utm_campaign"], ["beleza"])

    def test_imagem_vai_pelo_host_do_render(self):
        linha = services.montar_linhas(hoje=date(2026, 10, 1))[0]
        self.assertTrue(linha["Media URL"].startswith("https://cash-b.onrender.com/pinterest/pin/100/20261001/"))

    def test_divulgacao_de_afiliado_e_titulo_no_limite(self):
        for linha in services.montar_linhas(hoje=date(2026, 10, 1)):
            self.assertIn("link de afiliado", linha["Description"])
            self.assertLessEqual(len(linha["Title"]), services.TITULO_MAXIMO)

    def test_agenda_a_partir_do_dia_seguinte_em_utc(self):
        linhas = services.montar_linhas(hoje=date(2026, 10, 1))
        # 12h e 20h de Brasília (UTC-3) do dia 2
        self.assertEqual([l["Publish date"] for l in linhas], ["2026-10-02T15:00:00", "2026-10-02T23:00:00"])

    def test_csv_tem_as_colunas_na_ordem(self):
        texto = services.gerar_csv(services.montar_linhas(hoje=date(2026, 10, 1)))
        leitor = csv.reader(io.StringIO(texto))
        self.assertEqual(next(leitor), services.COLUNAS_CSV)
        self.assertEqual(len(list(leitor)), 2)

    def test_planilha_so_para_staff(self):
        url = reverse("pinterest_planilha")
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user(
            username="dono", password="x", cpf="39053344705", is_staff=True,
        )
        self.client.force_login(staff)
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta["Content-Disposition"])

    def test_comando_imprime_o_csv(self):
        saida = io.StringIO()
        call_command("gerar_planilha_pinterest", stdout=saida)
        self.assertTrue(saida.getvalue().startswith(",".join(services.COLUNAS_CSV)))


class ImagemPinTests(TestCase):
    def setUp(self):
        self.categoria_id, self.nome = next(iter(carregar_categorias_nivel1().items()))
        for item_id in range(1, 7):
            _criar_oferta(item_id, self.categoria_id, self.nome, vendas=100 - item_id)
        self.pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta)

    def _url(self, assinatura=None):
        chave = "20261001"
        return reverse("pinterest_imagem_pin", kwargs={
            "categoria_id": self.categoria_id, "chave": chave,
            "assinatura": assinatura or services._assinatura(self.categoria_id, chave),
        })

    def test_assinatura_errada_da_404(self):
        self.assertEqual(self.client.get(self._url(assinatura="falsa")).status_code, 404)

    @patch("pinterest.imagem._baixar_imagem", return_value=Image.new("RGB", (50, 50), "red"))
    def test_gera_uma_vez_e_depois_serve_do_disco(self, baixar):
        with patch.object(views, "PASTA_PINS", self.pasta):
            resposta = self.client.get(self._url())
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta["Content-Type"], "image/jpeg")
            self.assertEqual(Image.open(io.BytesIO(b"".join(resposta.streaming_content))).size, TAMANHO_PIN)
            chamadas = baixar.call_count
            self.client.get(self._url())
        self.assertEqual(chamadas, 4)
        self.assertEqual(baixar.call_count, 4)  # segunda vez veio do disco

    def test_mesma_chave_escolhe_as_mesmas_fotos(self):
        primeira = services.escolher_fotos(self.categoria_id, "20261001")
        self.assertEqual(primeira, services.escolher_fotos(self.categoria_id, "20261001"))
        self.assertEqual(len(primeira), 4)

    def test_nao_repete_produto_com_mesmo_nome(self):
        Oferta.objects.all().delete()
        for item_id in range(1, 5):
            _criar_oferta(item_id, self.categoria_id, self.nome, vendas=10, nome="Mesmo produto")
        self.assertEqual(len(services.escolher_fotos(self.categoria_id, "20261001")), 1)

    @patch("pinterest.imagem._baixar_imagem", return_value=None)
    def test_arte_sem_foto_nao_quebra(self, _baixar):
        self.assertEqual(gerar_imagem_pin_categoria("Esportes e Atividades ao Ar Livre", []).size, TAMANHO_PIN)
