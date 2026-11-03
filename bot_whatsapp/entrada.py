"""Link de entrada nos grupos: a página do anúncio que manda a pessoa pro grupo com vaga.

- Página: seunome.appfiliado.com.br/<slug>/ (meusite/entrada.py), com o pixel do Meta da pessoa. O
  endereço antigo, com /g/<slug>/, continua valendo.
- Ordem: os grupos do link enchem na ordem do nome ("#1", "#2"... em ordem numérica). O da vez é
  o primeiro que ainda não chegou no limite e tem link de convite.
- Membros: vêm da aba Grupos (os grupos do link são acompanhados sozinhos).
- Convites: o worker lê o link de convite de cada grupo (o número do bot precisa ser administrador);
  sem isso, a pessoa cola o link à mão.
- Lotando: quando nenhum grupo tem vaga folgada, a pessoa recebe um aviso e, se pediu, o Appfiliado
  cria o próximo grupo sozinho (grupos_novos.py) e coloca no link.

Faz parte do Bot de WhatsApp (Standard e Premium). Criar o próximo grupo sozinho é do Premium."""

import logging
import re
import threading
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection
from django.db.models import F, Sum
from django.utils import timezone

from accounts.ratelimit import _obter_ip
from cashback_shopee import meta_capi
from licencas import planos
from licencas.models import MODULO_WHATSAPP
from painel import cripto

from . import grupos_novos, membros
from .models import AcessoEntrada, ConexaoWhatsApp, ConviteGrupo, GrupoMonitorado, LinkEntrada, PedidoGrupo

logger = logging.getLogger(__name__)

FOLGA = 95  # % do limite: daí pra cima o grupo conta como "lotando"
RELER_CONVITE = timedelta(hours=12)
INTERVALO_DO_AVISO = timedelta(hours=24)
PADRAO_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")
# Os nomes das outras páginas do Meu site (meusite/urls_publico.py) e alguns que podem vir a ser usados.
SLUGS_RESERVADOS = {"b", "p", "r", "g", "s", "ir", "foto", "capa", "entrar", "admin", "api", "static", "media",
                    "favicon", "robots", "sitemap", "login", "sair", "painel", "www"}
# Quem abre o link só para montar a prévia (o navegador do Instagram e do Facebook, de onde vem o
# anúncio, não está aqui: esse é gente de verdade).
ROBOS = ("facebookexternalhit", "facebot", "whatsapp/", "telegrambot", "twitterbot", "googlebot", "bingbot",
         "crawler", "spider", "slurp")


def liberado(conta) -> bool:
    return MODULO_WHATSAPP in conta.modulos_liberados()


