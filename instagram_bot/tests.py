from decimal import Decimal

from django.test import TestCase, override_settings

from ofertas.models import Oferta

from . import conteudo


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
    CASHBACK_MAXIMO_POR_PRODUTO=10,
    CASHBACK_MULTIPLICADOR_CAMPANHA=1,
)
class ConteudoDoCatalogoTests(TestCase):
    """Conteúdo montado a partir das ofertas sincronizadas.

    O que mais importa aqui é o comportamento com catálogo vazio: se a sincronização
    com a Shopee falhar, essas funções precisam devolver None pra quem chama pular o
    post - publicar um story anunciando "0%" de cashback é pior que não publicar.
    """

    def _criar_oferta(self, item_id, preco, comissao, nome_curto):
        return Oferta.objects.create(
            item_id=item_id,
            nome=f"Produto {item_id}",
            nome_curto=nome_curto,
            preco_min=Decimal(preco),
            preco_max=Decimal(preco),
            percentual_comissao=Decimal(comissao),
            categoria_id=1,
            categoria_nome="Eletrônicos",
        )

    def test_sem_catalogo_devolve_none_em_vez_de_numero_zerado(self):
        self.assertIsNone(conteudo.maior_cashback_de_hoje())
        self.assertIsNone(conteudo.maior_valor_de_volta_hoje())
        self.assertIsNone(conteudo.a_conta_de_uma_oferta())

    def test_oferta_sem_preco_nao_entra_na_conta(self):
        # Preço zerado geraria "0%" e uma conta sem sentido - some da seleção.
        Oferta.objects.create(
            item_id=99, nome="Sem preço", preco_min=Decimal("0"), preco_max=Decimal("0"),
            percentual_comissao=Decimal("0.5000"), categoria_id=1,
        )
        self.assertIsNone(conteudo.maior_cashback_de_hoje())

    def test_escolhe_a_oferta_com_maior_percentual(self):
        self._criar_oferta(1, "89.90", "0.4200", "fone bluetooth")
        self._criar_oferta(2, "219.00", "0.1500", "cafeteira")

        resultado = conteudo.maior_cashback_de_hoje()

        # 42% de comissão x 20% de repasse = 8,4%
        self.assertEqual(resultado["numero"], "8,4%")
        self.assertIn("fone bluetooth", resultado["apoio"])

    def test_valor_em_reais_bate_com_o_cashback_da_oferta(self):
        oferta = self._criar_oferta(1, "89.90", "0.4200", "fone bluetooth")

        resultado = conteudo.maior_valor_de_volta_hoje()

        self.assertEqual(resultado["numero"], f"R$ {oferta.valor_cashback_estimado:.2f}".replace(".", ","))

    def test_conta_fecha_preco_menos_cashback(self):
        oferta = self._criar_oferta(1, "89.90", "0.4200", "fone bluetooth")

        conta = conteudo.a_conta_de_uma_oferta()

        esperado = oferta.preco_min - oferta.valor_cashback_estimado
        self.assertEqual(conta["destaque"][1], f"R$ {esperado:.2f}".replace(".", ","))

    def test_respeita_o_teto_por_produto(self):
        # Produto caro com comissão alta: sem o teto daria bem mais que R$ 10.
        self._criar_oferta(1, "900.00", "0.4200", "notebook")

        resultado = conteudo.maior_valor_de_volta_hoje()

        self.assertEqual(resultado["numero"], "R$ 10,00")


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
    CASHBACK_MAXIMO_POR_PRODUTO=10,
    CASHBACK_MULTIPLICADOR_CAMPANHA=1,
)
class ComboDeStoriesTests(TestCase):
    def setUp(self):
        self.oferta = Oferta.objects.create(
            item_id=1, nome="Fone de Ouvido Bluetooth TWS", nome_curto="fone bluetooth",
            preco_min=Decimal("89.90"), preco_max=Decimal("89.90"),
            imagem_url="https://exemplo.com/fone.jpg",
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )

    def test_sequencia_abre_com_produto_e_fecha_ensinando_o_caminho(self):
        combo = conteudo.combo_de_stories_do_dia()

        self.assertEqual(
            [s["formato"] for s in combo],
            ["numero_com_produto", "conta", "passos"],
        )

    def test_so_o_primeiro_story_leva_foto(self):
        # A foto abre e dá cara ao número; repetida nos três, a sequência vira catálogo.
        combo = conteudo.combo_de_stories_do_dia()

        self.assertEqual(combo[0]["imagem_url"], self.oferta.imagem_url)
        self.assertNotIn("imagem_url", combo[1])
        self.assertNotIn("imagem_url", combo[2])

    def test_sem_catalogo_nao_monta_combo(self):
        Oferta.objects.all().delete()
        self.assertIsNone(conteudo.combo_de_stories_do_dia())

    def test_passo_a_passo_usa_o_rotulo_real_da_vitrine(self):
        """Trava o acoplamento com ofertas/views.py: o story ensina a ordenar por um
        rótulo específico, e se alguém renomear a ordenação lá, o passo a passo passa a
        mandar a pessoa procurar uma opção que não existe mais."""
        from ofertas.views import ORDENACOES_ROTULOS

        self.assertEqual(
            conteudo.ORDENACAO_MAIOR_CASHBACK,
            ORDENACOES_ROTULOS["maior_cashback"],
        )
        passos = conteudo.como_achar_na_vitrine()["passos"]
        self.assertTrue(any(conteudo.ORDENACAO_MAIOR_CASHBACK in p for p in passos))
