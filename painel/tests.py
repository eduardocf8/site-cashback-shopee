import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from licencas.models import Assinatura, ContaAppfiliado, ProdutoZouti

from . import cripto
from .emails import link_definir_senha

HOST = "app.appfiliado.com.br"
SENHA = "uma-senha-boa-123"


@override_settings(
    APPFILIADO_PAINEL_HOSTS=[HOST],
    ALLOWED_HOSTS=[HOST, "testserver"],
    APPFILIADO_PAINEL_URL=f"https://{HOST}",
)
class BasePainel(TestCase):
    def setUp(self):
        cache.clear()  # o contador de tentativas de login fica no cache
        self.client = Client(HTTP_HOST=HOST)
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", nome="Bia Souza", modulos_cortesia="whatsapp",
        )
        self.conta.definir_senha(SENHA)
        self.conta.save()

    def entrar(self, email="bia@exemplo.com", senha=SENHA):
        return self.client.post("/entrar/", {"email": email, "senha": senha})


class TestDominio(BasePainel):
    def test_raiz_do_dominio_pede_login(self):
        resposta = self.client.get("/")
        self.assertRedirects(resposta, "/entrar/?proximo=%2F", fetch_redirect_response=False)

    def test_nada_da_cash_b_aparece_no_dominio_do_painel(self):
        resposta = self.client.get("/admin/")
        self.assertEqual(resposta.status_code, 404)
        self.assertContains(resposta, "Appfiliado", status_code=404)
        self.assertNotContains(resposta, "cash-b", status_code=404)

    def test_api_de_licencas_tambem_responde_no_dominio(self):
        resposta = self.client.post(
            "/licencas/validar/", data='{"chave": "%s"}' % self.conta.chave, content_type="application/json",
        )
        self.assertTrue(resposta.json()["valido"])

    def test_deixa_claro_que_e_so_pra_shopee(self):
        html = self.client.get("/entrar/").content.decode()
        self.assertIn("afiliados Shopee", html)
        self.assertIn("sem vínculo oficial com a Shopee", html)

    def test_painel_nao_existe_no_dominio_da_cash_b(self):
        self.assertEqual(Client().get("/entrar/").status_code, 404)


class TestLogin(BasePainel):
    def test_login_certo_entra_e_volta_pra_pagina_pedida(self):
        resposta = self.client.post("/entrar/?proximo=/plano/", {"email": "BIA@exemplo.com", "senha": SENHA})
        self.assertRedirects(resposta, "/plano/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), "Olá, Bia")
        self.conta.refresh_from_db()
        self.assertIsNotNone(self.conta.ultimo_login)

    def test_proximo_pra_outro_site_e_ignorado(self):
        resposta = self.client.post("/entrar/?proximo=https://golpe.com/", {"email": "bia@exemplo.com", "senha": SENHA})
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)

    def test_email_com_maiusculas_no_cadastro_tambem_entra(self):
        ContaAppfiliado.objects.filter(pk=self.conta.pk).update(email="Bia@Exemplo.com")
        self.assertRedirects(self.entrar(), "/", fetch_redirect_response=False)

    def test_senha_errada(self):
        self.assertContains(self.entrar(senha="errada"), "E-mail ou senha incorretos")

    def test_conta_sem_senha_recebe_orientacao(self):
        ContaAppfiliado.objects.create(email="nova@exemplo.com")
        self.assertContains(self.entrar(email="nova@exemplo.com", senha="qualquer"), "ainda não criou sua senha")

    def test_muitas_tentativas_bloqueiam_mesmo_com_a_senha_certa(self):
        for _ in range(8):
            self.entrar(senha="errada")
        self.assertContains(self.entrar(), "Muitas tentativas")

    def test_sair(self):
        self.entrar()
        self.client.post("/sair/")
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_trocar_a_senha_em_outro_lugar_derruba_a_sessao(self):
        self.entrar()
        self.conta.definir_senha("outra-senha-boa-456")
        self.conta.save()
        self.assertEqual(self.client.get("/").status_code, 302)


