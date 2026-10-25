"""Sequência de e-mails de dicas pros novos assinantes: lembrar do Appfiliado e mostrar o valor dele,
um assunto por e-mail, escritos pelo fundador (Eduardo), às 10h dos dias 2, 4, 6, 8, 10, 12 e 21
depois da primeira assinatura. Cada e-mail se adapta aos módulos da pessoa: quem tem o módulo
recebe como tirar mais dele; quem não tem, no máximo uma oferta curta no fim.

Para quando a pessoa cancela/é reembolsada (sem assinatura que dê acesso) ou clica em "não quero
mais receber" no rodapé. Se o servidor estava fora no dia, o e-mail ainda sai no dia seguinte;
depois disso é pulado (nunca saem dois no mesmo dia). O worker chama enviar_pendentes()."""

import logging
import re
from html import unescape
from datetime import date, timedelta
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from licencas.models import (MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM, MODULO_NOTAS, MODULO_SITE, MODULO_WHATSAPP, MODULO_WHATSAPP_PREMIUM,
                             Assinatura, ContaAppfiliado)

from .models import EmailValorEnviado

logger = logging.getLogger(__name__)

HORA = 10
JANELA = timedelta(days=23)  # depois do último e-mail (dia 21), a conta sai da lista
SAL = "emails-de-dicas"
REMETENTE = "Eduardo, do Appfiliado"
COMISSAO_PRO_EMISSOR = 1000  # comissão em 30 dias a partir da qual o e-mail final fala do Emissor NFS-e

# (chave, dia, assunto, pronto). "historia" espera o texto do Eduardo (painel/emails/valor/historia.html).
SEQUENCIA = [
    ("historia", 2, "Por que eu criei o Appfiliado", False),
    ("bot", 4, "O grupo que vende todo dia não é sorte", True),
    ("resultados", 6, "Você sabe qual grupo te dá mais comissão?", True),
    ("radar", 8, "Onde achar o produto que vende antes de todo mundo", True),
    ("campanhas", 10, "Datas duplas e Black Friday no piloto automático", True),
    ("site_carrosseis", 12, "Seu link na bio e seu Instagram trabalhando junto", True),
    ("como_vai", 21, "Como estão indo as suas vendas?", True),
]


def link_para_parar(conta) -> str:
    from .emails import url_do_painel

    return url_do_painel("painel_parar_dicas", signing.dumps(conta.pk, salt=SAL))


def conta_do_link(token: str):
    try:
        pk = signing.loads(token, salt=SAL)
    except signing.BadSignature:
        return None
    return ContaAppfiliado.objects.filter(pk=pk).first()


def _inicio(conta):
    from .primeiros_passos import inicio_como_cliente

    return inicio_como_cliente(conta)


def _numeros_30_dias(conta, hoje: date) -> dict:
    from . import resultados

    inicio = hoje - timedelta(days=30)
    totais = resultados.totais(conta, inicio, hoje)
    melhor = resultados.por_sub_id(conta, inicio, hoje, limite=1)
    return {"comissao": totais["comissao_estimada"], "pedidos": totais["pedidos"],
            "melhor": melhor[0] if melhor and melhor[0]["comissao"] else None}


def contexto(conta, chave: str, hoje: date | None = None) -> dict:
    from .emails import url_do_painel
    from .relatorio import url_do_logo

    hoje = hoje or timezone.localdate()
    liberados = set(conta.modulos_liberados())
    estatico = settings.APPFILIADO_PAINEL_URL.rstrip("/") + "/static/painel/emails/"
    dados = {
        "nome": (conta.nome or "").split(" ")[0],
        "tem_bot": MODULO_WHATSAPP in liberados, "premium_bot": MODULO_WHATSAPP_PREMIUM in liberados,
        "tem_site": MODULO_SITE in liberados, "tem_carrosseis": MODULO_CARROSSEIS in liberados,
        "premium_carrosseis": MODULO_CARROSSEIS_PREMIUM in liberados,
        "tem_notas": MODULO_NOTAS in liberados, "shopee_conectada": bool(conta.shopee_validado_em),
        "url_logo": url_do_logo(), "img": estatico, "url_planos": settings.APPFILIADO_URL_PLANOS,
        "url_parar": link_para_parar(conta),
        # estilos inline (e-mail não garante <style>): parágrafo, item com "↳" e destaque
        "p": "margin:0 0 14px;font-size:15px;line-height:1.6;color:#1C2B23;",
        "li": "margin:0 0 8px;padding-left:4px;font-size:15px;line-height:1.55;color:#1C2B23;",
        "dica": "margin:4px 0 16px;padding:12px 14px;background:#F6F3EA;border-radius:10px;font-size:14px;line-height:1.55;color:#1C2B23;",
        "url": {nome: url_do_painel(f"painel_{nome}") for nome in (
            "inicio", "resultados", "radar", "conversor", "configuracoes", "whatsapp_ofertas", "whatsapp_campanhas",
            "whatsapp_mensagens", "whatsapp_alertas", "meu_site", "carrosseis", "notas")},
    }
    if chave == "como_vai":
        dados["numeros"] = _numeros_30_dias(conta, hoje)
        dados["sugerir_emissor"] = not dados["tem_notas"] and dados["numeros"]["comissao"] >= COMISSAO_PRO_EMISSOR
    return dados


