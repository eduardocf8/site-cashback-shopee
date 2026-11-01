from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import cripto
from painel.tests import BasePainel

from . import ofertas, shopee_ofertas
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp

SP = ZoneInfo("America/Sao_Paulo")
# Uma segunda-feira, 14h em São Paulo.
AGORA = datetime(2026, 10, 19, 14, 0, tzinfo=SP)
GRUPOS = [{"jid": "1@g.us", "nome": "Ofertas VIP"}, {"jid": "2@g.us", "nome": "Achadinhos"}]


def produto(item_id, **extra):
    base = {"item_id": str(item_id), "shop_id": "9", "nome": f"Produto {item_id}", "link": f"https://shopee.com.br/p-i.9.{item_id}",
            "imagem": f"https://cf.shopee.com.br/file/{item_id}", "preco": 39.9, "comissao": 10.0, "desconto": 20.0,
            "vendas": 500, "avaliacao": 4.8, "loja": "Loja"}
    base.update(extra)
    return base


class TestShopeeOfertas(TestCase):
    def config(self, **campos):
        return ConfiguracaoOfertas(**campos)

    def test_id_da_loja(self):
        self.assertEqual(shopee_ofertas.extrair_id_da_loja("https://shopee.com.br/shop/123456"), "123456")
        self.assertEqual(shopee_ofertas.extrair_id_da_loja("https://shopee.com.br/Fone-i.777.888"), "777")
        self.assertEqual(shopee_ofertas.extrair_id_da_loja("998877"), "998877")
        self.assertEqual(shopee_ofertas.extrair_id_da_loja("https://shopee.com.br/collections/123"), "")

    def test_normaliza_o_produto_da_api(self):
        p = shopee_ofertas.normalizar_produto({
            "itemId": 5, "productName": "Fone", "priceMin": "39.90", "price": "45", "commissionRate": "0.12",
            "priceDiscountRate": 30, "sales": 1200, "ratingStar": "4.7", "imageUrl": "https://img", "productLink": "https://p",
        })
        self.assertEqual((p["item_id"], p["preco"], p["comissao"], p["desconto"], p["vendas"]), ("5", 39.9, 12.0, 30.0, 1200))

    def test_busca_monta_a_consulta_e_tira_campo_que_a_api_nao_conhece(self):
        config = self.config(tipo_busca="palavra_chave", palavra_chave="fone bluetooth", ordenacao="maior_comissao")
        respostas = [
            shopee_ofertas.ShopeeAPIError('Cannot query field "shopName" on type "ProductOfferV2".'),
            {"productOfferV2": {"nodes": [
                {"itemId": 1, "productName": "A", "productLink": "https://a", "priceDiscountRate": 10},
                {"itemId": 2, "productName": "B", "productLink": "https://b", "priceDiscountRate": 50},
                {"itemId": 3, "productName": "", "productLink": "https://c"},
            ], "pageInfo": {"hasNextPage": True}}},
        ]
        with mock.patch.object(shopee_ofertas, "executar_graphql_com_credenciais", side_effect=respostas) as api:
            produtos, tem_proxima = shopee_ofertas.buscar_produtos("id", "s", config, 3)
        consulta = api.call_args.args[2]
        self.assertIn('keyword:"fone bluetooth"', consulta)
        self.assertIn("page:3", consulta)
        self.assertIn("sortType:5", consulta)
        self.assertNotIn("shopName", consulta)
        self.assertEqual([p["item_id"] for p in produtos], ["1", "2"])  # sem nome fica de fora
        self.assertTrue(tem_proxima)

        config = self.config(tipo_busca="loja", loja="https://shopee.com.br/shop/4321", ordenacao="maior_desconto")
        resposta = {"productOfferV2": {"nodes": [
            {"itemId": 1, "productName": "A", "productLink": "https://a", "priceDiscountRate": 10},
            {"itemId": 2, "productName": "B", "productLink": "https://b", "priceDiscountRate": 50},
        ]}}
        with mock.patch.object(shopee_ofertas, "executar_graphql_com_credenciais", return_value=resposta) as api:
            produtos, tem_proxima = shopee_ofertas.buscar_produtos("id", "s", config, 1)
        self.assertIn("shopId:4321", api.call_args.args[2])
        self.assertEqual([p["item_id"] for p in produtos], ["2", "1"])  # maior desconto primeiro
        self.assertFalse(tem_proxima)

    def test_filtros(self):
        config = self.config(comissao_minima=10, desconto_minimo=15, preco_minimo=Decimal("20"),
                             preco_maximo=Decimal("50"), vendas_minimas=100, avaliacao_minima=Decimal("4.5"))
        self.assertTrue(shopee_ofertas.passa_nos_filtros(produto(1), config))
        for campo, valor in [("comissao", 9), ("desconto", 10), ("preco", 19.9), ("preco", 60), ("vendas", 50), ("avaliacao", 4.2)]:
            with self.subTest(campo=campo):
                self.assertFalse(shopee_ofertas.passa_nos_filtros(produto(1, **{campo: valor}), config))
        zerados = self.config(preco_minimo=Decimal("0"), preco_maximo=Decimal("0"), avaliacao_minima=Decimal("0"))
        self.assertTrue(shopee_ofertas.passa_nos_filtros(produto(1), zerados))  # 0 = sem filtro
        categorias = self.config(tipo_busca="categoria", categorias=["pet"])
        self.assertTrue(shopee_ofertas.passa_nos_filtros(produto(1, nome="Ração para gato castrado"), categorias))
        self.assertFalse(shopee_ofertas.passa_nos_filtros(produto(1, nome="Fone de ouvido"), categorias))

    def test_link_de_afiliado_com_sub_ids(self):
        resposta = {"generateShortLink": {"shortLink": "https://s.shopee.com.br/abc"}}
        with mock.patch.object(shopee_ofertas, "executar_graphql_com_credenciais", return_value=resposta) as api:
            link = shopee_ofertas.gerar_link_afiliado("id", "s", "https://shopee.com.br/p", ["grupos", "zap"])
        self.assertEqual(link, "https://s.shopee.com.br/abc")
        self.assertIn('subIds:["grupos", "zap"]', api.call_args.args[2])
        with self.assertRaises(shopee_ofertas.SubIdInvalido):
            shopee_ofertas.gerar_link_afiliado("id", "s", "https://p", ["com-hifen"])

    def test_texto_no_formato_do_app(self):
        texto = ofertas.montar_texto(produto(1, nome="Fone Bluetooth X"), "https://s.shopee.com.br/abc", "PROMO10")
        self.assertTrue(texto.startswith("Fone Bluetooth X"))
        self.assertIn("✅ Por: R$ 39,90", texto)
        self.assertIn("Cupom: PROMO10", texto)
        self.assertIn("🛒 Compre aqui:\nhttps://s.shopee.com.br/abc", texto)


