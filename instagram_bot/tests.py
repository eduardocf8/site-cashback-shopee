from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from links.models import Click
from ofertas.models import Oferta, OfertaManual

from . import conteudo, services, templates_imagem
from .models import RegistroPublicacao


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
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


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
)
class ComboDeStoriesTests(TestCase):
    def setUp(self):
        self.oferta = Oferta.objects.create(
            item_id=1, nome="Fone de Ouvido Bluetooth TWS", nome_curto="fone bluetooth",
            preco_min=Decimal("89.90"), preco_max=Decimal("89.90"),
            imagem_url="https://exemplo.com/fone.jpg",
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )

    def test_sequencia_abre_com_capa_e_fecha_ensinando_o_caminho(self):
        combo = conteudo.combo_de_stories_do_dia()

        self.assertEqual(
            [s["formato"] for s in combo],
            ["capa", "numero_com_produto", "conta", "numero_com_produto", "passos"],
        )

    def test_produto_com_maior_percentual_pode_ser_diferente_do_de_maior_valor(self):
        # Bicicleta cara com % bem menor que o fone (2% x 8,4%), mas em R$ vale mais
        # (R$14 x R$7,55) - os dois stories de número têm que escolher produtos
        # diferentes nesse caso, cada um pela sua própria métrica.
        Oferta.objects.create(
            item_id=2, nome="Bicicleta MTB Aro 29", nome_curto="bicicleta",
            preco_min=Decimal("700.00"), preco_max=Decimal("700.00"),
            percentual_comissao=Decimal("0.1000"), categoria_id=1,
        )

        combo = conteudo.combo_de_stories_do_dia()

        story_percentual, story_reais = combo[1], combo[3]
        self.assertEqual(story_percentual["numero"], "8,4%")
        self.assertEqual(story_percentual["legenda_produto"], "fone bluetooth")
        self.assertEqual(story_reais["legenda_produto"], "bicicleta")

    def test_capa_conta_e_passos_nao_levam_foto(self):
        # As fotos abrem cada bloco de número (% e R$); os outros três stories não
        # levam, pra não repetir imagem e virar catálogo.
        combo = conteudo.combo_de_stories_do_dia()

        self.assertNotIn("imagem_url", combo[0])
        self.assertEqual(combo[1]["imagem_url"], self.oferta.imagem_url)
        self.assertNotIn("imagem_url", combo[2])
        self.assertEqual(combo[3]["imagem_url"], self.oferta.imagem_url)
        self.assertNotIn("imagem_url", combo[4])

    def test_nome_do_produto_aparece_so_como_legenda_da_foto(self):
        """O nome vem do Gemini e às vezes é longo. Repetido no texto de apoio e no
        título da conta, ocupava o espaço sem acrescentar nada - a foto já diz do que
        se trata."""
        combo = conteudo.combo_de_stories_do_dia()
        nome = self.oferta.nome_curto

        self.assertEqual(combo[1]["legenda_produto"], nome)
        self.assertNotIn(nome, combo[1]["apoio"])
        self.assertNotIn(nome, combo[2]["titulo"])
        self.assertNotIn(nome, combo[3]["apoio"])

    def test_sem_catalogo_nao_monta_combo(self):
        Oferta.objects.all().delete()
        self.assertIsNone(conteudo.combo_de_stories_do_dia())

    def test_rotulos_nao_prometem_o_maior_absoluto_do_catalogo(self):
        """A busca do combo é só entre as ~400 mais vendidas (ver comentário em
        combo_de_stories_do_dia), não o catálogo inteiro - por isso o rótulo (+
        subrótulo) não pode dizer "o maior de hoje" sem qualificar (um produto pouco
        vendido pode ter % ou R$ maior e não entrar na conta, o que já gerou confusão
        comparando com a vitrine, que ordena o catálogo inteiro - ver conversa de
        2026-09-02)."""
        combo = conteudo.combo_de_stories_do_dia()

        for indice in (0, 1, 3):
            story = combo[indice]
            texto = story.get("titulo") or f"{story['rotulo']} {story.get('subrotulo', '')}"
            self.assertIn("mais vendidos", texto)
            self.assertNotRegex(texto.lower(), r"\bo maior\b.*\bhoje\b")

    def test_rotulo_e_subrotulo_cabem_na_largura_da_imagem(self):
        """rotulo/subrotulo em gerar_imagem_numero_com_produto são desenhados numa
        linha cada, sem quebra automática (diferente de titulo/apoio) - um texto
        comprido demais estoura a largura do story e corta na imagem final."""
        from PIL import Image, ImageDraw

        from .templates_imagem import _fonte

        combo = conteudo.combo_de_stories_do_dia()
        img = Image.new("RGB", (1080, 1920))
        draw = ImageDraw.Draw(img)
        escala = min(1920 / 1080, 1.4)
        fonte_rotulo = _fonte(int(30 * escala), mono=True, negrito=True)
        fonte_subrotulo = _fonte(int(20 * escala))
        largura_max = 1080 - 88 * 2

        for indice in (1, 3):
            rotulo = combo[indice]["rotulo"]
            largura = draw.textlength(rotulo.upper(), font=fonte_rotulo)
            self.assertLessEqual(largura, largura_max, f"rótulo estoura a largura: {rotulo!r}")

            subrotulo = combo[indice]["subrotulo"]
            largura_sub = draw.textlength(subrotulo, font=fonte_subrotulo)
            self.assertLessEqual(largura_sub, largura_max, f"subrótulo estoura a largura: {subrotulo!r}")

    def test_chamada_para_a_bio_fica_solta_e_nao_dentro_da_frase(self):
        """Dentro do rodapé, "link na bio" lê como parte da explicação; solto e
        centralizado, lê como a ação a tomar - e cai na mesma posição do story de
        oferta, então a chamada fica sempre no mesmo lugar."""
        passo_a_passo = conteudo.como_achar_na_vitrine()

        self.assertTrue(passo_a_passo["link_bio"])
        self.assertNotIn("bio", passo_a_passo["rodape"].lower())

    def test_passo_a_passo_usa_os_rotulos_reais_da_vitrine(self):
        """Trava o acoplamento com ofertas/views.py: o story ensina a ordenar por
        rótulos específicos, e se alguém renomear alguma ordenação lá, o passo a passo
        passa a mandar a pessoa procurar uma opção que não existe mais."""
        from ofertas.views import ORDENACOES_ROTULOS

        self.assertEqual(
            conteudo.ORDENACAO_MAIOR_CASHBACK,
            ORDENACOES_ROTULOS["maior_cashback"],
        )
        self.assertEqual(
            conteudo.ORDENACAO_MAIOR_CASHBACK_REAIS,
            ORDENACOES_ROTULOS["maior_cashback_reais"],
        )
        passos = conteudo.como_achar_na_vitrine()["passos"]
        self.assertTrue(any(conteudo.ORDENACAO_MAIOR_CASHBACK in p for p in passos))
        self.assertTrue(any(conteudo.ORDENACAO_MAIOR_CASHBACK_REAIS in p for p in passos))


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

    def test_publica_os_cinco_stories(self):
        registros = services.publicar_combo_de_stories(timezone.localdate(), self.request)

        self.assertEqual(len(registros), 5)
        for registro in registros:
            self.assertEqual(registro.tipo, RegistroPublicacao.TIPO_STORY)
            self.assertEqual(registro.conteudo_tipo, RegistroPublicacao.CONTEUDO_COMBO_DIARIO)

    def test_sem_catalogo_nao_publica_nada(self):
        Oferta.objects.all().delete()

        self.assertEqual(services.publicar_combo_de_stories(timezone.localdate(), self.request), [])

    def test_executor_diario_reporta_os_cinco(self):
        """O executor esperava um registro por despachante; com o combo ele precisa
        reportar os cinco, senão o retorno da tarefa esconde o que foi publicado."""
        resultados = services.executar_publicacoes_do_dia(self.request)

        do_combo = [r for r in resultados if r["conteudo_tipo"] == RegistroPublicacao.CONTEUDO_COMBO_DIARIO]
        self.assertEqual(len(do_combo), 5)

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


