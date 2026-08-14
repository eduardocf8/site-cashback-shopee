from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse

from links.models import Click
from pedidos.models import Pedido
from saques.models import Saque
from saques.services import calcular_saldo_disponivel

from .forms import ChavePixForm, EditarPerfilForm, RegistroForm
from .models import ConfiguracaoIndicacao, Indicacao
from .tokens import enviar_email_verificacao, validar_token_verificacao

User = get_user_model()

ITENS_POR_PAGINA = 10


def registrar(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    codigo_indicacao = request.POST.get("ref") or request.GET.get("ref", "")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            _criar_indicacao_se_valida(usuario, codigo_indicacao)
            enviar_email_verificacao(usuario, request)
            login(request, usuario)
            return redirect("dashboard")
    else:
        form = RegistroForm()

    return render(request, "accounts/registrar.html", {"form": form, "codigo_indicacao": codigo_indicacao})


def _criar_indicacao_se_valida(usuario, codigo_indicacao):
    if not codigo_indicacao or not ConfiguracaoIndicacao.esta_ativa():
        return
    indicador = User.objects.filter(codigo_indicacao=codigo_indicacao).exclude(pk=usuario.pk).first()
    if indicador:
        Indicacao.objects.create(indicador=indicador, indicado=usuario)


def verificar_email(request, token):
    dados = validar_token_verificacao(token)
    if not dados:
        messages.error(request, "Esse link de verificação é inválido ou expirou.")
        return redirect("home")

    try:
        usuario = User.objects.get(pk=dados["user_id"])
    except User.DoesNotExist:
        messages.error(request, "Conta não encontrada.")
        return redirect("home")

    if usuario.email != dados["email"]:
        messages.error(request, "Esse link não é mais válido — o e-mail da conta mudou.")
        return redirect("home")

    if not usuario.email_verificado:
        usuario.email_verificado = True
        usuario.save(update_fields=["email_verificado"])

    messages.success(request, "E-mail verificado com sucesso!")
    return redirect("dashboard" if request.user.is_authenticated else "login")


@login_required
def reenviar_verificacao(request):
    if request.user.email_verificado:
        messages.info(request, "Seu e-mail já está verificado.")
    else:
        enviar_email_verificacao(request.user, request)
        messages.success(request, "Enviamos um novo link de verificação pro seu e-mail.")
    return redirect("dashboard")


@login_required
def dashboard(request):
    pedidos_usuario = Pedido.objects.filter(usuario=request.user)

    saldos = {chave: Decimal("0") for chave, _ in Pedido.STATUS_CHOICES}
    for linha in pedidos_usuario.values("status").annotate(total=Sum("valor_cashback")):
        saldos[linha["status"]] = linha["total"] or Decimal("0")

    filtro_pedidos = request.GET.get("status_pedido", "")
    pedidos_filtrados = pedidos_usuario.order_by("-data_compra")
    if filtro_pedidos in dict(Pedido.STATUS_CHOICES):
        pedidos_filtrados = pedidos_filtrados.filter(status=filtro_pedidos)
    pedidos_pagina = Paginator(pedidos_filtrados, ITENS_POR_PAGINA).get_page(request.GET.get("pagina_pedidos"))

    filtro_saques = request.GET.get("status_saque", "")
    saques_filtrados = request.user.saques.all()
    if filtro_saques in dict(Saque.STATUS_CHOICES):
        saques_filtrados = saques_filtrados.filter(status=filtro_saques)
    saques_pagina = Paginator(saques_filtrados, ITENS_POR_PAGINA).get_page(request.GET.get("pagina_saques"))

    filtro_clicks = request.GET.get("tipo_click", "")
    clicks_filtrados = request.user.clicks.all()
    if filtro_clicks in dict(Click.TIPO_CHOICES):
        clicks_filtrados = clicks_filtrados.filter(tipo=filtro_clicks)
    clicks_pagina = Paginator(clicks_filtrados, ITENS_POR_PAGINA).get_page(request.GET.get("pagina_clicks"))

    saldo_disponivel = calcular_saldo_disponivel(request.user)
    saque_valor_minimo = settings.SAQUE_VALOR_MINIMO
    progresso_saque_percentual = (
        min(100, int(saldo_disponivel / saque_valor_minimo * 100)) if saque_valor_minimo else 100
    )

    indicacao_ativa = ConfiguracaoIndicacao.esta_ativa()
    link_indicacao = request.build_absolute_uri(f"{reverse('registrar')}?ref={request.user.codigo_indicacao}")
    indicacoes = request.user.indicacoes_feitas.select_related("indicado").all()
    indicacoes_concluidas = sum(1 for indicacao in indicacoes if indicacao.pedido_bonus_indicador_id)

    contexto = {
        "saldo_pendente": saldos[Pedido.STATUS_PENDENTE],
        "saldo_validado": saldos[Pedido.STATUS_VALIDADO],
        # "Liberado" mostra só o que ainda pode ser sacado (saldo_disponivel), não o total
        # histórico já liberado - senão o valor nunca baixava depois de um saque, dando a
        # impressão errada de que ainda tinha mais pra sacar do que realmente tem.
        "saldo_liberado": saldo_disponivel,
        "saldo_sacado": saldos[Pedido.STATUS_LIBERADO] - saldo_disponivel,
        "saldo_cancelado": saldos[Pedido.STATUS_CANCELADO],
        "saldo_disponivel": saldo_disponivel,
        "saque_valor_minimo": saque_valor_minimo,
        "progresso_saque_percentual": progresso_saque_percentual,
        "clicks": clicks_pagina,
        "pedidos": pedidos_pagina,
        "saques": saques_pagina,
        "filtro_pedidos": filtro_pedidos,
        "filtro_saques": filtro_saques,
        "filtro_clicks": filtro_clicks,
        "status_pedidos_choices": Pedido.STATUS_CHOICES,
        "status_saques_choices": Saque.STATUS_CHOICES,
        "tipo_clicks_choices": Click.TIPO_CHOICES,
        "chave_pix_form": ChavePixForm(instance=request.user),
        "indicacao_ativa": indicacao_ativa,
        "link_indicacao": link_indicacao,
        "indicacoes": indicacoes,
        "indicacoes_concluidas": indicacoes_concluidas,
    }
    return render(request, "accounts/dashboard.html", contexto)


@login_required
def editar_chave_pix(request):
    if request.method == "POST":
        form = ChavePixForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Chave PIX atualizada com sucesso!")
            return redirect("dashboard")
    else:
        form = ChavePixForm(instance=request.user)

    return render(request, "accounts/chave_pix.html", {"form": form})


@login_required
def excluir_chave_pix(request):
    if request.method == "POST":
        request.user.chave_pix = ""
        request.user.tipo_chave_pix = ""
        request.user.save(update_fields=["chave_pix", "tipo_chave_pix"])
        messages.success(request, "Chave PIX removida.")

    return redirect("dashboard")


@login_required
def editar_perfil(request):
    if request.method == "POST":
        # Captura o e-mail antigo antes de validar o form: como o form usa
        # instance=request.user (mesmo objeto), form.is_valid() já escreve o
        # e-mail novo direto no request.user em memória.
        email_antigo = request.user.email
        form = EditarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            usuario = form.save(commit=False)
            email_mudou = usuario.email != email_antigo
            if email_mudou:
                usuario.email_verificado = False
            usuario.save()

            if email_mudou:
                enviar_email_verificacao(usuario, request)
                messages.success(
                    request,
                    "Dados atualizados! Como você mudou o e-mail, mandamos um novo link de "
                    "verificação pra ele.",
                )
            else:
                messages.success(request, "Dados atualizados com sucesso!")
            return redirect("dashboard")
    else:
        form = EditarPerfilForm(instance=request.user)

    return render(request, "accounts/editar_perfil.html", {"form": form})
