import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from datetime import date, timedelta
from urllib.parse import quote

from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from accounts.ratelimit import _incrementar_contador, _obter_ip
from atendimento import comandos as comandos_whatsapp
from bot_whatsapp import campanhas
from bot_whatsapp.models import AlertaDisparado, ConexaoWhatsApp
from licencas import api_shopee
from licencas.models import (
    INCLUI, MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM, MODULO_INSTAGRAM, MODULO_INSTAGRAM_PREMIUM, MODULO_VIDEOS,
    MODULO_WHATSAPP, MODULOS, ContaAppfiliado,
)
from licencas.services import resposta_validacao

from . import cripto
from . import modulos as mod
from . import exportar, periodos, primeiros_passos, relatorio, resultados, telas
from .models import MetaMensal, RegraSubId, RelatorioEmail
from .autenticacao import (
    conta_logada,
    conta_requerida,
    destino_seguro,
    fazer_login,
    fazer_logout,
    login_bloqueado,
    registrar_falha_login,
    token_senha,
)
from .emails import enviar_email_recuperar_senha
from .forms import (
    EntrarForm, EsqueciSenhaForm, NovaSenhaForm, RegraSubIdForm, RelatorioEmailForm, ShopeeForm, TrocarSenhaForm,
)
from .shopee import testar_credenciais

NOMES_MODULOS = dict(MODULOS)
MAXIMO_REGRAS_SUB_ID = 20
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

logger = logging.getLogger(__name__)


def _contexto(request, ativo: str, **extra) -> dict:
    conta = conta_logada(request)
    liberados = conta.modulos_liberados() if conta else []
    return {
        "conta": conta,
        "menu": mod.menu(liberados, ativo, conta),
        "modulos_liberados": liberados,
        "url_planos": settings.APPFILIADO_URL_PLANOS,
        "icones": mod.ICONES,
        "aviso_relatorio": relatorio.aviso_da_tela(conta) if conta and ativo in TELAS_COM_AVISO_DO_RELATORIO else None,
        "bot_parado": _bot_parado(conta, liberados),
        **extra,
    }


def _bot_parado(conta, liberados) -> str:
    """Faixa vermelha no topo do painel quando o WhatsApp parou sem a pessoa pedir: o motivo
    ("deslogou" ou "caiu") ou "" (ver bot_whatsapp/avisos_de_queda.py)."""
    from bot_whatsapp.avisos_de_queda import esta_parado

    if not conta or MODULO_WHATSAPP not in liberados:
        return ""
    conexao = ConexaoWhatsApp.objects.filter(conta=conta).first()
    return conexao.parado_motivo if esta_parado(conexao) else ""


TELAS_COM_AVISO_DO_RELATORIO = {"inicio", "resultados", "configuracoes"}


def _hoje_por_extenso() -> str:
    hoje = timezone.localdate()
    return f"{DIAS_SEMANA[hoje.weekday()].capitalize()}, {hoje.day} de {MESES[hoje.month - 1]}"


# --- Entrar / sair / senha ---------------------------------------------------------

def entrar(request):
    if conta_logada(request):
        return redirect("painel_inicio")
    form = EntrarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ip = _obter_ip(request)
        email = form.cleaned_data["email"].strip().lower()
        if login_bloqueado(ip, email):
            form.add_error(None, "Muitas tentativas. Espere 15 minutos ou use \"Esqueci minha senha\".")
        else:
            conta = ContaAppfiliado.objects.filter(email__iexact=email).first()
            if conta and conta.tem_senha and conta.confere_senha(form.cleaned_data["senha"]):
                fazer_login(request, conta)
                return redirect(destino_seguro(request, request.GET.get("proximo", "")))
            if not (conta and conta.tem_senha):
                make_password(form.cleaned_data["senha"])  # mesmo tempo de resposta: não revela se a conta existe
            registrar_falha_login(ip, email)
            # Mesma mensagem com ou sem conta (e com ou sem senha criada): não dá para
            # descobrir quem é cliente testando e-mails.
            form.add_error(None, "E-mail ou senha incorretos. Se ainda não criou sua senha, use "
                                 "\"Criar ou recuperar senha\" abaixo.")
    return render(request, "painel/entrar.html", {"form": form})


