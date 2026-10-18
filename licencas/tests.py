import hashlib
import hmac
import json
from datetime import date, timedelta

from django.core import mail
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import Assinatura, ContaAppfiliado, EventoWebhookZouti, ProdutoZouti
from .services import assinatura_webhook_valida, resposta_validacao

SEGREDO = "segredo-de-teste"
PRODUTO_BOT = "prod_bot"
PRODUTO_SITE = "prod_site"


def _iso(d: date) -> str:
    return f"{d.isoformat()}T12:00:00.000Z"


def _assinatura_payload(
    sub_id="sub_1", email="cliente@exemplo.com", status="ACTIVE", produto=PRODUTO_BOT,
    atualizada="2026-10-01T10:00:00.000Z", fim_periodo=None, order_id="ord_1",
):
    """Mesmo formato do exemplo de Subscription da documentação da Zouti."""
    fim = fim_periodo or (timezone.localdate() + timedelta(days=30))
    return {
        "id": sub_id,
        "order_id": order_id,
        "status": status,
        "customer": {"id": "cus_1", "name": "Cliente Exemplo", "email": email},
        "plan": {"id": "plan_1", "name": "Mensal", "interval": "MONTHLY"},
        "current_period_end": _iso(fim),
        "next_payment_date": _iso(fim),
        "line_items": [{"name": "Plano", "product_id": produto, "quantity": 1}],
        "cancel_at_period_end": False,
        "updated_at": atualizada,
    }


@override_settings(ZOUTI_WEBHOOK_SECRET=SEGREDO)
class BaseZouti(TestCase):
    def setUp(self):
        self.client = Client()
        ProdutoZouti.objects.create(zouti_product_id=PRODUTO_BOT, nome="Bot", modulos="whatsapp")
        ProdutoZouti.objects.create(zouti_product_id=PRODUTO_SITE, nome="Site", modulos="site,vitrine")
        self._evento = 0

    def enviar(self, tipo_evento, payload, objeto="Subscription", evento_id=None, segredo=SEGREDO):
        self._evento += 1
        corpo = json.dumps(payload).encode()
        assinatura = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
        # O e-mail com a chave sai em transaction.on_commit - aqui roda na hora.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                "/licencas/webhook/zouti/",
                data=corpo,
                content_type="application/json",
                HTTP_X_ZOUTI_SIGNATURE=f"t=1717000000000,v1={assinatura}",
                HTTP_X_ZOUTI_EVENT_ID=evento_id or f"evt_{self._evento}",
                HTTP_X_ZOUTI_EVENT_TYPE=tipo_evento,
                HTTP_X_ZOUTI_OBJECT_NAME=objeto,
                HTTP_X_ZOUTI_OBJECT_ID=payload.get("id", ""),
            )

    def validar(self, chave):
        resposta = self.client.post(
            "/licencas/validar/", data=json.dumps({"chave": chave}), content_type="application/json",
        )
        return resposta.json()


class TestAssinaturaDoWebhook(TestCase):
    def test_hmac_do_corpo_bruto(self):
        corpo = b'{"a": 1}'
        v1 = hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
        self.assertTrue(assinatura_webhook_valida(corpo, f"t=123,v1={v1}", SEGREDO))

    def test_hmac_com_timestamp_tambem_aceito(self):
        corpo = b'{"a": 1}'
        v1 = hmac.new(SEGREDO.encode(), b"123." + corpo, hashlib.sha256).hexdigest()
        self.assertTrue(assinatura_webhook_valida(corpo, f"t=123,v1={v1}", SEGREDO))

    def test_recusa_assinatura_errada_ou_sem_segredo(self):
        corpo = b'{"a": 1}'
        v1 = hmac.new(b"outro", corpo, hashlib.sha256).hexdigest()
        self.assertFalse(assinatura_webhook_valida(corpo, f"t=123,v1={v1}", SEGREDO))
        self.assertFalse(assinatura_webhook_valida(corpo, "", SEGREDO))
        self.assertFalse(assinatura_webhook_valida(corpo, f"t=123,v1={v1}", ""))


