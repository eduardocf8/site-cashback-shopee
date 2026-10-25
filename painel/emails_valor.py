"""Sequência de e-mails de dicas pros novos assinantes: lembrar do Appfiliado e mostrar o valor dele,
um assunto por e-mail, escritos pelo fundador (Eduardo), às 10h dos dias 2, 4, 6, 8, 10, 12 e 21
depois da primeira assinatura. Cada e-mail se adapta aos módulos da pessoa: quem tem o módulo
recebe como tirar mais dele; quem não tem, no máximo uma oferta curta no fim.

Para quando a pessoa cancela/é reembolsada (sem assinatura que dê acesso) ou clica em "não quero
mais receber" no rodapé. Se o servidor estava fora no dia, o e-mail ainda sai no dia seguinte;
depois disso é pulado (nunca saem dois no mesmo dia). O worker chama enviar_pendentes()."""

import logging
import re
from datetime import date, timedelta
from email.utils import formataddr, parseaddr
from html import unescape

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from licencas.models import (MODULO_CARROSSEIS, MODULO_CARROSSEIS_PREMIUM, MODULO_NOTAS, MODULO_SITE, MODULO_WHATSAPP,
                             MODULO_WHATSAPP_PREMIUM,
                             Assinatura, ContaAppfiliado)

from .models import EmailValorEnviado, TextoEmailDica
from .textos_dicas import TEXTOS

logger = logging.getLogger(__name__)

HORA = 10
JANELA = timedelta(days=23)  # depois do último e-mail (dia 21), a conta sai da lista
SAL = "emails-de-dicas"
REMETENTE = "Eduardo, do Appfiliado"
COMISSAO_PRO_EMISSOR = 1000  # comissão em 30 dias a partir da qual o e-mail final fala do Emissor NFS-e

# (chave, dia). Os textos ficam no banco (TextoEmailDica, editáveis no admin); o padrão está em textos_dicas.py.
SEQUENCIA = [("historia", 2), ("bot", 4), ("resultados", 6), ("radar", 8), ("campanhas", 10),
             ("site_carrosseis", 12), ("como_vai", 21)]

# Estilos inline (e-mail não garante <style>).
ESTILO_P = "margin:0 0 14px;font-size:15px;line-height:1.6;color:#1C2B23;"
ESTILO_ITEM = "margin:0 0 8px;padding-left:4px;font-size:15px;line-height:1.55;color:#1C2B23;"
ESTILO_DICA = "margin:4px 0 16px;padding:12px 14px;background:#F6F3EA;border-radius:10px;font-size:14px;line-height:1.55;color:#1C2B23;"
ESTILO_LINK = "color:#1F3A2E;"


def texto_do_email(chave: str):
    """O texto salvo no admin, ou o padrão (textos_dicas.py) se ainda não estiver no banco."""
    salvo = TextoEmailDica.objects.filter(chave=chave).first()
    if salvo:
        return salvo
    t = TEXTOS[chave]
    return TextoEmailDica(chave=chave, assunto=t["assunto"], texto=t["texto"], texto_sem=t.get("texto_sem", ""),
                          ativo=t.get("ativo", True))


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


def contexto(conta, chave: str, hoje: date | None = None, liberados=None) -> dict:
    from .emails import url_do_painel
    from .relatorio import url_do_logo

    hoje = hoje or timezone.localdate()
    liberados = set(conta.modulos_liberados() if liberados is None else liberados)
    dados = {
        "nome": (conta.nome or "").split(" ")[0],
        "tem_bot": MODULO_WHATSAPP in liberados, "premium_bot": MODULO_WHATSAPP_PREMIUM in liberados,
        "tem_site": MODULO_SITE in liberados, "tem_carrosseis": MODULO_CARROSSEIS in liberados,
        "premium_carrosseis": MODULO_CARROSSEIS_PREMIUM in liberados,
        "tem_notas": MODULO_NOTAS in liberados, "shopee_conectada": bool(conta.shopee_validado_em),
        "url_logo": url_do_logo(), "img": settings.APPFILIADO_PAINEL_URL.rstrip("/") + "/static/painel/emails/",
        "url_parar": link_para_parar(conta),
        "links": {
            "planos": settings.APPFILIADO_URL_PLANOS,
            **{nome: url_do_painel(rota) for nome, rota in {
                "inicio": "painel_inicio", "resultados": "painel_resultados", "radar": "painel_radar",
                "conversor": "painel_conversor", "configuracoes": "painel_configuracoes",
                "automacao": "painel_whatsapp_ofertas", "campanhas": "painel_whatsapp_campanhas",
                "mensagens": "painel_whatsapp_mensagens", "alerta": "painel_whatsapp_alertas", "site": "painel_meu_site",
                "carrosseis": "painel_carrosseis", "notas": "painel_notas", "sugestoes": "painel_sugestoes",
            }.items()},
        },
        "numeros": None, "sugerir_emissor": False,
    }
    if chave == "como_vai":
        dados["numeros"] = _numeros_30_dias(conta, hoje) if conta.pk else {
            "comissao": 287.4, "pedidos": 42, "melhor": {"sub_id": "grupovip", "comissao": 131.9}}
        dados["sugerir_emissor"] = not dados["tem_notas"] and dados["numeros"]["comissao"] >= COMISSAO_PRO_EMISSOR
    return dados