@require_POST
@conta_requerida
def ocultar_passos(request):
    """Botões do cartão "Primeiros passos": adiar por 12 horas ou esconder de vez."""
    conta = conta_logada(request)
    if request.POST.get("acao") == "nunca":
        conta.passos_ocultos = True
    else:
        conta.passos_adiados_ate = timezone.now() + primeiros_passos.ADIAR_POR
    conta.save(update_fields=["passos_ocultos", "passos_adiados_ate"])
    return redirect("painel_inicio")


@require_POST
def sair(request):
    fazer_logout(request)
    return redirect("painel_entrar")


def esqueci_senha(request):
    form = EsqueciSenhaForm(request.POST or None)
    enviado = False
    if request.method == "POST" and form.is_valid():
        if _incrementar_contador(f"painel_esqueci:{_obter_ip(request)}", 3600) <= 5:
            conta = ContaAppfiliado.objects.filter(email__iexact=form.cleaned_data["email"].strip()).first()
            if conta:
                enviar_email_recuperar_senha(conta)
        # Mesma resposta exista ou não a conta - não dá para descobrir quem é cliente.
        enviado = True
    return render(request, "painel/esqueci_senha.html", {"form": form, "enviado": enviado})


def definir_senha(request, uidb64, token):
    try:
        conta = ContaAppfiliado.objects.filter(pk=int(force_str(urlsafe_base64_decode(uidb64)))).first()
    except (TypeError, ValueError, OverflowError):
        conta = None
    if not conta or not token_senha.check_token(conta, token):
        return render(request, "painel/definir_senha.html", {"link_invalido": True}, status=400)

    form = NovaSenhaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        conta.definir_senha(form.cleaned_data["senha"])
        conta.save(update_fields=["senha", "atualizada_em"])
        fazer_login(request, conta)
        messages.success(request, "Senha criada. Bem-vindo ao seu painel!")
        return redirect("painel_inicio")
    return render(request, "painel/definir_senha.html", {"form": form, "conta": conta})


# --- Páginas do painel ---------------------------------------------------------------

@conta_requerida
def inicio(request):
    conta = conta_logada(request)
    liberados = conta.modulos_liberados()
    hoje = telas.hoje()
    # No dia 1º o mês novo ainda não tem números (a Shopee libera o dia só no dia seguinte):
    # a página mostra o mês que acabou de fechar. A partir do dia 2, o mês atual.
    mes_fechado = hoje.day == 1
    fim_mes = hoje - timedelta(days=1) if mes_fechado else hoje
    inicio_mes = fim_mes.replace(day=1)

    cartoes_modulos = [item for item in mod.menu(liberados, "", conta) if item["modulo"]]
    # O mesmo checklist dos e-mails de primeiros passos (a senha já foi criada: a pessoa entrou).
    passos = [p for p in primeiros_passos.passos(conta, liberados) if p["chave"] != "senha"]
    contexto = {
        "hoje": _hoje_por_extenso(),
        "passos": passos,
        "passos_pendentes": bool(primeiros_passos.pendentes(passos)) and primeiros_passos.cartao_visivel(conta),
        "cartoes_modulos": cartoes_modulos,
        "primeiro_nome": (conta.nome or "").split(" ")[0],
        "shopee_conectada": bool(conta.shopee_validado_em),
        "sincronizacao": telas.estado_sincronizacao(conta),
        "nome_mes": telas.nome_mes(fim_mes.year, fim_mes.month),
        "mes_fechado": mes_fechado,
        "aviso_campanha": campanhas.aviso_da_inicio(conta, hoje) if MODULO_WHATSAPP in liberados else None,
        "alertas_novos": (AlertaDisparado.objects.filter(conta=conta, visto=False).count()
                          if MODULO_WHATSAPP in liberados else 0),
    }
    if conta.shopee_validado_em:
        mes = resultados.totais(conta, inicio_mes, fim_mes)
        do_dia = resultados.totais(conta, hoje, hoje)
        ontem = hoje - timedelta(days=1)
        contexto.update({
            "mes": mes,
            "do_dia": do_dia,
            "ontem": ontem,
            "do_ontem": resultados.totais(conta, ontem, ontem),
            "meta": telas.situacao_meta(conta, fim_mes.year, fim_mes.month, hoje),
            # Os outros meses com meta (em fechamento e fechada), em linhas curtas embaixo do cartão.
            "outros_meses": [m for m in telas.metas_dos_tres_meses(conta, hoje)
                             if m["mes_valor"] != f"{fim_mes.year}-{fim_mes.month:02d}"],
        })
    return render(request, "painel/inicio.html", _contexto(request, "inicio", **contexto))


