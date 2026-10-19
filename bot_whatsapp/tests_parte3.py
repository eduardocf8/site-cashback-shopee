from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import cripto
from painel.forms import ConfiguracaoOfertasForm
from painel.tests import BasePainel

from . import ia, ofertas, shopee_ofertas
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp
from .tests_ofertas import AGORA, GRUPOS, link_falso, produto

TEXTO = "🔥 Fone Bluetooth TWS\nDe R$ 199,90 por R$ 59,90\nCupom: FONE10\n🛒 Compre aqui:\n{{LINK_DE_AFILIADO}}"
COM_CHAVE = override_settings(APPFILIADO_GEMINI_API_KEY="chave-de-teste")


class TestSalvosNoTopo(TestCase):
    def test_grupos_e_origens_salvos_ficam_no_topo_com_divisa(self):
        conta = ContaAppfiliado.objects.create(email="bia@exemplo.com")
        grupos = [{"jid": f"{i}@g.us", "nome": nome} for i, nome in enumerate(["Alfa", "Beta", "Gama", "Zeta"])]
        config = ConfiguracaoOfertas.objects.create(
            conta=conta, grupos=[grupos[3], grupos[1]], origens=[grupos[2]],
        )
        form = ConfiguracaoOfertasForm(instance=config, grupos_disponiveis=grupos)
        destinos = [(l["opcao"].choice_label, l["divisa"]) for l in form.linhas_dos_grupos]
        self.assertEqual(destinos, [("Beta", False), ("Zeta", False), ("Alfa", True), ("Gama", False)])
        origens = [(l["opcao"].choice_label, l["divisa"]) for l in form.linhas_das_origens]
        self.assertEqual(origens, [("Gama", False), ("Alfa", True), ("Beta", False), ("Zeta", False)])

    def test_sem_salvos_e_alfabetico_sem_divisa(self):
        conta = ContaAppfiliado.objects.create(email="bia@exemplo.com")
        config = ConfiguracaoOfertas.objects.create(conta=conta)
        form = ConfiguracaoOfertasForm(instance=config, grupos_disponiveis=[
            {"jid": "2@g.us", "nome": "beta"}, {"jid": "1@g.us", "nome": "Alfa"},
        ])
        self.assertEqual([(l["opcao"].choice_label, l["divisa"]) for l in form.linhas_dos_grupos],
                         [("Alfa", False), ("beta", False)])