def link_falso(app_id, secret, url, sub_ids, ferramenta=""):
    return f"https://s.shopee.com.br/{url[-1]}" + (f"-{'-'.join(sub_ids)}" if sub_ids else "")


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotor(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp_premium", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, grupos=GRUPOS, intervalo_minutos=5, sub_ids="grupos",
        )
        self.motor = ofertas.Motor()

    def rodar(self, produtos_por_pagina, agora=AGORA):
        def busca(app_id, secret, config, pagina):
            lista = produtos_por_pagina.get(pagina, [])
            return list(lista), pagina < max(produtos_por_pagina)
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca) as buscar:
            self.motor.uma_volta(agora)
        self.config.refresh_from_db()
        return buscar

    def envios(self):
        return list(EnvioWhatsApp.objects.order_by("id").values_list("item_id", "destino"))

    def test_envia_para_os_grupos_e_espera_o_intervalo(self, _link):
        self.rodar({1: [produto(1), produto(2)]})
        self.assertEqual(self.envios(), [("1", "1@g.us"), ("1", "2@g.us")])
        envio = EnvioWhatsApp.objects.first()
        self.assertEqual((envio.origem, envio.imagem_url, envio.link_afiliado), ("oferta", "https://cf.shopee.com.br/file/1", "https://s.shopee.com.br/1-grupos"))
        self.assertIn("https://s.shopee.com.br/1-grupos", envio.texto)
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=5))

        self.rodar({1: [produto(1), produto(2)]}, AGORA + timedelta(minutes=2))  # antes do intervalo
        self.assertEqual(len(self.envios()), 2)
        self.rodar({1: [produto(1), produto(2)]}, AGORA + timedelta(minutes=5))
        self.assertEqual(self.envios()[2:], [("2", "1@g.us"), ("2", "2@g.us")])

    def test_sub_id_proprio_de_um_grupo_e_padrao_nos_outros(self, gerar_link):
        tres = GRUPOS + [{"jid": "3@g.us", "nome": "VIP"}]
        ConfiguracaoOfertas.objects.update(grupos=tres, sub_ids_por_grupo={"3@g.us": "vip", "9@g.us": "desmarcado"})
        self.rodar({1: [produto(1)]})
        links = dict(EnvioWhatsApp.objects.values_list("destino", "link_afiliado"))
        self.assertEqual(links, {
            "1@g.us": "https://s.shopee.com.br/1-grupos", "2@g.us": "https://s.shopee.com.br/1-grupos",
            "3@g.us": "https://s.shopee.com.br/1-vip",
        })
        self.assertEqual(gerar_link.call_count, 2)  # um link por combinação de Sub IDs
        textos = {t.replace("1-grupos", "X").replace("1-vip", "X") for t in EnvioWhatsApp.objects.values_list("texto", flat=True)}
        self.assertEqual(len(textos), 1)  # mesmo texto em todos, só o link muda

    def test_nao_repete_no_mesmo_grupo_por_n_dias(self, _link):
        EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", origem="oferta", item_id="1", estado="enviado")
        self.rodar({1: [produto(1)]})
        self.assertEqual(self.envios()[1:], [("1", "2@g.us")])  # só o grupo que ainda não recebeu

        EnvioWhatsApp.objects.all().delete()
        antigo = EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", origem="oferta", item_id="1")
        EnvioWhatsApp.objects.filter(pk=antigo.pk).update(criado_em=AGORA - timedelta(days=8))
        self.config.proximo_envio_em = None
        self.config.save()
        self.motor.cache.clear()
        self.rodar({1: [produto(1)]})
        self.assertEqual(len(self.envios()), 3)  # passou de 7 dias: pode de novo nos dois

    def test_continua_nas_proximas_paginas(self, _link):
        self.config.comissao_minima = 15
        self.config.save()
        self.rodar({1: [produto(1)], 2: [produto(2, comissao=20)], 3: [produto(3)]})
        self.assertEqual(self.envios()[0][0], "2")
        self.assertEqual(self.config.pagina_atual, 3)

    def test_sem_produto_novo_espera_30_minutos(self, _link):
        self.config.desconto_minimo = 90
        self.config.save()
        self.rodar({1: [produto(1)], 2: [produto(2)]})
        self.assertEqual(self.envios(), [])
        self.assertIn("Nenhuma oferta nova", self.config.situacao)
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=30))

    def test_horario_dias_e_limite(self, _link):
        self.config.horario_inicio, self.config.horario_fim = time(18), time(23)
        self.config.save()
        self.rodar({1: [produto(1)]})
        self.assertEqual((self.envios(), self.config.situacao), ([], "Fora do horário de envio."))

        self.config.horario_inicio, self.config.horario_fim = time(7), time(23)
        self.config.dias_semana = [5, 6]  # só fim de semana; AGORA é segunda
        self.config.save()
        self.rodar({1: [produto(1)]})
        self.assertEqual(self.envios(), [])

        self.config.dias_semana = list(range(7))
        self.config.limite_diario = 1
        self.config.save()
        hoje_cedo = EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", origem="oferta", item_id="99")
        EnvioWhatsApp.objects.filter(pk=hoje_cedo.pk).update(criado_em=AGORA - timedelta(hours=5))
        self.rodar({1: [produto(1)]})
        self.assertEqual(self.config.situacao, "Limite de ofertas de hoje atingido.")
        EnvioWhatsApp.objects.filter(pk=hoje_cedo.pk).update(criado_em=AGORA - timedelta(hours=15))  # ontem
        self.rodar({1: [produto(1)]})
        self.assertEqual(self.envios()[-2:], [("1", "1@g.us"), ("1", "2@g.us")])

    def test_janela_que_passa_da_meia_noite(self, _link):
        config = ConfiguracaoOfertas(horario_inicio=time(20), horario_fim=time(2), dias_semana=list(range(7)))
        self.assertTrue(ofertas.dentro_do_horario(config, datetime(2026, 10, 19, 23, 30)))
        self.assertTrue(ofertas.dentro_do_horario(config, datetime(2026, 10, 19, 1, 0)))
        self.assertFalse(ofertas.dentro_do_horario(config, datetime(2026, 10, 19, 12, 0)))

    def test_whatsapp_desconectado_ou_pausado(self, _link):
        ConexaoWhatsApp.objects.update(estado="desconectado")
        self.rodar({1: [produto(1)]})
        self.assertEqual((self.envios(), self.config.situacao), ([], "Esperando o WhatsApp conectar."))
        ConexaoWhatsApp.objects.update(estado="conectado")
        ConfiguracaoOfertas.objects.update(ativo=False)
        self.rodar({1: [produto(1)]})
        self.assertEqual(self.envios(), [])

    def test_erro_na_busca_tenta_de_novo_em_5_minutos(self, _link):
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=RuntimeError("API fora do ar")):
            self.motor.uma_volta(AGORA)
        self.config.refresh_from_db()
        self.assertIn("API fora do ar", self.config.ultimo_erro)
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=5))

    def test_testar_busca_explica_por_que_nao_achou(self, _link):
        self.config.pedido_teste_em = timezone.now()
        self.config.save()
        self.rodar({1: []})
        self.assertIn("não devolveu nenhum produto", self.config.teste_erro)
        self.config.pedido_teste_em = timezone.now()
        self.config.desconto_minimo = 99
        self.config.save()
        self.rodar({1: [produto(1), produto(2)]})
        self.assertIn("devolveu 2 produtos", self.config.teste_erro)
        self.assertIn("2 barrados pelos filtros", self.config.teste_erro)

    def test_testar_busca_nao_envia_nem_mexe_na_posicao(self, _link):
        self.config.ativo = False
        self.config.pedido_teste_em = timezone.now()
        self.config.pagina_atual = 7
        self.config.save()
        self.rodar({1: [produto(1), produto(2, comissao=1)], 2: [produto(3)]})
        self.assertFalse(self.config.testando)
        self.assertEqual([o["nome"] for o in self.config.teste_resultado], ["Produto 1", "Produto 2", "Produto 3"])
        self.assertIn(ofertas.LINK_DE_EXEMPLO, self.config.teste_resultado[0]["texto"])
        self.assertEqual((self.envios(), self.config.pagina_atual), ([], 7))