@override_settings(
    SHOPEE_CASHBACK_PERCENTUAL=20,
    CASHBACK_MAXIMO_POR_PRODUTO=10,
    CASHBACK_MULTIPLICADOR_CAMPANHA=1,
    INSTAGRAM_BOT_ATIVO=True,
    INSTAGRAM_REQUER_APROVACAO=True,
    INSTAGRAM_APROVADOR_EMAIL="dono@exemplo.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PublicacaoDiretaSemAprovacaoTests(TestCase):
    """Story de oferta e combo diário postam direto, sem passar pelo e-mail de
    aprovação - mesmo com INSTAGRAM_REQUER_APROVACAO=True (decisão de 2026-09-02, ver
    services.CONTEUDO_TIPOS_SEM_APROVACAO). O resto do conteúdo (dica de economia,
    lembrete, institucional) continua exigindo aprovação normalmente."""

    def setUp(self):
        Oferta.objects.create(
            item_id=1, nome="Fone de Ouvido Bluetooth TWS", nome_curto="fone bluetooth",
            preco_min=Decimal("89.90"), preco_max=Decimal("89.90"),
            imagem_url="https://exemplo.com/fone.jpg",
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )
        self.request = RequestFactory().get("/")

    @patch("instagram_bot.services.timezone")
    @patch("instagram_bot.instagram_client.publicar_imagem")
    def test_story_de_oferta_publica_direto_sem_email(self, mock_publicar, mock_timezone):
        mock_publicar.return_value = "media123"
        mock_timezone.localdate.return_value = timezone.localdate()
        mock_timezone.localtime.return_value = datetime(2026, 9, 2, 12, 0)

        registro = services.publicar_story_oferta_do_momento(timezone.localdate(), self.request)

        self.assertEqual(registro.status, RegistroPublicacao.STATUS_PUBLICADO)
        self.assertEqual(len(mail.outbox), 0)

    @patch("instagram_bot.instagram_client.publicar_imagem")
    def test_combo_publica_direto_sem_email(self, mock_publicar):
        mock_publicar.return_value = "media123"

        registros = services.publicar_combo_de_stories(timezone.localdate(), self.request)

        self.assertTrue(registros)
        self.assertTrue(all(r.status == RegistroPublicacao.STATUS_PUBLICADO for r in registros))
        self.assertEqual(len(mail.outbox), 0)

    def test_dica_de_economia_continua_exigindo_aprovacao(self):
        """Confirma que a mudança é específica pra oferta/combo, não desliga a
        aprovação pra tudo por engano."""
        registro = services.publicar_story_dica(timezone.localdate(), self.request)

        self.assertEqual(registro.status, RegistroPublicacao.STATUS_PENDENTE_APROVACAO)
        self.assertEqual(len(mail.outbox), 1)

    def test_story_de_oferta_curado_a_mao_continua_exigindo_aprovacao(self):
        """Só o story ESCOLHIDO PELO BOT (publicar_story_oferta_do_momento) pula
        aprovação - o mesmo CONTEUDO_OFERTA_DIARIA escolhido à mão (botão "Criar
        story" no admin, ou por link) continua pedindo aprovação: tem dado digitado à
        mão (preço/desconto/comissão) que vale a pena conferir antes de publicar
        (decisão de 2026-09-03, revertendo o que esse caminho tinha herdado sem
        querer no dia anterior)."""
        oferta_manual = OfertaManual.objects.create(
            product_link="https://shopee.com.br/produto-curado",
            nome="Produto curado à mão",
            imagem_url="https://exemplo.com/produto.jpg",
            preco_antigo=Decimal("100.00"), preco_novo=Decimal("80.00"),
            percentual_comissao=Decimal("0.1000"),
        )

        registro = services.publicar_story_oferta_curada(oferta_manual, self.request)

        self.assertEqual(registro.status, RegistroPublicacao.STATUS_PENDENTE_APROVACAO)
        self.assertEqual(len(mail.outbox), 1)


class EspacamentoDosStoriesDeOfertaTests(TestCase):
    """8 stories de oferta por dia (NUMERO_STORIES_OFERTAS_POR_DIA), espalhados
    igualmente entre HORA_INICIO_STORIES_OFERTA (8h) e HORA_FIM_STORIES_OFERTA (20h) -
    decisão de 2026-09-02 (antes eram 5, sem horário-alvo nenhum: o cron postava assim
    que chamava, então dependia só da frequência dele pra não ficar tudo bem cedo)."""

    def setUp(self):
        Oferta.objects.create(
            item_id=1, nome="Fone de Ouvido Bluetooth TWS", nome_curto="fone bluetooth",
            preco_min=Decimal("89.90"), preco_max=Decimal("89.90"),
            imagem_url="https://exemplo.com/fone.jpg",
            percentual_comissao=Decimal("0.4200"), categoria_id=1,
        )
        self.request = RequestFactory().get("/")
        patcher = patch("instagram_bot.services.timezone")
        self.mock_timezone = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_timezone.localdate.return_value = timezone.localdate()

    def _definir_hora_atual(self, hora, minuto):
        self.mock_timezone.localtime.return_value = datetime(2026, 9, 2, hora, minuto)

    def test_horarios_alvo_ficam_igualmente_espacados_entre_8h_e_20h(self):
        horarios = [
            services._horario_do_proximo_story(indice)
            for indice in range(services.NUMERO_STORIES_OFERTAS_POR_DIA)
        ]

        self.assertEqual(
            horarios,
            [time(8, 0), time(9, 30), time(11, 0), time(12, 30), time(14, 0), time(15, 30), time(17, 0), time(18, 30)],
        )

    def test_nao_posta_antes_do_horario_do_primeiro_story(self):
        self._definir_hora_atual(7, 59)

        self.assertIsNone(services.publicar_story_oferta_do_momento(timezone.localdate(), self.request))

    def test_posta_a_partir_do_horario_do_primeiro_story(self):
        self._definir_hora_atual(8, 0)

        registro = services.publicar_story_oferta_do_momento(timezone.localdate(), self.request)

        self.assertIsNotNone(registro)

    def test_segundo_story_so_libera_no_horario_alvo_dele_nao_antes(self):
        RegistroPublicacao.objects.create(
            data=timezone.localdate(), tipo=RegistroPublicacao.TIPO_STORY,
            conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
            status=RegistroPublicacao.STATUS_SIMULADO, sucesso=True,
        )

        self._definir_hora_atual(9, 0)
        self.assertIsNone(services.publicar_story_oferta_do_momento(timezone.localdate(), self.request))

        self._definir_hora_atual(9, 30)
        self.assertIsNotNone(services.publicar_story_oferta_do_momento(timezone.localdate(), self.request))

    def test_para_de_postar_depois_dos_oito(self):
        for _ in range(services.NUMERO_STORIES_OFERTAS_POR_DIA):
            RegistroPublicacao.objects.create(
                data=timezone.localdate(), tipo=RegistroPublicacao.TIPO_STORY,
                conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
                status=RegistroPublicacao.STATUS_SIMULADO, sucesso=True,
            )
        self._definir_hora_atual(19, 0)

        self.assertIsNone(services.publicar_story_oferta_do_momento(timezone.localdate(), self.request))


class DiversidadeDaEscolhaDeOfertaTests(TestCase):
    """Antes, a escolha sempre pegava a categoria mais vendida e, dentro dela, o
    produto #1 em vendas - como esses rankings quase não mudam de um dia pro outro, era
    sempre o mesmo resultado. Agora sorteia dentro de um pool maior (ver
    TAMANHO_POOL_CATEGORIAS/TAMANHO_POOL_PRODUTOS_POR_CATEGORIA em services.py) - esses
    testes confirmam que chamadas repetidas não convergem sempre pro mesmo produto."""

    def setUp(self):
        for categoria_id in range(1, 6):
            for indice in range(3):
                Oferta.objects.create(
                    item_id=categoria_id * 100 + indice,
                    nome=f"Produto {categoria_id}-{indice}",
                    categoria_id=categoria_id,
                    vendas=100 - indice,
                    percentual_comissao=Decimal("0.05"),
                )

    def test_chamadas_repetidas_no_mesmo_dia_nao_convergem_pro_mesmo_produto(self):
        hoje = timezone.localdate()

        escolhidas = {services._escolher_oferta_do_momento(hoje).item_id for _ in range(30)}

        self.assertGreater(len(escolhidas), 1)


class IrParaStoryDeOfertaTests(TestCase):
    """Link enviado por DM - precisa exigir login (pra creditar o cashback à pessoa
    certa, igual ofertas/views.py::ir_para_oferta) e gerar um Click TIPO_STORY_DM."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="compradora", password="senha123", cpf="39053344705"
        )
        self.registro = RegistroPublicacao.objects.create(
            data=timezone.localdate(),
            tipo=RegistroPublicacao.TIPO_STORY,
            conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
            status=RegistroPublicacao.STATUS_PUBLICADO,
            sucesso=True,
            oferta_item_id=555,
            link_produto_original="https://shopee.com.br/produto-i.1.555",
        )

    def test_exige_login(self):
        resposta = self.client.get(reverse("instagram_story_ir", args=[self.registro.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta.url)

    @override_settings(
        SHOPEE_AFFILIATE_APP_ID="app123",
        SHOPEE_AFFILIATE_SECRET="segredo123",
        SHOPEE_AFFILIATE_API_URL="https://open-api.affiliate.shopee.com.br/graphql",
    )
    @patch("links.services.gerar_link_curto")
    def test_logado_gera_click_tipo_story_dm_e_redireciona(self, mock_gerar_link):
        mock_gerar_link.return_value = "https://shope.ee/storylink123"
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("instagram_story_ir", args=[self.registro.pk]))

        click = Click.objects.get()
        self.assertEqual(click.tipo, Click.TIPO_STORY_DM)
        self.assertEqual(click.url_original, self.registro.link_produto_original)
        self.assertEqual(click.item_id_alvo, self.registro.oferta_item_id)
        self.assertRedirects(resposta, "https://shope.ee/storylink123", fetch_redirect_response=False)

    def test_sem_link_guardado_volta_pra_home_com_erro(self):
        self.registro.link_produto_original = ""
        self.registro.save(update_fields=["link_produto_original"])
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("instagram_story_ir", args=[self.registro.pk]))

        self.assertRedirects(resposta, reverse("home"))