@conta_requerida
def resultados_view(request):
    conta = conta_logada(request)
    hoje = telas.hoje()
    periodo = telas.periodo_da_requisicao(request.GET, hoje)
    contexto = {
        "periodo": periodo,
        "presets": periodos.PRESETS,
        "agrupamentos": periodos.AGRUPAMENTOS,
        "metricas": telas.METRICAS,
        "nome_metrica": telas.NOMES_METRICAS[periodo["metrica"]],
        "shopee_conectada": bool(conta.shopee_validado_em),
        "sincronizacao": telas.estado_sincronizacao(conta),
    }
    if conta.shopee_validado_em:
        linhas = resultados.serie(conta, periodo["inicio"], periodo["fim"], periodo["agrupar"])
        mesmo_mes = (periodo["inicio"].year, periodo["inicio"].month) == (periodo["fim"].year, periodo["fim"].month)
        contexto.update({
            "totais": resultados.totais(conta, periodo["inicio"], periodo["fim"]),
            "inclui_hoje": periodo["fim"] >= hoje,
            "linhas": list(reversed(linhas)),
            "grafico": telas.barras(linhas, periodo["metrica"]),
            "sub_ids": resultados.por_sub_id(conta, periodo["inicio"], periodo["fim"]),
            "meta": telas.situacao_meta(conta, periodo["fim"].year, periodo["fim"].month, hoje) if mesmo_mes else None,
        })
        celular = request.COOKIES.get(resultados.COOKIE_TELA) == "celular"
        contexto.update(_vendas_da_tela(conta, periodo, request.GET, celular))
    return render(request, "painel/resultados.html", _contexto(request, "resultados", **contexto))


def _vendas_da_tela(conta, periodo, parametros, celular=False) -> dict:
    """Produtos mais vendidos e a lista de vendas do período (20 por página; 10 no celular)."""
    filtradas = resultados.filtrar_vendas(conta, periodo["inicio"], periodo["fim"], parametros)
    por_pagina = resultados.VENDAS_POR_PAGINA_CELULAR if celular else resultados.VENDAS_POR_PAGINA
    pagina = Paginator(filtradas["vendas"], por_pagina).get_page(parametros.get("pagina"))
    nome_do_grupo = filtradas["nome_do_grupo"]
    for venda in pagina:
        venda.grupo = nome_do_grupo(venda.sub_id)
    return {
        "ranking": resultados.ranking_produtos(resultados.vendas_do_periodo(conta, periodo["inicio"], periodo["fim"])),
        "pagina_vendas": pagina,
        "paginas_vendas": pagina.paginator.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1),
        "grupos_vendas": filtradas["grupos"],
        "tela_vendas": "celular" if celular else "computador",
        "filtros_vendas": filtradas["filtros"],
        "situacoes_vendas": resultados.FILTROS_SITUACAO,
        "tem_vendas_guardadas": resultados.VendaItem.objects.filter(conta=conta).exists(),
        # o formulário dos filtros das vendas mantém o período escolhido no topo
        "parametros_periodo": [(c, parametros[c]) for c in ("periodo", "de", "ate", "agrupar", "metrica") if parametros.get(c)],
    }