class TestRevisorIA(TestCase):
    def revisar(self, resposta, tipo="contextual"):
        with mock.patch.object(ia, "_chamar", return_value=resposta) as chamar:
            resultado = ia.revisar(TEXTO, tipo, ofertas.MARCADOR_DO_LINK)
        return resultado, chamar

    @COM_CHAVE
    def test_usa_o_texto_revisado(self):
        revisado = TEXTO.replace("Fone Bluetooth TWS", "Fone Bluetooth TWS sem fio")
        (texto, ok, status), chamar = self.revisar(revisado)
        self.assertEqual((texto, ok), (revisado, True))
        self.assertIn("revisada pela IA (contextual)", status)
        prompt, temperatura = chamar.call_args.args
        self.assertIn("{{LINK_DE_AFILIADO}}", prompt)
        self.assertIn("contextual conservadora", prompt)
        self.assertEqual(temperatura, 0.25)

    @COM_CHAVE
    def test_mantem_o_original_quando_a_ia_mexe_no_que_nao_pode(self):
        casos = {
            "preço": TEXTO.replace("59,90", "49,90"),
            "lugar do link": TEXTO.replace("{{LINK_DE_AFILIADO}}", "https://s.shopee.com.br/x"),
            "cupom": TEXTO.replace("FONE10", "FONE15"),
            "aumentou": TEXTO + ("bla " * 400),
            "vazio": "",
        }
        for nome, resposta in casos.items():
            with self.subTest(nome):
                (texto, ok, status), _ = self.revisar(resposta)
                self.assertEqual((texto, ok), (TEXTO, False))
                self.assertIn("original", status)

    @COM_CHAVE
    def test_erro_na_ia_manda_o_original_com_motivo_claro(self):
        sobrecarga = ia.ErroDaIA("This model is currently experiencing high demand.", 503)
        with mock.patch.object(ia, "_chamar", side_effect=sobrecarga):
            texto, ok, status = ia.revisar(TEXTO, "leve", ofertas.MARCADOR_DO_LINK)
        self.assertEqual((texto, ok), (TEXTO, False))
        self.assertEqual(status, "O Gemini estava sobrecarregado (instabilidade do Google) - foi o texto original.")
        with mock.patch.object(ia, "_chamar", side_effect=ia.ErroDaIA("quota", 429)):
            self.assertIn("Limite de uso", ia.revisar(TEXTO, "leve", ofertas.MARCADOR_DO_LINK)[2])

    @COM_CHAVE
    def test_sobrecarregado_tenta_de_novo_e_depois_o_modelo_reserva(self):
        chamados = []

        def chamar_modelo(modelo, prompt, temperatura):
            chamados.append(modelo)
            if modelo != "gemini-2.5-flash-lite":
                raise ia.ErroDaIA("high demand" if modelo == "gemini-3.1-flash-lite" else "not found",
                                  503 if modelo == "gemini-3.1-flash-lite" else 404)
            return "ok"

        esperas = []
        with mock.patch.object(ia, "_chamar_modelo", side_effect=chamar_modelo):
            self.assertEqual(ia._chamar("p", 0.1, esperar=esperas.append), "ok")
        self.assertEqual(chamados, ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"])
        self.assertEqual(esperas, [2])

    @COM_CHAVE
    def test_chave_recusada_nao_insiste(self):
        with mock.patch.object(ia, "_chamar_modelo", side_effect=ia.ErroDaIA("API key not valid", 400)) as chamar:
            with self.assertRaises(ia.ErroDaIA):
                ia._chamar("p", 0.1, esperar=lambda _: None)
        self.assertEqual(chamar.call_count, 1)

    @override_settings(APPFILIADO_GEMINI_API_KEY="", GEMINI_API_KEY="")
    def test_sem_chave_fica_indisponivel(self):
        self.assertFalse(ia.disponivel())
        texto, ok, _ = ia.revisar(TEXTO, "leve", ofertas.MARCADOR_DO_LINK)
        self.assertEqual((texto, ok), (TEXTO, False))


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotorComSimulacaoEIA(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        self.conexao = ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, grupos=GRUPOS, intervalo_minutos=5, sub_ids="grupos",
        )
        self.motor = ofertas.Motor()

    def rodar(self, produtos, agora=AGORA):
        with mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=(list(produtos), False)):
            self.motor.uma_volta(agora)
        self.config.refresh_from_db()

    def test_simulacao_nao_envia_e_nao_bloqueia_depois(self, _):
        self.config.simulacao = True
        self.config.save()
        self.conexao.estado = "desconectado"  # buscando na Shopee, simula sem WhatsApp
        self.conexao.save()
        self.rodar([produto(1)])
        envios = EnvioWhatsApp.objects.all()
        self.assertEqual({e.estado for e in envios}, {"simulado"})
        self.assertEqual(len(envios), 2)
        self.assertIn("https://s.shopee.com.br/1-grupos", envios[0].texto)  # link de verdade no texto
        self.assertFalse(EnvioWhatsApp.objects.filter(estado="pendente").exists())  # nada para o WhatsApp

        # enquanto simula, conta para o limite e para não repetir
        self.assertEqual(ofertas.ofertas_enviadas_hoje(self.conta, AGORA, simulacao=True), 1)
        self.assertEqual(ofertas.grupos_que_ainda_nao_receberam(self.config, "1", AGORA), [])
        # desligou a simulação: o produto simulado pode sair de verdade
        self.config.simulacao = False
        self.assertEqual(ofertas.ofertas_enviadas_hoje(self.conta, AGORA), 0)
        self.assertEqual(len(ofertas.grupos_que_ainda_nao_receberam(self.config, "1", AGORA)), 2)

    @COM_CHAVE
    def test_ia_revisa_o_texto_antes_de_enfileirar(self, _):
        self.config.ia_ativa = True
        self.config.ia_tipo = "leve"
        self.config.save()

        def revisar(texto, tipo, marcador):
            return texto.replace("Produto 1", "Produto Um"), True, "Última oferta revisada pela IA (leve)."

        with mock.patch.object(ia, "revisar", side_effect=revisar) as chamada:
            self.rodar([produto(1)])
        self.assertEqual(chamada.call_count, 1)  # uma revisão por oferta, não por grupo
        envio = EnvioWhatsApp.objects.first()
        self.assertTrue(envio.revisado_ia)
        self.assertIn("Produto Um", envio.texto)
        self.assertIn("https://s.shopee.com.br/1-grupos", envio.texto)
        self.assertEqual((self.config.ia_status, self.config.ia_revisoes_no_dia), ("Última oferta revisada pela IA (leve).", 1))

    @COM_CHAVE
    def test_sem_revisao_guarda_o_motivo_em_cada_envio(self, _):
        self.config.ia_ativa = True
        self.config.save()
        with mock.patch.object(ia, "revisar", return_value=("x", False, "A IA mexeu em algum preço. Foi o texto original, por segurança.")):
            self.rodar([produto(1)])
        self.assertEqual({e.ia_motivo for e in EnvioWhatsApp.objects.all()},
                         {"A IA mexeu em algum preço. Foi o texto original, por segurança."})
        # revisada: sem motivo
        with mock.patch.object(ia, "revisar", return_value=("ok {{LINK_DE_AFILIADO}}", True, "Última oferta revisada pela IA (contextual).")):
            self.rodar([produto(2)], agora=AGORA + timedelta(minutes=10))
        self.assertEqual(EnvioWhatsApp.objects.filter(item_id="2").first().ia_motivo, "")

    @COM_CHAVE
    def test_limite_de_revisoes_por_dia(self, _):
        self.config.ia_ativa = True
        self.config.ia_dia = timezone.localtime(AGORA).date()
        self.config.ia_revisoes_no_dia = ia.MAXIMO_POR_DIA
        self.config.save()
        with mock.patch.object(ia, "revisar") as chamada:
            self.rodar([produto(1)])
        chamada.assert_not_called()
        self.assertFalse(EnvioWhatsApp.objects.first().revisado_ia)
        self.assertIn("Limite", self.config.ia_status)

    @COM_CHAVE
    def test_teste_da_busca_mostra_o_motivo_na_primeira(self, _):
        self.config.ia_ativa = True
        self.config.pedido_teste_em = timezone.now()
        self.config.save()
        with mock.patch.object(ia, "revisar", return_value=(TEXTO, False, "O Gemini estava sobrecarregado - foi o texto original.")), \
                mock.patch.object(shopee_ofertas, "buscar_produtos", return_value=([produto(1), produto(2)], False)):
            self.motor.atender_testes(AGORA)
        self.config.refresh_from_db()
        primeira, segunda = self.config.teste_resultado[:2]
        self.assertEqual((primeira["revisado_ia"], primeira["ia_status"]), (False, "O Gemini estava sobrecarregado - foi o texto original."))
        self.assertEqual(segunda["ia_status"], "")

    def test_ia_desligada_nao_chama(self, _):
        with mock.patch.object(ia, "revisar") as chamada:
            self.rodar([produto(1)])
        chamada.assert_not_called()


