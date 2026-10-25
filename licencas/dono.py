"""Painel do dono do Appfiliado (página no admin e resumo semanal por e-mail): receita
recorrente, assinantes, entradas e saídas, uso do produto e o que precisa de atenção.

Receita recorrente mensal = soma das assinaturas que valem hoje (ativas ou em teste), com a
anual dividida por 12. Cortesias não entram. O histórico de meses usa a data de criação e a de
encerramento de cada assinatura (com o valor atual dela)."""

from collections import OrderedDict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import Assinatura, ContaAppfiliado, EventoWebhookZouti, ProdutoZouti, ResumoSemanalDono

SEM_USO_APOS = timedelta(days=7)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ZERO = Decimal("0.00")
# Fora da receita e das contas de assinantes: a que nunca foi paga e a que está com o pagamento
# atrasado (sem acesso agora). Assim o mês atual do histórico bate com o cartão de receita.
FORA_DA_CONTA = [Assinatura.STATUS_INCOMPLETA, Assinatura.STATUS_ATRASADA]


def _soma_mensal(assinaturas) -> Decimal:
    return sum((a.valor_mensal or ZERO for a in assinaturas), ZERO)


def ativas(quando=None):
    """Assinaturas que valiam no momento `quando` (None = agora, pelo status atual)."""
    base = Assinatura.objects.select_related("conta")
    if quando is None:
        return list(base.filter(status__in=Assinatura.STATUS_QUE_LIBERAM))
    return [a for a in base.filter(criada_em__lte=quando).exclude(status__in=FORA_DA_CONTA)
            if not a.encerrada_em or a.encerrada_em > quando]


def _nome_do_produto(assinatura, nomes: dict) -> str:
    ids = assinatura.lista_product_ids()
    return " + ".join(nomes.get(i, "Produto não cadastrado") for i in ids) or (assinatura.plano or "Sem produto")


def _inicio_do_mes(dia: date) -> datetime:
    return timezone.make_aware(datetime(dia.year, dia.month, 1))


def evolucao(agora, meses: int = 12) -> list[dict]:
    hoje = timezone.localtime(agora).date()
    linhas = []
    todas = list(Assinatura.objects.exclude(status__in=FORA_DA_CONTA))
    for voltar in range(meses - 1, -1, -1):
        ano, mes = hoje.year, hoje.month - voltar
        while mes < 1:
            ano, mes = ano - 1, mes + 12
        inicio = _inicio_do_mes(date(ano, mes, 1))
        proximo = _inicio_do_mes(date(ano + (mes == 12), mes % 12 + 1, 1))
        fim = min(proximo, agora)
        valendo = [a for a in todas if a.criada_em <= fim and (not a.encerrada_em or a.encerrada_em > fim)]
        linhas.append({
            "mes": f"{MESES[mes - 1]}/{str(ano)[2:]}", "assinaturas": len(valendo),
            "contas": len({a.conta_id for a in valendo}), "receita": _soma_mensal(valendo),
            "novas": sum(1 for a in todas if inicio <= a.criada_em < proximo),
            "saidas": sum(1 for a in todas if a.encerrada_em and inicio <= a.encerrada_em < proximo),
        })
    maior = max((l["receita"] for l in linhas), default=ZERO) or Decimal(1)
    for linha in linhas:
        linha["altura"] = int(linha["receita"] / maior * 100)
    return linhas


def entradas_e_saidas(inicio, fim) -> dict:
    nomes = dict(ProdutoZouti.objects.values_list("zouti_product_id", "nome"))
    novas = (Assinatura.objects.filter(criada_em__gte=inicio, criada_em__lt=fim)
             .exclude(status=Assinatura.STATUS_INCOMPLETA).select_related("conta").order_by("criada_em"))
    saidas = (Assinatura.objects.filter(encerrada_em__gte=inicio, encerrada_em__lt=fim)
              .select_related("conta").order_by("encerrada_em"))
    item = lambda a: {"a": a, "produto": _nome_do_produto(a, nomes)}  # noqa: E731
    return {
        "novas": [item(a) for a in novas],
        "saidas": [{**item(a), "tipo": a.get_status_display()} for a in saidas],
        "canceladas": sum(1 for a in saidas if a.status == Assinatura.STATUS_CANCELADA),
        "reembolsadas": sum(1 for a in saidas if a.status == Assinatura.STATUS_REEMBOLSADA),
        "chargebacks": sum(1 for a in saidas if a.status == Assinatura.STATUS_CHARGEBACK),
    }


