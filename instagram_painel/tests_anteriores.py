"""Responder quem comentou (ou mandou DM) antes de a automação estar ligada (anteriores.py)."""

from datetime import timedelta
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import anteriores, api
from . import webhook as W
from .models import Automacao, Disparo, Repasse
from .tests import HOST, IG_ID, SENHA, conectada, conta


def quando(horas_atras: float) -> str:
    return (timezone.now() - timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def comentario(cid, autor, texto, horas=1, username=None):
    return {"id": cid, "text": texto, "timestamp": quando(horas),
            "from": {"id": autor, "username": username or f"pessoa{autor}"}}


@mock.patch.object(api, "posts_recentes", return_value=[{"id": "m1"}, {"id": "m2"}])
class TestBuscarComentarios(TestCase):
    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, ig_id=IG_ID, nome="Garrafa", gatilho=Automacao.COMENTARIO,
                                          midia_id="m1", palavras="quero", texto_dm="Aqui está:",
                                          link="https://s.shopee.com.br/abc")

    def rodar(self, paginas):
        with mock.patch.object(api, "comentarios", side_effect=paginas) as chamadas:
            r = anteriores.pedir(self.a)
            anteriores.processar()
        r.refresh_from_db()
        return r, chamadas

    def test_poe_na_fila_quem_ainda_nao_recebeu(self, _posts):
        Disparo.objects.create(automacao=self.a, evento_id="velho", autor_id="1", dm_ok=True)  # já recebeu
        r, chamadas = self.rodar([
            ([comentario("c1", "1", "quero"), comentario("c2", "2", "QUERO!"), comentario("c3", "3", "lindo")], "pag2"),
            ([comentario("c4", "4", "quero", horas=24 * 8),  # passou do prazo de 7 dias
              comentario("c5", IG_ID, "quero"),  # a própria conta
              comentario("c6", "2", "quero de novo")], ""),  # a mesma pessoa
        ])
        self.assertEqual(r.estado, Repasse.PRONTO)
        self.assertEqual((r.enfileirados, r.pulados, r.sem_palavra), (1, 2, 1))
        d = Disparo.objects.get(evento_id="c2")
        self.assertTrue(d.na_fila and d.anterior)
        self.assertLess(d.evento_em, timezone.now())
        self.assertEqual(chamadas.call_args_list[1].args, ("tok", "m1", "pag2"))  # segunda página

    def test_todos_os_posts_e_a_automacao_do_post_vem_antes(self, _posts):
        geral = Automacao.objects.create(conta=self.c, ig_id=IG_ID, nome="Todos", gatilho=Automacao.COMENTARIO,
                                         palavras="quero", texto_dm="Oi")
        with mock.patch.object(api, "comentarios", side_effect=[([comentario("c1", "1", "quero")], ""),
                                                                ([comentario("c2", "2", "quero")], "")]):
            anteriores.pedir(geral)
            anteriores.processar()
        r = geral.repasses.get()
        self.assertEqual((r.enfileirados, r.de_outra), (1, 1))  # o de m1 é da automação do post
        self.assertTrue(Disparo.objects.filter(automacao=geral, evento_id="c2").exists())

    def test_a_fila_manda_e_respeita_o_prazo_do_comentario(self, _posts):
        self.rodar([([comentario("c1", "1", "quero"), comentario("c2", "2", "quero", horas=24 * 7 - 3)], "")])
        Disparo.objects.filter(evento_id="c2").update(evento_em=timezone.now() - timedelta(days=7, minutes=5))
        with mock.patch.object(api, "resposta_privada", return_value="d1") as privada, \
                mock.patch.object(api, "responder_comentario", return_value="r1"):
            W.enviar_fila()
        privada.assert_called_once()
        self.assertEqual(privada.call_args.args[2], "c1")
        self.assertIn("passou do prazo", Disparo.objects.get(evento_id="c2").erro)

    def test_erro_do_instagram_aparece_na_busca(self, _posts):
        r, _ = self.rodar(api.ErroInstagram("Unsupported get request (código 100)"))
        self.assertEqual(r.estado, Repasse.ERRO)
        self.assertIn("Unsupported get request", r.mensagem)

    def test_nao_busca_pausada_story_nem_duas_vezes_seguidas(self, _posts):
        self.a.ativa = False
        self.a.save()
        with self.assertRaisesMessage(anteriores.ErroAnteriores, "Ligue a automação"):
            anteriores.pedir(self.a)
        self.a.ativa = True
        self.a.save()
        primeira = anteriores.pedir(self.a)
        self.assertEqual(anteriores.pedir(self.a), primeira)  # a que está na fila
        Repasse.objects.filter(pk=primeira.pk).update(estado=Repasse.PRONTO)
        with self.assertRaisesMessage(anteriores.ErroAnteriores, "acabou de buscar"):
            anteriores.pedir(self.a)
        story = Automacao.objects.create(conta=self.c, ig_id=IG_ID, nome="Story", gatilho=Automacao.STORY,
                                         palavras="quero", texto_dm="Oi")
        self.assertIn("story", anteriores.motivo_para_nao_buscar(story))