@conta_requerida
def exportar_vendas(request):
    """Excel com todas as vendas do período (com os filtros da tela) e os produtos."""
    conta = conta_logada(request)
    if not conta.shopee_validado_em:
        return redirect("painel_resultados")
    periodo = telas.periodo_da_requisicao(request.GET, telas.hoje())
    filtradas = resultados.filtrar_vendas(conta, periodo["inicio"], periodo["fim"], request.GET)
    conteudo = exportar.planilha_de_vendas(
        filtradas["vendas"], resultados.ranking_produtos(filtradas["vendas"], limite=None), filtradas["nome_do_grupo"],
    )
    nome = f"vendas-shopee-{periodo['inicio']:%Y-%m-%d}-a-{periodo['fim']:%Y-%m-%d}.xlsx"
    resposta = HttpResponse(
        conteudo, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta


@require_POST
@conta_requerida
def atualizar_resultados(request):
    conta = conta_logada(request)
    if conta.shopee_validado_em:
        estado = telas.estado_sincronizacao(conta)
        curta = request.POST.get("periodo") == "curto"
        recente = estado and estado.pedido_em and timezone.now() - estado.pedido_em < timedelta(minutes=2)
        # Pedido recente igual (ou um de 30 dias, que já cobre o curto): não pede de novo.
        if not recente or (not curta and estado.pedido_curto and estado.aguardando):
            resultados.pedir_atualizacao(conta, curta=curta)
        messages.info(request, ("Pedimos à Shopee os pedidos de ontem e o que foi validado ontem e hoje." if curta else
                                "Pedimos os números dos últimos 30 dias à Shopee.") + " Em até 1 minuto eles aparecem aqui.")
    return redirect(destino_seguro(request, request.POST.get("voltar", "")))


@conta_requerida
def estado_resultados(request):
    """A tela com "Atualizando com a Shopee…" pergunta aqui, de tempos em tempos, se
    a busca terminou - e se recarrega sozinha quando terminar."""
    conta = conta_logada(request)
    estado = telas.estado_sincronizacao(conta)
    atualizando = bool(conta.shopee_validado_em) and (not estado or estado.atualizando)
    return JsonResponse({"atualizando": atualizando})


def _linhas_da_conferencia(ao_vivo: dict, nome_mes: str) -> list[dict]:
    """As linhas da tabela "Direto na Shopee" (resultados.conferencia_na_shopee)."""
    if "erro" in ao_vivo:
        return [{"rotulo": "Busca na Shopee", "erro": ao_vivo["erro"]}]
    linhas = []
    compra, validacao = ao_vivo["por_compra"], ao_vivo["por_validacao"]
    if "erro" in compra:
        linhas.append({"rotulo": f"Feitos em {nome_mes}", "erro": compra["erro"]})
    else:
        linhas.append({"rotulo": f"Feitos em {nome_mes} e validados", "destaque": True, "r": compra["validados"],
                       "detalhe": "é o jeito do e-mail de meta mensal da Shopee", "incompleto": compra["incompleto"]})
        if len(compra["canais"]) > 1 or (compra["canais"] and compra["canais"][0][0] != "sem canal informado"):
            linhas += [{"rotulo": f"canal: {canal}", "sub": True, "r": r} for canal, r in compra["canais"]]
        linhas.append({"rotulo": f"Feitos em {nome_mes}, ainda pendentes", "r": compra["pendentes"]})
        linhas.append({"rotulo": f"Feitos em {nome_mes}, cancelados", "r": compra["cancelados"], "detalhe": "fora das contas"})
        linhas.append({"rotulo": f"Feitos em {nome_mes}, sem os cancelados", "r": compra["total"], "detalhe": "validados + pendentes"})
    if "erro" in validacao:
        linhas.append({"rotulo": f"Validados em {nome_mes}", "erro": validacao["erro"]})
    else:
        detalhe = "comprados em qualquer data"
        if validacao["compra_mais_antiga"]:
            detalhe += f"; compra mais antiga: {validacao['compra_mais_antiga']:%d/%m/%Y}"
        linhas.append({"rotulo": f"Validados em {nome_mes}", "r": validacao["total"], "detalhe": detalhe,
                       "incompleto": validacao["incompleto"]})
    return linhas


@conta_requerida
def conferir_faturamento(request):
    """Página escondida: o faturamento de um mês contado de três jeitos, para conferir com a Shopee.
    Só para contas com a chave beta_conferir_faturamento (admin); as outras recebem 404."""
    conta = conta_logada(request)
    if not conta.beta_conferir_faturamento:
        raise Http404
    hoje = telas.hoje()
    passado = (hoje.replace(day=1) - timedelta(days=1))
    escolhido = str(request.GET.get("mes") or f"{passado.year}-{passado.month:02d}")
    try:
        ano, mes = (int(x) for x in escolhido.split("-"))
        date(ano, mes, 1)
    except (ValueError, TypeError):
        ano, mes = passado.year, passado.month
    meses = []
    d = hoje.replace(day=1)
    for _ in range(4):
        d = (d - timedelta(days=1)).replace(day=1)
        meses.append({"valor": f"{d.year}-{d.month:02d}", "nome": telas.nome_mes(d.year, d.month), "ativo": (d.year, d.month) == (ano, mes)})
    c = telas.conferencia_faturamento(conta, ano, mes)
    ao_vivo = resultados.conferencia_na_shopee(conta, c["inicio"], c["fim"]) if request.GET.get("shopee") else None
    linhas = _linhas_da_conferencia(ao_vivo, c["nome_mes"]) if ao_vivo else []
    return render(request, "painel/conferir_faturamento.html", _contexto(
        request, "resultados", c=c, meses=meses, ao_vivo=ao_vivo, linhas_ao_vivo=linhas, mes_escolhido=f"{ano}-{mes:02d}"))


@conta_requerida
def metas_view(request):
    conta = conta_logada(request)
    hoje = telas.hoje()
    opcoes = telas.meses_para_metas(hoje)
    escolhido = request.GET.get("mes") or request.POST.get("mes") or f"{hoje.year}-{hoje.month:02d}"
    ano_mes = next(((a, m) for a, m in opcoes if f"{a}-{m:02d}" == escolhido), (hoje.year, hoje.month))
    ano, mes = ano_mes

    if request.method == "POST":
        gmv = request.POST.get("tipo") == "gmv"
        faixas = telas.faixa_em_gmv_do_formulario(request.POST) if gmv else telas.faixas_do_formulario(request.POST)
        if faixas:
            MetaMensal.objects.update_or_create(conta=conta, ano=ano, mes=mes, defaults={"faixas": faixas})
            messages.success(request, f"Metas de {telas.nome_mes(ano, mes)} salvas.")
        else:
            MetaMensal.objects.filter(conta=conta, ano=ano, mes=mes).delete()
            messages.info(request, f"Metas de {telas.nome_mes(ano, mes)} apagadas.")
        return redirect(f"{request.path}?mes={ano}-{mes:02d}")

    faixas = telas.faixas_do_mes(conta, ano, mes)
    padrao = [100, 125, 150]
    linhas = []
    for i in range(3):
        faixa = faixas[i] if i < len(faixas) else {}
        linhas.append({
            "n": i + 1,
            "percentual": faixa.get("percentual") or padrao[i],
            "faturamento": faixa.get("faturamento"),
            "bonus": faixa.get("bonus"),
        })
    em_gmv = bool(faixas) and (faixas[0].get("gmv") or 0) > 0
    return render(request, "painel/metas.html", _contexto(
        request, "metas",
        em_gmv=em_gmv, meta_gmv=faixas[0] if em_gmv else {},
        opcoes=[{"valor": f"{a}-{m:02d}", "nome": telas.nome_mes(a, m), "ativo": (a, m) == ano_mes,
                 "fase": ("Próximo mês" if (a, m) > (hoje.year, hoje.month) else telas.NOMES_FASES[telas.fase_da_meta(a, m, hoje)[0]])}
                for a, m in opcoes],
        tres_meses=list(reversed(telas.metas_dos_tres_meses(conta, hoje))) if conta.shopee_validado_em else [],
        # O próximo mês não está entre os três detalhados: o cartão dele fica ao lado do formulário.
        situacao_proximo=(telas.situacao_meta(conta, ano, mes, hoje)
                          if faixas and (ano, mes) > (hoje.year, hoje.month) else None),
        mes_valor=f"{ano}-{mes:02d}",
        nome_mes=telas.nome_mes(ano, mes),
        linhas=linhas,
        situacao=telas.situacao_meta(conta, ano, mes, hoje) if faixas else None,
        shopee_conectada=bool(conta.shopee_validado_em),
    ))


@conta_requerida
def modulo(request, slug):
    item = mod.POR_SLUG.get(slug)
    if not item or not mod.ve_beta(item, conta_logada(request)):
        raise Http404
    if slug in mod.URL_DE_SLUG:  # módulo com página própria (ex: /m/site/ -> /meu-site/)
        return redirect(mod.URL_DE_SLUG[slug])
    conta = conta_logada(request)
    situacao = mod.estado(item, conta.modulos_liberados())
    item = {**item, "icone_path": mod.ICONES[item["icone"]]}
    return render(request, "painel/modulo.html", _contexto(request, slug, item=item, situacao=situacao))


# Ainda não existem no produto; os códigos seguem na licença pra voltar depois sem migração.
MODULOS_OCULTOS = {MODULO_VIDEOS}
# Até o lançamento do Estúdio Instagram, quem não testa vê o nome antigo e não vê as Automações.
ANTES_DO_LANCAMENTO = {MODULO_CARROSSEIS: "Gerador de carrosséis", MODULO_CARROSSEIS_PREMIUM: "Gerador de carrosséis (premium)"}
SO_DEPOIS_DO_LANCAMENTO = {MODULO_INSTAGRAM, MODULO_INSTAGRAM_PREMIUM}


@conta_requerida
def plano(request):
    conta = conta_logada(request)
    liberados = conta.modulos_liberados()
    hoje = timezone.localdate()
    cortesia = set(conta.cortesia_vigente(hoje))
    for codigo in list(cortesia):
        cortesia.update(INCLUI.get(codigo, []))  # o básico que vem junto com o premium da cortesia
    novo = mod.lancado() or conta.beta_estudio_instagram
    linhas_modulos = []
    for codigo, nome in MODULOS:
        if codigo in MODULOS_OCULTOS or (not novo and codigo in SO_DEPOIS_DO_LANCAMENTO):
            continue
        if not novo:
            nome = ANTES_DO_LANCAMENTO.get(codigo, nome)
        elif codigo == MODULO_CARROSSEIS:
            nome = "Estúdio Instagram"
        if codigo in liberados:
            origem = "Cortesia" if codigo in cortesia else "Assinatura"
        else:
            origem = ""
        linhas_modulos.append({"codigo": codigo, "nome": nome, "liberado": codigo in liberados, "origem": origem})
    return render(request, "painel/plano.html", _contexto(
        request, "plano",
        linhas_modulos=linhas_modulos,
        assinaturas=conta.assinaturas.all(),
        validacao=resposta_validacao(conta),
    ))


@sensitive_post_parameters("secret", "senha_atual", "nova_senha", "nova_senha2", "senha", "senha1", "senha2")
@conta_requerida
def configuracoes(request):
    conta = conta_logada(request)
    form_shopee = ShopeeForm(initial={"app_id": conta.shopee_app_id})
    form_senha = TrocarSenhaForm(conta=conta)
    form_regra = RegraSubIdForm()
    preferencia, _ = RelatorioEmail.objects.get_or_create(conta=conta)
    form_relatorio = RelatorioEmailForm(instance=preferencia)

    if request.method == "POST" and request.POST.get("formulario") == "relatorio":
        form_relatorio = RelatorioEmailForm(request.POST, instance=preferencia)
        if form_relatorio.is_valid():
            preferencia = form_relatorio.save()
            if request.POST.get("acao") == "testar":
                if not conta.shopee_validado_em:
                    messages.error(request, "Conecte sua conta da Shopee para receber o relatório.")
                else:
                    # Quem manda é o worker: antes ele busca os números de ontem na Shopee (se ainda
                    # não saíram, vai um aviso no lugar do relatório).
                    RelatorioEmail.objects.filter(pk=preferencia.pk).update(envio_agora_pedido_em=timezone.now())
                    messages.success(request, "Buscando os números de ontem na Shopee. O relatório chega em "
                                              f"{', '.join(preferencia.destinatarios())} em alguns minutos.")
            elif preferencia.ativo:
                messages.success(request, f"Pronto! O relatório chega todo dia às {preferencia.hora:02d}:00, com os números de ontem.")
            else:
                messages.info(request, "Relatório diário desligado.")
            return redirect(f"{request.path}#relatorio")

    elif request.method == "POST" and request.POST.get("formulario") == "shopee":
        form_shopee = ShopeeForm(request.POST)
        if form_shopee.is_valid():
            app_id = form_shopee.cleaned_data["app_id"].strip()
            secret = form_shopee.cleaned_data["secret"].strip() or cripto.decifrar(conta.shopee_secret_cifrado)
            if not secret:
                form_shopee.add_error("secret", "Informe o Secret.")
            else:
                funcionou, mensagem = testar_credenciais(app_id, secret)
                if funcionou:
                    conta.shopee_app_id = app_id
                    conta.shopee_secret_cifrado = cripto.cifrar(secret)
                    conta.shopee_validado_em = timezone.now()
                    conta.save(update_fields=[
                        "shopee_app_id", "shopee_secret_cifrado", "shopee_validado_em", "atualizada_em",
                    ])
                    resultados.pedir_atualizacao(conta)
                    messages.success(request, f"{mensagem} Seus resultados aparecem em Resultados em instantes.")
                    return redirect("painel_configuracoes")
                form_shopee.add_error(None, mensagem)

    elif request.method == "POST" and request.POST.get("formulario") == "senha":
        form_senha = TrocarSenhaForm(request.POST, conta=conta)
        if form_senha.is_valid():
            conta.definir_senha(form_senha.cleaned_data["senha"])
            conta.save(update_fields=["senha", "atualizada_em"])
            fazer_login(request, conta)  # renova a sessão atual; as outras caem
            messages.success(request, "Senha alterada.")
            return redirect("painel_configuracoes")

    elif request.method == "POST" and request.POST.get("formulario") == "regra_sub_id":
        form_regra = RegraSubIdForm(request.POST)
        if conta.regras_sub_id.count() >= MAXIMO_REGRAS_SUB_ID:
            form_regra.add_error(None, f"Dá para ter até {MAXIMO_REGRAS_SUB_ID} agrupamentos.")
        elif form_regra.is_valid():
            RegraSubId.objects.create(conta=conta, **form_regra.cleaned_data)
            messages.success(request, "Agrupamento criado.")
            return redirect(f"{request.path}#sub-ids")

    elif request.method == "POST" and request.POST.get("formulario") == "whatsapp_codigo":
        if comandos_whatsapp.pode_vincular_outro(conta):
            comandos_whatsapp.gerar_codigo(conta)
        else:
            messages.error(request, f"Dá para vincular até {comandos_whatsapp.NUMEROS_POR_CONTA} números. "
                                    "Desvincule um deles para vincular outro.")
        return redirect(f"{request.path}#whatsapp")

    elif request.method == "POST" and request.POST.get("formulario") == "whatsapp_desvincular":
        comandos_whatsapp.desvincular(conta, request.POST.get("conversa"))
        messages.info(request, "Número desvinculado. Ele não recebe mais os seus resultados pelo WhatsApp.")
        return redirect(f"{request.path}#whatsapp")

    elif request.method == "POST" and request.POST.get("formulario") == "apagar_regra_sub_id":
        RegraSubId.objects.filter(conta=conta, pk=request.POST.get("regra")).delete()
        messages.info(request, "Agrupamento apagado.")
        return redirect(f"{request.path}#sub-ids")

    return render(request, "painel/configuracoes.html", _contexto(
        request, "configuracoes", form_shopee=form_shopee, form_senha=form_senha, form_regra=form_regra,
        form_relatorio=form_relatorio, preferencia_relatorio=preferencia, api=api_shopee,
        regras=resultados.resumo_das_regras(conta, telas.hoje()),
        whatsapp=_whatsapp_resultados(conta),
    ))


def _whatsapp_resultados(conta) -> dict | None:
    """Cartão "Lia no WhatsApp": os números vinculados e o código para vincular outro. Quem responde
    é o worker (agente de vendas); aqui no web basta saber o número. Sem número conhecido, o cartão some."""
    numero = comandos_whatsapp.numero_do_appfiliado()
    if not numero:
        return None
    vinculados = comandos_whatsapp.numeros_vinculados(conta)
    pode_vincular = len(vinculados) < comandos_whatsapp.NUMEROS_POR_CONTA
    codigo = comandos_whatsapp.codigo_valido(conta) if pode_vincular else None
    return {
        "vinculados": [{"pk": c.pk, "telefone": _telefone_formatado(c.telefone) or c.nome or "Seu WhatsApp",
                        "desde": c.vinculada_em} for c in vinculados],
        "pode_vincular": pode_vincular,
        "maximo": comandos_whatsapp.NUMEROS_POR_CONTA,
        "codigo": codigo,
        "vence_em": codigo.criado_em + comandos_whatsapp.VALIDADE_DO_CODIGO if codigo else None,
        "link": f"https://wa.me/{numero}" + (f"?text={quote(f'VINCULAR {codigo.codigo}')}" if codigo else ""),
        "numero": _telefone_formatado(numero),
    }


def _telefone_formatado(numero: str) -> str:
    if numero.startswith("55") and len(numero) in (12, 13):
        return f"+55 ({numero[2:4]}) {numero[4:-4]}-{numero[-4:]}"
    return f"+{numero}" if numero else ""


# --- Erros ---------------------------------------------------------------------------

def erro_404(request, exception=None):
    return render(request, "painel/erro.html", {"titulo": "Página não encontrada",
                                                 "texto": "Esse endereço não existe no painel."}, status=404)


def erro_500(request):
    return render(request, "painel/erro.html", {"titulo": "Algo deu errado",
                                                 "texto": "Tivemos um problema aqui. Tente de novo em instantes."},
                  status=500)


def parar_dicas(request, token):
    """Link do rodapé dos e-mails de dicas (painel/emails_valor.py): para a sequência, sem login."""
    from django.http import Http404

    from . import emails_valor

    conta = emails_valor.conta_do_link(token)
    if not conta:
        raise Http404
    if not conta.sem_dicas_por_email:
        type(conta).objects.filter(pk=conta.pk).update(sem_dicas_por_email=True)
    return render(request, "painel/parar_dicas.html", {"email": conta.email})


@conta_requerida
def sugestoes(request):
    """Sugerir melhoria: formulário pros afiliados mandarem ideias (painel/sugestoes.py)."""
    from django.contrib import messages

    from . import sugestoes as servico_sugestoes
    from .forms import SugestaoForm
    from .models import Sugestao

    conta = conta_logada(request)
    form = SugestaoForm(request.POST or None)
    if request.method == "POST":
        hoje = Sugestao.objects.filter(conta=conta, criada_em__gte=timezone.now() - timedelta(days=1)).count()
        if hoje >= servico_sugestoes.POR_DIA:
            messages.error(request, "Você já mandou muitas sugestões hoje. Obrigado! Manda as próximas amanhã.")
        elif form.is_valid():
            sugestao = form.criar(conta)
            servico_sugestoes.avisar_voce(sugestao)
            messages.success(request, "Valeu! A sua sugestão chegou. Quando ela sair do papel, você recebe um aviso por e-mail.")
            return redirect("painel_sugestoes")
        else:
            messages.error(request, "Confira os campos marcados.")
    enviadas = Sugestao.objects.filter(conta=conta)[:10]
    return render(request, "painel/sugestoes.html", _contexto(request, "sugestoes", form=form, enviadas=enviadas))