class TestWebhookZouti(BaseZouti):
    def test_assinatura_invalida_recusada_e_registrada(self):
        resposta = self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(), segredo="errado")
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(ContaAppfiliado.objects.exists())
        evento = EventoWebhookZouti.objects.get()
        self.assertFalse(evento.assinatura_valida)

    def test_ativacao_cria_conta_e_manda_chave_uma_vez(self):
        self.assertEqual(self.enviar("SUBSCRIPTION_CREATED", _assinatura_payload(status="INCOMPLETE")).status_code, 200)
        self.assertEqual(len(mail.outbox), 0)  # ainda não pagou

        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(atualizada="2026-10-01T10:01:00.000Z"))
        self.enviar("SUBSCRIPTION_RENEWED", _assinatura_payload(atualizada="2026-11-01T10:00:00.000Z"))

        conta = ContaAppfiliado.objects.get(email="cliente@exemplo.com")
        self.assertEqual(conta.nome, "Cliente Exemplo")
        self.assertIsNotNone(conta.chave_enviada_em)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(conta.chave, mail.outbox[0].body)
        self.assertEqual(conta.assinaturas.get().status, Assinatura.STATUS_ATIVA)

    def test_evento_repetido_nao_e_reprocessado(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(), evento_id="evt_x")
        Assinatura.objects.update(status=Assinatura.STATUS_CANCELADA)
        resposta = self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(), evento_id="evt_x")
        self.assertTrue(resposta.json().get("duplicado"))
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_CANCELADA)

    def test_erro_ao_processar_responde_500_pra_zouti_tentar_de_novo(self):
        payload = _assinatura_payload()
        payload["customer"]["email"] = ""
        resposta = self.enviar("SUBSCRIPTION_ACTIVATED", payload)
        self.assertEqual(resposta.status_code, 500)
        self.assertFalse(EventoWebhookZouti.objects.get().processado_com_sucesso)

    def test_evento_mais_antigo_nao_desfaz_o_mais_novo(self):
        self.enviar("SUBSCRIPTION_CANCELED", _assinatura_payload(
            status="CANCELED", atualizada="2026-10-05T10:00:00.000Z", fim_periodo=timezone.localdate() - timedelta(days=1),
        ))
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(atualizada="2026-10-01T10:00:00.000Z"))
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_CANCELADA)

    def test_evento_que_nao_mexe_em_licenca_e_ignorado_sem_erro(self):
        resposta = self.enviar("ABANDONED_CART_CREATED", {"id": "cart_1"}, objeto="AbandonedCart")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Ignorado", EventoWebhookZouti.objects.get().resultado)


