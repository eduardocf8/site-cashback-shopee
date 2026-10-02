"""Conferência de margem de uma campanha de cashback, com os pedidos reais.

Pergunta que responde: "se o cashback fosse X vezes maior nos últimos N dias, a cash-b
ainda ficaria com margem em cada pedido?". Só lê, nunca escreve.

O cashback de um pedido é max(comissão x %, valor x piso) x multiplicador (ver
pedidos/services.py::_montar_defaults). O multiplicador entra no fim, então simular outro
multiplicador é refazer só esse passo sobre o valor já gravado: cashback_base =
valor_cashback / multiplicador_campanha. Nada de rebuscar a Shopee.

O que o comando separa de propósito:

- Pedido que disparou bônus de indicação fica de fora. O valor dele já está dobrado pelo
  programa de indicação, e durante uma campanha o bônus é guardado para o pedido seguinte
  (ver o painel da conta), então ele não se soma à campanha.
- Venda "indireta" (clique em "Ir pra Shopee") e venda por link/vitrine saem em linhas
  separadas, porque o piso e a comissão de cada uma são diferentes. A separação é pelo tipo
  do clique e não pela verificação item a item que o sistema faz na hora de pagar, então é
  uma aproximação: um pedido de vitrine que não bate com o item clicado conta como vitrine
  aqui, e o sistema o trata como indireto.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from accounts.models import Indicacao
from links.models import Click
from pedidos.models import Pedido

ZERO = Decimal("0")
DIAS_PADRAO = 60
MULTIPLICADOR_PADRAO = "1.5"


def _reais(valor: Decimal) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(numerador: Decimal, denominador: Decimal) -> str:
    if not denominador:
        return "-"
    return f"{numerador / denominador * 100:.1f}%".replace(".", ",")


class Command(BaseCommand):
    help = (
        "Refaz o cashback dos pedidos recentes com outro multiplicador e mostra se a margem "
        "(comissão - cashback) continua positiva em cada pedido. Só leitura."
    )

    def add_arguments(self, parser):
        parser.add_argument("--multiplicador", type=str, default=MULTIPLICADOR_PADRAO,
                            help=f"Multiplicador a simular (padrão {MULTIPLICADOR_PADRAO} = 50%% a mais).")
        parser.add_argument("--dias", type=int, default=DIAS_PADRAO,
                            help=f"Janela, em dias para trás, pela data da compra (padrão {DIAS_PADRAO}).")

    def _pedidos(self, dias: int):
        desde = timezone.now() - timedelta(days=dias)
        ids_de_bonus = set(
            Indicacao.objects.exclude(pedido_bonus_indicado=None).values_list("pedido_bonus_indicado_id", flat=True)
        ) | set(
            Indicacao.objects.exclude(pedido_bonus_indicador=None).values_list("pedido_bonus_indicador_id", flat=True)
        )
        base = (
            Pedido.objects.filter(usuario__isnull=False, click__isnull=False)
            .exclude(status=Pedido.STATUS_CANCELADO)
            .filter(Q(data_compra__gte=desde) | Q(data_compra__isnull=True, criado_em__gte=desde))
            .select_related("click")
        )
        return base.exclude(pk__in=ids_de_bonus), len(ids_de_bonus & set(base.values_list("pk", flat=True)))

    @staticmethod
    def _linha(grupo: dict, rotulo: str, out) -> None:
        if not grupo["n"]:
            out.write(f"  {rotulo:<26} nenhum pedido")
            return
        out.write(
            f"  {rotulo:<26} {grupo['n']:>4} pedidos | cashback hoje {_pct(grupo['cashback'], grupo['comissao']):>6} "
            f"da comissão -> simulado {_pct(grupo['simulado'], grupo['comissao']):>6}"
        )

    def handle(self, *args, **opcoes):
        try:
            multiplicador = Decimal(opcoes["multiplicador"].replace(",", "."))
        except Exception:
            raise CommandError("--multiplicador precisa ser um número, ex: 1.5")
        if multiplicador <= 0:
            raise CommandError("--multiplicador precisa ser maior que zero.")

        pedidos, excluidos_bonus = self._pedidos(opcoes["dias"])

        grupos = {k: {"n": 0, "comissao": ZERO, "cashback": ZERO, "simulado": ZERO, "valor": ZERO}
                  for k in ("indireta", "vitrine")}
        prejuizo = []
        for pedido in pedidos:
            tipo = "indireta" if pedido.click.tipo == Click.TIPO_HOME else "vitrine"
            base = pedido.valor_cashback / (pedido.multiplicador_campanha or Decimal("1"))
            simulado = (base * multiplicador).quantize(Decimal("0.01"))
            g = grupos[tipo]
            g["n"] += 1
            g["valor"] += pedido.valor_pedido
            g["comissao"] += pedido.valor_comissao
            g["cashback"] += base
            g["simulado"] += simulado
            if simulado > pedido.valor_comissao:
                prejuizo.append((simulado - pedido.valor_comissao, pedido, simulado, tipo))

        total = {k: sum(g[k] for g in grupos.values()) for k in ("n", "comissao", "cashback", "simulado", "valor")}
        out = self.stdout
        out.write(f"\nSimulação: cashback x{multiplicador} nos pedidos dos últimos {opcoes['dias']} dias")
        out.write("=" * 70)
        out.write(f"  pedidos analisados         {total['n']:>6}")
        if excluidos_bonus:
            out.write(f"  fora da conta (bônus de indicação): {excluidos_bonus}")
        if not total["n"]:
            out.write("  Nenhum pedido na janela.")
            return
        out.write("")
        out.write(f"  {'valor comprado':<28} {_reais(total['valor']):>14}")
        out.write(f"  {'comissão recebida':<28} {_reais(total['comissao']):>14}")
        out.write(f"  {'cashback hoje':<28} {_reais(total['cashback']):>14}")
        out.write(f"  {f'cashback simulado (x{multiplicador})':<28} {_reais(total['simulado']):>14}")
        margem_hoje = total["comissao"] - total["cashback"]
        margem_sim = total["comissao"] - total["simulado"]
        out.write(f"  {'margem hoje':<28} {_reais(margem_hoje):>14}")
        out.write(f"  {'margem simulada':<28} {_reais(margem_sim):>14}  ({_pct(margem_sim - margem_hoje, margem_hoje)} sobre a de hoje)")
        out.write("\n  Quanto da comissão vira cashback:")
        self._linha(grupos["vitrine"], "link / vitrine", out)
        self._linha(grupos["indireta"], "\"Ir pra Shopee\" (indireta)", out)

        out.write("")
        if not prejuizo:
            out.write(self.style.SUCCESS(
                f"  Nenhum pedido pagaria mais cashback do que a comissão recebida (x{multiplicador})."
            ))
        else:
            soma = sum(p[0] for p in prejuizo)
            out.write(self.style.ERROR(
                f"  {len(prejuizo)} pedido(s) pagariam MAIS cashback do que a comissão recebida "
                f"(prejuízo somado {_reais(soma)}):"
            ))
            for perda, pedido, simulado, tipo in sorted(prejuizo, key=lambda x: -x[0])[:5]:
                out.write(f"    {pedido.order_id}  {tipo:<8} comissão {_reais(pedido.valor_comissao)} "
                          f"< cashback simulado {_reais(simulado)}")