class TestSenha(BasePainel):
    def test_esqueci_senha_manda_link_so_pra_quem_existe_mas_responde_igual(self):
        resposta = self.client.post("/senha/esqueci/", {"email": "bia@exemplo.com"})
        self.assertContains(resposta, "Se esse e-mail tiver uma assinatura")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"https://{HOST}/senha/definir/", mail.outbox[0].body)

        resposta = self.client.post("/senha/esqueci/", {"email": "ninguem@exemplo.com"})
        self.assertContains(resposta, "Se esse e-mail tiver uma assinatura")
        self.assertEqual(len(mail.outbox), 1)

    def test_link_define_senha_entra_e_nao_vale_de_novo(self):
        nova = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        caminho = link_definir_senha(nova).replace(f"https://{HOST}", "")

        self.assertContains(self.client.get(caminho), "Crie sua senha")
        resposta = self.client.post(caminho, {"senha": "senha-nova-789", "confirmacao": "senha-nova-789"})
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)
        nova.refresh_from_db()
        self.assertTrue(nova.confere_senha("senha-nova-789"))

        self.client.post("/sair/")
        self.assertContains(self.client.get(caminho), "Link vencido", status_code=400)

    def test_senhas_diferentes_ou_fracas_sao_recusadas(self):
        nova = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        caminho = link_definir_senha(nova).replace(f"https://{HOST}", "")
        self.assertContains(self.client.post(caminho, {"senha": "senha-nova-789", "confirmacao": "outra"}),
                            "não são iguais")
        self.assertContains(self.client.post(caminho, {"senha": "12345678", "confirmacao": "12345678"}),
                            "erro")
        nova.refresh_from_db()
        self.assertFalse(nova.tem_senha)

    def test_trocar_senha_logado(self):
        self.entrar()
        resposta = self.client.post("/configuracoes/", {
            "formulario": "senha", "senha_atual": SENHA,
            "senha": "nova-senha-boa-321", "confirmacao": "nova-senha-boa-321",
        })
        self.assertRedirects(resposta, "/configuracoes/", fetch_redirect_response=False)
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.confere_senha("nova-senha-boa-321"))
        self.assertEqual(self.client.get("/").status_code, 200)  # a sessão atual continua


class TestShopee(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    @mock.patch("painel.views.testar_credenciais", return_value=(True, "Conexão com a Shopee funcionando."))
    def test_salva_secret_cifrado_quando_a_shopee_aceita(self, _):
        resposta = self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "123", "secret": "segredo"})
        self.assertRedirects(resposta, "/configuracoes/", fetch_redirect_response=False)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.shopee_app_id, "123")
        self.assertNotIn("segredo", self.conta.shopee_secret_cifrado)
        self.assertEqual(cripto.decifrar(self.conta.shopee_secret_cifrado), "segredo")
        self.assertIsNotNone(self.conta.shopee_validado_em)
        self.assertNotContains(self.client.get("/configuracoes/"), "segredo")

    @mock.patch("painel.views.testar_credenciais", return_value=(False, "A Shopee não aceitou esse AppID e Secret."))
    def test_nao_salva_quando_a_shopee_recusa(self, _):
        resposta = self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "123", "secret": "errado"})
        self.assertContains(resposta, "não aceitou")
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.shopee_app_id, "")

    @mock.patch("painel.views.testar_credenciais", return_value=(True, "ok"))
    def test_secret_em_branco_mantem_o_salvo(self, testar):
        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("antigo")
        self.conta.save()
        self.client.post("/configuracoes/", {"formulario": "shopee", "app_id": "456", "secret": ""})
        testar.assert_called_with("456", "antigo")

    def test_cifra_e_decifra(self):
        cifrado = cripto.cifrar("abc")
        self.assertNotEqual(cifrado, "abc")
        self.assertEqual(cripto.decifrar(cifrado), "abc")
        self.assertEqual(cripto.decifrar("lixo"), "")


