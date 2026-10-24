"""Comando explorar_limite_catalogo: mede quantos produtos cada busca da Shopee traz."""

import io
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from links import shopee_client


def falsa_api(query):
    """Feed geral: itens 1 a 120 (3 páginas de 50). Ordem 5: 60 a 180. "fone": 500 a 549."""
    pagina = int(query.split("page:")[1].split(",")[0])
    if "keyword" in query:
        faixa = range(500, 550)
    elif "productCatId" in query:
        categoria = int(query.split("productCatId:")[1].split(",")[0].split(")")[0])
        faixa = range(categoria * 1000, categoria * 1000 + 30)
    elif "sortType:5" in query:
        faixa = range(60, 181)
    else:
        faixa = range(1, 121)
    lista = list(faixa)
    nos = lista[(pagina - 1) * 50: pagina * 50]
    return {"productOfferV2": {"nodes": [{"itemId": i} for i in nos],
                               "pageInfo": {"hasNextPage": pagina * 50 < len(lista)}}}


@mock.patch("time.sleep")
@mock.patch.object(shopee_client, "executar_graphql", side_effect=falsa_api)
class TestExplorarCatalogo(SimpleTestCase):
    def rodar(self, *args):
        saida = io.StringIO()
        call_command("explorar_limite_catalogo", *args, stdout=saida)
        return saida.getvalue()

    def test_feed_geral_como_antes(self, api, _):
        saida = self.rodar()
        self.assertIn("feed geral: 120 produtos (fim em 3 página(s))", saida)
        self.assertIn("listType:0", api.call_args_list[0].args[0])

    def test_uma_busca_com_ordem_e_palavra(self, api, _):
        saida = self.rodar("--palavra", "fone", "--ordem", "2")
        self.assertIn("palavra 'fone', ordem 2 (mais vendidos): 50 produtos", saida)
        query = api.call_args_list[0].args[0]
        self.assertIn('keyword:"fone"', query)
        self.assertIn("sortType:2", query)
        self.assertNotIn("listType", query)

    def test_pacote_soma_os_produtos_unicos(self, api, _):
        saida = self.rodar("--pacote", "--palavras", "fone")
        self.assertIn("ordem 5 (maior comissão): 121 produtos (fim em 3 página(s)); 60 novos; 61 também estão no feed geral", saida)
        self.assertIn("Somando as 6 buscas: 230 produtos únicos, contra 120 do feed geral sozinho (+110)", saida)

    def test_teto_de_seguranca(self, api, _):
        saida = self.rodar("--max-paginas", "2")
        self.assertIn("parou no teto de 2 páginas com hasNextPage=True", saida)

    def test_categorias(self, api, _):
        with mock.patch("ofertas.services.carregar_categorias_nivel1", return_value={1: "Beleza", 2: "Áudio"}):
            saida = self.rodar("--categorias")
        self.assertIn("categoria 1 (Beleza): 30 produtos", saida)
        self.assertIn("Somando as 3 buscas: 180 produtos únicos, contra 120 do feed geral sozinho (+60)", saida)
        self.assertTrue(any("productCatId:2" in c.args[0] for c in api.call_args_list))