def _automatico(chave: str, d: dict) -> tuple[bool, str, tuple[str, str] | None]:
    """(recebe o texto "com o módulo"?, print, (texto do botão, destino)) de cada e-mail."""
    tem_bot = d["tem_bot"]
    if chave == "bot":
        return (tem_bot, "bot-ofertas.jpg", ("Abrir a Automação", "automacao")) if tem_bot else \
            (False, "conversor.jpg", ("Abrir o Conversor", "conversor"))
    if chave == "resultados":
        return True, "resultados.jpg", ("Ver meus resultados", "resultados")
    if chave == "radar":
        return True, "radar-produtos.jpg", ("Abrir o Radar", "radar")
    if chave == "campanhas":
        return (True, "bot-campanhas.jpg", ("Abrir as Campanhas", "campanhas")) if tem_bot else \
            (False, "", ("Abrir o Radar", "radar"))
    if chave == "site_carrosseis":
        if d["tem_site"] or d["tem_carrosseis"]:
            return True, "site-editor.jpg" if d["tem_site"] else "carrossel-editor.jpg", ("Abrir o Appfiliado", "inicio")
        return False, "carrossel-editor.jpg", ("Ver os planos", "planos")
    if chave == "como_vai":
        return True, "", ("Sugerir uma melhoria", "sugestoes")
    return True, "", None


def _condicoes(d: dict) -> dict:
    return {"bot": d["tem_bot"], "premium": d["premium_bot"], "site": d["tem_site"], "carrosséis": d["tem_carrosseis"],
            "carrosseis": d["tem_carrosseis"], "carrosséis premium": d["premium_carrosseis"],
            "carrosseis premium": d["premium_carrosseis"], "notas": d["tem_notas"], "api": d["shopee_conectada"],
            "emissor": d["sugerir_emissor"]}


def _inline(texto: str, d: dict) -> str:
    from django.utils.html import escape

    texto = escape(texto).replace("{nome}", escape(d["nome"]) or "")

    def link(m):
        destino = d["links"].get(m.group(2).strip(), m.group(2).strip() if m.group(2).strip().startswith("https://") else "")
        return f'<a href="{destino}" style="{ESTILO_LINK}">{m.group(1)}</a>' if destino else m.group(1)

    texto = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, texto)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)


def _numeros_html(d: dict) -> str:
    from .templatetags.painel_extras import brl, numero

    n = d["numeros"] or {}
    if n.get("pedidos"):
        melhor = (f" O lugar que mais vendeu foi <strong>{n['melhor']['sub_id']}</strong> ({brl(n['melhor']['comissao'])})."
                  if n.get("melhor") else "")
        return (f"Nos últimos 30 dias, os seus links geraram <strong>{brl(n['comissao'])} de comissão estimada</strong> em "
                f"<strong>{numero(n['pedidos'])} pedido{'s' if n['pedidos'] != 1 else ''}</strong>.{melhor}")
    if d["shopee_conectada"]:
        return ("Ainda não vi vendas nos seus links nos últimos 30 dias. Se quiser, responda este e-mail contando como "
                "você está divulgando que eu te ajudo a achar o caminho.")
    return ("Ainda não consigo ver os seus números porque a API da Shopee não está conectada. Leva poucos minutos: é em "
            f'<a href="{d["links"]["configuracoes"]}" style="{ESTILO_LINK}">Configurações</a>, no painel.')