class TestTelaDeOfertas(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.modulos_cortesia = "whatsapp_premium"  # os limites do Standard têm testes próprios
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS + [
            {"jid": "77@newsletter", "nome": "Canal da Bia", "tipo": "canal"},
        ])

    def dados(self, **extra):
        base = {
            "modo": "shopee", "tipo_busca": "palavra_chave", "palavra_chave": "fone", "loja": "", "ordenacao": "mais_vendidos",
            "comissao_minima": "10", "desconto_minimo": "0", "preco_minimo": "19,90", "preco_maximo": "",
            "vendas_minimas": "0", "avaliacao_minima": "4,5", "cupom": "", "sub_ids": "grupos, zap",
            "grupos": ["2@g.us"], "subid_1@g.us": "vip", "subid_2@g.us": "", "intervalo_minutos": "10", "horario_inicio": "08:00", "horario_fim": "22:00",
            "dias_semana": ["0", "1", "2", "3", "4"], "limite_diario": "40", "repetir_apos_dias": "7",
        }
        base.update(extra)
        return base

    def test_aba_conexao_sem_ultimos_envios(self):
        html = self.client.get("/whatsapp/").content.decode()
        self.assertNotIn("Últimos envios", html)
        self.assertIn(">Automação</a>", html)
        self.assertLess(html.index('id="titulo-teste"'), html.index('id="titulo-historico"'))  # teste logo abaixo da conexão

    def test_ultimas_ofertas_mostra_10_e_teste_da_busca_minimiza(self):
        for i in range(15):
            EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", destino_nome="Grupo", origem="oferta",
                                         item_id=str(i), produto=f"Produto número {i:02d}", estado="enviado")
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertEqual(html.count("Produto número"), 10)
        self.assertIn("Produto número 14", html)  # as mais novas
        self.assertNotIn("Produto número 04", html)
        self.assertIn('data-recolher="teste-da-busca"', html)
        self.assertIn('aria-controls="teste-corpo"', html)
        self.assertIn("painel/recolher", html)

    def test_salvar_ligar_pausar_e_testar(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn(">Automação</a>", html)
        self.assertIn("Achadinhos", html)

        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertRedirects(resposta, "/whatsapp/ofertas/", fetch_redirect_response=False)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual(config.grupos, [{"jid": "2@g.us", "nome": "Achadinhos"}])
        self.assertEqual((config.preco_minimo, config.avaliacao_minima, config.sub_ids), (Decimal("19.90"), Decimal("4.5"), "grupos, zap"))
        self.assertEqual(config.dias_semana, [0, 1, 2, 3, 4])
        self.assertEqual(config.sub_ids_por_grupo, {"1@g.us": "vip"})  # grupo desmarcado mantém o que foi digitado
        self.assertEqual(config.lista_sub_ids("1@g.us"), ["vip"])
        self.assertEqual(config.lista_sub_ids("2@g.us"), ["grupos", "zap"])
        self.assertContains(self.client.get("/whatsapp/ofertas/"), 'name="subid_1@g.us" value="vip"')

        self.client.post("/whatsapp/ofertas/ligar/")
        config.refresh_from_db()
        self.assertTrue(config.ativo)
        self.client.post("/whatsapp/ofertas/pausar/")
        config.refresh_from_db()
        self.assertFalse(config.ativo)

        self.client.post("/whatsapp/ofertas/testar/")
        self.assertTrue(self.client.get("/whatsapp/ofertas/estado/").json()["testando"])
        self.assertContains(self.client.get("/whatsapp/ofertas/"), "Buscando na Shopee")

    def test_a_tela_sabe_quando_uma_oferta_sai(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertEqual(html.count("data-ao-vivo"), 2)  # status e últimas enviadas (modo busca)
        antes = self.client.get("/whatsapp/ofertas/estado/").json()["versao"]
        self.assertIn(f'data-versao="{antes}"', html)
        self.assertEqual(self.client.get("/whatsapp/ofertas/estado/").json()["versao"], antes)  # nada mudou

        envio = EnvioWhatsApp.objects.create(conta=self.conta, destino="1@g.us", origem="oferta", item_id="1", produto="Fone")
        na_fila = self.client.get("/whatsapp/ofertas/estado/").json()["versao"]
        self.assertNotEqual(na_fila, antes)
        envio.estado = "enviado"
        envio.save()
        self.assertNotEqual(self.client.get("/whatsapp/ofertas/estado/").json()["versao"], na_fila)

    def test_mudar_o_intervalo_recalcula_a_proxima_oferta(self):
        self.client.post("/whatsapp/ofertas/", self.dados(intervalo_minutos="10"))
        ultima = timezone.now() - timedelta(minutes=4)
        ConfiguracaoOfertas.objects.filter(conta=self.conta).update(
            ativo=True, ultimo_envio_em=ultima, proximo_envio_em=ultima + timedelta(minutes=10),
        )
        self.client.post("/whatsapp/ofertas/", self.dados(intervalo_minutos="5"))
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual(config.proximo_envio_em, ultima + timedelta(minutes=5))

        self.client.post("/whatsapp/ofertas/", self.dados(intervalo_minutos="3"))  # já passou: sai agora
        config.refresh_from_db()
        self.assertLessEqual(abs((config.proximo_envio_em - timezone.now()).total_seconds()), 5)

    def test_filtros_em_branco_sao_opcionais(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        for campo in ("comissao_minima", "desconto_minimo", "vendas_minimas", "limite_diario"):
            self.assertRegex(html, rf'name="{campo}"(?![^>]*value=)')  # sem 0 de padrão
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(
            comissao_minima="", desconto_minimo="", vendas_minimas="", limite_diario="", preco_minimo="", avaliacao_minima="",
            preco_maximo="0,00",
        ))
        self.assertRedirects(resposta, "/whatsapp/ofertas/", fetch_redirect_response=False)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((config.comissao_minima, config.desconto_minimo, config.vendas_minimas, config.limite_diario), (0, 0, 0, 0))
        self.assertIsNone(config.preco_minimo)
        self.assertIsNone(config.preco_maximo)  # 0,00 vira "sem filtro"

    def test_lista_tem_busca_canais_e_atualizar(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn('id="busca-grupos"', html)
        self.assertIn('class="selo-canal">Canal</span>', html)
        resposta = self.client.post("/whatsapp/grupos/", {"voltar": "/whatsapp/ofertas/"})
        self.assertRedirects(resposta, "/whatsapp/ofertas/", fetch_redirect_response=False)
        self.assertTrue(ConexaoWhatsApp.objects.get(conta=self.conta).pedido_grupos)
        resposta = self.client.post("/whatsapp/grupos/", {"voltar": "https://golpe.com/"})
        self.assertRedirects(resposta, "/whatsapp/", fetch_redirect_response=False)

        self.client.post("/whatsapp/ofertas/", self.dados(grupos=["77@newsletter"]))
        self.assertEqual(ConfiguracaoOfertas.objects.get(conta=self.conta).grupos, [{"jid": "77@newsletter", "nome": "Canal da Bia"}])

    def test_erros_do_formulario(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(
            palavra_chave="", sub_ids="com-hifen", preco_minimo="50", preco_maximo="10", dias_semana=[],
            **{"subid_2@g.us": "tem espaço"},
        ))
        html = resposta.content.decode()
        for erro in ["Informe a palavra-chave.", "só pode ter letras e números", "menor que o mínimo", "pelo menos um dia",
                     "Sub ID de “Achadinhos”"]:
            self.assertIn(erro, html)
        self.assertFalse(ConfiguracaoOfertas.objects.filter(conta=self.conta).exclude(palavra_chave="").exists())

    def test_nao_liga_sem_grupo(self):
        self.client.post("/whatsapp/ofertas/ligar/")
        self.assertFalse(ConfiguracaoOfertas.objects.get(conta=self.conta).ativo)

    def test_conta_sem_o_modulo(self):
        self.conta.modulos_cortesia = ""
        self.conta.save()
        self.assertContains(self.client.get("/whatsapp/ofertas/"), "Não incluso no seu plano")
        self.client.post("/whatsapp/ofertas/ligar/")
        self.assertFalse(ConfiguracaoOfertas.objects.filter(ativo=True).exists())



CINCO_GRUPOS = [{"jid": f"{i}@g.us", "nome": f"Grupo {i}"} for i in range(1, 6)]
GRUPOS_ALEM_DO_STANDARD = [{"jid": f"{i}@g.us", "nome": f"Grupo {i}"} for i in range(1, 33)]  # 32: 2 a mais que o Standard


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotorNoPlanoStandard(TestCase):
    """Standard: até 30 grupos, 60 ofertas por grupo por dia, intervalo de 15 min no mínimo,
    sem copiar ofertas e sem IA."""

    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS_ALEM_DO_STANDARD)
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, grupos=GRUPOS_ALEM_DO_STANDARD, intervalo_minutos=5, sub_ids="grupos",
        )
        self.motor = ofertas.Motor()

    def rodar(self, produtos, agora=AGORA):
        with mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=(list(produtos), False)):
            self.motor.uma_volta(agora)
        self.config.refresh_from_db()

    def enviados_hoje(self, destino, quantos):
        EnvioWhatsApp.objects.bulk_create([
            EnvioWhatsApp(conta=self.conta, destino=destino, origem="oferta", item_id=f"velho{i}", estado="enviado")
            for i in range(quantos)])
        EnvioWhatsApp.objects.filter(destino=destino, item_id__startswith="velho").update(criado_em=AGORA - timedelta(hours=1))

    def test_so_os_30_primeiros_grupos_e_intervalo_minimo(self, _link):
        self.rodar([produto(1)])
        destinos = list(EnvioWhatsApp.objects.order_by("id").values_list("destino", flat=True))
        self.assertEqual(destinos, [f"{i}@g.us" for i in range(1, 31)])
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=15))  # pediu 5, o plano é 15

    def test_premium_vai_para_todos_os_grupos_e_respeita_o_intervalo_escolhido(self, _link):
        self.conta.modulos_cortesia = "whatsapp_premium"
        self.conta.save()
        self.rodar([produto(1)])
        self.assertEqual(EnvioWhatsApp.objects.count(), 32)
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=5))

    def test_limite_de_ofertas_por_grupo_no_dia(self, _link):
        self.enviados_hoje("1@g.us", 60)
        self.rodar([produto(1)])
        novos = set(EnvioWhatsApp.objects.filter(item_id="1").values_list("destino", flat=True))
        self.assertEqual(novos, {f"{i}@g.us" for i in range(2, 31)})  # o grupo 1 já recebeu as 60 de hoje

        for i in range(2, 31):
            self.enviados_hoje(f"{i}@g.us", 60)
        self.config.proximo_envio_em = None
        self.config.save()
        self.rodar([produto(2)])
        self.assertFalse(EnvioWhatsApp.objects.filter(item_id="2").exists())
        self.assertIn("60 ofertas de hoje", self.config.situacao)

    def test_copiar_ofertas_e_do_premium(self, _link):
        self.config.modo = ConfiguracaoOfertas.MODO_COPIAR
        self.config.origens = [{"jid": "9@g.us", "nome": "Origem"}]
        self.config.save()
        self.rodar([])
        self.assertIn("plano Premium", self.config.situacao)

    def test_ia_nao_revisa_no_standard(self, _link):
        self.config.ia_ativa = True
        with mock.patch.object(ofertas.ia, "revisar") as revisar:
            texto, revisado = ofertas.revisar_com_ia(self.config, "texto original", AGORA)
        revisar.assert_not_called()
        self.assertEqual((texto, revisado), ("texto original", False))