def montar(conta, chave: str, hoje: date | None = None) -> tuple[str, str, str]:
    """(assunto, texto, html)."""
    assunto = next(a for c, _, a, _ in SEQUENCIA if c == chave)
    html = render_to_string(f"painel/emails/valor/{chave}.html", contexto(conta, chave, hoje))
    corpo = html.split("<!--corpo-->")[1].split("<!--/corpo-->")[0] if "<!--corpo-->" in html else html
    # Versão em texto: os botões e links viram "texto: endereço"; as imagens saem.
    corpo = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f"{strip_tags(m.group(2)).strip()}: {m.group(1)}",
                   corpo, flags=re.S)
    corpo = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", corpo)
    linhas = [re.sub(r"[ \t]+", " ", linha).strip() for linha in unescape(strip_tags(corpo)).splitlines()]
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    texto += f"\n\nNão quer mais receber estas dicas? {link_para_parar(conta)}"
    return assunto, texto, html


def enviar(conta, chave: str, hoje: date | None = None) -> None:
    assunto, texto, html = montar(conta, chave, hoje)
    endereco = parseaddr(settings.APPFILIADO_EMAIL_REMETENTE)[1]
    mensagem = EmailMultiAlternatives(
        subject=assunto, body=texto, to=[conta.email], from_email=formataddr((REMETENTE, endereco)),
        reply_to=[settings.APPFILIADO_EMAIL_SUPORTE] if settings.APPFILIADO_EMAIL_SUPORTE else None,
        headers={"List-Unsubscribe": f"<{link_para_parar(conta)}>"},
    )
    mensagem.attach_alternative(html, "text/html")
    mensagem.send()


def enviar_pendentes(agora=None) -> list[str]:
    agora = agora or timezone.now()
    local = timezone.localtime(agora)
    hoje = local.date()
    linhas = []
    contas = (ContaAppfiliado.objects.filter(sem_dicas_por_email=False,
                                             assinaturas__status__in=Assinatura.STATUS_QUE_LIBERAM,
                                             assinaturas__criada_em__gte=agora - JANELA).distinct())
    for conta in contas:
        inicio = _inicio(conta)
        if not inicio or agora - inicio > JANELA:
            continue  # já era cliente antes (assinou mais um módulo)
        comeco = timezone.localtime(inicio).date()
        enviados = EmailValorEnviado.objects.filter(conta=conta)
        feitos = set(enviados.values_list("chave", flat=True))
        if enviados.filter(pulado=False, enviado_em__date=hoje).exists():
            continue  # já saiu um hoje
        for chave, dia, _assunto, pronto in SEQUENCIA:
            if chave in feitos:
                continue
            alvo = comeco + timedelta(days=dia)
            if hoje < alvo:
                break
            if hoje > alvo + timedelta(days=1):  # passou do dia (servidor fora): pula
                EmailValorEnviado.objects.get_or_create(conta=conta, chave=chave, defaults={"pulado": True})
                continue
            if not pronto:
                continue
            if hoje == alvo and local.hour < HORA:
                break
            _, criado = EmailValorEnviado.objects.get_or_create(conta=conta, chave=chave)
            if not criado:
                break  # outro processo pegou
            try:
                enviar(conta, chave, hoje)
                linhas.append(f"Dicas: e-mail '{chave}' pra {conta.email}.")
            except Exception:  # noqa: BLE001 - tenta de novo na próxima volta
                logger.exception("Dicas: falha ao mandar '%s' pra conta %s", chave, conta.pk)
                EmailValorEnviado.objects.filter(conta=conta, chave=chave).delete()
            break
    return linhas