def por_produto(lista) -> list[dict]:
    nomes = dict(ProdutoZouti.objects.values_list("zouti_product_id", "nome"))
    grupos: dict[str, dict] = OrderedDict()
    for a in lista:
        nome = _nome_do_produto(a, nomes)
        g = grupos.setdefault(nome, {"produto": nome, "ativas": 0, "mensais": 0, "anuais": 0, "outras": 0,
                                     "receita": ZERO})
        g["ativas"] += 1
        ciclo = a.meses_por_ciclo or 1
        g["mensais" if ciclo == 1 else "anuais" if ciclo == 12 else "outras"] += 1
        g["receita"] += a.valor_mensal or ZERO
    return sorted(grupos.values(), key=lambda g: g["receita"], reverse=True)


def uso(agora, lista) -> dict:
    from bot_whatsapp.avisos_de_queda import esta_parado
    from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas
    from painel import primeiros_passos

    contas = {a.conta_id: a.conta for a in lista}
    parados = [c for c in ConexaoWhatsApp.objects.filter(parado_desde__isnull=False).select_related("conta")
               if esta_parado(c, agora)]
    pela_metade = []
    for conta in contas.values():
        faltam = primeiros_passos.pendentes(primeiros_passos.passos(conta))
        if faltam:
            pela_metade.append({"conta": conta, "faltam": [p["titulo"] for p in faltam]})
    sem_uso = []
    for conta in contas.values():
        ultimo = conta.ultimo_acesso_em or conta.ultimo_login
        if (ultimo or conta.criada_em) < agora - SEM_USO_APOS:
            sem_uso.append({"conta": conta, "ultimo": ultimo})
    sem_uso.sort(key=lambda s: s["ultimo"] or timezone.make_aware(datetime(2000, 1, 1)))
    return {
        "bots_ligados": ConfiguracaoOfertas.objects.filter(ativo=True).count(),
        "bots_conectados": ConexaoWhatsApp.objects.filter(estado=ConexaoWhatsApp.CONECTADO).count(),
        "parados": sorted(parados, key=lambda c: c.parado_desde),
        "pela_metade": pela_metade,
        "sem_uso": sem_uso,
    }


def atencao(agora) -> dict:
    from atendimento.models import Conversa
    from bot_whatsapp.models import ConfiguracaoOfertas
    from notas.models import NotaFiscal
    from painel.models import Sugestao

    desde = agora - timedelta(days=30)
    return {
        "atrasadas": list(Assinatura.objects.filter(status=Assinatura.STATUS_ATRASADA).select_related("conta")),
        "notas_recusadas": list(NotaFiscal.objects.filter(situacao=NotaFiscal.RECUSADA, criada_em__gte=desde)
                                .select_related("empresa__conta").order_by("-criada_em")[:30]),
        "bots_com_erro": list(ConfiguracaoOfertas.objects.filter(ativo=True).exclude(ultimo_erro="")
                              .select_related("conta")),
        "webhooks_com_falha": list(EventoWebhookZouti.objects.filter(
            assinatura_valida=True, processado_com_sucesso=False, recebido_em__gte=desde)[:30]),
        "conversas": list(Conversa.objects.filter(estado=Conversa.HUMANO).order_by("-ultima_recebida_em")[:30]),
        "sugestoes": list(Sugestao.objects.filter(situacao=Sugestao.NOVA_SITUACAO).select_related("conta")[:30]),
    }


def numeros(agora=None) -> dict:
    agora = agora or timezone.now()
    hoje = timezone.localtime(agora).date()
    lista = ativas()
    mes = entradas_e_saidas(_inicio_do_mes(hoje), agora + timedelta(seconds=1))
    receita = _soma_mensal(lista)
    contas = len({a.conta_id for a in lista})
    return {
        "agora": agora,
        "receita": receita,
        "contas": contas,
        "assinaturas": len(lista),
        "ticket": (receita / contas).quantize(ZERO) if contas else ZERO,
        "sem_valor": sum(1 for a in lista if a.valor is None),
        "mes": mes,
        "evolucao": evolucao(agora),
        "por_produto": por_produto(lista),
        "uso": uso(agora, lista),
        "atencao": atencao(agora),
    }


# --- Resumo semanal por e-mail (domingo às 9h, da semana de domingo a sábado) -------------

HORA_DO_RESUMO = 9