class TestPaginas(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_menu_mostra_cadeado_e_em_breve(self):
        html = self.client.get("/").content.decode()
        self.assertIn("Não incluso no seu plano", html)  # vídeos (fora do plano): cadeado
        self.assertIn("Em breve", html)  # Instagram (ainda não está no painel)

    def test_modulo_fora_do_plano_mostra_convite(self):
        self.assertRedirects(self.client.get("/m/site/"), "/meu-site/", fetch_redirect_response=False)
        self.assertContains(self.client.get("/meu-site/"), "Não incluso no seu plano")

    def test_modulo_ainda_nao_pronto_mostra_em_breve(self):
        self.assertContains(self.client.get("/m/instagram/"), "Em breve")

    def test_modulo_inexistente(self):
        self.assertEqual(self.client.get("/m/nada/").status_code, 404)

    def test_plano_mostra_modulos_assinaturas_e_chave(self):
        ProdutoZouti.objects.create(zouti_product_id="prod_site", nome="Site", modulos="site")
        Assinatura.objects.create(
            conta=self.conta, zouti_subscription_id="sub_1", zouti_product_ids="prod_site",
            plano="Mensal", status=Assinatura.STATUS_ATIVA, proxima_cobranca=timezone.localdate() + timedelta(days=20),
        )
        html = self.client.get("/plano/").content.decode()
        self.assertIn(self.conta.chave, html)
        self.assertIn("Mensal", html)
        self.assertEqual(len(re.findall(r"estado-liberado", html)), 2)  # whatsapp (cortesia) e site


@override_settings(APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestEmailDaChave(TestCase):
    def test_email_da_chave_convida_pra_criar_a_senha_do_painel(self):
        from licencas.services import enviar_email_chave

        conta = ContaAppfiliado.objects.create(email="nova@exemplo.com")
        enviar_email_chave(conta.pk)
        self.assertNotIn(conta.chave, mail.outbox[0].body)  # sem app, a chave não é mais mostrada
        self.assertIn(f"https://{HOST}/senha/definir/", mail.outbox[0].body)


# --- Fase 2: resultados, metas e Início --------------------------------------------

from datetime import date, datetime  # noqa: E402
from decimal import Decimal  # noqa: E402
from io import StringIO  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from django.core.management import call_command  # noqa: E402

from . import resultados, telas  # noqa: E402
from .models import (  # noqa: E402
    MetaMensal, RegraSubId, ResultadoDiario, ResultadoSubIdDiario, SincronizacaoResultados,
)
from .shopee import ShopeeAPIError, buscar_conversoes  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")


def ts(ano, mes, dia, hora=12):
    """Timestamp de um horário de São Paulo."""
    return int(datetime(ano, mes, dia, hora, tzinfo=SP).timestamp())


def conversao(compra, pedidos, comissao="10,00", utm="", conversion_id="c1"):
    return {"conversionId": conversion_id, "purchaseTime": compra, "netCommission": comissao,
            "utmContent": utm, "orders": pedidos}


def pedido(order_id, status, itens):
    return {"orderId": order_id, "orderStatus": status, "items": itens}


def item(preco, qtd=1, comissao="0", validado_em=None):
    return {"itemPrice": preco, "qty": qtd, "itemTotalCommission": comissao, "completeTime": validado_em}


class TestCalculo(TestCase):
    def test_regras_de_faturamento_e_comissoes(self):
        conversoes = [
            # compra 10/10, validada em 15/10
            conversao(ts(2026, 10, 10), [pedido("p1", "COMPLETED", [item("50,00", 2, "8,00", ts(2026, 10, 15))])],
                      comissao="8,00", utm="grupoA-story---"),
            # compra 10/10 cancelada: não entra no faturamento nem na estimada
            conversao(ts(2026, 10, 10), [pedido("p2", "CANCELLED", [item("200")])], comissao="30"),
            # 23h de 09/10 em São Paulo (02h de 10/10 em UTC) conta no dia 09
            conversao(ts(2026, 10, 9, 23), [pedido("p3", "PENDING", [item("40")])], comissao="4"),
        ]
        por_dia, por_sub_id = resultados.calcular_por_dia(conversoes)

        dia10 = por_dia[date(2026, 10, 10)]
        self.assertEqual(dia10["faturamento"], 100.0)
        self.assertEqual(dia10["pedidos"], {"p1"})
        self.assertEqual(dia10["comissao_estimada"], 8.0)
        self.assertEqual(dia10["comissao_validada"], 0.0)
        self.assertEqual(por_dia[date(2026, 10, 15)]["comissao_validada"], 8.0)
        self.assertEqual(por_dia[date(2026, 10, 9)]["faturamento"], 40.0)
        # cada venda conta uma vez, com os Sub IDs preenchidos juntos
        self.assertEqual(por_sub_id[(date(2026, 10, 10), "grupoA-story")]["vendas"], 1)
        self.assertEqual(por_sub_id[(date(2026, 10, 10), "grupoA-story")]["comissao_estimada"], 8.0)
        self.assertEqual(por_sub_id[(date(2026, 10, 10), "sem_subid")]["comissao_estimada"], 0.0)

    def test_sub_id_vem_com_os_5_campos_separados_por_hifen(self):
        self.assertEqual(resultados.sub_id({"utmContent": "----"}), "sem_subid")
        self.assertEqual(resultados.sub_id({"utmContent": "-"}), "sem_subid")
        self.assertEqual(resultados.sub_id({}), "sem_subid")
        self.assertEqual(resultados.sub_id({"utmContent": "siteconversor----"}), "siteconversor")
        self.assertEqual(resultados.sub_id({"utmContent": "grupoA--story--"}), "grupoA-story")

    def test_numeros_em_varios_formatos(self):
        self.assertEqual(resultados.para_numero("1.234,56"), 1234.56)
        self.assertEqual(resultados.para_numero("12.5"), 12.5)
        self.assertEqual(resultados.para_numero(None), 0.0)


class TestSincronizacao(TestCase):
    AGORA = datetime(2026, 10, 18, 15, 0, tzinfo=SP)

    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", shopee_app_id="123", shopee_secret_cifrado=cripto.cifrar("segredo"),
            shopee_validado_em=timezone.now(),
        )

    def sincronizar(self, conversoes):
        with mock.patch("painel.resultados.paginas_de_conversoes", return_value=[conversoes]) as buscar:
            resumo = resultados.sincronizar_conta(self.conta, agora=self.AGORA)
        return buscar, resumo

    def test_guarda_os_dias_da_janela_e_zera_os_sem_venda(self):
        antigo = ResultadoDiario.objects.create(
            conta=self.conta, dia=date(2026, 7, 1), faturamento=Decimal("999"), comissao_validada=Decimal("50"),
        )
        validada_velha = ResultadoDiario.objects.create(
            conta=self.conta, dia=date(2026, 8, 1), faturamento=Decimal("1"), comissao_validada=Decimal("77"),
        )
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=date(2026, 10, 1), sub_id="velho", vendas=3)

        buscar, resumo = self.sincronizar([
            conversao(ts(2026, 10, 10), [pedido("p1", "COMPLETED", [item("50", 1, "5", ts(2026, 10, 12))])],
                      comissao="5", utm="grupoA"),
        ])

        app_id, secret, inicio_ts, fim_ts = buscar.call_args.args
        self.assertEqual((app_id, secret), ("123", "segredo"))
        self.assertEqual(fim_ts, int(self.AGORA.timestamp()))
        self.assertEqual(resumo["dias"], 89)

        dia10 = ResultadoDiario.objects.get(conta=self.conta, dia=date(2026, 10, 10))
        self.assertEqual((dia10.pedidos, dia10.faturamento, dia10.comissao_estimada), (1, Decimal("50.00"), Decimal("5.00")))
        self.assertEqual(ResultadoDiario.objects.get(conta=self.conta, dia=date(2026, 10, 12)).comissao_validada, Decimal("5.00"))
        self.assertEqual(ResultadoDiario.objects.get(conta=self.conta, dia=date(2026, 10, 18)).faturamento, 0)

        # fora da janela da API: fica como estava
        antigo.refresh_from_db()
        self.assertEqual(antigo.faturamento, Decimal("999"))
        # dentro da janela, mas com mais de 60 dias: faturamento recalculado, validada mantida
        validada_velha.refresh_from_db()
        self.assertEqual((validada_velha.faturamento, validada_velha.comissao_validada), (0, Decimal("77")))

        self.assertEqual(list(ResultadoSubIdDiario.objects.values_list("sub_id", flat=True)), ["grupoA"])
        estado = SincronizacaoResultados.objects.get(conta=self.conta)
        self.assertEqual(estado.cobertura_inicio, date(2026, 7, 22))

    def test_sem_credenciais_nao_busca(self):
        self.conta.shopee_secret_cifrado = ""
        with self.assertRaises(ValueError):
            resultados.sincronizar_conta(self.conta)

    def test_fila_pedidos_manuais_primeiro_e_depois_os_atrasados(self):
        recente = ContaAppfiliado.objects.create(
            email="recente@exemplo.com", shopee_app_id="1", shopee_secret_cifrado=cripto.cifrar("s"),
            shopee_validado_em=timezone.now(),
        )
        SincronizacaoResultados.objects.create(conta=recente, iniciada_em=timezone.now(), concluida_em=timezone.now())
        pediu = ContaAppfiliado.objects.create(
            email="pediu@exemplo.com", shopee_app_id="2", shopee_secret_cifrado=cripto.cifrar("s"),
            shopee_validado_em=timezone.now(),
        )
        SincronizacaoResultados.objects.create(conta=pediu, iniciada_em=timezone.now() - timedelta(minutes=5))
        resultados.pedir_atualizacao(pediu)
        ContaAppfiliado.objects.create(email="semshopee@exemplo.com")

        self.assertEqual(resultados.contas_pendentes(), [pediu, self.conta])

    def test_processar_guarda_o_erro_e_o_comando_roda_a_fila(self):
        with mock.patch("painel.resultados.paginas_de_conversoes", side_effect=ShopeeAPIError("Credenciais inválidas")):
            saida = StringIO()
            call_command("sincronizar_painel", stdout=saida)
        self.assertIn("erro", saida.getvalue())
        estado = SincronizacaoResultados.objects.get(conta=self.conta)
        self.assertIn("Credenciais inválidas", estado.erro)
        self.assertFalse(estado.em_andamento)

        with mock.patch("painel.resultados.paginas_de_conversoes", return_value=[]):
            resultados.pedir_atualizacao(self.conta)
            call_command("sincronizar_painel", stdout=StringIO())
        estado.refresh_from_db()
        self.assertEqual(estado.erro, "")
        self.assertFalse(estado.aguardando)


    def test_atualizar_so_ontem_e_hoje(self):
        with mock.patch("painel.resultados.paginas_de_conversoes", return_value=[[]]) as buscar:
            resumo = resultados.sincronizar_conta(self.conta, agora=self.AGORA, curta=True)
        inicio = buscar.call_args[0][2]
        self.assertEqual(datetime.fromtimestamp(inicio, SP), datetime(2026, 10, 16, 23, 59, 59, tzinfo=SP))
        self.assertEqual((resumo["dias"], resumo["completa"]), (2, False))  # 17 e 18/10
        # O pedido curto vem do botão; um pedido de 30 dias ainda na fila não vira curto.
        estado = resultados.pedir_atualizacao(self.conta, curta=True)
        self.assertTrue(estado.pedido_curto)
        estado = resultados.pedir_atualizacao(self.conta)
        self.assertFalse(estado.pedido_curto)
        self.assertFalse(resultados.pedir_atualizacao(self.conta, curta=True).pedido_curto)
        with mock.patch.object(resultados, "sincronizar_conta", return_value={"conversoes": 0, "dias": 30, "completa": False}) as sinc:
            resultados.processar(self.conta)
        self.assertEqual(sinc.call_args.kwargs["curta"], False)
        resultados.pedir_atualizacao(self.conta, curta=True)
        with mock.patch.object(resultados, "sincronizar_conta", return_value={"conversoes": 0, "dias": 2, "completa": False, "curta": True}) as sinc:
            self.assertIn("ontem e hoje", resultados.processar(self.conta))
        self.assertEqual(sinc.call_args.kwargs["curta"], True)
        self.assertFalse(SincronizacaoResultados.objects.get(conta=self.conta).pedido_curto)


