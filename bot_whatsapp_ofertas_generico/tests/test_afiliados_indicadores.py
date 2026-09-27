from types import SimpleNamespace

import pytest

from afiliados import ConversorAfiliados


@pytest.fixture
def conversor():
    # Sem app_config e sem play: nao faz nenhuma chamada de rede/navegador,
    # so usa os defaults em branco de config.py - suficiente pra testar a
    # parte de calculo/parsing puro (nao a integracao com a API da Shopee).
    return ConversorAfiliados()


class TestConverterNumero:
    def test_int_e_float(self, conversor):
        assert conversor.converter_numero(10) == 10.0
        assert conversor.converter_numero(3.5) == 3.5

    def test_texto_formato_brasileiro(self, conversor):
        assert conversor.converter_numero("R$ 1.234,56") == 1234.56
        assert conversor.converter_numero("12,5") == 12.5

    def test_texto_invalido_retorna_none(self, conversor):
        assert conversor.converter_numero("abc") is None

    def test_none_retorna_none(self, conversor):
        # Diferente de _para_numero: converter_numero nao tem default 0.0,
        # devolve None quando nao da pra converter.
        assert conversor.converter_numero(None) is None


class TestParaNumero:
    def test_none_retorna_zero(self, conversor):
        assert conversor._para_numero(None) == 0.0

    def test_vazio_retorna_zero(self, conversor):
        assert conversor._para_numero("") == 0.0

    def test_formato_brasileiro_com_milhar(self, conversor):
        assert conversor._para_numero("1.234,56") == 1234.56

    def test_apenas_ponto_decimal(self, conversor):
        assert conversor._para_numero("12.34") == 12.34

    def test_texto_invalido_retorna_zero(self, conversor):
        assert conversor._para_numero("abc") == 0.0


class TestExtrairPrimeiroNumero:
    def test_encontra_primeiro_campo_presente(self, conversor):
        objeto = {"grossCommission": "10,00", "netCommission": "8,50"}
        # netCommission vem primeiro na lista de nomes buscados.
        resultado = conversor.extrair_primeiro_numero(
            objeto, ("netCommission", "grossCommission")
        )
        assert resultado == 8.5

    def test_soma_lista_de_itens(self, conversor):
        objeto = [{"commission": 1.5}, {"commission": 2.5}]
        assert conversor.extrair_primeiro_numero(objeto, ("commission",)) == 4.0

    def test_busca_recursiva_em_dict_aninhado(self, conversor):
        objeto = {"pedido": {"valores": {"commission": "5,00"}}}
        assert conversor.extrair_primeiro_numero(objeto, ("commission",)) == 5.0

    def test_campo_ausente_retorna_zero(self, conversor):
        # Diferente de converter_numero/config_numero: quando nenhum dos
        # nomes buscados existe em lugar nenhum da estrutura, o fallback
        # final e sempre 0.0 (nunca None) - agrupar_indicadores depende
        # disso pra poder somar direto sem checar None em todo lugar.
        assert conversor.extrair_primeiro_numero({"outraCoisa": 1}, ("commission",)) == 0.0


class TestCalcularResumoStatusPedidos:
    def test_conta_pedidos_por_status(self, conversor):
        conversoes = [
            {"orders": [{"orderStatus": "COMPLETED"}, {"orderStatus": "pending"}]},
            {"orders": [{"orderStatus": "COMPLETED"}]},
        ]
        assert conversor.calcular_resumo_status_pedidos(conversoes) == {
            "COMPLETED": 2,
            "PENDING": 1,
        }

    def test_status_ausente_vira_desconhecido(self, conversor):
        conversoes = [{"orders": [{}]}]
        assert conversor.calcular_resumo_status_pedidos(conversoes) == {"DESCONHECIDO": 1}

    def test_entradas_malformadas_sao_ignoradas(self, conversor):
        conversoes = [{"orders": "nao-e-lista"}, {"semOrders": True}, "nem-e-dict"]
        assert conversor.calcular_resumo_status_pedidos(conversoes) == {}


class TestComissaoConversaoValida:
    def test_zera_quando_todos_pedidos_invalidos(self, conversor):
        conversao = {"orders": [{"orderStatus": "CANCELLED"}, {"orderStatus": "UNPAID"}]}
        assert conversor._comissao_conversao_valida(conversao, 50.0) == 0.0

    def test_mantem_quando_ha_pedido_valido_misturado(self, conversor):
        conversao = {"orders": [{"orderStatus": "CANCELLED"}, {"orderStatus": "COMPLETED"}]}
        assert conversor._comissao_conversao_valida(conversao, 50.0) == 50.0

    def test_sem_orders_mantem_comissao_original(self, conversor):
        assert conversor._comissao_conversao_valida({}, 50.0) == 50.0


class TestClassificarSubIdRelatorio:
    def test_vazio_vira_sem_subid(self, conversor):
        assert conversor.classificar_sub_id_relatorio("") == "sem_subid"
        assert conversor.classificar_sub_id_relatorio(None) == "sem_subid"

    def test_mantem_valor_com_espacos_removidos(self, conversor):
        assert conversor.classificar_sub_id_relatorio("  grupo-ofertas  ") == "grupo-ofertas"


class TestNormalizarSubIdValor:
    def test_string_simples(self, conversor):
        assert conversor.normalizar_sub_id_valor("grupoA") == ["grupoA"]

    def test_string_com_separador(self, conversor):
        assert conversor.normalizar_sub_id_valor("grupoA|grupoB") == ["grupoA", "grupoB"]
        assert conversor.normalizar_sub_id_valor("grupoA,grupoB") == ["grupoA", "grupoB"]

    def test_lista_e_achatada_recursivamente(self, conversor):
        assert conversor.normalizar_sub_id_valor(["grupoA", ["grupoB", "grupoC"]]) == [
            "grupoA",
            "grupoB",
            "grupoC",
        ]

    def test_dict_usa_apenas_os_valores(self, conversor):
        assert conversor.normalizar_sub_id_valor({"chave": "grupoA"}) == ["grupoA"]

    def test_vazio(self, conversor):
        assert conversor.normalizar_sub_id_valor("") == []
        assert conversor.normalizar_sub_id_valor(None) == []


