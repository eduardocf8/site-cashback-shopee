import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone

from assistente.ia import IAIndisponivel, responder
from assistente.perguntas_teste import CASOS
from assistente.verificacao_voz import problemas_de_voz

MODELOS_PADRAO = "claude-sonnet-5-5,claude-haiku-4-5"


class Command(BaseCommand):
    help = (
        "Faz as mesmas perguntas de teste (assistente/perguntas_teste.py) a cada modelo e "
        "gera um relatório HTML com as respostas lado a lado, custo, tempo de resposta e "
        "problemas de voz encontrados - para escolher o modelo do assistente lendo as "
        "respostas, não só pelo preço. Usa a API de verdade: cada rodada custa alguns "
        "centavos de dólar (ver assistente/README.md)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--modelos", default=MODELOS_PADRAO,
            help=f"Modelos separados por vírgula (padrão: {MODELOS_PADRAO}).",
        )
        parser.add_argument(
            "--casos", default="",
            help="Só estes casos (ids separados por vírgula, ver perguntas_teste.py). Padrão: todos.",
        )
        parser.add_argument(
            "--saida", default="relatorio_comparacao_assistente.html",
            help="Arquivo HTML do relatório (padrão: relatorio_comparacao_assistente.html).",
        )
        parser.add_argument(
            "--cotacao", type=Decimal, default=Decimal("5.50"),
            help="Reais por dólar, para mostrar o custo em R$ (padrão: 5.50).",
        )

    def handle(self, *args, **options):
        modelos = [m.strip() for m in options["modelos"].split(",") if m.strip()]
        casos = CASOS
        if options["casos"]:
            ids = {i.strip() for i in options["casos"].split(",")}
            casos = [caso for caso in CASOS if caso.id in ids]
            desconhecidos = ids - {caso.id for caso in casos}
            if desconhecidos:
                raise CommandError(f"Casos não encontrados: {', '.join(sorted(desconhecidos))}")
        if not settings.ANTHROPIC_API_KEY:
            raise CommandError("Configure ANTHROPIC_API_KEY no .env antes de comparar.")

        cotacao = options["cotacao"]
        linhas = []
        for caso in casos:
            resultados = []
            for modelo in modelos:
                self.stdout.write(f"{caso.id} · {modelo} ...", ending=" ")
                self.stdout.flush()
                resultados.append(self._rodar(caso, modelo))
                self.stdout.write(resultados[-1]["situacao"])
            linhas.append({"caso": caso, "resultados": resultados})

        resumo = [self._resumir(modelo, i, linhas, cotacao) for i, modelo in enumerate(modelos)]
        html = render_to_string("assistente/relatorio_comparacao.html", {
            "gerado_em": timezone.localtime(),
            "modelos": modelos,
            "linhas": linhas,
            "resumo": resumo,
            "cotacao": cotacao,
        })
        saida = Path(options["saida"])
        saida.write_text(html, encoding="utf-8")

        self.stdout.write("")
        for r in resumo:
            self.stdout.write(
                f"{r['modelo']}: US$ {r['custo_total_usd']:.4f} (R$ {r['custo_total_brl']:.2f}) no total, "
                f"{r['tempo_medio']:.1f}s em média, {r['problemas_voz']} resposta(s) com problema de voz, "
                f"{r['erros_humano']} erro(s) de passagem para humano, {r['falhas']} falha(s)."
            )
        self.stdout.write(self.style.SUCCESS(f"Relatório salvo em {saida.resolve()}"))

    def _rodar(self, caso, modelo) -> dict:
        inicio = time.monotonic()
        try:
            resposta = responder(caso.mensagens, modelo=modelo)
        except IAIndisponivel as erro:
            return {"modelo": modelo, "erro": str(erro), "situacao": "ERRO", "segundos": time.monotonic() - inicio}
        segundos = time.monotonic() - inicio
        problemas = problemas_de_voz(resposta.texto)
        humano_errado = caso.espera_humano is not None and resposta.passar_para_humano != caso.espera_humano
        situacao = "ok"
        if resposta.motivo_falha:
            situacao = f"falha ({resposta.motivo_falha})"
        elif problemas or humano_errado:
            situacao = "revisar"
        return {
            "modelo": modelo,
            "resposta": resposta,
            "segundos": segundos,
            "problemas": problemas,
            "humano_errado": humano_errado,
            "situacao": situacao,
        }

    def _resumir(self, modelo, indice, linhas, cotacao) -> dict:
        resultados = [linha["resultados"][indice] for linha in linhas]
        respostas = [r["resposta"] for r in resultados if "resposta" in r]
        custo = sum((r.custo_usd or Decimal("0") for r in respostas), Decimal("0"))
        return {
            "modelo": modelo,
            "custo_total_usd": custo,
            "custo_total_brl": custo * cotacao,
            "custo_medio_brl": (custo * cotacao / len(respostas)) if respostas else Decimal("0"),
            "tempo_medio": sum(r["segundos"] for r in resultados) / len(resultados) if resultados else 0,
            "problemas_voz": sum(1 for r in resultados if r.get("problemas")),
            "erros_humano": sum(1 for r in resultados if r.get("humano_errado")),
            "falhas": sum(1 for r in resultados if "erro" in r or (r.get("resposta") and r["resposta"].motivo_falha)),
        }
