"""Comandos fixos no WhatsApp do Appfiliado: o assinante vincula o número dele no painel
(Configurações, "VINCULAR 123456") e pede por aqui os resultados, as metas, as vendas e os mais
vendidos. Sem IA: o texto é montado com os mesmos números do painel.

A Shopee só libera as vendas de um dia na manhã seguinte, então tudo vai até ontem. A exceção é a
comissão validada (comando "validada"): sai no mesmo dia. Como o pedido que valida hoje pode ter
sido comprado semanas atrás, o comando pede uma busca de 30 dias à Shopee (se a última tem mais de
ATUALIZACAO_RECENTE) e a resposta sai quando ela termina (servico.uma_volta -> respostas_prontas).
O comando "atualizar" faz o mesmo que o botão "Atualizar 30 dias" do painel e avisa quando termina.

Uma mensagem que não é comando (ou de quem não tem o número vinculado) segue para o agente de
vendas, como sempre."""

import re
import secrets
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CodigoVinculo, Conversa

VALIDADE_DO_CODIGO = timedelta(minutes=30)
COMANDOS_POR_DIA = 30  # por número: corta abuso e loop com outro robô
TENTATIVAS_DE_VINCULO_POR_DIA = 5  # chute de código
NUMEROS_POR_CONTA = 2
MAXIMO_VENDAS = 10
MAXIMO_TOP = 5
TAMANHO_DO_NOME = 60
ATUALIZACAO_RECENTE = timedelta(minutes=15)  # busca mais nova que isso: a validada responde na hora
ESPERA_PELA_SHOPEE = timedelta(minutes=5)  # sem a busca terminar, responde com o que tem
ACABOU_DE_ATUALIZAR = timedelta(minutes=2)  # "atualizar" logo depois de uma busca: não pede outra

AJUDA, RESULTADOS, METAS, VENDAS, TOP, VALIDADA, ATUALIZAR, VINCULAR, DESVINCULAR = (
    "ajuda", "resultados", "metas", "vendas", "top", "validada", "atualizar", "vincular", "desvincular")
# A mensagem inteira tem que ser o comando: "quero ver os resultados do bot" é conversa com o agente.
APELIDOS = {
    "ajuda": AJUDA, "menu": AJUDA, "comandos": AJUDA, "comando": AJUDA,
    "resultados": RESULTADOS, "resultado": RESULTADOS,
    "metas": METAS, "meta": METAS,
    "vendas": VENDAS, "venda": VENDAS, "pedidos": VENDAS,
    "top": TOP, "mais vendidos": TOP, "top 5": TOP, "top5": TOP,
    "validada": VALIDADA, "validadas": VALIDADA, "comissao validada": VALIDADA, "validada hoje": VALIDADA,
    "comissao": VALIDADA, "hoje": VALIDADA,
    "atualizar": ATUALIZAR, "atualiza": ATUALIZAR, "atualizacao": ATUALIZAR, "atualizar dados": ATUALIZAR,
    "sincronizar": ATUALIZAR,
    "vincular": VINCULAR,
    "desvincular": DESVINCULAR,
}
# Quem não vinculou e manda "ajuda" ou "menu" provavelmente quer falar com o agente.
SO_VINCULADOS = {AJUDA}
SO_EXPLICITOS = {"comandos", "comando"}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação e com espaços simples ("/Resultados!" -> "resultados")."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texto).split())


def identificar(texto: str) -> tuple[str, str] | None:
    """(comando, código do vínculo) ou None quando a mensagem não é comando."""
    limpo = normalizar(texto)
    vinculo = re.fullmatch(r"vincular ?(\d{6})", limpo)
    if vinculo:
        return VINCULAR, vinculo.group(1)
    comando = APELIDOS.get(limpo)
    return (comando, "") if comando else None