class TestExtrairSubIdsRelatorio:
    def test_extrai_de_utm_content(self, conversor):
        conversao = {"utmContent": "grupoA|grupoB"}
        assert conversor.extrair_sub_ids_relatorio(conversao) == ["grupoA", "grupoB"]

    def test_sem_utm_content_retorna_vazio(self, conversor):
        assert conversor.extrair_sub_ids_relatorio({}) == []

    def test_remove_duplicatas_mantendo_ordem(self, conversor):
        conversao = {"utmContent": "grupoA|grupoA|grupoB"}
        assert conversor.extrair_sub_ids_relatorio(conversao) == ["grupoA", "grupoB"]


class TestAgruparIndicadores:
    def test_agrupa_vendas_e_comissao_por_sub_id(self, conversor):
        conversoes = [
            {"utmContent": "grupoA", "netCommission": "10,00", "orderAmount": "100,00"},
            {"utmContent": "grupoA", "netCommission": "5,00", "orderAmount": "50,00"},
            {"utmContent": "grupoB", "netCommission": "20,00", "orderAmount": "200,00"},
        ]

        resultado = conversor.agrupar_indicadores(conversoes)

        por_sub_id = {linha["sub_id"]: linha for linha in resultado["linhas"]}
        assert por_sub_id["grupoA"]["vendas"] == 2
        assert por_sub_id["grupoA"]["comissao"] == 15.0
        assert por_sub_id["grupoB"]["vendas"] == 1
        assert por_sub_id["grupoB"]["comissao"] == 20.0

        assert resultado["totais"]["vendas"] == 3
        assert resultado["totais"]["comissao"] == 35.0
        assert resultado["debug"]["conversoes"] == 3

    def test_conversao_sem_sub_id_agrupa_em_sem_subid(self, conversor):
        conversoes = [{"netCommission": "10,00", "orderAmount": "100,00"}]
        resultado = conversor.agrupar_indicadores(conversoes)
        assert resultado["linhas"][0]["sub_id"] == "sem_subid"

    def test_comissao_zerada_quando_todos_pedidos_cancelados(self, conversor):
        conversoes = [
            {
                "utmContent": "grupoA",
                "netCommission": "50,00",
                "orderAmount": "100,00",
                "orders": [{"orderStatus": "CANCELLED"}],
            }
        ]
        resultado = conversor.agrupar_indicadores(conversoes)
        assert resultado["linhas"][0]["comissao"] == 0.0

    def test_lista_vazia(self, conversor):
        resultado = conversor.agrupar_indicadores([])
        assert resultado["linhas"] == []
        assert resultado["totais"] == {"vendas": 0, "comissao": 0.0, "valor": 0.0}


class TestConfigNumero:
    def test_le_atributo_do_config(self, conversor):
        config = SimpleNamespace(shopee_ofertas_comissao_minima="10,5")
        assert conversor.config_numero(config, "shopee_ofertas_comissao_minima") == 10.5

    def test_atributo_ausente_retorna_zero(self, conversor):
        config = SimpleNamespace()
        assert conversor.config_numero(config, "campo_que_nao_existe") == 0.0


class TestOfertaPassaFiltros:
    def _config_base(self, **overrides):
        base = dict(
            shopee_ofertas_comissao_minima=0,
            shopee_ofertas_desconto_minimo=0,
            shopee_ofertas_vendas_minimas=0,
            shopee_ofertas_preco_minimo="",
            shopee_ofertas_preco_maximo="",
            shopee_ofertas_avaliacao_minima="",
            shopee_ofertas_tipo_busca="geral",
            shopee_ofertas_categorias=[],
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_sem_filtros_qualquer_oferta_passa(self, conversor):
        oferta = {"nome": "Produto Qualquer", "comissao": 1, "desconto": 1, "vendas": 1, "preco": 1}
        assert conversor.oferta_passa_filtros(oferta, self._config_base()) is True

    def test_oferta_sem_nome_nao_passa(self, conversor):
        assert conversor.oferta_passa_filtros({}, self._config_base()) is False

    def test_comissao_abaixo_do_minimo_nao_passa(self, conversor):
        oferta = {"nome": "Produto X", "comissao": 5}
        config = self._config_base(shopee_ofertas_comissao_minima=10)
        assert conversor.oferta_passa_filtros(oferta, config) is False

    def test_preco_fora_da_faixa_nao_passa(self, conversor):
        oferta = {"nome": "Produto X", "preco": 500}
        config = self._config_base(shopee_ofertas_preco_maximo="100")
        assert conversor.oferta_passa_filtros(oferta, config) is False

    def test_filtro_de_categoria_bloqueia_produto_fora_da_categoria(self, conversor):
        oferta = {"nome": "Panela de Pressão"}
        config = self._config_base(shopee_ofertas_tipo_busca="categoria", shopee_ofertas_categorias=["moda"])
        assert conversor.oferta_passa_filtros(oferta, config) is False

    def test_filtro_de_categoria_libera_produto_da_categoria(self, conversor):
        oferta = {"nome": "Camiseta Masculina"}
        config = self._config_base(shopee_ofertas_tipo_busca="categoria", shopee_ofertas_categorias=["moda"])
        assert conversor.oferta_passa_filtros(oferta, config) is True
