"""Responde a pergunta que o Gerenciador de Anúncios não responde: dos cadastros que
entraram, quantos viraram gente que compra.

A Meta sabe dizer quanto custou cada CompleteRegistration. Ela não sabe dizer se
aquela pessoa voltou, gerou link e comprou - isso só existe aqui dentro. E é essa
segunda metade que decide se um CPA baixo é bom negócio ou é só tráfego barato: cadastro
que nunca gera link não vale nada, por mais barato que tenha saído.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum
from django.utils import timezone

from pedidos.models import Pedido

DIAS_PADRAO = 30


class Command(BaseCommand):
    help = (
        "Mostra o funil de uma coorte de cadastros: quantos verificaram o e-mail, "
        "quantos geraram link, quantos compraram e quanto de cashback saiu. Com "
        "--custo-por-cadastro, converte o CPA do anúncio no custo real por comprador."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=DIAS_PADRAO,
            help=f"Tamanho da janela, contada pra trás a partir de hoje (padrão: {DIAS_PADRAO}).",
        )
        parser.add_argument(
            "--desde", type=str, default="",
            help="Data inicial YYYY-MM-DD. Se informada, ignora --dias. Use a data em que "
                 "a campanha começou pra a coorte bater com o período do anúncio.",
        )
        parser.add_argument(
            "--ate", type=str, default="",
            help="Data final YYYY-MM-DD (inclusive). Padrão: hoje.",
        )
        parser.add_argument(
            "--custo-por-cadastro", type=float, default=0.0,
            help="CPA do anúncio, em reais. Com ele o comando calcula o custo por pessoa "
                 "que gerou link e por pessoa que comprou.",
        )
        parser.add_argument(
            "--sem-indicados", action="store_true",
            help="Tira da coorte quem entrou por indicação. Não existe campo de origem no "
                 "User, então essa é a forma mais próxima de isolar quem veio de fora - "
                 "ver a ressalva no fim da saída.",
        )
        parser.add_argument(
            "--por-semana", action="store_true",
            help="Quebra a coorte por semana de cadastro, pra ver se a ativação melhora "
                 "ou piora ao longo da campanha.",
        )

    # ------------------------------------------------------------------ datas

    def _janela(self, opcoes):
        fuso = timezone.get_current_timezone()
        agora = timezone.now()

        def _ler(texto, campo):
            try:
                data = timezone.datetime.strptime(texto, "%Y-%m-%d")
            except ValueError as erro:
                raise CommandError(f"--{campo} precisa ser YYYY-MM-DD: {erro}")
            return timezone.make_aware(data, fuso)

        fim = _ler(opcoes["ate"], "ate") + timedelta(days=1) if opcoes["ate"] else agora
        if opcoes["desde"]:
            inicio = _ler(opcoes["desde"], "desde")
        else:
            inicio = fim - timedelta(days=opcoes["dias"])
        if inicio >= fim:
            raise CommandError("A data inicial precisa ser anterior à final.")
        return inicio, fim

    # ------------------------------------------------------------------ saída

    def _linha(self, rotulo, quantidade, base, extra=""):
        fatia = f"{quantidade / base * 100:5.1f}%" if base else "    -"
        self.stdout.write(f"  {rotulo:<34} {quantidade:>6}  {fatia}  {extra}")

    def _bloco(self, usuarios, custo_por_cadastro, fim_da_fatia=None):
        total = usuarios.count()
        if total == 0:
            self.stdout.write("  Nenhum cadastro nessa janela.")
            return

        verificados = usuarios.filter(email_verificado=True).count()

        # annotate em vez de contar Click direto: o que interessa é quantas PESSOAS
        # geraram link, não quantos links saíram. Uma pessoa que gerou 40 links é um
        # ativado só, e contar clique somaria ela 40 vezes.
        com_clique = usuarios.annotate(n=Count("clicks")).filter(n__gt=0).count()

        pedidos = Pedido.objects.filter(usuario__in=usuarios)
        nao_cancelados = pedidos.exclude(status=Pedido.STATUS_CANCELADO)
        compradores = nao_cancelados.values("usuario").distinct().count()

        totais = nao_cancelados.aggregate(
            valor=Sum("valor_pedido"),
            comissao=Sum("valor_comissao"),
            cashback=Sum("valor_cashback"),
        )
        valor = totais["valor"] or Decimal("0")
        comissao = totais["comissao"] or Decimal("0")
        cashback = totais["cashback"] or Decimal("0")
        # O que sobra pra cash-b: a comissão que a Shopee paga menos o cashback que
        # volta pro usuário. Sem esta linha o relatório mostrava só o custo (o
        # cashback) e nenhuma receita, o que fazia qualquer campanha parecer prejuízo.
        margem = comissao - cashback

        self.stdout.write(f"  {'cadastros':<34} {total:>6}")
        if fim_da_fatia is not None:
            # Uma coorte de 3 dias não teve tempo de comprar. Sem esta linha, a fatia
            # mais recente sempre parece um desabamento, e a conclusão errada é cortar
            # a campanha justamente quando ela está indo bem.
            dias = max((timezone.now() - fim_da_fatia).days, 0)
            self.stdout.write(f"  {'dias de maturação desde o fim':<34} {dias:>6}")
        self._linha("e-mail verificado", verificados, total)
        self._linha("gerou ao menos 1 link", com_clique, total)
        self._linha("comprou ao menos 1x", compradores, total)

        if com_clique:
            self._linha(
                "comprou, entre os que geraram link", compradores, com_clique,
                "<- taxa de conversão real do produto",
            )

        self.stdout.write("")
        for rotulo, status in (
            ("pedidos pendentes", Pedido.STATUS_PENDENTE),
            ("pedidos validados", Pedido.STATUS_VALIDADO),
            ("pedidos liberados", Pedido.STATUS_LIBERADO),
            ("pedidos cancelados", Pedido.STATUS_CANCELADO),
        ):
            self.stdout.write(f"  {rotulo:<34} {pedidos.filter(status=status).count():>6}")
        self.stdout.write("")
        self.stdout.write(f"  {'valor comprado (GMV)':<34} {'R$ ' + f'{valor:.2f}':>9}")
        self.stdout.write(f"  {'comissão recebida':<34} {'R$ ' + f'{comissao:.2f}':>9}")
        self.stdout.write(f"  {'cashback devolvido':<34} {'R$ ' + f'{cashback:.2f}':>9}")
        self.stdout.write(f"  {'margem bruta':<34} {'R$ ' + f'{margem:.2f}':>9}")

        if custo_por_cadastro:
            self.stdout.write("")
            investido = Decimal(str(custo_por_cadastro)) * total
            self.stdout.write(f"  {'investido na coorte':<34} {'R$ ' + f'{investido:.2f}':>9}")
            if com_clique:
                self.stdout.write(
                    f"  {'custo por pessoa que gerou link':<34} "
                    f"{'R$ ' + f'{investido / com_clique:.2f}':>9}"
                )
            if compradores:
                self.stdout.write(
                    f"  {'custo por comprador':<34} "
                    f"{'R$ ' + f'{investido / compradores:.2f}':>9}"
                )
            else:
                self.stdout.write("  custo por comprador               nenhum comprador ainda")
            # O número que decide não é o custo por comprador: é quanto do investido
            # voltou como margem. Abaixo de 100% a coorte ainda não se pagou na
            # primeira compra - o que num negócio de recompra pode estar tudo bem,
            # desde que a pessoa volte.
            retorno = margem / investido * 100 if investido else Decimal("0")
            self.stdout.write(
                f"  {'margem / investido':<34} {f'{retorno:.1f}%':>9}  <- o número que decide"
            )

    # ------------------------------------------------------------------ tempo

    def _tempo_ate_primeiro_link(self, usuarios):
        """Mediana, não média: uma pessoa que cadastrou e só voltou 40 dias depois puxa
        a média sozinha e faz parecer que todo mundo demora."""
        horas = []
        for usuario in usuarios.prefetch_related("clicks"):
            clicks = list(usuario.clicks.all())
            if not clicks:
                continue
            primeiro = min(c.criado_em for c in clicks)
            horas.append((primeiro - usuario.date_joined).total_seconds() / 3600)
        if not horas:
            return None
        horas.sort()
        meio = len(horas) // 2
        return horas[meio] if len(horas) % 2 else (horas[meio - 1] + horas[meio]) / 2

    # ------------------------------------------------------------------ main

    def handle(self, *args, **opcoes):
        inicio, fim = self._janela(opcoes)
        Usuario = get_user_model()

        usuarios = Usuario.objects.filter(date_joined__gte=inicio, date_joined__lt=fim)
        if opcoes["sem_indicados"]:
            usuarios = usuarios.filter(indicacao_recebida__isnull=True)

        self.stdout.write(
            f"\nCoorte de cadastro: {inicio:%d/%m/%Y} a {(fim - timedelta(days=1)):%d/%m/%Y}"
            + ("  (sem indicados)" if opcoes["sem_indicados"] else "")
        )
        self.stdout.write("=" * 70)
        self._bloco(usuarios, opcoes["custo_por_cadastro"])

        mediana = self._tempo_ate_primeiro_link(usuarios)
        if mediana is not None:
            self.stdout.write("")
            self.stdout.write(
                f"  {'mediana até o 1º link':<34} {mediana:>6.1f}h  "
                "<- acima de ~48h, o cadastro esfriou antes de virar compra"
            )

        if opcoes["por_semana"]:
            self.stdout.write("\nPor semana de cadastro")
            self.stdout.write("=" * 70)
            semana = inicio
            while semana < fim:
                proxima = min(semana + timedelta(days=7), fim)
                fatia = usuarios.filter(date_joined__gte=semana, date_joined__lt=proxima)
                self.stdout.write(f"\n{semana:%d/%m} a {(proxima - timedelta(days=1)):%d/%m}")
                self._bloco(fatia, opcoes["custo_por_cadastro"], fim_da_fatia=proxima)
                semana = proxima

        self.stdout.write(
            "\nRessalva: não existe campo de origem no User, então esta coorte é TODO "
            "mundo que se cadastrou na janela, não só quem veio do anúncio. Enquanto a "
            "campanha for a fonte dominante, serve como aproximação - se um dia houver "
            "duas fontes grandes ao mesmo tempo, o número deixa de separar as duas."
        )
