from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from accounts.ratelimit import _incrementar_contador, _obter_ip
from licencas.models import MODULOS, ContaAppfiliado
from licencas.services import resposta_validacao

from . import cripto
from . import modulos as mod
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
from .forms import EntrarForm, EsqueciSenhaForm, NovaSenhaForm, ShopeeForm, TrocarSenhaForm
from .shopee import testar_credenciais

NOMES_MODULOS = dict(MODULOS)
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def _contexto(request, ativo: str, **extra) -> dict:
    conta = conta_logada(request)
    liberados = conta.modulos_liberados() if conta else []
    return {
        "conta": conta,
        "menu": mod.menu(liberados, ativo),
        "modulos_liberados": liberados,
        "url_planos": settings.APPFILIADO_URL_PLANOS,
        "icones": mod.ICONES,
        **extra,
    }


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
            if conta and conta.confere_senha(form.cleaned_data["senha"]):
                fazer_login(request, conta)
                return redirect(destino_seguro(request, request.GET.get("proximo", "")))
            registrar_falha_login(ip, email)
            if conta and not conta.tem_senha:
                form.add_error(None, "Você ainda não criou sua senha. Use \"Criar ou recuperar senha\" abaixo.")
            else:
                form.add_error(None, "E-mail ou senha incorretos.")
    return render(request, "painel/entrar.html", {"form": form})


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
        # Mesma resposta exista ou não a conta - não dá pra descobrir quem é cliente.
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
    cartoes_modulos = [
        {**item, "estado": mod.estado(item, liberados), "icone_path": mod.ICONES[item["icone"]],
         "href": item_menu["href"]}
        for item, item_menu in zip(mod.MODULOS_DO_MENU, mod.menu(liberados, ""))
        if item["modulo"]
    ]
    passos = [
        {"titulo": "Criar sua senha do painel", "feito": True},
        {"titulo": "Conectar sua conta de afiliado da Shopee", "feito": bool(conta.shopee_validado_em),
         "acao": "Conectar", "href": "painel_configuracoes"},
        {"titulo": "Conectar seu WhatsApp pelo QR Code", "feito": False, "em_breve": True},
        {"titulo": "Cadastrar as metas do mês da Shopee", "feito": False, "em_breve": True},
    ]
    return render(request, "painel/inicio.html", _contexto(
        request, "inicio", hoje=_hoje_por_extenso(), passos=passos, cartoes_modulos=cartoes_modulos,
        primeiro_nome=(conta.nome or "").split(" ")[0],
    ))


@conta_requerida
def modulo(request, slug):
    item = mod.POR_SLUG.get(slug)
    if not item or slug in mod.URL_DE_SLUG:
        raise Http404
    conta = conta_logada(request)
    situacao = mod.estado(item, conta.modulos_liberados())
    item = {**item, "icone_path": mod.ICONES[item["icone"]]}
    return render(request, "painel/modulo.html", _contexto(request, slug, item=item, situacao=situacao))


@conta_requerida
def plano(request):
    conta = conta_logada(request)
    liberados = conta.modulos_liberados()
    hoje = timezone.localdate()
    cortesia = conta.cortesia_vigente(hoje)
    linhas_modulos = []
    for codigo, nome in MODULOS:
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


@conta_requerida
def configuracoes(request):
    conta = conta_logada(request)
    form_shopee = ShopeeForm(initial={"app_id": conta.shopee_app_id})
    form_senha = TrocarSenhaForm(conta=conta)

    if request.method == "POST" and request.POST.get("formulario") == "shopee":
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
                    messages.success(request, mensagem)
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

    return render(request, "painel/configuracoes.html", _contexto(
        request, "configuracoes", form_shopee=form_shopee, form_senha=form_senha,
    ))


# --- Erros ---------------------------------------------------------------------------

def erro_404(request, exception=None):
    return render(request, "painel/erro.html", {"titulo": "Página não encontrada",
                                                 "texto": "Esse endereço não existe no painel."}, status=404)


def erro_500(request):
    return render(request, "painel/erro.html", {"titulo": "Algo deu errado",
                                                 "texto": "Tivemos um problema aqui. Tente de novo em instantes."},
                  status=500)
