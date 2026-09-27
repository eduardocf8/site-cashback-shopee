from parser import (
    eh_link_shopee,
    extrair_links,
    extrair_links_shopee,
    gerar_id_mensagem,
    limpar_link,
)


class TestLimparLink:
    def test_none_e_vazio_passam_direto(self):
        assert limpar_link(None) is None
        assert limpar_link("") == ""

    def test_remove_espacos_nas_pontas(self):
        assert limpar_link("  https://shopee.com.br/produto  ") == "https://shopee.com.br/produto"

    def test_remove_pontuacao_de_fechamento(self):
        assert limpar_link("https://shopee.com.br/produto.") == "https://shopee.com.br/produto"
        assert limpar_link("https://shopee.com.br/produto,") == "https://shopee.com.br/produto"
        assert limpar_link("https://shopee.com.br/produto)") == "https://shopee.com.br/produto"
        assert limpar_link("(https://shopee.com.br/produto)") == "(https://shopee.com.br/produto"

    def test_nao_mexe_em_link_ja_limpo(self):
        assert limpar_link("https://shopee.com.br/produto") == "https://shopee.com.br/produto"


class TestExtrairLinks:
    def test_vazio(self):
        assert extrair_links("") == []
        assert extrair_links(None) == []

    def test_extrai_um_link(self):
        assert extrair_links("confira: https://shopee.com.br/item-123!") == [
            "https://shopee.com.br/item-123"
        ]

    def test_extrai_varios_links(self):
        texto = "Opção 1: https://shopee.com.br/a e opção 2 https://exemplo.com/b."
        assert extrair_links(texto) == [
            "https://shopee.com.br/a",
            "https://exemplo.com/b",
        ]

    def test_texto_sem_link(self):
        assert extrair_links("promoção imperdível, corre lá!") == []


class TestEhLinkShopee:
    def test_dominios_conhecidos(self):
        assert eh_link_shopee("https://shopee.com.br/produto-123") is True
        assert eh_link_shopee("https://s.shopee.com.br/abc123") is True
        assert eh_link_shopee("https://shope.ee/abc") is True
        assert eh_link_shopee("https://shoope.top/abc") is True

    def test_case_insensitive(self):
        assert eh_link_shopee("HTTPS://SHOPEE.COM.BR/PRODUTO") is True

    def test_dominio_nao_shopee(self):
        assert eh_link_shopee("https://exemplo.com/produto") is False

    def test_vazio(self):
        assert eh_link_shopee("") is False
        assert eh_link_shopee(None) is False

    def test_sem_esquema_ainda_reconhece_pelo_texto(self):
        # urlparse sem "http(s)://" nao preenche netloc; o codigo cai no
        # fallback de comparar a string inteira (ver "alvo = host or link_limpo").
        assert eh_link_shopee("www.shopee.com.br/produto") is True


class TestExtrairLinksShopee:
    def test_filtra_apenas_shopee(self):
        texto = "Shopee: https://shopee.com.br/a - outro site: https://exemplo.com/b"
        assert extrair_links_shopee(texto) == ["https://shopee.com.br/a"]

    def test_nenhum_link_shopee(self):
        assert extrair_links_shopee("https://exemplo.com/a https://outro.com/b") == []


class TestGerarIdMensagem:
    def test_e_deterministico(self):
        id1 = gerar_id_mensagem("Fulano", "Oferta X", "https://shopee.com.br/a")
        id2 = gerar_id_mensagem("Fulano", "Oferta X", "https://shopee.com.br/a")
        assert id1 == id2

    def test_e_um_sha256_hex(self):
        id_msg = gerar_id_mensagem("Fulano", "texto", "link")
        assert len(id_msg) == 64
        assert all(c in "0123456789abcdef" for c in id_msg)

    def test_entradas_diferentes_geram_ids_diferentes(self):
        id1 = gerar_id_mensagem("Fulano", "Oferta X", "https://shopee.com.br/a")
        id2 = gerar_id_mensagem("Ciclano", "Oferta X", "https://shopee.com.br/a")
        assert id1 != id2

    def test_link_none_nao_quebra(self):
        # main.py as vezes chama isso com link=None (mensagem sem link) -
        # nao pode lançar excecao.
        id_msg = gerar_id_mensagem("Fulano", "texto", None)
        assert len(id_msg) == 64