def tratar(conversa: Conversa, texto: str) -> str | None:
    """A resposta do comando; "" quando é comando mas não vale responder (passou do limite do dia);
    None quando não é comando (segue para o agente)."""
    achado = identificar(texto)
    if not achado:
        return None
    comando, codigo = achado
    if not conversa.conta_id and comando in SO_VINCULADOS and normalizar(texto) not in SO_EXPLICITOS:
        return None
    hoje = timezone.localdate()
    if conversa.dia_dos_comandos != hoje:
        conversa.dia_dos_comandos, conversa.comandos_no_dia, conversa.tentativas_vinculo = hoje, 0, 0
    conversa.comandos_no_dia += 1
    conversa.save(update_fields=["dia_dos_comandos", "comandos_no_dia", "tentativas_vinculo", "atualizada_em"])
    if conversa.comandos_no_dia > COMANDOS_POR_DIA + 1:
        return ""
    if conversa.comandos_no_dia == COMANDOS_POR_DIA + 1:
        return f"Você chegou ao limite de {COMANDOS_POR_DIA} comandos por hoje. Amanhã libera de novo 🙂"

    if comando == VINCULAR:
        return _vincular(conversa, codigo)
    if not conversa.conta_id:
        return _como_vincular()
    if comando == DESVINCULAR:
        conversa.conta, conversa.vinculada_em = None, None
        conversa.save(update_fields=["conta", "vinculada_em", "atualizada_em"])
        return ("Pronto, este número não está mais ligado à sua conta do Appfiliado. "
                f"Para ligar de novo, gere um código em Configurações no painel: {_url('painel_configuracoes')}#whatsapp")
    if comando == AJUDA:
        return ajuda(conversa.conta)
    impedimento = _impedimento(conversa.conta)
    if impedimento:
        return impedimento
    if comando == VALIDADA:
        return _pedir_validada(conversa)
    if comando == ATUALIZAR:
        return _pedir_atualizacao(conversa)
    return {RESULTADOS: resultados, METAS: metas, VENDAS: vendas, TOP: top}[comando](conversa.conta)


# --- Comissão validada de hoje -------------------------------------------------------------

def _pedir_validada(conversa: Conversa) -> str:
    """Responde na hora se a última busca na Shopee é recente; se não, pede uma e avisa que a
    resposta vem quando ela terminar."""
    from painel import resultados as res
    from painel.models import SincronizacaoResultados

    agora = timezone.now()
    estado = SincronizacaoResultados.objects.filter(conta=conversa.conta).first()
    if estado and estado.concluida_em and not estado.erro and not estado.aguardando \
            and agora - estado.concluida_em < ATUALIZACAO_RECENTE:
        return validada(conversa.conta)
    if not (estado and estado.aguardando):
        res.pedir_atualizacao(conversa.conta, curta=True)  # a curta já busca o que foi validado hoje
    _esperar(conversa, "validada_pedida_em", agora)
    return "Buscando a comissão validada de hoje na Shopee ⏳ Em até 1 minuto te mando aqui."


# --- Atualizar com a Shopee ----------------------------------------------------------------

def _pedir_atualizacao(conversa: Conversa) -> str:
    """O botão "Atualizar 30 dias" do painel, pelo WhatsApp: pede a busca e avisa quando termina."""
    from painel import resultados as res
    from painel.models import SincronizacaoResultados

    agora = timezone.now()
    estado = SincronizacaoResultados.objects.filter(conta=conversa.conta).first()
    if estado and estado.concluida_em and not estado.erro and not estado.aguardando \
            and agora - estado.concluida_em < ACABOU_DE_ATUALIZAR:
        return (f"Seus dados já estão atualizados com a Shopee (às {timezone.localtime(estado.concluida_em):%H:%M}). "
                + _o_que_mandar())
    if not (estado and estado.aguardando and not estado.pedido_curto):
        res.pedir_atualizacao(conversa.conta)
    _esperar(conversa, "atualizacao_pedida_em", agora)
    return "Atualizando seus dados com a Shopee ⏳ Te aviso aqui quando terminar (costuma levar até 1 minuto)."


def _o_que_mandar() -> str:
    return "Mande *resultados*, *vendas*, *top*, *metas* ou *validada* para ver os números."


def _resposta_da_atualizacao(conta, estado, terminou: bool) -> str:
    if not terminou:
        return ("A Shopee está demorando para responder. Quando a atualização terminar, os números novos aparecem "
                "nos comandos e no painel.")
    if estado.erro:
        return "Não consegui atualizar com a Shopee agora. Tente de novo em alguns minutos."
    return (f"✅ Pronto! Seus dados foram atualizados com a Shopee às {timezone.localtime(estado.concluida_em):%H:%M}. "
            + _o_que_mandar())


def _resposta_da_validada(conta, estado, terminou: bool) -> str:
    aviso = ""
    if not terminou or estado.erro:
        aviso = "A Shopee não respondeu agora, então esse é o número da última atualização."
    return validada(conta, aviso)


# Comandos que esperam a busca na Shopee terminar: (campo da conversa, quem monta a resposta).
ESPERAS = (("validada_pedida_em", _resposta_da_validada), ("atualizacao_pedida_em", _resposta_da_atualizacao))