class TestCicloDaAssinatura(BaseZouti):
    def chave(self):
        return ContaAppfiliado.objects.get(email="cliente@exemplo.com").chave

    def test_atraso_bloqueia(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        self.enviar("SUBSCRIPTION_LATE_RENEWAL_WARNING", _assinatura_payload(atualizada="2026-11-02T10:00:00.000Z"))
        dados = self.validar(self.chave())
        self.assertFalse(dados["valido"])
        self.assertIn("atrasado", dados["motivo"])

    def test_cancelada_mantem_acesso_ate_o_fim_do_periodo_pago(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        self.enviar("SUBSCRIPTION_CANCELED", _assinatura_payload(
            status="CANCELED", atualizada="2026-10-02T10:00:00.000Z", fim_periodo=timezone.localdate() + timedelta(days=10),
        ))
        self.assertTrue(self.validar(self.chave())["valido"])

        Assinatura.objects.update(acesso_ate=timezone.localdate() - timedelta(days=1))
        dados = self.validar(self.chave())
        self.assertFalse(dados["valido"])
        self.assertIn("cancelada", dados["motivo"])

    def test_estorno_pelo_pagamento_bloqueia_e_so_renovacao_reabre(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        self.enviar("PAYMENT_REFUNDED", {"id": "pmt_1", "status": "REFUNDED", "subscription_id": "sub_1"}, objeto="Payment")
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_REEMBOLSADA)

        # Um evento de status qualquer depois do estorno não devolve o acesso...
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(atualizada="2026-10-03T10:00:00.000Z"))
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_REEMBOLSADA)
        # ...só uma renovação paga.
        self.enviar("SUBSCRIPTION_RENEWED", _assinatura_payload(atualizada="2026-11-01T10:00:00.000Z"))
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_ATIVA)

    def test_estorno_parcial_nao_bloqueia(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        self.enviar(
            "PAYMENT_REFUNDED", {"id": "pmt_1", "status": "PARTIALLY_REFUNDED", "subscription_id": "sub_1"},
            objeto="Payment",
        )
        self.assertEqual(Assinatura.objects.get().status, Assinatura.STATUS_ATIVA)

    def test_chargeback_pelo_pedido_bloqueia(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(order_id="ord_9"))
        self.enviar("ORDER_DISPUTED", {"id": "ord_9", "status": "DISPUTED"}, objeto="Order")
        dados = self.validar(self.chave())
        self.assertFalse(dados["valido"])
        self.assertIn("Chargeback", dados["motivo"])


class TestValidacaoEModulos(BaseZouti):
    def test_resposta_mantem_campos_antigos_e_traz_modulos(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        conta = ContaAppfiliado.objects.get()
        dados = self.validar(conta.chave)
        self.assertEqual(dados["valido"], True)
        self.assertEqual(dados["motivo"], "")
        self.assertEqual(dados["plano"], "Mensal")
        self.assertTrue(dados["expira_em"])
        self.assertEqual(dados["conta_ativa"], True)
        self.assertEqual(dados["modulos"], ["whatsapp"])

    def test_dois_produtos_somam_modulos_na_mesma_chave(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(sub_id="sub_2", produto=PRODUTO_SITE, order_id="ord_2"))
        self.assertEqual(ContaAppfiliado.objects.count(), 1)
        self.assertEqual(self.validar(ContaAppfiliado.objects.get().chave)["modulos"], ["whatsapp", "site", "vitrine"])

    def test_plano_sem_bot_abre_conta_mas_nao_o_app_antigo(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(produto=PRODUTO_SITE))
        dados = self.validar(ContaAppfiliado.objects.get().chave)
        self.assertFalse(dados["valido"])
        self.assertTrue(dados["conta_ativa"])
        self.assertIn("não inclui o bot", dados["motivo"])

    def test_produto_mapeado_depois_vale_na_hora(self):
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload(produto="prod_novo"))
        chave = ContaAppfiliado.objects.get().chave
        self.assertEqual(self.validar(chave)["modulos"], [])
        ProdutoZouti.objects.create(zouti_product_id="prod_novo", nome="Pacote", modulos="whatsapp,videos")
        self.assertEqual(self.validar(chave)["modulos"], ["whatsapp", "videos"])

    def test_cortesia_libera_ate_o_prazo(self):
        conta = ContaAppfiliado.objects.create(email="eu@exemplo.com", modulos_cortesia="whatsapp,site")
        dados = self.validar(conta.chave)
        self.assertTrue(dados["valido"])
        self.assertEqual(dados["plano"], "Cortesia")

        conta.cortesia_ate = timezone.localdate() - timedelta(days=1)
        conta.save()
        dados = resposta_validacao(conta)
        self.assertFalse(dados["valido"])
        self.assertEqual(dados["modulos"], [])

    def test_chave_desconhecida(self):
        dados = self.validar("AF-NAOEXISTE")
        self.assertFalse(dados["valido"])
        self.assertIn("não encontrada", dados["motivo"])

    def test_requisicao_invalida(self):
        resposta = self.client.post("/licencas/validar/", data="[1]", content_type="application/json")
        self.assertEqual(resposta.status_code, 400)


class TestAdmin(BaseZouti):
    def test_telas_do_admin_abrem_e_salvam_modulos(self):
        from django.contrib.auth import get_user_model

        admin = get_user_model().objects.create_superuser(
            username="admin", email="admin@exemplo.com", password="senha-forte-123",
        )
        self.client.force_login(admin)
        self.enviar("SUBSCRIPTION_ACTIVATED", _assinatura_payload())
        conta = ContaAppfiliado.objects.get()

        for url in [
            "/admin/licencas/contaappfiliado/",
            f"/admin/licencas/contaappfiliado/{conta.pk}/change/",
            "/admin/licencas/produtozouti/add/",
            "/admin/licencas/eventowebhookzouti/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

        resposta = self.client.post("/admin/licencas/produtozouti/add/", {
            "zouti_product_id": "prod_pacote", "nome": "Pacote", "modulos": ["site", "videos"],
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(ProdutoZouti.objects.get(zouti_product_id="prod_pacote").modulos, "site,videos")


@override_settings(APPFILIADO_API_HOSTS=["api.appfiliado.com.br"], ALLOWED_HOSTS=["api.appfiliado.com.br", "testserver"])
class TestDominioDaApi(TestCase):
    def test_dominio_da_api_so_responde_licencas(self):
        cliente = Client(HTTP_HOST="api.appfiliado.com.br")
        self.assertEqual(cliente.get("/").status_code, 404)
        self.assertEqual(cliente.get("/admin/").status_code, 404)
        resposta = cliente.post("/licencas/validar/", data=json.dumps({"chave": "x"}), content_type="application/json")
        self.assertEqual(resposta.status_code, 200)


class TestMigracaoDasLicencasAntigas(TransactionTestCase):
    """A chave de quem já usava o app (época da Kiwify) tem que continuar valendo."""

    def test_licenca_ativa_vira_conta_com_cortesia_e_mesma_chave(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("licencas", "0001_initial")])
        apps_antigos = executor.loader.project_state([("licencas", "0001_initial")]).apps
        Licenca = apps_antigos.get_model("licencas", "Licenca")
        Licenca.objects.create(chave="AF-ANTIGA1", email="Dono@Exemplo.com", nome="Dono", status="ativa")
        Licenca.objects.create(chave="AF-ANTIGA2", email="ex@exemplo.com", status="cancelada")

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        # Até a última migração, pra o modelo atual bater com as colunas do banco.
        executor.migrate(executor.loader.graph.leaf_nodes())

        dono = ContaAppfiliado.objects.get(chave="AF-ANTIGA1")
        self.assertEqual(dono.email, "dono@exemplo.com")
        self.assertEqual(dono.modulos_liberados(), ["whatsapp"])
        self.assertIsNotNone(dono.chave_enviada_em)
        self.assertEqual(ContaAppfiliado.objects.get(chave="AF-ANTIGA2").modulos_liberados(), [])
