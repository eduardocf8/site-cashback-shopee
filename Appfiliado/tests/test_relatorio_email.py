from relatorio_email import (
    formatar_moeda,
    montar_bloco_validado_html,
    montar_corpo_email,
    montar_tabela_html,
)


class TestFormatarMoeda:
    def test_formata_padrao_brasileiro(self):
        assert formatar_moeda(1234.5) == "R$ 1.234,50"

    def test_none_vira_zero(self):
        assert formatar_moeda(None) == "R$ 0,00"

    def test_texto_invalido_vira_zero(self):
        assert formatar_moeda("abc") == "R$ 0,00"


class TestMontarBlocoValidadoHtml:
    def test_inclui_pedidos_faturamento_e_comissao(self):
        html = montar_bloco_validado_html(
            "Ontem", {"pedidos": 116, "faturamento": 8124.42, "comissao": 978.40}
        )
        assert "Ontem" in html
        assert "116" in html
        assert "R$ 8.124,42" in html
        assert "R$ 978,40" in html

    def test_dados_none_nao_quebra_e_mostra_zero(self):
        html = montar_bloco_validado_html("Mês", None)
        assert "R$ 0,00" in html
        assert ">0<" in html


class TestMontarTabelaHtml:
    def test_sem_linhas_mostra_mensagem(self):
        html = montar_tabela_html("Ontem", {"linhas": [], "totais": {}})
        assert "Nenhuma venda/conversão" in html

    def test_com_linhas_mostra_sub_id_e_totais(self):
        resumo = {
            "linhas": [{"sub_id": "grupoA", "vendas": 3, "comissao": 15.0}],
            "totais": {"vendas": 3, "comissao": 15.0},
        }
        html = montar_tabela_html("Ontem", resumo)
        assert "grupoA" in html
        assert "R$ 15,00" in html


class TestMontarCorpoEmail:
    def _resumo_vazio(self):
        return {"linhas": [], "totais": {}}

    def test_sem_dados_validados_nao_inclui_secao_nova(self):
        corpo = montar_corpo_email(
            self._resumo_vazio(), self._resumo_vazio(), "05/10/2026 08:00", "Outubro/2026 (até ontem)"
        )
        assert "Comissões validadas" not in corpo
        assert "Comissões estimadas" in corpo

    def test_com_dados_validados_inclui_secao_e_valores(self):
        validado_ontem = {"pedidos": 116, "faturamento": 8124.42, "comissao": 978.40}
        validado_mes = {"pedidos": 386, "faturamento": 31028.30, "comissao": 2517.00}

        corpo = montar_corpo_email(
            self._resumo_vazio(),
            self._resumo_vazio(),
            "05/10/2026 08:00",
            "Outubro/2026 (até ontem)",
            validado_ontem=validado_ontem,
            validado_mes=validado_mes,
        )

        assert "Comissões validadas" in corpo
        assert "116" in corpo
        assert "R$ 8.124,42" in corpo
        assert "386" in corpo
        assert "R$ 31.028,30" in corpo
        # A seção de comissões validadas deve usar o mesmo título de mês
        # das comissões estimadas (mesmo mês de referência).
        assert corpo.count("Outubro/2026 (até ontem)") == 2

    def test_secao_validada_vem_depois_da_estimada(self):
        corpo = montar_corpo_email(
            self._resumo_vazio(),
            self._resumo_vazio(),
            "05/10/2026 08:00",
            "Outubro/2026 (até ontem)",
            validado_ontem={"pedidos": 1, "faturamento": 10.0, "comissao": 1.0},
            validado_mes={"pedidos": 2, "faturamento": 20.0, "comissao": 2.0},
        )
        assert corpo.index("Comissões estimadas") < corpo.index("Comissões validadas")