def _esperar(conversa: Conversa, campo: str, agora) -> None:
    if not getattr(conversa, campo):
        setattr(conversa, campo, agora)
        conversa.save(update_fields=[campo, "atualizada_em"])


def respostas_prontas(agora=None) -> list[tuple[Conversa, str]]:
    """Conversas esperando a busca na Shopee (validada ou atualizar) que terminou, ou passou da espera:
    (conversa, resposta). Já limpa o pedido de cada uma."""
    from painel.models import SincronizacaoResultados

    agora = agora or timezone.now()
    prontas = []
    for campo, responder in ESPERAS:
        for conversa in Conversa.objects.filter(**{f"{campo}__isnull": False}).select_related("conta")[:20]:
            pedida = getattr(conversa, campo)
            estado = SincronizacaoResultados.objects.filter(conta_id=conversa.conta_id).first() if conversa.conta_id else None
            terminou = bool(estado and estado.iniciada_em and estado.iniciada_em >= pedida
                            and estado.concluida_em and estado.concluida_em >= estado.iniciada_em)
            if not terminou and agora - pedida < ESPERA_PELA_SHOPEE and conversa.conta_id:
                continue
            setattr(conversa, campo, None)
            conversa.save(update_fields=[campo, "atualizada_em"])
            if not conversa.conta_id:
                continue  # desvinculou enquanto esperava
            prontas.append((conversa, responder(conversa.conta, estado, terminou)))
    return prontas


# --- Vínculo -----------------------------------------------------------------------------

def gerar_codigo(conta) -> CodigoVinculo:
    """Código novo de 6 dígitos (troca o anterior da conta, se houver)."""
    agora = timezone.now()
    validos = set(CodigoVinculo.objects.filter(criado_em__gte=agora - VALIDADE_DO_CODIGO)
                  .exclude(conta=conta).values_list("codigo", flat=True))
    codigo = f"{secrets.randbelow(10**6):06d}"
    while codigo in validos:
        codigo = f"{secrets.randbelow(10**6):06d}"
    vinculo, _ = CodigoVinculo.objects.update_or_create(conta=conta, defaults={"codigo": codigo, "criado_em": agora})
    return vinculo


def codigo_valido(conta) -> CodigoVinculo | None:
    vinculo = CodigoVinculo.objects.filter(conta=conta).first()
    if vinculo and vinculo.criado_em >= timezone.now() - VALIDADE_DO_CODIGO:
        return vinculo
    return None


def desvincular(conta, conversa_id) -> int:
    if not str(conversa_id or "").isdigit():
        return 0
    return Conversa.objects.filter(conta=conta, pk=conversa_id).update(conta=None, vinculada_em=None)


def numeros_vinculados(conta) -> list[Conversa]:
    return list(Conversa.objects.filter(conta=conta).order_by("vinculada_em", "pk"))


def pode_vincular_outro(conta) -> bool:
    return Conversa.objects.filter(conta=conta).count() < NUMEROS_POR_CONTA


def numero_do_appfiliado() -> str:
    """Só os dígitos do WhatsApp do Appfiliado (o número do agente de vendas)."""
    from bot_whatsapp.models import ConexaoWhatsApp

    numero = ""
    if settings.ATENDIMENTO_CONTA_ID:
        numero = (ConexaoWhatsApp.objects.filter(conta_id=settings.ATENDIMENTO_CONTA_ID)
                  .values_list("numero", flat=True).first() or "")
    return re.sub(r"\D", "", numero or settings.APPFILIADO_WHATSAPP_SUPORTE or "")


