from categorias_shopee import normalizar_texto, produto_pertence_as_categorias


class TestNormalizarTexto:
    def test_remove_acentos_e_baixa_caixa(self):
        assert normalizar_texto("Camiseta Básica Pólo") == "camiseta basica polo"

    def test_vazio(self):
        assert normalizar_texto(None) == ""
        assert normalizar_texto("") == ""

    def test_ja_normalizado_nao_muda(self):
        assert normalizar_texto("tenis esportivo") == "tenis esportivo"


class TestProdutoPertenceAsCategorias:
    def test_sem_categoria_selecionada_nao_filtra(self):
        assert produto_pertence_as_categorias("Qualquer Produto", []) is True
        assert produto_pertence_as_categorias("Qualquer Produto", None) is True

    def test_categoria_invalida_e_ignorada_e_nao_filtra(self):
        assert produto_pertence_as_categorias("Qualquer Produto", ["categoria-que-nao-existe"]) is True

    def test_produto_bate_com_categoria_moda(self):
        assert produto_pertence_as_categorias("Camiseta Masculina Slim", ["moda"]) is True

    def test_produto_nao_bate_com_categoria_moda(self):
        assert produto_pertence_as_categorias("Panela de Pressão 5L", ["moda"]) is False

    def test_nome_vazio_com_categoria_selecionada_nao_passa(self):
        assert produto_pertence_as_categorias("", ["moda"]) is False
        assert produto_pertence_as_categorias(None, ["moda"]) is False

    def test_comparacao_e_sem_acento_e_sem_caixa(self):
        # A palavra-chave "camiseta" deve bater mesmo com acentuação/caixa
        # diferentes no nome do produto vindo da API.
        assert produto_pertence_as_categorias("CAMISÉTA Premium", ["moda"]) is True
