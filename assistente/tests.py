import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx2
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from pedidos.models import CampanhaCashback

from .base_conhecimento import dados_do_momento, descrever_campanha, html_para_texto, montar_base
from .ia import (
    MENSAGEM_PASSAR_PARA_HUMANO,
    PAPEL_ASSISTENTE,
    PAPEL_PESSOA,
    IAIndisponivel,
    Mensagem,
    RespostaIA,
    responder,
)
from .instrucoes import montar_instrucoes
from .precos import calcular_custo_usd
from .provedores import obter_provedor
from .verificacao_voz import problemas_de_voz


def _resposta_api(texto=None, stop_reason="end_turn", model="claude-sonnet-5-5", **uso):
    """Imita o objeto que o SDK devolve em messages.create."""
    if texto is None:
        texto = json.dumps({"resposta": "Não custa nada para usar a cash-b.", "passar_para_humano": False})
    usage = {
        "input_tokens": 50, "output_tokens": 100,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 8000,
    }
    usage.update(uso)
    return SimpleNamespace(
        stop_reason=stop_reason,
        model=model,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=texto)],
        usage=SimpleNamespace(**usage),
    )


class HtmlParaTextoTests(SimpleTestCase):
    def test_pega_so_o_conteudo_principal_com_estrutura(self):
        html = """
            <div class="topo">cash-b</div>
            <div class="container">
                <div class="nav-topo"><a href="/">Voltar pro início</a></div>
                <h1>Perguntas</h1>
                <details><summary>Custa algo?</summary><p>Não,
                    nada.</p></details>
                <ul><li>Um</li><li>Dois</li></ul>
                <form><button>Enviar</button></form>
                <script>alert(1)</script>
            </div>
            <footer>Rodapé</footer>
        """
        self.assertEqual(html_para_texto(html), "# Perguntas\n\nP: Custa algo?\n\nNão, nada.\n\n- Um\n\n- Dois")


class BaseConhecimentoTests(TestCase):
    @override_settings(CASHBACK_MINIMO_VENDA_DIRETA=2.5, SAQUE_VALOR_MINIMO=Decimal("35.00"))
    def test_numeros_vem_do_sistema_e_nao_de_texto_fixo(self):
        base = montar_base()
        self.assertIn("2,5% em venda direta", base)
        self.assertIn("R$ 35,00", base)
        momento = dados_do_momento()
        self.assertIn("2,5% em venda direta", momento)
        self.assertIn("R$ 35,00", momento)

    def test_tem_endereco_das_paginas_e_nao_tem_navegacao(self):
        base = montar_base()
        self.assertIn('endereco="https://cash-b.com/perguntas-frequentes/"', base)
        self.assertIn('endereco="https://cash-b.com/regras-do-cashback/"', base)
        self.assertNotIn("Voltar pro início", base)
        self.assertNotIn("{%", base)

    def test_campanha_em_andamento(self):
        agora = timezone.now()
        CampanhaCashback.objects.create(
            multiplicador=Decimal("1.5"), inicio=agora - timedelta(hours=1), fim=agora + timedelta(hours=5)
        )
        texto = descrever_campanha(agora)
        self.assertIn("EM ANDAMENTO", texto)
        self.assertIn("50% a mais de cashback", texto)

    def test_campanha_anunciada(self):
        agora = timezone.now()
        CampanhaCashback.objects.create(
            multiplicador=Decimal("1.5"), inicio=agora + timedelta(days=2), fim=agora + timedelta(days=2, hours=23)
        )
        self.assertIn("Próxima campanha", descrever_campanha(agora))

    def test_sem_campanha(self):
        self.assertIn("Nenhuma campanha", descrever_campanha())


class InstrucoesTests(SimpleTestCase):
    def test_regras_de_voz_vem_do_voz_md(self):
        instrucoes = montar_instrucoes()
        self.assertIn('**"Pix", não "PIX".**', instrucoes)
        self.assertNotIn("{regras_de_voz}", instrucoes)
        # Só a seção de regras, não o histórico de onde foram aplicadas.
        self.assertNotIn("Onde essas regras já foram aplicadas", instrucoes)


@override_settings(ANTHROPIC_API_KEY="chave-de-teste", ASSISTENTE_IA_PROVEDOR="claude",
                   ASSISTENTE_IA_MODELO="claude-sonnet-5-5")