def _vincular(conversa: Conversa, codigo: str) -> str:
    if not codigo:
        return _como_vincular()
    if conversa.tentativas_vinculo >= TENTATIVAS_DE_VINCULO_POR_DIA:
        return "Muitas tentativas de vincular hoje. Tente de novo amanhã com um código novo do painel."
    with transaction.atomic():
        vinculo = (CodigoVinculo.objects.select_for_update().select_related("conta")
                   .filter(codigo=codigo, criado_em__gte=timezone.now() - VALIDADE_DO_CODIGO).first())
        if not vinculo:
            conversa.tentativas_vinculo += 1
            conversa.save(update_fields=["tentativas_vinculo", "atualizada_em"])
            return ("Esse código não vale (errado ou vencido: cada código vale 30 minutos). "
                    f"Gere um novo em Configurações no painel: {_url('painel_configuracoes')}#whatsapp")
        conta = vinculo.conta
        if conversa.conta_id != conta.pk and \
                Conversa.objects.filter(conta=conta).exclude(pk=conversa.pk).count() >= NUMEROS_POR_CONTA:
            # O código continua valendo: dá para desvincular um número no painel e mandar de novo.
            return (f"Sua conta do Appfiliado já tem {NUMEROS_POR_CONTA} números vinculados, o máximo. Para vincular "
                    f"este, desvincule um deles em Configurações no painel: {_url('painel_configuracoes')}#whatsapp")
        conversa.conta, conversa.vinculada_em = conta, timezone.now()
        conversa.save(update_fields=["conta", "vinculada_em", "atualizada_em"])
        vinculo.delete()
    return f"Pronto! Este número está ligado à sua conta do Appfiliado ({conta.email}).\n\n" + ajuda(conta)


def _como_vincular() -> str:
    return ("Para ver seus resultados por aqui, vincule este número à sua conta do Appfiliado: no painel, "
            f"em Configurações, gere o código e mande aqui \"VINCULAR\" e o código. {_url('painel_configuracoes')}#whatsapp")


def _impedimento(conta) -> str:
    if not conta.modulos_liberados():
        return ("Sua assinatura do Appfiliado não está ativa, então os resultados ficam parados. "
                f"Veja o seu plano no painel: {_url('painel_plano')}")
    if not conta.shopee_validado_em:
        return ("Sua conta de afiliado da Shopee ainda não está conectada ao Appfiliado. "
                f"Conecte em Configurações: {_url('painel_configuracoes')}")
    return ""


# --- Respostas ---------------------------------------------------------------------------

def ajuda(conta) -> str:
    primeiro = (conta.nome or "").split(" ")[0]
    return (f"Oi{', ' + primeiro if primeiro else ''}! Aqui é a Lia, a assistente do Appfiliado. Comandos que eu entendo por aqui:\n\n"
            "*resultados*: ontem, últimos 7 dias e o mês\n"
            "*metas*: como está a meta do mês\n"
            "*vendas*: os produtos vendidos ontem\n"
            "*top*: os mais vendidos dos últimos 7 dias\n"
            "*validada*: a comissão validada de hoje\n"
            "*atualizar*: busca agora os dados mais novos na Shopee\n"
            "*desvincular*: tira este número da sua conta\n\n"
            "A Shopee libera as vendas de um dia na manhã seguinte, então os números vão até ontem. "
            "A exceção é a comissão validada, que sai no mesmo dia.")


def resultados(conta) -> str:
    from painel import resultados as res
    from painel import telas

    ontem = _ontem()
    semana = ontem - timedelta(days=6)
    inicio_mes = ontem.replace(day=1)
    blocos = [
        (f"*Ontem ({ontem:%d/%m})*", res.totais(conta, ontem, ontem)),
        (f"*Últimos 7 dias ({semana:%d/%m} a {ontem:%d/%m})*", res.totais(conta, semana, ontem)),
        (f"*{telas.nome_mes(ontem.year, ontem.month)} até ontem*", res.totais(conta, inicio_mes, ontem)),
    ]
    linhas = ["📊 *Seus resultados na Shopee*"]
    for titulo, t in blocos:
        linhas += ["", titulo, f"Pedidos: {_inteiro(t['pedidos'])}", f"Faturamento: {brl(t['faturamento'])}",
                   f"Comissão estimada: {brl(t['comissao_estimada'])}", f"Comissão validada: {brl(t['comissao_validada'])}"]
    return _fechar(conta, linhas, "painel_resultados")


def validada(conta, aviso: str = "") -> str:
    from painel import resultados as res
    from painel import telas

    hoje = timezone.localdate()
    ontem = hoje - timedelta(days=1)
    linhas = [f"✅ *Comissão validada hoje ({hoje:%d/%m})*",
              brl(res.totais(conta, hoje, hoje)["comissao_validada"]), "",
              f"Ontem ({ontem:%d/%m}): {brl(res.totais(conta, ontem, ontem)['comissao_validada'])}",
              f"{telas.nome_mes(hoje.year, hoje.month)} até agora: "
              f"{brl(res.totais(conta, hoje.replace(day=1), hoje)['comissao_validada'])}", "",
              "É o único número que a Shopee libera no mesmo dia: pedidos, faturamento e comissão estimada "
              "de hoje saem amanhã de manhã."]
    if aviso:
        linhas += ["", aviso]
    return _fechar(conta, linhas, "painel_resultados", aviso_de_ontem=False)