def formatar(texto: str, d: dict, imagem: str = "", botao: tuple[str, str] | None = None) -> str:
    """O texto no formato simples (ver textos_dicas.py) em HTML de e-mail."""
    condicoes = _condicoes(d)
    linhas = []
    for linha in (texto or "").replace("\r\n", "\n").split("\n"):
        achado = re.match(r"\s*\[(sem )?([a-zçãéí ]+)\]\s+(?!\()", linha, flags=re.I)
        if achado and achado.group(2).strip().lower() in condicoes:
            vale = condicoes[achado.group(2).strip().lower()]
            if bool(achado.group(1)) == bool(vale):
                continue
            linha = linha[achado.end():]
        linhas.append(linha)
    blocos, atual = [], []
    for linha in linhas + [""]:
        if linha.strip():
            atual.append(linha.strip())
        elif atual:
            blocos.append(atual)
            atual = []
    html = []
    for bloco in blocos:
        primeira = bloco[0]
        if len(bloco) == 1 and primeira == "{imagem}":
            if imagem:
                html.append(f'<img src="{d["img"]}{imagem}" width="552" alt="" style="display:block;width:100%;max-width:552px;'
                            'height:auto;margin:4px 0 18px;border:1px solid #E5DFCD;border-radius:10px;">')
            continue
        if len(bloco) == 1 and primeira == "{botao}":
            if botao:
                html.append('<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 18px;"><tr>'
                            '<td style="background:#F2C230;border-radius:10px;">'
                            f'<a href="{d["links"].get(botao[1], botao[1])}" style="display:inline-block;padding:12px 20px;'
                            f'font-size:15px;font-weight:bold;color:#1F3A2E;text-decoration:none;">{botao[0]}</a></td></tr></table>')
            continue
        if len(bloco) == 1 and primeira == "{numeros}":
            html.append(f'<p style="{ESTILO_P}">{_numeros_html(d)}</p>')
            continue
        normais = []
        for linha in bloco:
            if linha.startswith("↳"):
                if normais:
                    html.append(f'<p style="{ESTILO_P}">{"<br>".join(normais)}</p>')
                    normais = []
                html.append(f'<div style="{ESTILO_ITEM}">↳ {_inline(linha[1:].strip(), d)}</div>')
            else:
                normais.append(_inline(linha, d))
        if not normais:
            html[-1] = html[-1].replace(ESTILO_ITEM, ESTILO_ITEM + "margin-bottom:16px;", 1)
            continue
        dica = re.match(r"(minha dica|dica|lembrete):\s*", bloco[0], flags=re.I) and not bloco[0].startswith("↳")
        if dica:
            prefixo, resto = normais[0].split(":", 1)
            normais[0] = f"<strong>{prefixo}:</strong>{resto}"
            html.append(f'<div style="{ESTILO_DICA}">{"<br>".join(normais)}</div>')
        else:
            html.append(f'<p style="{ESTILO_P}">{"<br>".join(normais)}</p>')
    return "\n".join(html)


def montar(conta, chave: str, hoje: date | None = None, liberados=None, texto=None) -> tuple[str, str, str]:
    """(assunto, texto, html). texto: um TextoEmailDica (a prévia do admin passa o que está sendo editado)."""
    texto = texto or texto_do_email(chave)
    d = contexto(conta, chave, hoje, liberados)
    com_modulo, imagem, botao = _automatico(chave, d)
    corpo = formatar(texto.texto if com_modulo or not texto.texto_sem.strip() else texto.texto_sem, d, imagem, botao)
    html = render_to_string("painel/emails/valor/_base.html", {**d, "corpo": corpo, "p": ESTILO_P})
    # Versão em texto: os botões e links viram "texto: endereço"; as imagens saem.
    meio = html.split("<!--corpo-->")[1].split("<!--/corpo-->")[0]
    meio = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f"{strip_tags(m.group(2)).strip()}: {m.group(1)}",
                  meio, flags=re.S)
    meio = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", meio)
    linhas = [re.sub(r"[ \t]+", " ", linha).strip() for linha in unescape(strip_tags(meio)).splitlines()]
    texto_puro = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    texto_puro += f"\n\nNão quer mais receber estas dicas? {d['url_parar']}"
    return texto.assunto, texto_puro, html


def enviar(conta, chave: str, hoje: date | None = None, para: list[str] | None = None, **kwargs) -> None:
    assunto, texto, html = montar(conta, chave, hoje, **kwargs)
    endereco = parseaddr(settings.APPFILIADO_EMAIL_REMETENTE)[1]
    mensagem = EmailMultiAlternatives(
        subject=assunto, body=texto, to=para or [conta.email], from_email=formataddr((REMETENTE, endereco)),
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
        ativos = {t.chave: t.ativo for t in TextoEmailDica.objects.all()}
        for chave, dia in SEQUENCIA:
            pronto = ativos[chave] if chave in ativos else TEXTOS[chave].get("ativo", True)
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
