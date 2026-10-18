from formatador import (
    FECHAMENTOS,
    corrigir_precos_invertidos,
    extrair_chamada_original,
    extrair_percentual,
    extrair_precos,
    formatar_texto_oferta,
    limpar_linhas,
    linha_e_chamada_antiga,
    linha_tem_apenas_preco_ou_preco_com_rotulo,
    montar_bloco_preco,
    preco_para_numero,
    preparar_descricao_original,
    remover_links,
)


class TestLimparLinhas:
    def test_remove_linhas_vazias_e_normaliza_quebras(self):
        texto = "Linha 1\r\n\r\nLinha 2\r\n\r\n"
        assert limpar_linhas(texto) == "Linha 1\nLinha 2"

    def test_remove_apenas_duplicatas_consecutivas(self):
        texto = "A\nA\nB\nA"
        # A repetida logo em seguida some, mas o A no final (nao consecutivo
        # ao primeiro bloco) e mantido.
        assert limpar_linhas(texto) == "A\nB\nA"

    def test_duplicata_consecutiva_ignora_caixa(self):
        assert limpar_linhas("Oferta Boa\noferta boa\nOutra linha") == "Oferta Boa\nOutra linha"

    def test_vazio(self):
        assert limpar_linhas("") == ""
        assert limpar_linhas(None) == ""


class TestRemoverLinks:
    def test_remove_link_no_final(self):
        assert remover_links("veja aqui https://shopee.com.br/produto") == "veja aqui"

    def test_sem_link_so_tira_espacos_das_pontas(self):
        assert remover_links("  texto sem link  ") == "texto sem link"

    def test_vazio(self):
        assert remover_links(None) == ""


class TestExtrairPrecos:
    def test_um_preco_simples(self):
        assert extrair_precos("De R$99,00 por R$79,90") == ["R$99,00", "R$79,90"]

    def test_preco_com_milhar(self):
        assert extrair_precos("Só R$ 1.234,56 hoje") == ["R$ 1.234,56"]

    def test_sem_preco(self):
        assert extrair_precos("promoção incrível, aproveite") == []


class TestPrecoParaNumero:
    def test_none_ou_vazio(self):
        assert preco_para_numero(None) is None
        assert preco_para_numero("") is None

    def test_formato_brasileiro_com_milhar(self):
        assert preco_para_numero("R$ 1.234,56") == 1234.56

    def test_formato_sem_milhar(self):
        assert preco_para_numero("R$99,00") == 99.0

    def test_texto_invalido(self):
        assert preco_para_numero("preço a combinar") is None


class TestCorrigirPrecosInvertidos:
    def test_swap_quando_atual_maior_que_antigo(self):
        # Alguem digitou "de/por" ao contrario - o codigo corrige.
        antigo, atual = corrigir_precos_invertidos("R$ 100,00", "R$ 150,00")
        assert (antigo, atual) == ("R$ 150,00", "R$ 100,00")

    def test_mantem_ordem_quando_ja_correta(self):
        antigo, atual = corrigir_precos_invertidos("R$ 150,00", "R$ 100,00")
        assert (antigo, atual) == ("R$ 150,00", "R$ 100,00")

    def test_mantem_original_se_algum_preco_invalido(self):
        assert corrigir_precos_invertidos(None, "R$ 10,00") == (None, "R$ 10,00")


class TestExtrairPercentual:
    def test_encontra_percentual(self):
        assert extrair_percentual("Desconto de 50% OFF") == "50%"

    def test_sem_percentual(self):
        assert extrair_percentual("sem desconto aqui") is None


class TestLinhaTemApenasPreco:
    def test_linha_curta_com_preco_e_apenas_preco(self):
        assert linha_tem_apenas_preco_ou_preco_com_rotulo("✅ Por: R$ 99,00") is True

    def test_linha_sem_preco_nao_e_apenas_preco(self):
        assert linha_tem_apenas_preco_ou_preco_com_rotulo("Produto muito bom, recomendo") is False

    def test_linha_longa_com_preco_no_meio_nao_conta_como_apenas_preco(self):
        linha = (
            "este produto e realmente incrivel e vai te surpreender com a "
            "qualidade e o design moderno por apenas R$ 199,90"
        )
        assert linha_tem_apenas_preco_ou_preco_com_rotulo(linha) is False

    def test_linha_vazia(self):
        assert linha_tem_apenas_preco_ou_preco_com_rotulo("") is False


class TestLinhaChamadaAntiga:
    def test_linha_vazia_e_antiga(self):
        assert linha_e_chamada_antiga("") is True
        assert linha_e_chamada_antiga("   ") is True

    def test_trecho_de_aviso_e_antiga(self):
        assert linha_e_chamada_antiga("Preço sujeito a alteração a qualquer momento.") is True
        assert linha_e_chamada_antiga("compre aqui agora mesmo") is True

    def test_so_simbolos_e_antiga(self):
        assert linha_e_chamada_antiga("🔥🔥🔥") is True

    def test_texto_normal_nao_e_antiga(self):
        assert linha_e_chamada_antiga("Produto incrível pra o dia a dia") is False


class TestMontarBlocoPreco:
    def test_dois_precos(self):
        assert montar_bloco_preco("De: R$ 199,90 Por: R$ 99,90") == (
            "💸 De: R$ 199,90\n✅ Por: R$ 99,90"
        )

    def test_um_preco(self):
        assert montar_bloco_preco("Por apenas R$ 49,90") == "✅ Por: R$ 49,90"

    def test_so_percentual(self):
        assert montar_bloco_preco("50% de desconto, sem valor exato") == "💥 Desconto: 50%"

    def test_nada(self):
        assert montar_bloco_preco("sem preço nem desconto aqui") == ""


class TestPipelineCompletoDeOferta:
    TEXTO_ORIGEM = (
        "🔥 Fone Bluetooth Top 🔥\n"
        "Antes: R$ 199,90\n"
        "Agora: R$ 99,90\n"
        "Qualidade incrível, super recomendo esse fone pra quem trabalha o dia todo\n"
        "https://shopee.com.br/produto-123\n"
        "Preço sujeito a alteração a qualquer momento.\n"
    )

    def test_extrai_chamada_original(self):
        assert extrair_chamada_original(self.TEXTO_ORIGEM) == "🔥 Fone Bluetooth Top 🔥"

    def test_prepara_descricao_sem_precos_nem_avisos(self):
        descricao = preparar_descricao_original(self.TEXTO_ORIGEM)
        assert descricao == (
            "Qualidade incrível, super recomendo esse fone pra quem trabalha o dia todo"
        )

    def test_formatar_texto_oferta_monta_as_partes_esperadas(self):
        link_final = "https://shopee.com.br/AFILIADO123"
        resultado = formatar_texto_oferta(self.TEXTO_ORIGEM, link_final)
        partes = resultado.split("\n\n")

        assert partes[0] == "🔥 Fone Bluetooth Top 🔥"
        assert partes[1] == "Qualidade incrível, super recomendo esse fone pra quem trabalha o dia todo"
        assert partes[2] == "💸 De: R$ 199,90\n✅ Por: R$ 99,90"
        assert partes[3] == f"🛒 Compre aqui:\n{link_final}"
        # O fechamento e sorteado entre algumas opcoes - so confere que e
        # uma delas, nao qual exatamente.
        assert partes[4] in FECHAMENTOS

    def test_sem_link_final_nao_inclui_bloco_de_compra(self):
        resultado = formatar_texto_oferta(self.TEXTO_ORIGEM, link_final="")
        assert "Compre aqui" not in resultado