def _linhas_da_meta(situacao) -> list[str]:
    """Um mês da meta, na fase dele (painel.telas.situacao_meta)."""
    nome = situacao["nome_mes"]
    fecha = situacao["fecha_em"].strftime("%d/%m")
    if situacao["previa"]:
        linhas = [f"🟡 *{nome}: prévia* (fecha em {fecha})", f"Faturamento até ontem (estimado): {brl(situacao['faturamento'])}"]
    elif situacao["em_fechamento"]:
        linhas = [f"🔵 *{nome}: em fechamento até {fecha}*",
                  (f"Garantido (validado): {brl(situacao['validado'])} · pendente: {brl(situacao['pendente'])} · "
                   f"cancelado: {brl(situacao['cancelado'])}"),
                  situacao["frase_possivel"]]
    elif situacao["fechada"] and not situacao["sem_pedidos_guardados"]:
        linhas = [f"🟢 *{nome}: fechada*", f"Validado (final): {brl(situacao['faturamento'])}"]
    else:
        linhas = [f"*{nome}: {situacao['nome_fase'].lower()}*", f"Faturamento estimado: {brl(situacao['faturamento'])}"]
    for faixa in situacao["faixas_tela"]:
        bonus = (f", bônus de {situacao['gmv_percentual']:g}% do GMV" if situacao.get("modo_gmv")
                 else f", bônus de {brl(faixa['bonus'])}" if faixa.get("bonus") else "")
        estado = faixa["estado"]
        if estado == "batida":
            texto = "garantida" if situacao["em_fechamento"] else "batida na prévia" if situacao["previa"] else "batida"
            linhas.append(f"✅ {faixa['nome']} ({brl(faixa['faturamento'])}{bonus}): {texto}")
        elif estado == "possivel":
            linhas.append(f"🔷 {faixa['nome']} ({brl(faixa['faturamento'])}{bonus}): depende dos pendentes")
        elif estado == "fora":
            texto = "fora de alcance" if situacao["em_fechamento"] else f"ficou a {brl(faixa['falta'])}"
            linhas.append(f"⬜ {faixa['nome']} ({brl(faixa['faturamento'])}{bonus}): {texto}")
        else:
            linhas.append(f"⬜ {faixa['nome']} ({brl(faixa['faturamento'])}{bonus}): faltam {brl(faixa['falta'])}")
    if situacao["previa"]:
        if situacao["proxima"] and situacao["dias_restantes"] > 0:
            dias = situacao["dias_restantes"]
            quando = "no último dia do mês" if dias == 1 else f"nos {dias} dias que faltam"
            linhas.append(f"Para a próxima faixa: {brl(situacao['por_dia'])} por dia {quando}.")
        if situacao["dias_restantes"] > 0:
            projetada = f" ({situacao['nome_faixa_projetada']})" if situacao["nome_faixa_projetada"] else ""
            linhas.append(f"No ritmo atual, o mês fecha em {brl(situacao['projecao'])}{projetada}.")
        if situacao["bonus_garantido"] and not situacao.get("modo_gmv"):
            linhas.append(f"Bônus da faixa batida na prévia: {brl(situacao['bonus_garantido'])}")
    elif situacao["em_fechamento"] and situacao["faixa_em_jogo"]:
        linhas.append(f"Para garantir a faixa {situacao['faixa_em_jogo']['nome']}, faltam {brl(situacao['falta_validar'])} "
                      f"serem validados (dá para perder até {brl(situacao['pode_perder'])} em cancelamentos).")
    elif situacao["fechada"] and situacao["bonus_garantido"]:
        linhas.append(f"Bônus de {nome}: {brl(situacao['bonus_garantido'])}")
    return linhas


def metas(conta) -> str:
    """Os três meses da meta: o atual (prévia), o passado (em fechamento) e o retrasado (fechada). A meta
    de um mês só fecha no último dia do mês seguinte, contando só os pedidos validados."""
    from painel import telas

    hoje = _ontem() + timedelta(days=1)
    meses = telas.metas_dos_tres_meses(conta, hoje)
    if not meses:
        nome_mes = telas.nome_mes(hoje.year, hoje.month)
        return (f"Você ainda não cadastrou a meta de {nome_mes}. Cadastre em Metas no painel e peça de novo por aqui: "
                f"{_url('painel_metas')}")
    linhas = ["🎯 *Metas da Shopee*", ""]
    for situacao in meses:
        linhas += _linhas_da_meta(situacao) + [""]
    linhas.append("A meta de um mês fecha no último dia do mês seguinte e conta só os pedidos validados.")
    return _fechar(conta, linhas, "painel_metas")