def ordem_natural(nome: str):
    """"Grupo #10" depois de "Grupo #9"."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", nome or "")]


# --- Grupos do link --------------------------------------------------------------------------

def salvar_grupos(link: LinkEntrada, jids: list[str], conexao) -> None:
    """Guarda os grupos do link (só os do número do bot), acompanha os membros deles na aba Grupos
    e prepara o link de convite de cada um (o worker lê)."""
    possiveis = {g["jid"]: g for g in membros.grupos_possiveis(conexao)}
    escolhidos = [j for j in dict.fromkeys(jids) if j in possiveis]
    link.grupos = escolhidos
    link.save(update_fields=["grupos", "atualizado_em"])
    membros.garantir(link.conta, escolhidos, conexao)
    for jid in escolhidos:
        ConviteGrupo.objects.get_or_create(conta=link.conta, jid=jid)


def situacao(link: LinkEntrada) -> dict:
    """Os grupos do link na ordem em que enchem, com membros, convite e o grupo da vez."""
    monitorados = {g.jid: g for g in GrupoMonitorado.objects.filter(conta=link.conta, jid__in=link.grupos)}
    convites = {c.jid: c for c in ConviteGrupo.objects.filter(conta=link.conta, jid__in=link.grupos)}
    linhas = []
    for jid in link.grupos:
        grupo = monitorados.get(jid)
        quantos = grupo.membros if grupo and grupo.membros is not None else 0
        convite = convites.get(jid)
        linhas.append({
            "jid": jid, "nome": grupo.nome if grupo else jid, "membros": quantos,
            "cheio": quantos >= link.limite_por_grupo, "lotando": quantos * 100 >= link.limite_por_grupo * FOLGA,
            "convite": convite.link if convite else "", "manual": bool(convite and convite.manual),
            "erro_convite": convite.erro if convite else "", "no_grupo": grupo.no_grupo if grupo else True,
            "ocupacao": min(100, round(quantos * 100 / link.limite_por_grupo)) if link.limite_por_grupo else 0,
        })
    linhas.sort(key=lambda linha: ordem_natural(linha["nome"]))
    da_vez = next((l for l in linhas if not l["cheio"] and l["convite"] and l["no_grupo"]), None)
    return {"grupos": linhas, "da_vez": da_vez, "folgados": sum(1 for l in linhas if not l["lotando"] and l["no_grupo"])}


def grupo_da_vez(link: LinkEntrada) -> dict | None:
    return situacao(link)["da_vez"]


# --- API de Conversões do Meta ------------------------------------------------------------------
# A página manda PageView e Lead pelo pixel (navegador). Com o token salvo, os mesmos eventos também
# saem pelo servidor, com o mesmo event_id: o Meta junta os dois e não conta duas vezes. O id nasce
# na página (id_do_evento) e vai no toque do botão (?eid=) para o Lead dos dois lados bater.

PADRAO_EID = re.compile(r"^[0-9a-f]{32}$")
PADRAO_TOKEN = re.compile(r"^[A-Za-z0-9_|-]{30,1000}$")


def id_do_evento(valor: str = "") -> str:
    valor = str(valor or "")
    return valor if PADRAO_EID.match(valor) else uuid.uuid4().hex


def tem_api_de_conversoes(link: LinkEntrada) -> bool:
    return bool(link.pixel_id and link.capi_token_cifrado)


def _dados_da_pessoa(request) -> dict:
    """IP, navegador e os identificadores do clique no anúncio (fbp, fbc): é com eles que o Meta
    liga o evento a quem viu o anúncio. Na primeira visita o cookie _fbc ainda não existe, mas o
    fbclid do anúncio vem na URL."""
    dados = {"client_user_agent": request.META.get("HTTP_USER_AGENT", "")}
    ip = _obter_ip(request)
    if ip and ip != "desconhecido":
        dados["client_ip_address"] = ip
    if request.COOKIES.get("_fbp"):
        dados["fbp"] = request.COOKIES["_fbp"]
    fbclid = str(request.GET.get("fbclid") or "").strip()[:500]
    if request.COOKIES.get("_fbc"):
        dados["fbc"] = request.COOKIES["_fbc"]
    elif fbclid:
        dados["fbc"] = f"fb.1.{int(time.time() * 1000)}.{fbclid}"
    return dados


def evento_no_servidor(link: LinkEntrada, request, nome: str, event_id: str, url: str) -> None:
    """Manda o evento pela API de Conversões, sem segurar a página (em segundo plano), e guarda no
    link se o Meta aceitou (o painel mostra)."""
    if not tem_api_de_conversoes(link):
        return
    token = cripto.decifrar(link.capi_token_cifrado)
    if not token:
        return
    evento = {"event_name": nome, "event_time": int(time.time()), "event_id": event_id,
              "action_source": "website", "event_source_url": url, "user_data": _dados_da_pessoa(request)}
    pk, pixel = link.pk, link.pixel_id

    def enviar():
        erro = meta_capi.mandar(pixel, token, [evento])
        LinkEntrada.objects.filter(pk=pk).update(capi_enviado_em=timezone.now(), capi_erro=erro)

    _em_segundo_plano(enviar)


def _em_segundo_plano(funcao) -> None:
    def rodar():
        try:
            funcao()
        except Exception:
            logger.exception("Link de entrada: falha ao mandar evento pela API de Conversões")
        finally:
            connection.close()  # a conexão é desta thread

    threading.Thread(target=rodar, daemon=True).start()


# --- Contagem ---------------------------------------------------------------------------------

def e_robo(request) -> bool:
    """O Meta e o WhatsApp abrem o link para montar a prévia: não conta como visita."""
    agente = (request.META.get("HTTP_USER_AGENT") or "").lower()
    return not agente or any(r in agente for r in ROBOS)


def contar(link: LinkEntrada, campanha: str = "", grupo_jid: str = "", clique: bool = False) -> None:
    registro, _ = AcessoEntrada.objects.get_or_create(
        link=link, dia=timezone.localdate(), grupo_jid=grupo_jid if clique else "", campanha=str(campanha or "")[:80])
    campo = "cliques" if clique else "visitas"
    AcessoEntrada.objects.filter(pk=registro.pk).update(**{campo: F(campo) + 1})


def estatisticas(link: LinkEntrada, hoje=None) -> dict:
    hoje = hoje or timezone.localdate()
    acessos = AcessoEntrada.objects.filter(link=link)

    def soma(desde):
        total = acessos.filter(dia__gte=desde).aggregate(v=Sum("visitas"), c=Sum("cliques"))
        visitas, cliques = total["v"] or 0, total["c"] or 0
        return {"visitas": visitas, "cliques": cliques, "taxa": round(cliques * 100 / visitas) if visitas else None}

    trinta = hoje - timedelta(days=29)
    por_grupo = dict(acessos.filter(dia__gte=trinta).exclude(grupo_jid="").values("grupo_jid")
                     .annotate(total=Sum("cliques")).values_list("grupo_jid", "total"))
    por_campanha = list(acessos.filter(dia__gte=trinta).exclude(campanha="").values("campanha")
                        .annotate(visitas=Sum("visitas"), cliques=Sum("cliques")).order_by("-cliques")[:10])
    return {"hoje": soma(hoje), "sete": soma(hoje - timedelta(days=6)), "trinta": soma(trinta),
            "por_grupo": por_grupo, "por_campanha": por_campanha}


# --- Worker -----------------------------------------------------------------------------------

def convites_para_ler(agora) -> list[ConviteGrupo]:
    """Convites que o worker precisa ler (novos ou com mais de 12 h), dos links ativos de quem tem o Bot."""
    from django.db.models import Q

    vencidos = Q(lido_em__isnull=True) | Q(lido_em__lt=agora - RELER_CONVITE)
    convites = (ConviteGrupo.objects.filter(vencidos, manual=False, conta__links_entrada__ativo=True).distinct()
                .select_related("conta").order_by("lido_em")[:20])
    return [c for c in convites if liberado(c.conta)]


def registrar_convite(convite: ConviteGrupo, link: str, erro: str, agora) -> None:
    convite.link, convite.erro, convite.lido_em = (link or convite.link)[:200], erro[:300], agora
    convite.save(update_fields=["link", "erro", "lido_em"])


def cuidar_dos_links(agora) -> list[str]:
    """Links ativos sem grupo folgado: avisa a pessoa (uma vez por dia) e, se ela pediu, cria o
    próximo grupo (até grupos_novos.POR_DIA por dia). Devolve uma linha de log por ação."""
    logs = []
    for link in LinkEntrada.objects.filter(ativo=True).defer("foto").select_related("conta"):
        if not link.grupos or not liberado(link.conta):  # sem o Bot (assinatura acabou): não avisa nem cria
            continue
        estado = situacao(link)
        if estado["folgados"]:
            continue
        criando = PedidoGrupo.objects.filter(link_entrada=link, estado=PedidoGrupo.PENDENTE).exists()
        pedido = None
        premium = planos.bot_premium(link.conta)  # criar sozinho é do Premium; os outros planos só recebem o aviso
        if (link.criar_sozinho and premium and not criando
                and grupos_novos.criados_hoje(link.conta, agora) < grupos_novos.POR_DIA):
            pedido = _pedir_o_proximo(link, estado, agora)
            if pedido:
                logs.append(f"Link de entrada {link.pk}: pedindo o grupo {pedido.nome}")
        if not criando and (not link.aviso_lotando_em or agora - link.aviso_lotando_em > INTERVALO_DO_AVISO):
            _avisar(link, estado, pedido, premium)
            link.aviso_lotando_em = agora
            link.save(update_fields=["aviso_lotando_em"])
    return logs


def _pedir_o_proximo(link: LinkEntrada, estado: dict, agora) -> PedidoGrupo | None:
    conexao = ConexaoWhatsApp.objects.filter(conta=link.conta).first()
    if not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO:
        return None
    from .models import ConfiguracaoOfertas

    ultimo = estado["grupos"][-1]
    automacao = grupos_novos.vagas_na_automacao(link.conta)
    nome = grupos_novos.proximo_nome(ultimo["nome"], grupos_novos.nomes_em_uso(link.conta, conexao))
    config = ConfiguracaoOfertas.objects.filter(conta=link.conta).first()
    return PedidoGrupo.objects.create(
        conta=link.conta, link_entrada=link, base_jid=ultimo["jid"], copiar_foto_e_descricao=True, so_admins=True,
        nome=nome, sub_ids=grupos_novos.sugerir_sub_ids(config, ultimo["jid"], nome),
        administradores=list(link.admins_dos_novos or [])[: grupos_novos.MAXIMO_ADMINS],
        incluir_na_automacao=automacao["vagas"] > 0 and not automacao["sem_automacao"],
    )


def _avisar(link: LinkEntrada, estado: dict, pedido: PedidoGrupo | None, premium: bool = True) -> None:
    from painel.emails import url_do_painel

    if pedido:
        texto = (f"Os grupos do seu link de entrada /{link.slug}/ estão quase cheios, então o Appfiliado está criando "
                 f"o grupo \"{pedido.nome}\" e já vai colocá-lo no link.")
    else:
        texto = (f"Os grupos do seu link de entrada /{link.slug}/ estão quase cheios (todos com mais de {FOLGA}% do "
                 f"limite de {link.limite_por_grupo} pessoas). Crie o próximo grupo e coloque no link para não perder "
                 "quem clica no anúncio.")
        if not premium:
            texto += " No plano Premium, o Appfiliado cria o próximo grupo sozinho e já coloca no link."
    try:
        send_mail("Appfiliado: os grupos do seu link de entrada estão lotando",
                  f"{texto}\n\nVeja no painel: {url_do_painel('painel_whatsapp_entrada')}",
                  settings.APPFILIADO_EMAIL_REMETENTE, [link.conta.email])
    except Exception:  # noqa: BLE001 - o aviso no painel continua aparecendo
        logger.exception("Link de entrada: não deu para mandar o aviso de lotação do link %s", link.pk)


def grupo_criado(pedido: PedidoGrupo, jid: str, link_convite: str, agora) -> None:
    """Chamado quando o grupo de um pedido do link fica pronto: entra no link, já com o convite."""
    link = pedido.link_entrada
    if not link:
        return
    if jid not in link.grupos:
        link.grupos = [*link.grupos, jid]
        link.save(update_fields=["grupos", "atualizado_em"])
    ConviteGrupo.objects.update_or_create(conta=link.conta, jid=jid,
                                          defaults={"link": link_convite[:200], "lido_em": agora, "erro": ""})