class TestBuscarDMs(TestCase):
    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, ig_id=IG_ID, nome="DM", gatilho=Automacao.DIRETO,
                                          palavras="cupom", texto_dm="O cupom é BIA10")

    def test_dms_das_ultimas_24_horas(self):
        conversas = [
            {"updated_time": quando(1), "messages": {"data": [
                {"id": "mid1", "created_time": quando(1), "from": {"id": "7", "username": "ana"}, "message": "tem cupom?"},
                {"id": "mid0", "created_time": quando(1.5), "from": {"id": IG_ID, "username": "achadosdabia"},
                 "message": "cupom"}]}},  # a própria conta
            {"updated_time": quando(30), "messages": {"data": [
                {"id": "mid2", "created_time": quando(30), "from": {"id": "8"}, "message": "cupom"}]}},  # mais de 24 h
        ]
        with mock.patch.object(api, "conversas_recentes", return_value=conversas):
            anteriores.pedir(self.a)
            anteriores.processar()
        r = self.a.repasses.get()
        self.assertEqual((r.estado, r.enfileirados), (Repasse.PRONTO, 1))
        self.assertEqual(Disparo.objects.get().autor_id, "7")


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestTelaDosAnteriores(TestCase):
    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, ig_id=IG_ID, ig_username="achadosdabia", nome="Garrafa",
                                          gatilho=Automacao.COMENTARIO, midia_id="m1", palavras="quero", texto_dm="Oi")
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})

    def test_botao_pede_a_busca_e_mostra_o_resultado(self):
        pagina = self.client.get(f"/estudio/automacoes/{self.a.pk}/").content.decode()
        self.assertIn("Responder quem já comentou", pagina)
        self.client.post(f"/estudio/automacoes/{self.a.pk}/anteriores/")
        r = self.a.repasses.get()
        self.assertEqual(r.estado, Repasse.FILA)
        Repasse.objects.filter(pk=r.pk).update(estado=Repasse.PRONTO, enfileirados=12, pulados=3,
                                               terminado_em=timezone.now())
        pagina = self.client.get(f"/estudio/automacoes/{self.a.pk}/").content.decode()
        self.assertIn("<b>12</b> pessoas na fila", pagina)
        self.assertIn("3 já tinham recebido", pagina)


@override_settings(APPFILIADO_PAINEL_HOSTS=[HOST], ALLOWED_HOSTS=[HOST, "testserver"], APPFILIADO_PAINEL_URL=f"https://{HOST}")
class TestAndamentoNaTela(TestCase):
    """O cartão se atualiza sozinho (situacao/) enquanto a busca roda e enquanto tem gente na fila."""

    def setUp(self):
        self.c = conta()
        self.ig = conectada(self.c)
        self.a = Automacao.objects.create(conta=self.c, ig_id=IG_ID, ig_username="achadosdabia", nome="Garrafa",
                                          gatilho=Automacao.COMENTARIO, midia_id="m1", palavras="quero", texto_dm="Oi")
        self.client = Client(HTTP_HOST=HOST)
        self.client.post("/entrar/", {"email": "bia@exemplo.com", "senha": SENHA})
        self.url = f"/estudio/automacoes/{self.a.pk}/anteriores/situacao/"

    def test_acompanha_a_busca_e_o_envio(self):
        r = anteriores.pedir(self.a)
        cartao = self.client.get(self.url).content.decode()
        self.assertIn("data-acompanhar", cartao)
        self.assertIn("A busca começa em instantes", cartao)
        Repasse.objects.filter(pk=r.pk).update(pedido_em=timezone.now() - timedelta(minutes=15))
        self.assertIn("pode estar reiniciando", self.client.get(self.url).content.decode())
        with mock.patch.object(api, "comentarios", return_value=([comentario("c1", "1", "quero"),
                                                                  comentario("c2", "2", "quero")], "")):
            anteriores.processar()
        Disparo.objects.filter(evento_id="c1").update(na_fila=False, dm_ok=True, enviado_em=timezone.now())
        cartao = self.client.get(self.url).content.decode()
        self.assertIn("Enviando: <b>1</b> de 2 já receberam", cartao)
        self.assertIn("data-acompanhar", cartao)
        Disparo.objects.filter(evento_id="c2").update(na_fila=False, erro="Não enviada: passou do prazo do Instagram.")
        cartao = self.client.get(self.url).content.decode()
        self.assertIn("Pronto: <b>1</b> de 2 receberam (1 não deu", cartao)
        self.assertNotIn("data-acompanhar", cartao)  # acabou: para de perguntar
