"""Primeiros passos de quem acabou de assinar: a lista do que falta configurar (depende dos
módulos que a pessoa tem), o cartão da página Início e os e-mails do dia 1 e do dia 3.

Os e-mails só saem pra quem ainda tem algum passo pendente e só nos primeiros dias depois da
primeira assinatura (a garantia é de 7 dias: a ideia é ajudar antes de a pessoa desistir).
Quem já era cliente e assina outro módulo não recebe. O worker chama enviar_pendentes()."""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Min
from django.utils import timezone

from licencas.models import (MODULO_CARROSSEIS, MODULO_NOTAS, MODULO_SITE, MODULO_WHATSAPP, Assinatura,
                             ContaAppfiliado)

logger = logging.getLogger(__name__)

DIA_DO_PRIMEIRO_EMAIL = timedelta(days=1)
DIA_DO_SEGUNDO_EMAIL = timedelta(days=3)
JANELA = timedelta(days=7)  # depois disso (ou de clientes antigos), nada de e-mail


def passos(conta, liberados=None) -> list[dict]:
    """Cada passo: chave, titulo, detalhe (pro e-mail), feito, acao e href (nome da URL do painel)."""
    from bot_whatsapp.models import ConexaoWhatsApp, ConfiguracaoOfertas
    from carrosseis.models import Carrossel
    from meusite.models import SiteAfiliado
    from notas.models import EmpresaNotas

    liberados = set(conta.modulos_liberados() if liberados is None else liberados)
    lista = [{"chave": "senha", "titulo": "Criar a senha do painel", "detalhe": "",
              "feito": conta.tem_senha, "acao": "Criar senha", "href": ""}]
    # Só quem tem apenas o Emissor de notas não precisa da API da Shopee.
    if not liberados or liberados & {MODULO_WHATSAPP, MODULO_SITE, MODULO_CARROSSEIS} or not liberados & {MODULO_NOTAS}:
        lista.append({"chave": "shopee", "titulo": "Conectar sua conta de afiliado da Shopee",
                      "detalhe": "a API da Shopee, em Configurações", "feito": bool(conta.shopee_validado_em),
                      "acao": "Conectar", "href": "painel_configuracoes"})
    if MODULO_WHATSAPP in liberados:
        conexao = ConexaoWhatsApp.objects.filter(conta=conta).first()
        config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
        lista += [
            {"chave": "whatsapp", "titulo": "Conectar seu WhatsApp pelo QR Code", "detalhe": "como no WhatsApp Web",
             "feito": bool(conexao and (conexao.conectado_em or conexao.estado == ConexaoWhatsApp.CONECTADO)),
             "acao": "Conectar", "href": "painel_whatsapp"},
            {"chave": "ofertas", "titulo": "Ligar as ofertas automáticas",
             "detalhe": "escolha os grupos e clique em Ligar ofertas",
             "feito": bool(config and (config.ativo or config.ultimo_envio_em)),
             "acao": "Configurar", "href": "painel_whatsapp_ofertas"},
        ]
    if MODULO_SITE in liberados:
        site = SiteAfiliado.objects.filter(conta=conta).first()
        lista.append({"chave": "site", "titulo": "Publicar seu site", "detalhe": "escolha o endereço e o nome",
                      "feito": bool(site and site.endereco and site.nome and site.publicado),
                      "acao": "Montar o site", "href": "painel_meu_site"})
    if MODULO_CARROSSEIS in liberados:
        lista.append({"chave": "carrossel", "titulo": "Gerar seu primeiro carrossel",
                      "detalhe": "cole o link de um produto da Shopee",
                      "feito": Carrossel.objects.filter(conta=conta).exists(),
                      "acao": "Gerar", "href": "painel_carrosseis"})
    if MODULO_NOTAS in liberados:
        lista.append({"chave": "notas", "titulo": "Cadastrar a empresa e o certificado digital",
                      "detalhe": "para emitir as notas", "acao": "Cadastrar", "href": "painel_notas",
                      "feito": EmpresaNotas.objects.filter(conta=conta).exclude(certificado_cifrado="").exists()})
    return lista


ADIAR_POR = timedelta(hours=12)


def cartao_visivel(conta, agora=None) -> bool:
    """O cartão do Início some de vez com "Não mostrar novamente" e por 12 horas com "Me lembre mais tarde"."""
    if conta.passos_ocultos:
        return False
    return not conta.passos_adiados_ate or conta.passos_adiados_ate <= (agora or timezone.now())


def pendentes(lista: list[dict]) -> list[dict]:
    return [p for p in lista if not p["feito"]]


# --- E-mails ------------------------------------------------------------------------

def inicio_como_cliente(conta):
    """Quando a primeira assinatura que dá acesso foi criada (None = não tem nenhuma)."""
    return conta.assinaturas.filter(status__in=Assinatura.STATUS_QUE_LIBERAM).aggregate(m=Min("criada_em"))["m"]