def _brl(valor) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def semana_anterior(agora) -> tuple[date, date]:
    """(domingo, sábado) da semana que terminou antes de `agora`."""
    hoje = timezone.localtime(agora).date()
    domingo_desta = hoje - timedelta(days=(hoje.weekday() + 1) % 7)
    return domingo_desta - timedelta(days=7), domingo_desta - timedelta(days=1)


def montar_resumo(agora) -> tuple[str, str]:
    domingo, sabado = semana_anterior(agora)
    inicio = timezone.make_aware(datetime.combine(domingo, datetime.min.time()))
    fim = inicio + timedelta(days=7)
    n = numeros(agora)
    # Receita no fim da semana comparada com o começo dela (as duas pelo histórico).
    receita_antes, receita_fim = _soma_mensal(ativas(inicio)), _soma_mensal(ativas(min(fim, agora)))
    semana = entradas_e_saidas(inicio, fim)
    variacao = receita_fim - receita_antes
    sinal = "+" if variacao >= 0 else "−"
    linhas = [
        "Resumo da semana do Appfiliado",
        f"{domingo:%d/%m} (domingo) a {sabado:%d/%m} (sábado)",
        "",
        f"Receita recorrente mensal no fim da semana: {_brl(receita_fim)} ({sinal}{_brl(abs(variacao))} na semana)",
        f"Hoje: {_brl(n['receita'])} · {n['contas']} assinante(s) ativo(s), {n['assinaturas']} assinatura(s)",
        "",
        f"Novas assinaturas na semana: {len(semana['novas'])}",
    ]
    for item in semana["novas"]:
        a = item["a"]
        ciclo = "/ano" if (a.meses_por_ciclo or 1) == 12 else "/mês"
        linhas.append(f"  • {a.conta.email} · {item['produto']}" + (f" · {_brl(a.valor)}{ciclo}" if a.valor else ""))
    linhas.append(f"Saídas na semana: {len(semana['saidas'])} ({semana['canceladas']} cancelada(s), "
                  f"{semana['reembolsadas']} reembolsada(s), {semana['chargebacks']} chargeback(s))")
    for item in semana["saidas"]:
        linhas.append(f"  • {item['a'].conta.email} · {item['produto']} · {item['tipo']}")
    uso_, atencao_ = n["uso"], n["atencao"]
    linhas += [
        "",
        "Agora:",
        f"  • Bots ligados: {uso_['bots_ligados']} · conectados: {uso_['bots_conectados']} · parados: {len(uso_['parados'])}",
        f"  • Sem entrar no painel há 7 dias ou mais: {len(uso_['sem_uso'])}",
        f"  • Configuração pela metade: {len(uso_['pela_metade'])}",
        f"  • Pagamentos atrasados: {len(atencao_['atrasadas'])}",
        f"  • Notas recusadas (30 dias): {len(atencao_['notas_recusadas'])}",
        f"  • Bots com erro: {len(atencao_['bots_com_erro'])}",
        f"  • Avisos da Zouti com falha (30 dias): {len(atencao_['webhooks_com_falha'])}",
        f"  • Conversas do agente esperando você: {len(atencao_['conversas'])}",
        f"  • Sugestões novas dos afiliados: {len(atencao_['sugestoes'])}",
        "",
        f"Painel completo: {settings.APPFILIADO_ADMIN_URL.rstrip('/')}/licencas/contaappfiliado/painel-do-dono/",
    ]
    assunto = f"Appfiliado: resumo da semana de {domingo:%d/%m} a {sabado:%d/%m}"
    return assunto, "\n".join(linhas)


def enviar_resumo_semanal(agora=None) -> list[str]:
    """Chamado pelo worker a cada volta: no domingo, a partir das 9h, manda o da semana anterior
    (uma vez só; se o worker estava fora às 9h, manda assim que voltar, ainda no domingo)."""
    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    destino = settings.APPFILIADO_EMAIL_SUPORTE
    if not destino or local.weekday() != 6 or local.hour < HORA_DO_RESUMO:
        return []
    domingo, _ = semana_anterior(agora)
    _, criado = ResumoSemanalDono.objects.get_or_create(semana=domingo)
    if not criado:
        return []
    assunto, corpo = montar_resumo(agora)
    try:
        EmailMessage(subject=assunto, body=corpo, to=[destino], from_email=settings.APPFILIADO_EMAIL_REMETENTE).send()
    except Exception:  # noqa: BLE001
        ResumoSemanalDono.objects.filter(semana=domingo).delete()  # tenta de novo na próxima volta
        raise
    return [f"Resumo semanal do dono enviado para {destino} (semana de {domingo:%d/%m})."]
