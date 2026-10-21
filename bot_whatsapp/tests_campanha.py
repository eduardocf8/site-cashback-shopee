"""Motor das ofertas no modo campanha: no dia ligado, vale a configuração da campanha
(só na memória); no dia seguinte, a da Automação, que nunca é alterada."""

from datetime import datetime, time, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from licencas.models import ContaAppfiliado
from painel import cripto

from . import ofertas, shopee_ofertas
from .models import CampanhaBot, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp
from .tests_ofertas import GRUPOS, SP, link_falso, produto

ONZE_ONZE = datetime(2026, 11, 11, 0, 30, tzinfo=SP)  # uma quarta, meia-noite e meia
DIA_SEGUINTE = datetime(2026, 11, 12, 0, 30, tzinfo=SP)
SEM_QUARTA = [0, 1, 3, 4, 5, 6]


@mock.patch.object(shopee_ofertas, "gerar_link_afiliado", side_effect=link_falso)
class TestMotorNaCampanha(TestCase):
    def setUp(self):
        self.conta = ContaAppfiliado.objects.create(
            email="bia@exemplo.com", modulos_cortesia="whatsapp_premium", shopee_app_id="123",
            shopee_secret_cifrado=cripto.cifrar("s"), shopee_validado_em=timezone.now(),
        )
        ConexaoWhatsApp.objects.create(conta=self.conta, estado="conectado", grupos=GRUPOS)
        # Automação: das 7h às 23h, sem quarta-feira, uma oferta por hora, cupom NORMAL.
        self.config = ConfiguracaoOfertas.objects.create(
            conta=self.conta, ativo=True, grupos=GRUPOS, intervalo_minutos=60, horario_inicio=time(7),
            horario_fim=time(23), dias_semana=SEM_QUARTA, cupom="NORMAL",
        )
        self.campanha = CampanhaBot.objects.create(
            conta=self.conta, ativo=True, datas_ligadas=["11.11"], intervalo_minutos=10, desconto_minimo=30,
            frase_abertura="🔥 11.11!", cupom="C1111", pagina_ativa=True, link_campanha="https://shopee.com.br/m/11-11",
            link_campanha_a_cada=3,
        )
        self.motor = ofertas.Motor()
        self.paginas = []

    def rodar(self, agora, produtos=None):
        produtos = produtos or [produto(i, desconto=40) for i in range(1, 11)]

        def busca(app_id, secret, config, pagina):
            self.paginas.append((pagina, config.palavra_chave))
            return list(produtos), False
        # o relógio do sistema no momento do teste (os envios ficam com essa hora)
        with mock.patch.object(shopee_ofertas, "buscar_produtos", side_effect=busca), \
                mock.patch("django.utils.timezone.now", return_value=agora):
            self.motor.uma_volta(agora)
        self.config.refresh_from_db()

    def ofertas(self):
        return EnvioWhatsApp.objects.filter(origem="oferta").order_by("id")

    def test_no_dia_vale_a_campanha_e_a_automacao_nao_muda(self, _link):
        self.rodar(ONZE_ONZE, [produto(1, desconto=20), produto(2, desconto=40)])
        envio = self.ofertas().first()
        self.assertEqual(envio.item_id, "2")  # desconto mínimo da campanha (30%)
        self.assertTrue(envio.texto.startswith("🔥 11.11!\n\n"))
        self.assertIn("Cupom: C1111", envio.texto)
        self.assertEqual(self.config.proximo_envio_em, ONZE_ONZE + timedelta(minutes=10))
        # nada da campanha foi parar na configuração da Automação
        self.assertEqual((self.config.intervalo_minutos, self.config.cupom, self.config.dias_semana,
                          self.config.horario_inicio, self.config.desconto_minimo),
                         (60, "NORMAL", SEM_QUARTA, time(7), 0))

    def test_no_dia_seguinte_volta_a_automacao(self, _link):
        self.rodar(DIA_SEGUINTE)
        self.assertFalse(self.ofertas().exists())
        self.assertEqual(self.config.situacao, "Fora do horário de envio.")
        self.rodar(DIA_SEGUINTE.replace(hour=8))
        envio = self.ofertas().first()
        self.assertIn("Cupom: NORMAL", envio.texto)
        self.assertNotIn("11.11", envio.texto)

    def test_modo_campanha_desligado_ou_data_desmarcada_nao_mudam_nada(self, _link):
        for mudanca in ({"ativo": False}, {"datas_ligadas": ["12.12"]}):
            CampanhaBot.objects.filter(pk=self.campanha.pk).update(**{"ativo": True, "datas_ligadas": ["11.11"], **mudanca})
            self.rodar(ONZE_ONZE)
            self.assertFalse(self.ofertas().exists(), mudanca)  # quarta e meia-noite: fora da Automação

    def test_texto_das_ofertas_desligado_mantem_ritmo_filtros_e_a_pagina(self, _link):
        CampanhaBot.objects.filter(pk=self.campanha.pk).update(mensagem_ativa=False)
        for i in range(3):
            self.rodar(ONZE_ONZE + timedelta(minutes=10 * i), [produto(1, desconto=20)] + [
                produto(n, desconto=40) for n in range(2, 6)])
        envio = self.ofertas().first()
        self.assertEqual(envio.item_id, "2")  # o filtro da campanha vale
        self.assertNotIn("11.11", envio.texto)
        self.assertIn("Cupom: NORMAL", envio.texto)
        self.assertTrue(EnvioWhatsApp.objects.filter(origem="campanha").exists())  # a página é à parte

    def test_pagina_desligada_nao_vai(self, _link):
        CampanhaBot.objects.filter(pk=self.campanha.pk).update(pagina_ativa=False)
        for i in range(3):
            self.rodar(ONZE_ONZE + timedelta(minutes=10 * i))
        self.assertEqual(self.ofertas().values("item_id").distinct().count(), 3)
        self.assertFalse(EnvioWhatsApp.objects.filter(origem="campanha").exists())
        self.assertTrue(self.ofertas().first().texto.startswith("🔥 11.11!"))  # o texto das ofertas continua

    def test_pagina_da_campanha_a_cada_n_ofertas(self, _link):
        for i in range(3):
            self.rodar(ONZE_ONZE + timedelta(minutes=10 * i))
        self.assertEqual(self.ofertas().values("item_id").distinct().count(), 3)
        paginas = EnvioWhatsApp.objects.filter(origem="campanha")
        self.assertEqual(sorted(paginas.values_list("destino", flat=True)), ["1@g.us", "2@g.us"])
        pagina = paginas.first()
        self.assertEqual(pagina.formato, "previa")
        # só o link da página (sem produto), com o texto padrão e o cupom
        self.assertEqual(pagina.texto, "🛍️ 11.11: todas as ofertas num lugar só\nhttps://s.shopee.com.br/1\n\n🎟️ Cupom: C1111")
        self.assertEqual(pagina.imagem_url, "")
        CampanhaBot.objects.filter(pk=self.campanha.pk).update(titulo_pagina="🔥 CHEGOU!", texto_pagina="Corre que tá acabando!")
        for i in range(3, 6):
            self.rodar(ONZE_ONZE + timedelta(minutes=10 * i))
        textos = EnvioWhatsApp.objects.filter(origem="campanha").values_list("texto", flat=True)
        self.assertTrue(any(t.startswith("🔥 CHEGOU!\n\nCorre que tá acabando!\nhttps://") for t in textos))
        # a página não conta como oferta: o limite e o "a cada 3" seguem certos
        self.assertEqual(ofertas.ofertas_enviadas_hoje(self.conta, ONZE_ONZE + timedelta(minutes=50)), 6)

    def test_intervalo_da_campanha_vale_na_hora(self, _link):
        # Última oferta às 22h50 do dia 10, com a próxima marcada para 23h50 (intervalo de 1 hora).
        ConfiguracaoOfertas.objects.filter(pk=self.config.pk).update(
            ultimo_envio_em=ONZE_ONZE - timedelta(minutes=100), proximo_envio_em=ONZE_ONZE + timedelta(minutes=20))
        self.rodar(ONZE_ONZE)  # 00h30: com o intervalo de 10 minutos da campanha, já pode
        self.assertEqual(self.ofertas().count(), 2)

    def test_sem_produto_espera_os_30_minutos_mesmo_na_campanha(self, _link):
        ConfiguracaoOfertas.objects.filter(pk=self.config.pk).update(ultimo_envio_em=ONZE_ONZE - timedelta(hours=2))
        self.rodar(ONZE_ONZE, [produto(1, desconto=5)])  # nada passa no desconto mínimo da campanha
        self.assertIn("Nenhuma oferta nova", self.config.situacao)
        buscas = len(self.paginas)
        self.rodar(ONZE_ONZE + timedelta(seconds=5))
        self.assertEqual(len(self.paginas), buscas)  # não buscou de novo antes da hora

    def test_palavra_chave_da_campanha_recomeca_a_busca(self, _link):
        CampanhaBot.objects.filter(pk=self.campanha.pk).update(palavra_chave="fone")
        self.motor.cache[self.conta.pk] = {"chave": "busca-normal", "produtos": [], "em": 0}
        ConfiguracaoOfertas.objects.filter(pk=self.config.pk).update(pagina_atual=7, pagina_em=ONZE_ONZE)
        self.rodar(ONZE_ONZE)
        self.assertEqual(self.paginas[0], (1, "fone"))
        self.assertEqual(self.config.palavra_chave, "")  # a Automação continua sem palavra-chave