class TestTelaNoPlanoStandard(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()  # BasePainel: só "whatsapp" (Standard)
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS_ALEM_DO_STANDARD)

    def dados(self, **extra):
        base = {
            "modo": "shopee", "tipo_busca": "geral", "ordenacao": "mais_vendidos", "grupos": ["1@g.us"],
            "intervalo_minutos": "15", "horario_inicio": "08:00", "horario_fim": "22:00",
            "dias_semana": ["0", "1", "2", "3", "4"], "repetir_apos_dias": "7",
        }
        base.update(extra)
        return base

    def test_tela_mostra_o_que_o_plano_libera(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("No seu plano: até 30 grupos e canais, 60 ofertas por dia em cada um", html)
        self.assertIn('data-maximo="30"', html)
        self.assertRegex(html, r'value="copiar" disabled><span>Copiar de grupos e canais <small class="selo-premium">Premium')
        self.assertIn("A revisão com IA é do", html)

        self.conta.modulos_cortesia = "whatsapp_premium"
        self.conta.save()
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertNotIn("No seu plano:", html)
        self.assertIn('data-maximo="200"', html)
        self.assertNotIn('class="selo-premium"', html)

    def test_validacoes_do_plano(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(
            grupos=[f"{i}@g.us" for i in range(1, 32)], intervalo_minutos="5"))
        html = resposta.content.decode()
        self.assertIn("até 30 grupos e canais.", html)
        self.assertIn("o intervalo mínimo é de 15 minutos", html)

        resposta = self.client.post("/whatsapp/ofertas/", self.dados(modo="copiar", origens=["5@g.us"], intervalo_minutos="0"))
        self.assertContains(resposta, "Copiar ofertas de outros grupos e canais é do plano Premium.")
        self.assertFalse(ConfiguracaoOfertas.objects.filter(conta=self.conta, modo="copiar").exists())

        resposta = self.client.post("/whatsapp/ofertas/", self.dados(grupos=["1@g.us", "2@g.us", "3@g.us"], ia_ativa="on"))
        self.assertRedirects(resposta, "/whatsapp/ofertas/", fetch_redirect_response=False)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((len(config.grupos), config.intervalo_minutos, config.ia_ativa), (3, 15, False))

    def test_grupos_salvos_alem_do_plano_aparecem_avisados(self):
        ConfiguracaoOfertas.objects.create(conta=self.conta, grupos=GRUPOS_ALEM_DO_STANDARD)
        self.assertContains(self.client.get("/whatsapp/ofertas/"), "os 2 últimos da lista não recebem ofertas")


class TestRitmoComMuitosGrupos(TestCase):
    """Com muitos grupos, a oferta leva minutos para sair: a próxima espera a fila andar e a fila de
    envio não deixa uma conta grande segurar as outras."""

    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="grande@exemplo.com", modulos_cortesia="whatsapp_premium", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        self.grupos = [{"jid": f"{i}@g.us", "nome": f"Grupo {i}"} for i in range(1, 201)]
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=self.grupos)
        self.config = ConfiguracaoOfertas.objects.create(conta=self.conta, ativo=True, grupos=self.grupos, intervalo_minutos=3,
                                                         horario_inicio="08:00", horario_fim="22:00", dias_semana=[0, 1, 2, 3, 4, 5, 6])
        self.config.refresh_from_db()  # horários como time, não texto

    def test_premium_envia_para_200_grupos(self):
        self.assertEqual(len(ofertas.grupos_do_plano(self.config)), 200)
        self.assertEqual(ofertas.minutos_por_rodada(200), 14)  # 200 x 4 s

    def test_proxima_oferta_espera_a_fila_andar(self):
        EnvioWhatsApp.objects.bulk_create([EnvioWhatsApp(conta=self.conta, destino=f"{i}@g.us", origem="oferta", item_id="1")
                                           for i in range(1, 32)])
        motivo = ofertas.motivo_para_esperar(self.config, self.conexao, AGORA.replace(hour=12))
        self.assertEqual(motivo, "Enviando a oferta anterior: faltam 31 mensagens. A próxima sai depois.")
        EnvioWhatsApp.objects.filter(destino="31@g.us").update(estado="enviado")
        self.assertEqual(ofertas.motivo_para_esperar(self.config, self.conexao, AGORA.replace(hour=12)), "")

    def test_estimativa_da_tela(self):
        ritmo = ofertas.ritmo_com_muitos_grupos(self.config, ofertas.regras_do_plano(self.config))
        self.assertEqual(ritmo, {"grupos": 200, "minutos": 14, "por_dia": 60, "limitado": True})  # 14 h / 14 min
        self.config.grupos = self.grupos[:10]
        self.assertIsNone(ofertas.ritmo_com_muitos_grupos(self.config, ofertas.regras_do_plano(self.config)))

    def test_os_tempos_batem_com_o_gerenciador(self):
        from bot_whatsapp import gerenciador

        por_volta = gerenciador.INTERVALO
        self.assertEqual(ofertas.SEGUNDOS_POR_MENSAGEM, -(-gerenciador.ESPACO_ENTRE_ENVIOS // por_volta) * por_volta)

    def test_fila_de_envio_reveza_as_contas(self):
        from bot_whatsapp import gerenciador

        outra = ContaAppfiliado.objects.create(email="pequena@exemplo.com", modulos_cortesia="whatsapp")
        EnvioWhatsApp.objects.bulk_create([EnvioWhatsApp(conta=self.conta, destino=f"{i}@g.us", origem="oferta", item_id="1")
                                           for i in range(1, 101)])
        EnvioWhatsApp.objects.create(conta=outra, destino="9@g.us", origem="oferta", item_id="2")
        enviadas = []

        class Cliente:
            def send_message(self, destino, *args, **kwargs):
                enviadas.append(destino.User)
                return mock.Mock(ID="X")

        sessao = mock.Mock(conectada=True, cliente=Cliente())
        g = gerenciador.Gerenciador.__new__(gerenciador.Gerenciador)
        g.sessoes, g.ultimo_envio = {self.conta.pk: sessao, outra.pk: sessao}, {}
        with mock.patch.object(gerenciador, "ler_foto", return_value=None):
            g.enviar_pendentes()
        self.assertEqual(sorted(enviadas), ["1", "9"])  # uma de cada conta, mesmo com 100 na fila da primeira
