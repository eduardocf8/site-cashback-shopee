from datetime import timedelta
from decimal import Decimal

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from ofertas.models import Oferta

from . import conteudo, services, templates_imagem
from .models import RegistroPublicacao


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

    def test_produto_capado_nao_vira_maior_cashback_do_dia(self):
        # Só existe essa oferta, e ela bate no teto (R$10 sobre R$700 vira ~1,4%) - o
        # "recorde" de hoje não pode ser um % artificialmente baixo por causa do teto,
        # melhor não publicar nada do que publicar um número que engana (caso real:
        # bicicleta de R$700+ virando "o maior cashback de hoje" com 1,4%).
        self._criar_oferta(1, "700.00", "0.4200", "bicicleta")

        self.assertIsNone(conteudo.maior_cashback_de_hoje())

    def test_produto_capado_nao_rouba_o_topo_de_produto_sem_teto(self):
        self._criar_oferta(1, "700.00", "0.4200", "bicicleta")  # capado: ~1,4%
        self._criar_oferta(2, "50.00", "0.1000", "capinha")  # sem teto: 10% x 20% = 2%

        resultado = conteudo.maior_cashback_de_hoje()

        self.assertEqual(resultado["numero"], "2,0%")
        self.assertIn("capinha", resultado["apoio"])

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

    def test_nome_do_produto_aparece_so_como_legenda_da_foto(self):
        """O nome vem do Gemini e às vezes é longo. Repetido no texto de apoio e no
        título da conta, ocupava o espaço três vezes sem acrescentar nada - a foto já
        diz do que se trata."""
        combo = conteudo.combo_de_stories_do_dia()
        nome = self.oferta.nome_curto

        self.assertEqual(combo[0]["legenda_produto"], nome)
        self.assertNotIn(nome, combo[0]["apoio"])
        self.assertNotIn(nome, combo[1]["titulo"])

    def test_sem_catalogo_nao_monta_combo(self):
        Oferta.objects.all().delete()
        self.assertIsNone(conteudo.combo_de_stories_do_dia())

    def test_chamada_para_a_bio_fica_solta_e_nao_dentro_da_frase(self):
        """Dentro do rodapé, "link na bio" lê como parte da explicação; solto e
        centralizado, lê como a ação a tomar - e cai na mesma posição do story de
        oferta, então a chamada fica sempre no mesmo lugar."""
        passo_a_passo = conteudo.como_achar_na_vitrine()

        self.assertTrue(passo_a_passo["link_bio"])
        self.assertNotIn("bio", passo_a_passo["rodape"].lower())

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