def vendas(conta) -> str:
    from painel import resultados as res
    from painel.models import VendaItem

    ontem = _ontem()
    itens = list(res.vendas_do_periodo(conta, ontem, ontem).order_by("-comprado_em", "pedido_id", "posicao"))
    if not itens:
        return _fechar(conta, [f"🛒 Nenhuma venda em {ontem:%d/%m} (ontem)."], "painel_resultados", "?periodo=ontem")
    validos = [i for i in itens if i.situacao != VendaItem.CANCELADO]
    comissao = sum((i.comissao for i in validos), 0)
    linhas = [f"🛒 *Vendas de ontem ({ontem:%d/%m})*",
              f"{len(validos)} {'produto vendido' if len(validos) == 1 else 'produtos vendidos'}, "
              f"comissão de {brl(comissao)}", ""]
    for item in itens[:MAXIMO_VENDAS]:
        quando = timezone.localtime(item.comprado_em)
        qtd = f"{item.quantidade}x " if item.quantidade > 1 else ""
        cancelado = " ❌ cancelado" if item.situacao == VendaItem.CANCELADO else ""
        linhas.append(f"• {quando:%H:%M} {qtd}{_curto(item.nome)}: {brl(item.valor)}, comissão {brl(item.comissao)}{cancelado}")
    if len(itens) > MAXIMO_VENDAS:
        linhas.append(f"…e mais {len(itens) - MAXIMO_VENDAS}.")
    return _fechar(conta, linhas, "painel_resultados", "?periodo=ontem")


def top(conta) -> str:
    from painel import resultados as res

    ontem = _ontem()
    semana = ontem - timedelta(days=6)
    ranking = res.ranking_produtos(res.vendas_do_periodo(conta, semana, ontem), limite=MAXIMO_TOP)
    if not ranking:
        return _fechar(conta, [f"🏆 Nenhuma venda nos últimos 7 dias ({semana:%d/%m} a {ontem:%d/%m})."], "painel_resultados")
    linhas = [f"🏆 *Mais vendidos dos últimos 7 dias ({semana:%d/%m} a {ontem:%d/%m})*", ""]
    for posicao, linha in enumerate(ranking, start=1):
        unidades = linha["unidades"] or 0
        linhas.append(f"{posicao}. {_curto(linha['nome'])}: {unidades} {'unidade' if unidades == 1 else 'unidades'}, "
                      f"comissão {brl(linha['comissao'] or 0)}")
    return _fechar(conta, linhas, "painel_resultados")


# --- Apoio -------------------------------------------------------------------------------

def brl(valor) -> str:
    texto = f"{float(valor or 0):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def _inteiro(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def _ontem():
    return timezone.localdate() - timedelta(days=1)


def _curto(nome: str) -> str:
    nome = " ".join((nome or "Produto").split())
    return nome if len(nome) <= TAMANHO_DO_NOME else nome[:TAMANHO_DO_NOME - 1].rstrip() + "…"


def _url(nome: str) -> str:
    from painel.emails import url_do_painel

    return url_do_painel(nome)


def _fechar(conta, linhas: list[str], tela: str, sufixo: str = "", aviso_de_ontem: bool = True) -> str:
    """Rodapé: quando os números foram buscados na Shopee, aviso de ontem ainda zerado e o link."""
    from painel import relatorio
    from painel.models import SincronizacaoResultados

    agora = timezone.localtime()
    rodape = []
    if aviso_de_ontem and agora.hour < 12 and not relatorio.numeros_de_ontem_sairam(conta, agora.date()):
        rodape.append("Ontem ainda aparece zerado? A Shopee costuma liberar as vendas do dia anterior entre 7h e 8h.")
    estado = SincronizacaoResultados.objects.filter(conta=conta).first()
    if estado and estado.concluida_em:
        quando = timezone.localtime(estado.concluida_em)
        rodape.append(f"Atualizado {'às' if quando.date() == agora.date() else f'em {quando:%d/%m} às'} {quando:%H:%M}.")
    rodape.append(f"Mais detalhes no painel: {_url(tela)}{sufixo}")
    return "\n".join(linhas + [""] + rodape)
