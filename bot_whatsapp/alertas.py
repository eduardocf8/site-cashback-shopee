"""Alerta de preço (aba do Bot de WhatsApp): a conta escolhe produtos da Shopee e, de
tempos em tempos (no intervalo que escolher, a partir do mínimo do plano), o worker
confere o preço de cada um na API de afiliados. Quando o preço cai pelo menos a "queda
mínima" (%), o alerta aparece no painel e, se a pessoa quiser, chega por e-mail e sai
nos grupos do WhatsApp com o link de afiliado.

A queda é medida contra a "referência" de cada produto: começa no preço de quando ele
foi adicionado, sobe junto se o preço subir e vira o preço novo a cada alerta - assim o
mesmo desconto não avisa duas vezes, e um produto que subiu e voltou a cair avisa."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections
from django.template.loader import render_to_string
from django.utils import timezone

from licencas import planos

from . import copia, shopee_ofertas
from .models import (
    AlertaDisparado, AlertaPreco, ConexaoWhatsApp, ConfiguracaoOfertas, EnvioWhatsApp, ProdutoAcompanhado,
)

logger = logging.getLogger(__name__)

INTERVALO_MOTOR = 30  # segundos entre uma conferência e outra da fila
PONTOS_NO_HISTORICO = 60
SUB_ID = "alerta"  # Sub ID do link de afiliado do e-mail e do painel (em Resultados)
MAXIMO_LINKS_POR_VEZ = 10
CONFERIR_AGORA_A_CADA = timedelta(minutes=5)


class LimiteDoPlano(Exception):
    """Mensagem pronta para a tela."""


def regras(conta) -> dict:
    from licencas.models import MODULO_WHATSAPP

    liberados = conta.modulos_liberados()
    return {**planos.bot(liberados), "liberado": MODULO_WHATSAPP in liberados}


def intervalo_efetivo(alerta, regras_da_conta) -> int:
    return max(alerta.intervalo_minutos, regras_da_conta["alerta_intervalo_minimo"])


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def moeda(valor) -> str:
    texto = f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


# --- Produtos ------------------------------------------------------------------------

def adicionar(conta, produto: dict) -> tuple[ProdutoAcompanhado, bool]:
    """(produto acompanhado, se é novo). Levanta LimiteDoPlano."""
    existente = ProdutoAcompanhado.objects.filter(conta=conta, item_id=produto["item_id"]).first()
    if existente:
        return existente, False
    limite = regras(conta)["alerta_produtos"]
    if ProdutoAcompanhado.objects.filter(conta=conta).count() >= limite:
        raise LimiteDoPlano(f"Seu plano acompanha até {limite} produtos. Remova algum para adicionar outro.")
    preco = _dinheiro(produto.get("preco"))
    novo = ProdutoAcompanhado.objects.create(
        conta=conta, item_id=produto["item_id"], nome=(produto.get("nome") or "")[:300],
        imagem=(produto.get("imagem") or "")[:1000], link=(produto.get("link") or "")[:1000],
        preco_inicial=preco, preco_atual=preco, menor_preco=preco, referencia=preco,
        historico=[[timezone.now().isoformat(timespec="minutes"), float(preco)]], conferido_em=timezone.now(),
    )
    return novo, True


def produto_da_shopee(conta, item_id: str) -> dict | None:
    from .ofertas import credenciais

    app_id, secret = credenciais(conta)
    return shopee_ofertas.buscar_produto_por_item(app_id, secret, item_id)


def adicionar_item(conta, item_id: str) -> tuple[ProdutoAcompanhado, bool]:
    """Pela vitrine ou pelas ofertas do bot: busca o preço de agora na Shopee."""
    produto = produto_da_shopee(conta, item_id)
    if not produto:
        raise LimiteDoPlano("A Shopee não devolveu esse produto agora (sem estoque ou sem comissão de afiliado).")
    return adicionar(conta, produto)


def adicionar_links(conta, texto: str) -> dict:
    """Cola um ou vários links: {"adicionados", "ja_tinha", "erros"} (nomes/links)."""
    links = list(dict.fromkeys(copia.links_shopee(texto)))
    if not links:
        raise LimiteDoPlano("Não achei nenhum link da Shopee. Cole o link do produto.")
    if len(links) > MAXIMO_LINKS_POR_VEZ:
        raise LimiteDoPlano(f"Cole até {MAXIMO_LINKS_POR_VEZ} links por vez.")

    def achar(link):
        try:
            item_id = copia.identificar_produto(link)
            return link, produto_da_shopee(conta, item_id) if item_id else None
        except Exception:  # noqa: BLE001
            logger.warning("Alerta de preço: não achei o produto de %s", link, exc_info=True)
            return link, None

    with ThreadPoolExecutor(max_workers=min(5, len(links))) as fila:
        achados = list(fila.map(achar, links))
    resultado = {"adicionados": [], "ja_tinha": [], "erros": []}
    for link, produto in achados:
        if not produto:
            resultado["erros"].append(link)
            continue
        acompanhado, novo = adicionar(conta, produto)  # LimiteDoPlano para tudo: a tela avisa
        resultado["adicionados" if novo else "ja_tinha"].append(acompanhado.nome)
    return resultado


def buscar_na_vitrine(conta, palavra: str) -> list[dict]:
    from .ofertas import credenciais

    app_id, secret = credenciais(conta)
    busca = ConfiguracaoOfertas(tipo_busca=ConfiguracaoOfertas.BUSCA_PALAVRA, palavra_chave=palavra[:120],
                                ordenacao="mais_vendidos")
    produtos, _ = shopee_ofertas.buscar_produtos(app_id, secret, busca, 1)
    return produtos[:12]


# --- Conferência ---------------------------------------------------------------------

def registrar_preco(produto: ProdutoAcompanhado, preco: Decimal, agora, queda_minima: int) -> AlertaDisparado | None:
    """Guarda o preço novo e devolve o alerta, se a queda chegou à mínima."""
    preco = _dinheiro(preco)
    if produto.preco_atual != preco:
        produto.historico = (list(produto.historico or []) + [[agora.isoformat(timespec="minutes"), float(preco)]])[-PONTOS_NO_HISTORICO:]
    produto.preco_atual = preco
    produto.menor_preco = min(produto.menor_preco, preco) if produto.menor_preco is not None else preco
    referencia = max(produto.referencia or preco, preco)  # subiu: a referência acompanha
    alerta = None
    if preco < referencia and (referencia - preco) / referencia * 100 >= max(1, queda_minima):
        queda = ((referencia - preco) / referencia * 100).quantize(Decimal("0.1"))
        alerta = AlertaDisparado.objects.create(
            conta=produto.conta, produto=produto, nome=produto.nome, imagem=produto.imagem,
            preco_antes=referencia, preco_agora=preco, queda=queda,
        )
        referencia = preco
        produto.ultimo_alerta_em = agora
    produto.referencia = referencia
    produto.indisponivel = False
    produto.conferido_em = agora
    produto.save()
    return alerta


def conferir(alerta: AlertaPreco, agora) -> list[AlertaDisparado]:
    """Confere todos os produtos da conta (até o limite do plano) e avisa das quedas."""
    from .ofertas import credenciais

    conta = alerta.conta
    app_id, secret = credenciais(conta)
    limite = regras(conta)["alerta_produtos"]
    disparados, falhas = [], 0
    for produto in ProdutoAcompanhado.objects.filter(conta=conta).order_by("adicionado_em")[:limite]:
        try:
            achado = shopee_ofertas.buscar_produto_por_item(app_id, secret, produto.item_id)
        except Exception:  # noqa: BLE001 - um produto com problema não para os outros
            logger.warning("Alerta de preço: erro ao conferir %s", produto.item_id, exc_info=True)
            falhas += 1
            continue
        if not achado or not achado.get("preco"):
            produto.indisponivel, produto.conferido_em = True, agora
            produto.save(update_fields=["indisponivel", "conferido_em"])
            continue
        produto.nome = (achado.get("nome") or produto.nome)[:300]
        produto.imagem = (achado.get("imagem") or produto.imagem)[:1000]
        produto.link = (achado.get("link") or produto.link)[:1000]
        disparado = registrar_preco(produto, achado["preco"], agora, alerta.queda_minima)
        if disparado:
            disparados.append(disparado)
    if falhas:
        alerta.ultimo_erro = f"Não deu para conferir {falhas} produto{'s' if falhas > 1 else ''} agora. Tento de novo na próxima vez."
    if disparados:
        avisar(alerta, disparados)
    return disparados


# --- Avisos --------------------------------------------------------------------------

def montar_mensagem(modelo: str, nome: str, antes, agora_, queda, link: str) -> str:
    """Troca os campos do modelo ({produto}, {preco_antes}, {preco_agora}, {queda}, {link}).
    Sem {link} no modelo, o link vai no fim (a mensagem precisa dele)."""
    texto = (modelo or "").strip() or ""
    if not texto:
        from .models import MODELO_ALERTA_PADRAO

        texto = MODELO_ALERTA_PADRAO
    campos = {"{produto}": nome, "{preco_antes}": moeda(antes), "{preco_agora}": moeda(agora_),
              "{queda}": f"{float(queda):g}%".replace(".", ","), "{link}": link}
    if "{link}" not in texto:
        texto += "\n\n{link}"
    for campo, valor in campos.items():
        texto = texto.replace(campo, valor)
    return texto


def avisar(alerta: AlertaPreco, disparados: list[AlertaDisparado]) -> None:
    from .ofertas import credenciais

    conta = alerta.conta
    app_id, secret = credenciais(conta)
    for d in disparados:  # link de afiliado do painel e do e-mail (Sub ID "alerta")
        try:
            d.link_afiliado = shopee_ofertas.gerar_link_afiliado(app_id, secret, d.produto.link, [SUB_ID])[:500]
        except Exception:  # noqa: BLE001
            logger.warning("Alerta de preço: sem link de afiliado para %s", d.produto_id, exc_info=True)
            d.link_afiliado = (d.produto.link or "")[:500]
        d.save(update_fields=["link_afiliado"])
    if alerta.avisar_email:
        try:
            enviar_email(conta, disparados)
            AlertaDisparado.objects.filter(pk__in=[d.pk for d in disparados]).update(enviado_email=True)
        except Exception:  # noqa: BLE001
            logger.exception("Alerta de preço: e-mail da conta %s não foi", conta.pk)
            alerta.ultimo_erro = "O e-mail do alerta não foi enviado. Os alertas estão aqui no painel."
    if alerta.enviar_grupos:
        postar_nos_grupos(alerta, disparados)


def enviar_email(conta, disparados: list[AlertaDisparado]) -> None:
    from painel.emails import url_do_painel
    from painel.relatorio import url_do_logo

    total = len(disparados)
    assunto = (f"Appfiliado — {disparados[0].nome[:60]} baixou {float(disparados[0].queda):g}%".replace(".", ",")
               if total == 1 else f"Appfiliado — {total} produtos baixaram de preço")
    dados = {"alertas": disparados, "url_alertas": url_do_painel("painel_whatsapp_alertas"), "url_logo": url_do_logo()}
    mensagem = EmailMultiAlternatives(
        subject=assunto, body=render_to_string("painel/email_alerta_preco.txt", dados), to=[conta.email],
        from_email=settings.APPFILIADO_EMAIL_REMETENTE,
    )
    mensagem.attach_alternative(render_to_string("painel/email_alerta_preco.html", dados), "text/html")
    mensagem.send()


def postar_nos_grupos(alerta: AlertaPreco, disparados: list[AlertaDisparado]) -> None:
    from .ofertas import MARCADOR_DO_LINK, enfileirar

    from .ofertas import grupos_do_plano

    conta = alerta.conta
    conexao = ConexaoWhatsApp.objects.filter(conta=conta).first()
    # Os mesmos grupos da Automação (até o máximo do plano), com os Sub IDs de cada um.
    config, _ = ConfiguracaoOfertas.objects.get_or_create(conta=conta)
    grupos = grupos_do_plano(config)
    if not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO:
        alerta.ultimo_erro = "Não postei nos grupos: conecte o WhatsApp na aba Conexão."
        return
    if not grupos:
        alerta.ultimo_erro = "Não postei nos grupos: escolha os grupos na aba Automação."
        return
    for d in disparados:
        texto = montar_mensagem(alerta.modelo_mensagem, d.nome, d.preco_antes, d.preco_agora, d.queda, MARCADOR_DO_LINK)
        try:
            enfileirar(config, grupos, texto, d.produto.link, item_id=d.produto.item_id, nome=d.nome,
                       imagem_url=d.imagem, origem=EnvioWhatsApp.ALERTA)
            d.postado_grupos = True
            d.save(update_fields=["postado_grupos"])
        except Exception:  # noqa: BLE001
            logger.warning("Alerta de preço: não postei %s nos grupos", d.pk, exc_info=True)
            alerta.ultimo_erro = "Não deu para postar um alerta nos grupos. Os alertas estão aqui no painel."


# --- Motor (thread do worker) ------------------------------------------------------------

class Motor:
    def rodar(self):
        while True:
            close_old_connections()
            try:
                self.uma_volta()
            except Exception:  # noqa: BLE001 - o worker não pode cair por causa disso
                logger.exception("Alerta de preço: erro no motor")
            time.sleep(INTERVALO_MOTOR)

    def uma_volta(self, agora=None):
        from django.db.models import Q

        agora = agora or timezone.now()
        vez = Q(ativo=True) & (Q(proxima_conferencia_em__isnull=True) | Q(proxima_conferencia_em__lte=agora))
        for alerta in AlertaPreco.objects.filter(vez | Q(pedido_conferir_em__isnull=False)).select_related("conta"):
            self.atender(alerta, agora)

    @staticmethod
    def _reservar(alerta, proxima) -> bool:
        """Só um processo confere esta vez (num deploy, dois workers rodam juntos)."""
        mesma = AlertaPreco.objects.filter(pk=alerta.pk, pedido_conferir_em=alerta.pedido_conferir_em)
        mesma = (mesma.filter(proxima_conferencia_em=alerta.proxima_conferencia_em) if alerta.proxima_conferencia_em
                 else mesma.filter(proxima_conferencia_em__isnull=True))
        if not mesma.update(proxima_conferencia_em=proxima, pedido_conferir_em=None):
            return False
        alerta.proxima_conferencia_em, alerta.pedido_conferir_em = proxima, None
        return True

    def atender(self, alerta, agora):
        conta = alerta.conta
        regras_da_conta = regras(conta)
        proxima = agora + timedelta(minutes=intervalo_efetivo(alerta, regras_da_conta))
        if not self._reservar(alerta, proxima):
            return
        if not regras_da_conta["liberado"]:
            alerta.ultimo_erro = "O alerta de preço é do Bot de WhatsApp. Renove a assinatura para voltar a conferir."
        elif not conta.shopee_configurada:
            alerta.ultimo_erro = "Conecte sua conta da Shopee em Configurações."
        else:
            alerta.ultimo_erro = ""
            try:
                conferir(alerta, agora)
            except Exception as erro:  # noqa: BLE001
                logger.exception("Alerta de preço: erro na conta %s", conta.pk)
                alerta.ultimo_erro = f"Deu erro ao conferir os preços: {str(erro)[:300]}"
            alerta.ultima_conferencia_em = agora
        alerta.save(update_fields=["ultimo_erro", "ultima_conferencia_em", "atualizado_em"])


def iniciar_em_segundo_plano() -> Motor:
    motor = Motor()
    threading.Thread(target=motor.rodar, name="alerta-de-preco", daemon=True).start()
    return motor