class TestAgruparSubIds(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(email="bia@exemplo.com")

    def regra(self, operador, texto, nome="Grupo"):
        return RegraSubId.objects.create(conta=self.conta, operador=operador, texto=texto, nome=nome)

    def test_os_6_filtros_sem_diferenciar_maiusculas(self):
        casos = [
            ("comeca", "GRUPO", "grupoVip", True), ("comeca", "grupo", "vipgrupo", False),
            ("nao_comeca", "grupo", "vipgrupo", True), ("nao_comeca", "grupo", "grupoVip", False),
            ("contem", "vip", "grupoVipNoite", True), ("contem", "vip", "grupoNoite", False),
            ("nao_contem", "vip", "grupoNoite", True), ("nao_contem", "vip", "grupoVip", False),
            ("termina", "noite", "grupoNOITE", True), ("termina", "noite", "noiteGrupo", False),
            ("nao_termina", "noite", "noiteGrupo", True), ("nao_termina", "noite", "grupoNoite", False),
        ]
        for operador, texto, valor, esperado in casos:
            with self.subTest(operador=operador, valor=valor):
                self.assertEqual(RegraSubId(operador=operador, texto=texto).casa(valor), esperado)

    def test_agrupa_na_ordem_e_soma(self):
        dia = date(2026, 10, 10)
        for sub, vendas, comissao in [("grupoA", 2, "10"), ("grupoB", 3, "20"), ("story", 1, "50"),
                                      ("sem_subid", 4, "5")]:
            ResultadoSubIdDiario.objects.create(conta=self.conta, dia=dia, sub_id=sub, vendas=vendas,
                                                comissao_estimada=Decimal(comissao))
        self.regra("comeca", "grupo", "Grupos")
        self.regra("contem", "a", "Nunca usado para grupoA")  # a primeira regra que casa vale
        linhas = resultados.por_sub_id(self.conta, dia, dia)
        self.assertEqual(
            [(l["sub_id"], l["vendas"], l["comissao"], l["quantidade"]) for l in linhas],
            [("story", 1, Decimal("50"), 1), ("Grupos", 5, Decimal("30"), 2), ("Sem Sub ID", 4, Decimal("5"), 1)],
        )

    def test_resumo_mostra_quantos_sub_ids_cada_regra_junta(self):
        hoje = date(2026, 10, 18)
        for sub in ("grupoA", "grupoB", "story"):
            ResultadoSubIdDiario.objects.create(conta=self.conta, dia=hoje, sub_id=sub, vendas=1)
        self.regra("comeca", "grupo")
        self.regra("termina", "zzz")
        resumo = resultados.resumo_das_regras(self.conta, hoje)
        self.assertEqual([(r["quantidade"], r["exemplos"]) for r in resumo], [(2, ["grupoA", "grupoB"]), (0, [])])


    def test_nome_para_vendas_sem_sub_id(self):
        dia = date(2026, 10, 10)
        for sub, vendas in [("sem_subid", 4), ("story", 1)]:
            ResultadoSubIdDiario.objects.create(conta=self.conta, dia=dia, sub_id=sub, vendas=vendas)
        self.regra("nao_comeca", "grupo", "Outros")  # não pega as vendas sem Sub ID
        self.regra("sem", "", "Orgânico")
        nomes = [l["sub_id"] for l in resultados.por_sub_id(self.conta, dia, dia)]
        self.assertEqual(sorted(nomes), ["Orgânico", "Outros"])
        self.assertEqual(resultados.resumo_das_regras(self.conta, dia)[1]["quantidade"], 1)
        self.assertTrue(RegraSubId(operador="sem").casa("sem_subid"))
        self.assertFalse(RegraSubId(operador="sem").casa("story"))
        from .forms import RegraSubIdForm
        form = RegraSubIdForm({"operador": "sem", "texto": "", "nome": "Orgânico"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(RegraSubIdForm({"operador": "comeca", "texto": " ", "nome": "X"}).is_valid())


class TestBuscaNaShopee(TestCase):
    def test_pagina_e_tira_campo_que_a_api_nao_conhece(self):
        respostas = [
            ShopeeAPIError('Cannot query field "netCommission" on type "ConversionReport".'),
            {"conversionReport": {"nodes": [{"conversionId": "1"}], "pageInfo": {"scrollId": "abc", "hasNextPage": True}}},
            {"conversionReport": {"nodes": [{"conversionId": "2"}], "pageInfo": {"scrollId": "", "hasNextPage": False}}},
        ]
        with mock.patch("painel.shopee.executar_graphql_com_credenciais", side_effect=respostas) as executar:
            conversoes = buscar_conversoes("123", "segredo", 1, 2)
        self.assertEqual([c["conversionId"] for c in conversoes], ["1", "2"])
        consultas = [chamada.args[2] for chamada in executar.call_args_list]
        self.assertIn("netCommission", consultas[0])
        self.assertNotIn("netCommission", consultas[1])
        self.assertIn('scrollId:"abc"', consultas[2])
        self.assertNotIn("netCommission", consultas[2])

    def test_outros_erros_sobem(self):
        with mock.patch("painel.shopee.executar_graphql_com_credenciais", side_effect=ShopeeAPIError("Sem permissão")):
            with self.assertRaises(ShopeeAPIError):
                buscar_conversoes("123", "segredo", 1, 2)


class TestTelas(TestCase):
    def test_ler_numero_br(self):
        self.assertEqual(telas.ler_numero_br("30.000,00"), 30000.0)
        self.assertEqual(telas.ler_numero_br("R$ 30.000"), 30000.0)
        self.assertEqual(telas.ler_numero_br("1250,5"), 1250.5)
        self.assertEqual(telas.ler_numero_br("37500"), 37500.0)
        self.assertEqual(telas.ler_numero_br("12.50"), 12.5)
        self.assertIsNone(telas.ler_numero_br(""))

    def test_faixas_do_formulario_completa_o_faturamento_pelo_percentual(self):
        faixas = telas.faixas_do_formulario({
            "percentual_1": "100", "faturamento_1": "30.000", "bonus_1": "300",
            "percentual_2": "125", "faturamento_2": "", "bonus_2": "500",
            "percentual_3": "150", "faturamento_3": "", "bonus_3": "",
        })
        self.assertEqual([f["faturamento"] for f in faixas], [30000.0, 37500.0, 45000.0])
        self.assertEqual(faixas[2]["bonus"], 0)

    def test_periodo_personalizado_e_validado(self):
        hoje = date(2026, 10, 18)
        periodo = telas.periodo_da_requisicao({"periodo": "personalizado", "de": "2026-12-01", "ate": "2026-10-01"}, hoje)
        self.assertEqual((periodo["inicio"], periodo["fim"]), (date(2026, 10, 1), hoje))
        periodo = telas.periodo_da_requisicao({"periodo": "personalizado", "de": "2020-01-01", "ate": "2026-10-10"}, hoje)
        self.assertEqual(periodo["inicio"], date(2025, 10, 10))
        periodo = telas.periodo_da_requisicao({"periodo": "xyz", "metrica": "nada"}, hoje)
        self.assertEqual((periodo["chave"], periodo["inicio"], periodo["metrica"]), ("mes", date(2026, 10, 1), "faturamento"))


@mock.patch("painel.telas.hoje", return_value=date(2026, 10, 18))
class TestTelasDeResultados(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def conectar_shopee(self):
        self.conta.shopee_app_id = "123"
        self.conta.shopee_secret_cifrado = cripto.cifrar("segredo")
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        for dia, faturamento, estimada, validada in [(1, "1000", "80", "0"), (10, "2500.50", "200", "35.5"), (18, "300", "25", "0")]:
            ResultadoDiario.objects.create(
                conta=self.conta, dia=date(2026, 10, dia), pedidos=3, faturamento=Decimal(faturamento),
                comissao_estimada=Decimal(estimada), comissao_validada=Decimal(validada),
            )
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 9, 30), faturamento=Decimal("777"))
        ResultadoSubIdDiario.objects.create(conta=self.conta, dia=date(2026, 10, 10), sub_id="grupoA",
                                            vendas=2, comissao_estimada=Decimal("150"))

    def test_sem_shopee_pede_pra_conectar(self, _):
        self.assertContains(self.client.get("/resultados/"), "Conecte sua conta da Shopee")
        html = self.client.get("/").content.decode()
        self.assertIn("Conectar sua conta de afiliado da Shopee", html)

    def test_inicio_sem_metas_oferece_cadastrar_sem_cobrar(self, _):
        self.conectar_shopee()
        html = self.client.get("/").content.decode()
        self.assertIn("Cadastrar metas", html)
        self.assertNotIn("Cadastrar as metas do mês", html)  # metas são opcionais: não viram passo pendente

    def test_inicio_mostra_ontem_e_a_validada_de_hoje(self, _):
        self.conectar_shopee()
        ResultadoDiario.objects.create(conta=self.conta, dia=date(2026, 10, 17), pedidos=7,
                                       faturamento=Decimal("812.40"), comissao_estimada=Decimal("61.10"))
        ResultadoDiario.objects.filter(conta=self.conta, dia=date(2026, 10, 18)).update(comissao_validada=Decimal("42.75"))
        html = self.client.get("/").content.decode()
        self.assertIn("<h2>Ontem</h2>", html)
        self.assertIn("R$ 812,40", html)
        self.assertIn("R$ 61,10", html)
        self.assertIn("Comissão validada hoje", html)
        self.assertIn("R$ 42,75", html)

    def test_no_dia_1_o_inicio_mostra_o_mes_que_fechou(self, _):
        self.conectar_shopee()
        with mock.patch("painel.telas.hoje", return_value=date(2026, 11, 1)):
            html = self.client.get("/").content.decode()
        self.assertIn("Mês passado", html)
        self.assertIn("Outubro/2026", html)
        self.assertIn("R$ 3.800,50", html)  # outubro inteiro
        self.assertIn("O mês novo aparece aqui amanhã", html)
        with mock.patch("painel.telas.hoje", return_value=date(2026, 11, 2)):
            html = self.client.get("/").content.decode()
        self.assertIn("Mês atual", html)
        self.assertIn("Novembro/2026", html)
        self.assertNotIn("Mês passado", html)

    def test_resultados_avisam_quando_o_periodo_inclui_hoje(self, _):
        self.conectar_shopee()
        aviso = "De hoje só aparece a comissão validada"
        self.assertContains(self.client.get("/resultados/?periodo=hoje"), aviso)
        self.assertNotContains(self.client.get("/resultados/?periodo=mes_passado"), aviso)

    def test_criar_e_apagar_agrupamento_nas_configuracoes(self, _):
        self.conectar_shopee()
        resposta = self.client.post("/configuracoes/", {
            "formulario": "regra_sub_id", "operador": "comeca", "texto": " grupo ", "nome": "Grupos de WhatsApp",
        })
        self.assertRedirects(resposta, "/configuracoes/#sub-ids", fetch_redirect_response=False)
        regra = RegraSubId.objects.get(conta=self.conta)
        self.assertEqual((regra.operador, regra.texto), ("comeca", "grupo"))

        html = self.client.get("/configuracoes/").content.decode()
        self.assertIn("Grupos de WhatsApp", html)
        self.assertIn("Junta 1 Sub ID", html)  # o grupoA dos dados de exemplo
        html = self.client.get("/resultados/").content.decode()
        self.assertIn("Grupos de WhatsApp", html)

        self.client.post("/configuracoes/", {"formulario": "apagar_regra_sub_id", "regra": regra.pk})
        self.assertFalse(RegraSubId.objects.exists())

    def test_agrupamento_de_outra_conta_nao_e_apagado(self, _):
        outra = ContaAppfiliado.objects.create(email="outra@exemplo.com")
        regra = RegraSubId.objects.create(conta=outra, operador="contem", texto="x", nome="X")
        self.client.post("/configuracoes/", {"formulario": "apagar_regra_sub_id", "regra": regra.pk})
        self.assertTrue(RegraSubId.objects.filter(pk=regra.pk).exists())

    def test_agrupamento_sem_texto_e_recusado(self, _):
        resposta = self.client.post("/configuracoes/", {
            "formulario": "regra_sub_id", "operador": "comeca", "texto": "  ", "nome": "Grupos",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(RegraSubId.objects.exists())

    def test_resultados_do_mes(self, _):
        self.conectar_shopee()
        html = self.client.get("/resultados/").content.decode()
        self.assertIn("R$ 3.800,50", html)  # faturamento de outubro (sem o 30/09)
        self.assertIn("R$ 305,00", html)  # estimada
        self.assertIn("R$ 35,50", html)  # validada
        self.assertIn("grupoA", html)

    def test_resultados_por_periodo_personalizado_e_mes_passado(self, _):
        self.conectar_shopee()
        html = self.client.get("/resultados/?periodo=personalizado&de=2026-09-30&ate=2026-10-01").content.decode()
        self.assertIn("R$ 1.777,00", html)
        html = self.client.get("/resultados/?periodo=mes_passado&agrupar=semana&metrica=pedidos").content.decode()
        self.assertIn("R$ 777,00", html)

    def test_meta_aparece_nos_resultados_e_no_inicio(self, _):
        self.conectar_shopee()
        MetaMensal.objects.create(conta=self.conta, ano=2026, mes=10, faixas=[
            {"percentual": 100, "faturamento": 3000, "bonus": 100},
            {"percentual": 125, "faturamento": 3750, "bonus": 200},
            {"percentual": 150, "faturamento": 4500, "bonus": 300},
        ])
        html = self.client.get("/resultados/").content.decode()
        self.assertIn("Meta do mês", html)
        self.assertIn("faltam R$ 699,50", html)  # falta para 150%
        self.assertIn("batendo a faixa 150%", html)

        # o Início só resume: sem gráfico, sem Sub IDs, sem a lista de faixas
        html = self.client.get("/").content.decode()
        self.assertIn("R$ 3.800,50", html)
        self.assertIn("Faltam <strong>R$ 699,50</strong> pra faixa <strong>150%</strong>", html)
        self.assertIn("Bônus garantido até agora: <strong>R$ 200,00</strong>", html)
        self.assertNotIn("Cadastrar as metas do mês", html)
        self.assertNotIn("grafico", html)
        self.assertNotIn("Sub ID", html)

    def test_atualizar_agora_pede_uma_vez_e_volta(self, _):
        self.conectar_shopee()
        resposta = self.client.post("/resultados/atualizar/", {"voltar": "/resultados/?periodo=7dias"})
        self.assertRedirects(resposta, "/resultados/?periodo=7dias", fetch_redirect_response=False)
        primeiro = SincronizacaoResultados.objects.get(conta=self.conta).pedido_em
        self.client.post("/resultados/atualizar/", {"voltar": "https://golpe.com/"})
        self.assertEqual(SincronizacaoResultados.objects.get(conta=self.conta).pedido_em, primeiro)
        self.assertContains(self.client.get("/resultados/"), "Atualizando com a Shopee")
        self.assertFalse(SincronizacaoResultados.objects.get(conta=self.conta).pedido_curto)

    def test_botoes_de_atualizar(self, _):
        self.conectar_shopee()
        html = self.client.get("/resultados/").content.decode()
        self.assertIn("Atualizar dia anterior e atual", html)
        self.assertIn("Atualizar 30 dias", html)
        self.assertNotIn("Atualizar agora", html)
        resposta = self.client.post("/resultados/atualizar/", {"voltar": "/resultados/", "periodo": "curto"}, follow=True)
        self.assertContains(resposta, "números de ontem e de hoje")
        self.assertTrue(SincronizacaoResultados.objects.get(conta=self.conta).pedido_curto)
        # Logo depois, pedir 30 dias vale (cobre o curto).
        self.client.post("/resultados/atualizar/", {"voltar": "/resultados/", "periodo": "30"})
        self.assertFalse(SincronizacaoResultados.objects.get(conta=self.conta).pedido_curto)

    def test_pagina_se_atualiza_sozinha_quando_a_busca_termina(self, _):
        self.conectar_shopee()
        resultados.pedir_atualizacao(self.conta)
        self.assertContains(self.client.get("/resultados/"), "painel/sincronizacao")
        self.assertEqual(self.client.get("/resultados/estado/").json(), {"atualizando": True})

        SincronizacaoResultados.objects.filter(conta=self.conta).update(
            iniciada_em=timezone.now(), concluida_em=timezone.now() + timedelta(seconds=30),
        )
        self.assertEqual(self.client.get("/resultados/estado/").json(), {"atualizando": False})
        self.assertNotContains(self.client.get("/resultados/"), "painel/sincronizacao")

    def test_cadastrar_e_apagar_metas(self, _):
        resposta = self.client.post("/metas/?mes=2026-11", {
            "percentual_1": "100", "faturamento_1": "30.000,00", "bonus_1": "250",
            "percentual_2": "125", "faturamento_2": "", "bonus_2": "400",
            "percentual_3": "", "faturamento_3": "", "bonus_3": "",
        })
        self.assertRedirects(resposta, "/metas/?mes=2026-11", fetch_redirect_response=False)
        meta = MetaMensal.objects.get(conta=self.conta, ano=2026, mes=11)
        self.assertEqual([f["faturamento"] for f in meta.faixas], [30000.0, 37500.0])
        self.assertContains(self.client.get("/metas/?mes=2026-11"), "37.500")

        self.client.post("/metas/?mes=2026-11", {"faturamento_1": ""})
        self.assertFalse(MetaMensal.objects.exists())

    def test_mes_fora_das_opcoes_cai_no_mes_atual(self, _):
        self.client.post("/metas/?mes=2030-01", {"percentual_1": "100", "faturamento_1": "1000"})
        self.assertTrue(MetaMensal.objects.filter(ano=2026, mes=10).exists())


class TestSemanaComecaNoDomingo(TestCase):
    def test_esta_semana_semana_passada_e_agrupar(self):
        from . import periodos

        terca = date(2026, 10, 20)
        self.assertEqual(periodos.inicio_da_semana(terca), date(2026, 10, 18))  # domingo
        self.assertEqual(periodos.inicio_da_semana(date(2026, 10, 18)), date(2026, 10, 18))  # domingo é o 1º dia
        self.assertEqual(periodos.inicio_da_semana(date(2026, 10, 17)), date(2026, 10, 11))  # sábado é o último
        self.assertEqual(periodos.intervalo_do_preset("semana", terca), (date(2026, 10, 18), terca))
        self.assertEqual(periodos.intervalo_do_preset("semana_passada", terca), (date(2026, 10, 11), date(2026, 10, 17)))
        linhas = [{"dia": date(2026, 10, d), "pedidos": 1} for d in (17, 18, 19)]
        grupos = periodos.agrupar(linhas, "semana")
        self.assertEqual([(g["inicio"], g["pedidos"]) for g in grupos], [(date(2026, 10, 17), 1), (date(2026, 10, 18), 2)])
