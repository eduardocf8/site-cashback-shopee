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
NICHOS = [
    {"id": "beleza", "nome": "Beleza", "categorias": ["beleza"], "palavra_chave": "", "grupos": ["1@g.us", "2@g.us"]},
    {"id": "casa", "nome": "Casa", "categorias": [], "palavra_chave": "cozinha", "grupos": ["3@g.us"]},
    {"id": "vazio", "nome": "Sem grupos", "categorias": [], "palavra_chave": "", "grupos": []},
]


def busca_por_nicho(app_id, secret, config, pagina):
    """Beleza: produtos de maquiagem; Casa (palavra "cozinha"): panelas."""
    if config.tipo_busca == ConfiguracaoOfertas.BUSCA_PALAVRA:
        return [produto(f"20{pagina}", nome="Panela de cozinha"), produto(f"21{pagina}", nome="Jogo de cozinha")], True
    return [produto(f"10{pagina}", nome="Batom matte"), produto(f"11{pagina}", nome="Carregador turbo")], True


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
            ("Batom matte", "1@g.us"), ("Batom matte", "2@g.us"),  # Beleza: o carregador não é da categoria
            ("Panela de cozinha", "3@g.us"),
        ])
        self.assertEqual(buscar.call_count, 2)  # o nicho sem grupos não busca
        self.assertEqual(self.config.proximo_envio_em, AGORA + timedelta(minutes=5))
        self.assertEqual(self.config.situacao, "")
        self.assertEqual(set(self.config.paginas_nichos), {"beleza", "casa"})
        self.assertEqual(self.config.paginas_nichos["casa"]["pagina"], 2)

        # Na vez seguinte cada nicho continua da sua lista.
        self.rodar(AGORA + timedelta(minutes=5))
        novos = EnvioWhatsApp.objects.order_by("id").values_list("item_id", "destino")[3:]
        # Casa: a 2ª da página 1 (ainda no cache); Beleza: o batom da página 2.
        self.assertEqual(list(novos), [("102", "1@g.us"), ("102", "2@g.us"), ("211", "3@g.us")])

    def test_limite_do_dia_conta_as_ofertas_de_todos_os_nichos(self, _link):
        self.config.limite_diario = 1
        self.config.save()
        self.rodar()
        self.assertEqual({p for p, _ in self.envios()}, {"Batom matte"})

    def test_premium_vencido_para_o_envio_por_nicho(self, _link):
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        self.rodar()
        self.assertEqual(self.envios(), [])
        self.assertIn("envio por nicho é do plano Premium", self.config.situacao)

    def test_sem_grupos_nos_nichos(self, _link):
        self.config.nichos = [{**n, "grupos": []} for n in NICHOS]
        self.config.save()
        self.rodar()
        self.assertEqual(self.config.situacao, "Escolha os grupos de cada nicho.")

    def test_copiando_de_grupos_nao_divide_por_nicho(self, _link):
        self.config.modo = ConfiguracaoOfertas.MODO_COPIAR
        self.assertFalse(self.config.por_nicho)

    def test_um_nicho_com_erro_nao_segura_os_outros(self, _link):
        def link(app_id, secret, url, sub_ids):
            if "201" in url:
                raise RuntimeError("link recusado")
            return link_falso(app_id, secret, url, sub_ids)
        with mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link):
            self.rodar()
        self.assertEqual({p for p, _ in self.envios()}, {"Batom matte"})
        self.assertIn("Casa: link recusado", self.config.ultimo_erro)

    def test_testar_busca_mostra_cada_nicho(self, _link):
        self.config.pedido_teste_em = timezone.now()
        self.config.save()
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca_por_nicho):
            self.motor.atender_testes(AGORA)
        self.config.refresh_from_db()
        nichos = [(o["nicho"], o.get("nome") or o.get("erro")[:10]) for o in self.config.teste_resultado]
        self.assertEqual(nichos[:3], [("Beleza", "Batom matte"), ("Beleza", "Batom matte"), ("Beleza", "Batom matte")])
        self.assertEqual([n for n, _ in nichos[3:6]], ["Casa"] * 3)
        self.assertEqual(nichos[6][0], "Sem grupos")  # sem grupos também aparece (ofertas em geral)


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
            "nicho_id": ["n1", "n2", "n3"], "nicho_nome": ["Beleza", " Casa  e cozinha ", ""],
            "nicho_palavra": ["", "panela", ""], "nicho_cat_n1": ["beleza", "inventada"],
            "nicho_de_1@g.us": "n1", "nicho_de_2@g.us": "n2", "nicho_de_3@g.us": "", "nicho_de_4@g.us": "n9",
            "grupos": ["4@g.us"],  # por nicho, valem os grupos dos nichos
        }
        base.update(extra)
        return base

    def test_salva_os_nichos_e_os_grupos_deles(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertEqual(resposta.status_code, 302)
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual(config.modo_envio, "nicho")
        self.assertEqual(config.nichos, [
            {"id": "n1", "nome": "Beleza", "categorias": ["beleza"], "palavra_chave": "", "grupos": ["1@g.us"]},
            {"id": "n2", "nome": "Casa e cozinha", "categorias": [], "palavra_chave": "panela", "grupos": ["2@g.us"]},
        ])
        self.assertEqual([g["jid"] for g in config.grupos], ["1@g.us", "2@g.us"])

        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertIn('value="Casa e cozinha"', html)
        self.assertIn('<option value="n1" selected>Beleza</option>', html)
        self.assertIn('id="modelo-nicho"', html)

    def test_validacoes(self):
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(**{"nicho_de_1@g.us": "", "nicho_de_2@g.us": ""}))
        self.assertContains(resposta, "Escolha os grupos de cada nicho")
        resposta = self.client.post("/whatsapp/ofertas/", self.dados(nicho_nome=["", "Casa", ""]))
        self.assertContains(resposta, "Dê um nome pra cada nicho.")
        self.assertFalse(ConfiguracaoOfertas.objects.filter(conta=self.conta, modo_envio="nicho").exists())

    def test_enviando_pra_todos_guarda_os_nichos(self):
        self.client.post("/whatsapp/ofertas/", self.dados(modo_envio="todos"))
        config = ConfiguracaoOfertas.objects.get(conta=self.conta)
        self.assertEqual((config.modo_envio, [g["jid"] for g in config.grupos]), ("todos", ["4@g.us"]))
        self.assertEqual(len(config.nichos), 2)

    def test_standard_nao_divide_por_nicho(self):
        self.conta.modulos_cortesia = "whatsapp"
        self.conta.save()
        html = self.client.get("/whatsapp/ofertas/").content.decode()
        self.assertRegex(html, r'value="nicho" disabled><span>Por nicho <small class="selo-premium">Premium')
        self.assertNotIn('id="lista-nichos"', html)
        self.assertIn("envio por nicho", html)
        resposta = self.client.post("/whatsapp/ofertas/", self.dados())
        self.assertContains(resposta, "O envio por nicho é do plano Premium.")