class ProvedorClaudeTests(TestCase):
    def setUp(self):
        patcher = patch("assistente.provedores.claude.anthropic.Anthropic")
        self.classe_cliente = patcher.start()
        self.addCleanup(patcher.stop)
        self.create = self.classe_cliente.return_value.beta.messages.create
        self.create.return_value = _resposta_api()

    def _parametros(self):
        return self.create.call_args.kwargs

    def test_resposta_normal(self):
        resposta = responder([Mensagem(PAPEL_PESSOA, "Quanto custa?")])
        self.assertEqual(resposta.texto, "Não custa nada para usar a cash-b.")
        self.assertFalse(resposta.passar_para_humano)
        self.assertIsNone(resposta.motivo_falha)
        self.assertEqual(resposta.modelo, "claude-sonnet-5-5")
        # 50 x $2 + 100 x $10 + 8000 x $0,20, por milhão de tokens
        self.assertEqual(resposta.custo_usd, Decimal("0.0027"))

    def test_base_vai_em_cache_e_dados_do_momento_ficam_fora_dele(self):
        responder([Mensagem(PAPEL_PESSOA, "Oi")])
        fixo, do_momento = self._parametros()["system"]
        self.assertEqual(fixo["cache_control"], {"type": "ephemeral"})
        self.assertIn("<base_de_conhecimento>", fixo["text"])
        self.assertNotIn("cache_control", do_momento)
        self.assertIn("<dados_do_momento>", do_momento["text"])
        self.assertNotIn("Agora:", fixo["text"])

    def test_sonnet_usa_esforco_baixo_e_modelo_alternativo_em_recusa(self):
        responder([Mensagem(PAPEL_PESSOA, "Oi")])
        parametros = self._parametros()
        self.assertEqual(parametros["model"], "claude-sonnet-5-5")
        self.assertEqual(parametros["output_config"]["effort"], "low")
        self.assertEqual(parametros["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(parametros["fallbacks"], "default")
        self.assertEqual(parametros["betas"], ["server-side-fallback-2026-07-01"])

    def test_haiku_nao_recebe_parametros_que_nao_aceita(self):
        self.create.return_value = _resposta_api(model="claude-haiku-4-5")
        resposta = responder([Mensagem(PAPEL_PESSOA, "Oi")], modelo="claude-haiku-4-5")
        parametros = self._parametros()
        self.assertEqual(parametros["model"], "claude-haiku-4-5")
        self.assertNotIn("effort", parametros["output_config"])
        self.assertNotIn("fallbacks", parametros)
        self.assertNotIn("betas", parametros)
        self.assertEqual(resposta.custo_usd, Decimal("0.00135"))

    def test_historico_vira_mensagens_e_comeca_pela_pessoa(self):
        responder([
            Mensagem(PAPEL_ASSISTENTE, "Boas-vindas!"),
            Mensagem(PAPEL_PESSOA, "Quanto tempo demora?"),
            Mensagem(PAPEL_ASSISTENTE, "Dia 1º do segundo mês."),
            Mensagem(PAPEL_PESSOA, "E em dezembro?"),
        ])
        self.assertEqual(self._parametros()["messages"], [
            {"role": "user", "content": "Quanto tempo demora?"},
            {"role": "assistant", "content": "Dia 1º do segundo mês."},
            {"role": "user", "content": "E em dezembro?"},
        ])

    def test_pedido_de_humano_do_modelo_e_respeitado(self):
        self.create.return_value = _resposta_api(
            json.dumps({"resposta": "Vou chamar alguém da equipe.", "passar_para_humano": True})
        )
        resposta = responder([Mensagem(PAPEL_PESSOA, "Cadê meu saque?")])
        self.assertTrue(resposta.passar_para_humano)
        self.assertEqual(resposta.texto, "Vou chamar alguém da equipe.")

    def test_respostas_nao_confiaveis_vao_para_uma_pessoa(self):
        casos = {
            "recusa": _resposta_api(stop_reason="refusal"),
            "resposta_cortada": _resposta_api('{"resposta": "Olá, o cashb', stop_reason="max_tokens"),
            "formato_invalido": _resposta_api("isso não é json"),
        }
        for motivo, resposta_api in casos.items():
            with self.subTest(motivo):
                self.create.return_value = resposta_api
                resposta = responder([Mensagem(PAPEL_PESSOA, "Oi")])
                self.assertEqual(resposta.motivo_falha, motivo)
                self.assertTrue(resposta.passar_para_humano)
                self.assertEqual(resposta.texto, MENSAGEM_PASSAR_PARA_HUMANO)
                self.assertIsNotNone(resposta.custo_usd)

    def test_resposta_vazia_vai_para_uma_pessoa(self):
        self.create.return_value = _resposta_api(json.dumps({"resposta": "  ", "passar_para_humano": False}))
        self.assertEqual(responder([Mensagem(PAPEL_PESSOA, "Oi")]).motivo_falha, "formato_invalido")

    def test_preco_do_modelo_alternativo_quando_ele_respondeu(self):
        self.create.return_value = _resposta_api(model="claude-haiku-4-5")
        resposta = responder([Mensagem(PAPEL_PESSOA, "Oi")])
        self.assertEqual(resposta.modelo, "claude-haiku-4-5")
        self.assertEqual(resposta.custo_usd, Decimal("0.00135"))

    def test_modelo_alternativo_fora_da_tabela_usa_preco_do_pedido(self):
        self.create.return_value = _resposta_api(model="claude-modelo-novo")
        self.assertEqual(responder([Mensagem(PAPEL_PESSOA, "Oi")]).custo_usd, Decimal("0.0027"))

    def test_erro_da_api_vira_ia_indisponivel(self):
        self.create.side_effect = anthropic.APIConnectionError(
            request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        with self.assertRaises(IAIndisponivel):
            responder([Mensagem(PAPEL_PESSOA, "Oi")])

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_chave_vira_ia_indisponivel(self):
        with self.assertRaises(IAIndisponivel):
            responder([Mensagem(PAPEL_PESSOA, "Oi")])
        self.create.assert_not_called()

    def test_historico_sem_mensagem_da_pessoa_e_erro_de_programacao(self):
        with self.assertRaises(ValueError):
            responder([Mensagem(PAPEL_ASSISTENTE, "Oi")])


class ProvedoresTests(SimpleTestCase):
    def test_provedor_desconhecido(self):
        with self.assertRaises(IAIndisponivel):
            obter_provedor("outra-empresa")


class PrecosTests(SimpleTestCase):
    def test_custo_com_cache(self):
        # 1M de entrada ($2) + 1M de saída ($10) + 1M gravado ($2,50) + 1M lido ($0,20)
        self.assertEqual(
            calcular_custo_usd("claude-sonnet-5-5", 1_000_000, 1_000_000, 1_000_000, 1_000_000),
            Decimal("14.7"),
        )

    def test_modelo_desconhecido(self):
        self.assertIsNone(calcular_custo_usd("modelo-que-nao-existe", 10, 10))


class VerificacaoVozTests(SimpleTestCase):
    def test_texto_correto_nao_tem_problema(self):
        texto = "Na cash-b o cashback volta via Pix, e no 10/10 tem 50% a mais. *Aproveite!*"
        self.assertEqual(problemas_de_voz(texto), [])

    def test_encontra_cada_deslize(self):
        casos = {
            "Saque via PIX.": "PIX",
            "Hoje tem +50% de cashback.": "sinal de mais",
            "Toda compra pode voltar dinheiro.": "condicional",
            "Bem-vindo ao cash-b!": "masculino",
            "**Atenção**": "dois asteriscos",
            "# Regras": "Markdown",
            "A Cash-B paga via Pix.": "Cash-B",
            "A cashb paga via Pix.": "cashb",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto):
                problemas = problemas_de_voz(texto)
                self.assertEqual(len(problemas), 1, problemas)
                self.assertIn(esperado, problemas[0])


@override_settings(ANTHROPIC_API_KEY="chave-de-teste")
class CompararModelosTests(TestCase):
    def _responder_falso(self, mensagens, modelo):
        if modelo == "claude-haiku-4-5":
            return RespostaIA(
                texto="Saque via PIX.", passar_para_humano=True, modelo=modelo,
                tokens_entrada=10, tokens_saida=10, custo_usd=Decimal("0.001"),
            )
        return RespostaIA(
            texto="O saque é via Pix.", passar_para_humano=False, modelo=modelo,
            tokens_entrada=10, tokens_saida=10, custo_usd=Decimal("0.002"),
        )

    def test_gera_relatorio_com_as_respostas_lado_a_lado(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "relatorio.html"
            with patch("assistente.management.commands.comparar_modelos_assistente.responder",
                       side_effect=self._responder_falso):
                call_command("comparar_modelos_assistente", casos="paga_pix,saque_minimo",
                             saida=str(saida), stdout=StringIO())
            html = saida.read_text(encoding="utf-8")
        self.assertIn("O saque é via Pix.", html)
        self.assertIn("Saque via PIX.", html)
        self.assertIn("claude-sonnet-5-5", html)
        self.assertIn("claude-haiku-4-5", html)
        self.assertIn("&quot;PIX&quot; em maiúsculas", html)
        self.assertIn("esperado o contrário", html)  # Haiku passou para humano sem precisar

    def test_erro_de_um_modelo_nao_interrompe_a_comparacao(self):
        def responder_com_erro(mensagens, modelo):
            if modelo == "claude-haiku-4-5":
                raise IAIndisponivel("fora do ar")
            return self._responder_falso(mensagens, modelo)

        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "relatorio.html"
            with patch("assistente.management.commands.comparar_modelos_assistente.responder",
                       side_effect=responder_com_erro):
                call_command("comparar_modelos_assistente", casos="paga_pix",
                             saida=str(saida), stdout=StringIO())
            html = saida.read_text(encoding="utf-8")
        self.assertIn("fora do ar", html)
        self.assertIn("O saque é via Pix.", html)

    def test_caso_desconhecido(self):
        with self.assertRaises(CommandError):
            call_command("comparar_modelos_assistente", casos="nao_existe", stdout=StringIO())

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sem_chave(self):
        with self.assertRaises(CommandError):
            call_command("comparar_modelos_assistente", stdout=StringIO())
