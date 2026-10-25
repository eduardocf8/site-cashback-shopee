"""Sugerir melhoria (painel/sugestoes.py)."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings

from .models import Sugestao
from .tests import BasePainel


@override_settings(APPFILIADO_EMAIL_SUPORTE="contato@appfiliado.com.br")
class TestSugestoes(BasePainel):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_menu_formulario_e_aviso_pra_voce(self):
        pagina = self.client.get("/sugestoes/")
        self.assertContains(pagina, "Ajude a construir o Appfiliado")
        self.assertContains(self.client.get("/"), ">Sugerir melhoria<")

        resposta = self.client.post("/sugestoes/", {"tipo": "melhoria", "ferramenta": "bot", "importancia": "3",
                                                     "mudaria": "Horário diferente pra cada grupo.", "ajudaria": "Vendo mais."},
                                    follow=True)
        self.assertContains(resposta, "Valeu! A sua sugestão chegou.")
        s = Sugestao.objects.get()
        self.assertEqual((s.tipo, s.ferramenta, s.descricao, s.importancia), ("melhoria", "bot", "Horário diferente pra cada grupo.", 3))
        self.assertEqual(mail.outbox[0].to, ["contato@appfiliado.com.br"])
        self.assertEqual(mail.outbox[0].reply_to, ["bia@exemplo.com"])
        self.assertContains(resposta, "Horário diferente pra cada grupo.")  # aparece em "Suas sugestões"

    def test_validacao_por_tipo(self):
        resposta = self.client.post("/sugestoes/", {"tipo": "melhoria", "importancia": "2"})
        self.assertContains(resposta, "Escolha a ferramenta.")
        self.assertContains(resposta, "Conte o que você mudaria.")
        resposta = self.client.post("/sugestoes/", {"tipo": "nova", "importancia": "2", "nova": "Telegram"})
        self.assertContains(resposta, "Conte que problema ela resolveria.")
        self.assertFalse(Sugestao.objects.exists())
        self.client.post("/sugestoes/", {"tipo": "nova", "importancia": "1", "nova": "Telegram", "problema": "Tenho canal lá."})
        self.assertEqual(Sugestao.objects.get().beneficio, "Tenho canal lá.")

    def test_feita_avisa_a_pessoa_uma_vez(self):
        s = Sugestao.objects.create(conta=self.conta, tipo="nova", descricao="Postar no Telegram", importancia=3)
        admin = get_user_model().objects.create_superuser("dono", "dono@exemplo.com", "senha-forte-123")
        self.client.force_login(admin)
        url = f"/admin/painel/sugestao/{s.pk}/change/"
        self.client.post(url, {"situacao": "feita", "anotacoes": ""}, HTTP_HOST="testserver")
        self.client.post(url, {"situacao": "feita", "anotacoes": "ok"}, HTTP_HOST="testserver")
        avisos = [m for m in mail.outbox if m.to == ["bia@exemplo.com"]]
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0].subject, "A sua sugestão virou realidade no Appfiliado")
        self.assertIn("Postar no Telegram", avisos[0].body)
