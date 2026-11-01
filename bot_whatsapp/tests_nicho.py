"""Envio por nicho (Premium): cada nicho busca as próprias ofertas e manda só pros grupos dele."""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import cripto
from painel.tests import BasePainel

from . import ofertas, shopee_ofertas
from .models import ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp
from .tests_ofertas import AGORA, link_falso, produto

GRUPOS = [{"jid": f"{i}@g.us", "nome": f"Grupo {i}"} for i in range(1, 5)]
NICHOS = {"1@g.us": "100630", "2@g.us": "100630"}  # Beleza; o 3 fica em "Todos"


def busca_por_nicho(app_id, secret, config, pagina):
    """Na categoria Beleza a Shopee devolve o batom e (por engano) um carregador, que a conferência
    da categoria barra; no "Todos", a busca geral traz os dois."""
    return [produto(f"10{pagina}", nome="Batom matte", categoria_id=100630),
            produto(f"11{pagina}", nome="Carregador turbo", categoria_id=100013)], True


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotorPorNicho(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp_premium", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, grupos=GRUPOS[:3], intervalo_minutos=5,
            modo_envio=ConfiguracaoOfertas.ENVIO_NICHO, nichos=NICHOS,
        )
        self.motor = ofertas.Motor()

    def rodar(self, agora=AGORA, busca=busca_por_nicho):
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca) as buscar:
            self.motor.uma_volta(agora)
        self.config.refresh_from_db()
        return buscar

    def envios(self):
        return list(EnvioWhatsApp.objects.order_by("id").values_list("produto", "destino"))

    def test_cada_nicho_manda_a_sua_oferta_pros_seus_grupos(self, _link):
        buscar = self.rodar()
        self.assertEqual(self.envios(), [
            ("Batom matte", "3@g.us"),  # Todos: ofertas em geral
            ("Batom matte", "1@g.us"), ("Batom matte", "2@g.us"),  # Beleza: o carregador não é da categoria
        ])
        self.assertEqual(buscar.call_count, 2)  # uma busca por nicho em uso
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=5))
        self.assertEqual(self.config.situacao, "")
        self.assertEqual(self.config.paginas_nichos["todos"]["pagina"], 2)
        self.assertEqual(set(self.config.paginas_nichos), {"todos", "100630"})

        # Na vez seguinte cada nicho continua da sua lista.
        self.rodar(AGORA + timedelta(minutes=5))
        novos = EnvioWhatsApp.objects.order_by("id").values_list("item_id", "destino")[3:]
        # Todos: o carregador (ainda no cache); Beleza: o batom da página 2.
        self.assertEqual(list(novos), [("111", "3@g.us"), ("102", "1@g.us"), ("102", "2@g.us")])

    def test_limite_do_dia_conta_as_ofertas_de_todos_os_nichos(self, _link):
        self.config.limite_diario = 1
        self.config.save()
        self.rodar()
        self.assertEqual(self.envios(), [("Batom matte", "3@g.us")])  # só o primeiro nicho

    def test_premium_vencido_para_o_envio_por_nicho(self, _link):
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        self.rodar()
        self.assertEqual(self.envios(), [])
        self.assertIn("envio por nicho é do plano Premium", self.config.situacao)

    def test_sem_nicho_escolhido_tudo_vai_pro_todos(self, _link):
        self.config.nichos = {}
        self.config.save()
        self.rodar()
        self.assertEqual(self.envios(), [("Batom matte", "1@g.us"), ("Batom matte", "2@g.us"), ("Batom matte", "3@g.us")])

    def test_copiando_de_grupos_nao_divide_por_nicho(self, _link):
        self.config.modo = ConfiguracaoOfertas.MODO_COPIAR
        self.assertFalse(self.config.por_nicho)

    def test_um_nicho_com_erro_nao_segura_os_outros(self, _link):
        def link(app_id, secret, url, sub_ids, ferramenta=""):
            if url.endswith("101") and sub_ids == ["vip"]:
                raise RuntimeError("link recusado")
            return link_falso(app_id, secret, url, sub_ids)
        self.config.sub_ids_por_grupo = {"3@g.us": "vip"}
        self.config.save()
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link):
            self.rodar()
        self.assertEqual(self.envios(), [("Batom matte", "1@g.us"), ("Batom matte", "2@g.us")])
        self.assertIn("Todos: link recusado", self.config.ultimo_erro)

    def test_testar_busca_mostra_cada_nicho(self, _link):
        self.config.pedido_teste_em = timezone.now()
        self.config.save()
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca_por_nicho):
            self.motor.atender_testes(AGORA)
        self.config.refresh_from_db()
        nichos = [(o["nicho"], o.get("nome")) for o in self.config.teste_resultado]
        self.assertEqual(nichos, [("Todos", "Batom matte"), ("Todos", "Carregador turbo"), ("Todos", "Batom matte")]
                         + [("Beleza", "Batom matte")] * 3)


