from django.test import TestCase
from django.urls import reverse

from .models import Indicacao, User


class CodigoIndicacaoTests(TestCase):
    def test_gera_codigo_ao_salvar(self):
        usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.assertTrue(usuario.codigo_indicacao)
        self.assertEqual(len(usuario.codigo_indicacao), 8)

    def test_codigos_gerados_sao_unicos(self):
        usuario1 = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        usuario2 = User.objects.create_user(username="bia", password="senha123", cpf="14783246947")
        self.assertNotEqual(usuario1.codigo_indicacao, usuario2.codigo_indicacao)

    def test_nao_sobrescreve_codigo_existente_ao_salvar_de_novo(self):
        usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        codigo_original = usuario.codigo_indicacao
        usuario.first_name = "Ana"
        usuario.save()
        self.assertEqual(usuario.codigo_indicacao, codigo_original)


class RegistrarComIndicacaoTests(TestCase):
    def setUp(self):
        self.indicador = User.objects.create_user(username="indicador", password="senha123", cpf="39053344705")

    def _dados_cadastro(self, **extra):
        dados = {
            "username": "novaconta",
            "email": "nova@example.com",
            "cpf": "14783246947",
            "password1": "senha-forte-123",
            "password2": "senha-forte-123",
        }
        dados.update(extra)
        return dados

    def test_cadastro_com_codigo_valido_cria_indicacao(self):
        self.client.post(
            reverse("registrar"), self._dados_cadastro(ref=self.indicador.codigo_indicacao)
        )
        novo_usuario = User.objects.get(username="novaconta")
        indicacao = Indicacao.objects.get(indicado=novo_usuario)
        self.assertEqual(indicacao.indicador, self.indicador)
        self.assertIsNone(indicacao.pedido_bonus_indicado)
        self.assertIsNone(indicacao.pedido_bonus_indicador)

    def test_cadastro_com_codigo_desconhecido_nao_cria_indicacao(self):
        self.client.post(reverse("registrar"), self._dados_cadastro(ref="NAOEXISTE"))
        novo_usuario = User.objects.get(username="novaconta")
        self.assertFalse(Indicacao.objects.filter(indicado=novo_usuario).exists())

    def test_cadastro_sem_codigo_nao_cria_indicacao(self):
        self.client.post(reverse("registrar"), self._dados_cadastro())
        novo_usuario = User.objects.get(username="novaconta")
        self.assertFalse(Indicacao.objects.filter(indicado=novo_usuario).exists())

    def test_pagina_de_cadastro_preenche_campo_oculto_com_ref_da_url(self):
        resposta = self.client.get(reverse("registrar"), {"ref": self.indicador.codigo_indicacao})
        self.assertContains(resposta, f'name="ref" value="{self.indicador.codigo_indicacao}"')


class DashboardIndicacaoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="ana", password="senha123", cpf="39053344705")
        self.client.force_login(self.usuario)

    def test_contexto_traz_link_de_indicacao_com_o_codigo_do_usuario(self):
        resposta = self.client.get(reverse("dashboard"))
        self.assertIn(self.usuario.codigo_indicacao, resposta.context["link_indicacao"])

    def test_lista_indicacoes_feitas_pelo_usuario(self):
        indicado = User.objects.create_user(username="bia", password="senha123", cpf="14783246947")
        Indicacao.objects.create(indicador=self.usuario, indicado=indicado)

        resposta = self.client.get(reverse("dashboard"))

        self.assertEqual(len(resposta.context["indicacoes"]), 1)
        self.assertEqual(resposta.context["indicacoes_concluidas"], 0)