class AlinhamentoDosPassosTests(TestCase):
    """Mede o alinhamento entre o número e o texto de cada passo.

    O círculo é mais alto que uma linha de texto, então desenhar os dois a partir do
    mesmo topo deixa o texto visivelmente mais alto que o número. É um desalinhamento
    pequeno o bastante pra voltar despercebido num ajuste futuro - por isso vale medir
    em vez de confiar no olho.
    """

    def _centros_do_primeiro_passo(self, imagem):
        from PIL import ImageColor

        largura, altura = imagem.size
        px = imagem.convert("RGB").load()
        roxo = ImageColor.getrgb(templates_imagem.CORES["brand"])
        margem, diametro = 88, int(72 * min(altura / 1080, 1.4))

        def proximo(p, alvo, tol=60):
            return sum(abs(p[i] - alvo[i]) for i in range(3)) < tol

        # o círculo: única mancha roxa na coluna da esquerda (a linha do rodapé fica
        # fora dessa faixa de x porque é fina e atravessa a largura toda)
        linhas_circulo = [
            y for y in range(altura)
            if any(proximo(px[x, y], roxo) for x in range(margem, margem + diametro, 4))
        ]
        # só a primeira mancha contígua = passo 1
        primeira = [linhas_circulo[0]]
        for y in linhas_circulo[1:]:
            if y - primeira[-1] > 5:
                break
            primeira.append(y)

        topo, base = primeira[0], primeira[-1]
        tinta = [
            y for y in range(topo - 30, base + 30)
            if any(proximo(px[x, y], (17, 24, 39), 90) for x in range(margem + diametro + 40, largura - 88, 4))
        ]
        return (topo + base) / 2, (tinta[0] + tinta[-1]) / 2

    def test_numero_e_texto_ficam_no_mesmo_centro(self):
        imagem = templates_imagem.gerar_imagem_passos(
            "Como achar esse produto",
            ["Abra cash-b.com", "Toque em Ofertas", 'Ordene por "Maior cashback"'],
        )

        centro_circulo, centro_texto = self._centros_do_primeiro_passo(imagem)

        # 4px é o resíduo normal entre o centro óptico da fonte e o centro do
        # desenho; desalinhado de verdade dá 12. O limite separa os dois casos.
        self.assertLess(abs(centro_circulo - centro_texto), 7)

    def test_alinhamento_se_mantem_com_passo_de_duas_linhas(self):
        imagem = templates_imagem.gerar_imagem_passos(
            "Como achar esse produto",
            ["Abra cash-b.com no navegador do celular e entre na sua conta", "Toque em Ofertas"],
        )

        centro_circulo, centro_texto = self._centros_do_primeiro_passo(imagem)

        # 4px é o resíduo normal entre o centro óptico da fonte e o centro do
        # desenho; desalinhado de verdade dá 12. O limite separa os dois casos.
        self.assertLess(abs(centro_circulo - centro_texto), 7)


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
    CASHBACK_MAXIMO_POR_PRODUTO=10,
    CASHBACK_MULTIPLICADOR_CAMPANHA=1,
    INSTAGRAM_BOT_ATIVO=False,
)
class PublicacaoDoComboTests(TestCase):
    """O combo ligado no calendário e no executor diário.

    Vale testar porque ele é o único despachante que publica mais de um registro por
    execução - o executor foi feito esperando um só, e um combo pela metade é pior que
    nenhum (a pessoa vê o número sem saber onde achar o produto).
    """

    def setUp(self):
        Oferta.objects.create(
            item_id=1, nome="Fone de Ouvido Bluetooth TWS", nome_curto="fone bluetooth",
            preco_min=Decimal("89.90"), preco_max=Decimal("89.90"),
            imagem_url="https://exemplo.com/fone.jpg",
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )
        # Mesmo em simulação a imagem é salva em disco e a URL pública é montada a
        # partir do request, então ele precisa ser real - não None.
        self.request = RequestFactory().get("/")

    def test_combo_entra_no_calendario_todo_dia(self):
        from datetime import date

        # uma semana inteira, pra garantir que não depende do dia
        for dia in range(7):
            data = date(2026, 8, 24) + timedelta(days=dia)
            with self.subTest(dia=data.strftime("%A")):
                self.assertIn(
                    RegistroPublicacao.CONTEUDO_COMBO_DIARIO,
                    conteudo.tipo_de_conteudo_do_dia(data),
                )

    def test_publica_os_tres_stories(self):
        registros = services.publicar_combo_de_stories(timezone.localdate(), self.request)

        self.assertEqual(len(registros), 3)
        for registro in registros:
            self.assertEqual(registro.tipo, RegistroPublicacao.TIPO_STORY)
            self.assertEqual(registro.conteudo_tipo, RegistroPublicacao.CONTEUDO_COMBO_DIARIO)

    def test_sem_catalogo_nao_publica_nada(self):
        Oferta.objects.all().delete()

        self.assertEqual(services.publicar_combo_de_stories(timezone.localdate(), self.request), [])

    def test_executor_diario_reporta_os_tres(self):
        """O executor esperava um registro por despachante; com o combo ele precisa
        reportar os três, senão o retorno da tarefa esconde o que foi publicado."""
        resultados = services.executar_publicacoes_do_dia(self.request)

        do_combo = [r for r in resultados if r["conteudo_tipo"] == RegistroPublicacao.CONTEUDO_COMBO_DIARIO]
        self.assertEqual(len(do_combo), 3)

    def test_nao_republica_o_combo_no_mesmo_dia(self):
        services.executar_publicacoes_do_dia(self.request)
        antes = RegistroPublicacao.objects.filter(
            conteudo_tipo=RegistroPublicacao.CONTEUDO_COMBO_DIARIO
        ).count()

        services.executar_publicacoes_do_dia(self.request)

        self.assertEqual(
            RegistroPublicacao.objects.filter(
                conteudo_tipo=RegistroPublicacao.CONTEUDO_COMBO_DIARIO
            ).count(),
            antes,
        )