class TestTelaDaParte3(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)

    def dados(self, **extra):
        base = {"modo": "shopee", "tipo_busca": "geral", "ordenacao": "mais_vendidos", "sub_ids": "", "grupos": ["1@g.us"],
                "intervalo_minutos": "10", "horario_inicio": "08:00", "horario_fim": "22:00",
                "dias_semana": ["0", "1"], "repetir_apos_dias": "7"}
        base.update(extra)
        return base

    @COM_CHAVE
    def test_salvar_ia_e_simulacao(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(ia_ativa="on", ia_tipo="criativa", simulacao="on"))
        self.assertEqual(resposta.status_code, 302)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((config.ia_ativa, config.ia_tipo, config.simulacao), (True, "criativa", True))
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("Modo simulação ligado", html)
        self.assertIn('class="selo-simulacao"', html)
        self.client.post("/whatsapp/ofertas/ligar/")
        self.assertIn("modo simulação", self.client.get("/whatsapp/ofertas/").content.decode())

    @override_settings(APPFILIADO_GEMINI_API_KEY="", GEMINI_API_KEY="")
    def test_sem_chave_a_ia_aparece_indisponivel_e_nao_liga(self):
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("ainda não está disponível", html)
        self.client.post("/whatsapp/ofertas/", self.dados(ia_ativa="on"))
        self.assertFalse(ConfiguracaoOfertas.objects.get(conta=self.conta).ia_ativa)

    def test_horarios_em_24h(self):
        from datetime import time

        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn('name="horario_inicio"', html)
        self.assertNotIn('type="time"', html)  # campo de texto: sem AM/PM do navegador
        self.client.post("/whatsapp/ofertas/", self.dados(horario_inicio="7:30", horario_fim="22:45"))
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((config.horario_inicio, config.horario_fim), (time(7, 30), time(22, 45)))
        self.assertContains(self.client.get("/whatsapp/ofertas/"), 'value="07:30"')
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(horario_fim="25:00"))
        self.assertEqual(resposta.status_code, 200)  # inválido: volta com erro

    def test_historico_mostra_simulado_ia_e_a_mensagem(self):
        EnvioWhatsApp.objects.create(
            conta=self.conta, destino="1@g.us", destino_nome="Ofertas VIP", origem="oferta", item_id="1",
            produto="Fone", texto="Texto completo da oferta", estado="simulado", revisado_ia=True,
        )
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn("Simulado", html)
        self.assertIn('class="selo-ia"', html)
        self.assertIn("Texto completo da oferta", html)
        EnvioWhatsApp.objects.create(
            conta=self.conta, destino="1@g.us", origem="oferta", item_id="2", produto="Mop", estado="enviado",
            ia_motivo="O Gemini estava sobrecarregado (instabilidade do Google) - foi o texto original.",
        )
        self.assertIn("Sem IA: O Gemini estava sobrecarregado", self.client.get("/whatsapp/ofertas/").content.decode())