def enviar_pendentes(agora=None) -> list[str]:
    agora = agora or timezone.now()
    linhas = []
    contas = (ContaAppfiliado.objects.filter(passos_email_2_em__isnull=True,
                                             assinaturas__status__in=Assinatura.STATUS_QUE_LIBERAM,
                                             assinaturas__criada_em__gte=agora - JANELA,
                                             assinaturas__criada_em__lte=agora - DIA_DO_PRIMEIRO_EMAIL)
              .distinct())
    for conta in contas:
        inicio = inicio_como_cliente(conta)
        if not inicio or agora - inicio > JANELA or agora - inicio < DIA_DO_PRIMEIRO_EMAIL:
            continue  # cliente antigo assinando mais um módulo: não é começo
        faltam = pendentes(passos(conta))
        segundo = agora - inicio >= DIA_DO_SEGUNDO_EMAIL
        if not faltam or (not segundo and conta.passos_email_1_em):
            if not faltam:  # já fez tudo: não precisa de mais nenhum
                ContaAppfiliado.objects.filter(pk=conta.pk).update(passos_email_1_em=conta.passos_email_1_em or agora,
                                                                   passos_email_2_em=agora)
            continue
        campos = {"passos_email_1_em": conta.passos_email_1_em or agora}
        if segundo:
            campos["passos_email_2_em"] = agora
        # Marca antes de mandar: com dois processos rodando juntos, só um manda.
        filtro = {"passos_email_2_em__isnull": True} if segundo else {"passos_email_1_em__isnull": True}
        if not ContaAppfiliado.objects.filter(pk=conta.pk, **filtro).update(**campos):
            continue
        if enviar_email(conta, passos(conta), segundo):
            linhas.append(f"Primeiros passos: e-mail {'2' if segundo else '1'} pra {conta.email} ({len(faltam)} pendente(s)).")
    return linhas


def _link(conta, passo) -> str:
    from .emails import link_definir_senha, url_do_painel

    return link_definir_senha(conta) if passo["chave"] == "senha" else url_do_painel(passo["href"])


def montar_email(conta, lista: list[dict], segundo: bool = False) -> tuple[str, str]:
    faltam = pendentes(lista)
    proximo = faltam[0]
    tem_bot = any(p["chave"] == "ofertas" for p in lista)
    linhas = []
    for passo in lista:
        detalhe = f" ({passo['detalhe']})" if passo["detalhe"] and not passo["feito"] else ""
        linhas.append(f"{'✅' if passo['feito'] else '⬜'} {passo['titulo']}{detalhe}")
    whatsapp = re.sub(r"\D", "", settings.APPFILIADO_WHATSAPP_SUPORTE or "")
    link_whatsapp = f"https://wa.me/{whatsapp}" if whatsapp else ""
    nome = f", {conta.nome.split(' ')[0]}" if conta.nome else ""
    quantos = f"{len(faltam)} passo{'s' if len(faltam) > 1 else ''}"
    if segundo:
        assunto = "Precisa de ajuda para configurar o Appfiliado?"
        abertura = (f"Notamos que ainda falta{'m' if len(faltam) > 1 else ''} {quantos} para você aproveitar o Appfiliado. "
                    "Se travou em alguma parte, a gente te ajuda: é só responder este e-mail"
                    + (f" ou chamar a gente no WhatsApp: {link_whatsapp}" if link_whatsapp else "") + ".")
    else:
        assunto = ("Falta pouco pras suas ofertas começarem a sair" if tem_bot
                   else "Falta pouco para começar a usar o Appfiliado")
        abertura = (f"Você está a {quantos} de ver o bot postando nos seus grupos:" if tem_bot
                    else f"Você está a {quantos} de começar a usar o Appfiliado:")
    corpo = (
        f"Olá{nome}!\n\n"
        f"{abertura}\n\n"
        + "\n".join(linhas) + "\n\n"
        f"Continuar de onde parei: {_link(conta, proximo)}\n\n"
        + ("" if segundo else "Travou em algum passo? A gente te ajuda: é só responder este e-mail"
           + (f" ou chamar a gente no WhatsApp: {link_whatsapp}" if link_whatsapp else "") + ".\n\n")
        + "Equipe Appfiliado"
    )
    return assunto, corpo


def enviar_email(conta, lista: list[dict], segundo: bool = False) -> bool:
    assunto, corpo = montar_email(conta, lista, segundo)
    try:
        EmailMessage(subject=assunto, body=corpo, to=[conta.email], from_email=settings.APPFILIADO_EMAIL_REMETENTE).send()
    except Exception:  # noqa: BLE001
        logger.exception("Primeiros passos: falha ao mandar o e-mail pra conta %s", conta.pk)
        return False
    return True