class TestTelaPorNicho(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.conta.shopee_validado_em = timezone.now()
        self.conta.modulos_cortesia = "whatsapp_premium"
        self.conta.save()
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)

    def dados(self, **extra):
        base = {
            "modo": "shopee", "modo_envio": "nicho", "tipo_busca": "geral", "ordenacao": "mais_vendidos",
            "intervalo_minutos": "10", "horario_inicio": "08:00", "horario_fim": "22:00",
            "dias_semana": ["0", "1", "2", "3", "4"], "repetir_apos_dias": "7",
            "grupos": ["1@g.us", "2@g.us", "3@g.us"],
            "nicho_de_1@g.us": "100631", "nicho_de_2@g.us": "todos", "nicho_de_3@g.us": "beleza", "nicho_de_4@g.us": "100636",
        }
        base.update(extra)
        return base

    def test_salva_o_nicho_de_cada_grupo(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertEqual(resposta.status_code, 302)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual(config.modo_envio, "nicho")
        # "Todos" e valor inválido não são guardados; o grupo 4 não recebe, mas o nicho dele fica guardado
        self.assertEqual(config.nichos, {"1@g.us": "100631", "4@g.us": "100636"})
        self.assertEqual([g["jid"] for g in config.grupos], ["1@g.us", "2@g.us", "3@g.us"])

        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn('class="lista-grupos por-nicho"', html)
        self.assertIn('<option value="100631" selected>Animais Domésticos</option>', html)
        self.assertIn('<option value="todos" selected class="nicho-todos">Todos</option>', html)
        self.assertNotIn("Palavra-chave do nicho", html)

        self.client.post("/whatsapp/ofertas/", self.dados(modo_envio="todos"))
        config.refresh_from_db()
        self.assertEqual((config.modo_envio, config.nichos), ("todos", {"1@g.us": "100631", "4@g.us": "100636"}))
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn('class="lista-grupos" id="lista-grupos"', html)
        self.assertIn('<span data-envio="nicho" hidden>Nicho</span>', html)

    def test_standard_nao_divide_por_nicho(self):
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertRegex(html, r'value="nicho" disabled><span>Por nicho <small class="selo-premium">Premium')
        self.assertNotIn('class="nicho-do-grupo', html)
        self.assertIn("envio por nicho", html)
        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertContains(resposta, "O envio por nicho é do plano Premium.")


class TestBuscaDoNicho(TestCase):
    def test_busca_direto_na_categoria_da_shopee(self):
        config = ConfiguracaoOfertas(nichos={})
        do_nicho = ofertas.config_do_nicho(config, {"id": "100631", "nome": "Animais Domésticos"}, [])
        with mock.patch.object(shopee_ofertas, "_consultar_produtos", return_value={"nodes": []}) as consulta:
            shopee_ofertas.buscar_produtos("1", "s", do_nicho, 1)
        self.assertIn("productCatId:100631", consulta.call_args.args[2])
        # a petisqueira que veio de outra categoria é barrada
        self.assertFalse(shopee_ofertas.passa_nos_filtros(produto(1, nome="Petisqueira porta petiscos", categoria_id=100636), do_nicho))
        self.assertTrue(shopee_ofertas.passa_nos_filtros(produto(2, nome="Coleira", categoria_id=100631), do_nicho))

    def test_petisco_de_gente_nao_e_pet_no_filtro_de_categorias(self):
        from .categorias import produto_pertence_as_categorias

        self.assertFalse(produto_pertence_as_categorias("Petisqueira 4 divisórias porta petiscos", ["pet"]))
        self.assertTrue(produto_pertence_as_categorias("Petisco para cachorro sabor carne", ["pet"]))
