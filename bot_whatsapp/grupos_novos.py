"""Criar o próximo grupo pelo Appfiliado (aba Grupos).

O painel só registra o pedido (PedidoGrupo); quem cria é o worker, pelo número conectado
(gerenciador.criar_grupos), porque só ele fala com o WhatsApp. O grupo nasce vazio: só o número do
bot e os administradores escolhidos. Quem entra depois é quem clica no link de convite.

O WhatsApp desconfia de número que cria muitos grupos em pouco tempo: POR_DIA por conta."""

import re
import unicodedata

from django.db import transaction
from django.utils import timezone

from .models import ConexaoWhatsApp, ConfiguracaoOfertas, GrupoMonitorado, PedidoGrupo

POR_DIA = 5
MAXIMO_ADMINS = 5
TAMANHO_DO_NOME = 100  # limite do WhatsApp para o nome do grupo


# --- Painel -----------------------------------------------------------------------------

def proximo_nome(base: str, existentes) -> str:
    """"Achadinhos #8" -> "Achadinhos #9"; "Ofertas 07" -> "Ofertas 08"; sem número -> "Nome 2".
    Pula os nomes que já existem."""
    base = " ".join(str(base or "").split()) or "Grupo de ofertas"
    usados = {str(n).strip().lower() for n in existentes}
    achou = re.match(r"^(.*?)(\d+)\s*$", base)
    prefixo, numero, largura = (achou.group(1), int(achou.group(2)), len(achou.group(2))) if achou else (base + " ", 1, 1)
    while True:
        numero += 1
        nome = f"{prefixo}{numero:0{largura}d}"[:TAMANHO_DO_NOME]
        if nome.lower() not in usados:
            return nome


def _letras_e_numeros(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", sem_acento).lower()


def sugerir_sub_ids(config, base_jid: str, nome: str) -> str:
    """Sub IDs do grupo novo, para separar as vendas de cada grupo:
    - o grupo de base tem Sub ID próprio: o mesmo, com o número do grupo novo ("bot, achadinhos8" ->
      "bot, achadinhos9");
    - senão: os Sub IDs padrão da Automação + a primeira palavra do nome com o número ("Achadinhos da
      Bia #9" -> "achadinhos9").
    A pessoa pode mudar antes de criar."""
    nome = str(nome or "")
    achou = re.search(r"(\d+)\s*$", nome)
    numero = achou.group(1) if achou else ""
    proprios = (config.sub_ids_por_grupo or {}).get(base_jid, "") if config and base_jid else ""
    lista = [s.strip() for s in proprios.split(",") if s.strip()]
    if lista:
        com_numero = re.match(r"^(.*?)(\d+)$", lista[-1])
        if not numero:
            return ""
        lista[-1] = (com_numero.group(1) if com_numero else lista[-1]) + numero
        return ", ".join(lista)
    palavras = [_letras_e_numeros(p) for p in re.split(r"\s+", re.sub(r"\d+\s*$", "", nome))]
    palavras = [p for p in palavras if p]
    proprio = ((palavras[0] if palavras else "grupo") + numero)[:40] if (palavras or numero) else ""
    padrao = [s.strip() for s in str(config.sub_ids if config else "").split(",") if s.strip()]
    return ", ".join([*padrao, proprio][:5]) if proprio else ""


def ler_sub_ids(texto: str) -> tuple[str, str]:
    """(Sub IDs arrumados "a, b", "") ou ("", motivo)."""
    from .shopee_ofertas import SubIdInvalido, validar_sub_ids

    sub_ids = [s.strip() for s in str(texto or "").split(",") if s.strip()]
    try:
        validar_sub_ids(sub_ids)
    except SubIdInvalido as erro:
        return "", str(erro)
    return ", ".join(sub_ids), ""


def criados_hoje(conta, agora=None) -> int:
    inicio = timezone.localtime(agora or timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return PedidoGrupo.objects.filter(conta=conta, criado_em__gte=inicio).exclude(estado=PedidoGrupo.ERRO).count()


def ler_numeros(texto: str) -> tuple[list[str], list[str]]:
    """"(11) 98888-7777, 5545999990000" -> números com DDI. Devolve (números, os que não entendeu)."""
    numeros, invalidos = [], []
    for parte in re.split(r"[,;\n]+", str(texto or "")):
        if not parte.strip():
            continue
        digitos = re.sub(r"\D", "", parte)
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        if 12 <= len(digitos) <= 15:
            numeros.append(digitos)
        else:
            invalidos.append(parte.strip())
    return list(dict.fromkeys(numeros)), invalidos


def _telefone(numero: str) -> str:
    if numero.startswith("55") and len(numero) in (12, 13):
        return f"({numero[2:4]}) {numero[4:-4]}-{numero[-4:]}"
    return f"+{numero}"


def ultimos_admins(conta) -> str:
    """Os administradores do último pedido (pra não digitar de novo)."""
    ultimo = PedidoGrupo.objects.filter(conta=conta).exclude(administradores=[]).first()
    return ", ".join(_telefone(n) for n in ultimo.administradores) if ultimo else ""


def nomes_em_uso(conta, conexao) -> list[str]:
    """Os nomes dos grupos do número e dos que estão sendo (ou foram) criados pelo Appfiliado."""
    pedidos = PedidoGrupo.objects.filter(conta=conta).exclude(estado=PedidoGrupo.ERRO).values_list("nome", flat=True)
    return [g.get("nome", "") for g in (conexao.grupos if conexao else []) or []] + list(pedidos)


def vagas_na_automacao(conta) -> dict:
    """Quantos grupos ainda cabem na Automação (contando os que estão sendo criados para entrar
    nela). sem_automacao = a pessoa ainda não configurou a Automação."""
    from licencas import planos

    regras = planos.bot(conta)
    config = ConfiguracaoOfertas.objects.filter(conta=conta).first()
    usados = len([g for g in (config.grupos if config else []) or [] if g.get("jid")])
    a_caminho = PedidoGrupo.objects.filter(conta=conta, estado=PedidoGrupo.PENDENTE, incluir_na_automacao=True).count()
    return {"vagas": max(0, regras["grupos"] - usados - a_caminho), "limite": regras["grupos"],
            "premium": regras.get("premium", False), "sem_automacao": config is None}


def pedir(conta, nome: str, base_jid: str, copiar: bool, so_admins: bool, admins_texto: str, incluir: bool,
          sub_ids_texto: str = "") -> tuple[PedidoGrupo | None, str]:
    """Registra o pedido (o worker cria). Devolve (pedido, "") ou (None, motivo)."""
    nome = " ".join(str(nome or "").split())[:TAMANHO_DO_NOME]
    if not nome:
        return None, "Dê um nome ao grupo."
    if criados_hoje(conta) >= POR_DIA:
        return None, (f"Hoje você já criou {POR_DIA} grupos, o máximo do dia. O WhatsApp desconfia de número que cria "
                      "muitos grupos em pouco tempo: amanhã libera de novo.")
    conexao = ConexaoWhatsApp.objects.filter(conta=conta).first()
    if not conexao or conexao.estado != ConexaoWhatsApp.CONECTADO:
        return None, "Conecte o WhatsApp na aba Conexão para criar grupos."
    numeros, invalidos = ler_numeros(admins_texto)
    if invalidos:
        return None, f"Não entendi {'o número' if len(invalidos) == 1 else 'os números'} {', '.join(invalidos)}. Use DDD e número, como (11) 98888-7777."
    sub_ids, motivo = ler_sub_ids(sub_ids_texto)
    if motivo:
        return None, motivo
    numeros = [n for n in numeros if n != conexao.numero][:MAXIMO_ADMINS]
    base_jid = base_jid if any(g.get("jid") == base_jid for g in conexao.grupos or []) else ""
    automacao = vagas_na_automacao(conta)
    incluir = incluir and automacao["vagas"] > 0 and not automacao["sem_automacao"]
    pedido = PedidoGrupo.objects.create(
        conta=conta, nome=nome, base_jid=base_jid, copiar_foto_e_descricao=copiar and bool(base_jid),
        so_admins=so_admins, administradores=numeros, incluir_na_automacao=incluir, sub_ids=sub_ids,
    )
    return pedido, ""


# --- Worker -----------------------------------------------------------------------------

def concluir(pedido: PedidoGrupo, jid: str, link: str, membros: int, avisos: list[str], agora=None) -> None:
    """O grupo foi criado: guarda o link e coloca o grupo na lista do bot, na aba Grupos e (se
    pediu) na Automação, com o mesmo nicho do grupo de base."""
    from .ofertas import regras_do_plano

    agora = agora or timezone.now()
    with transaction.atomic():
        conexao = ConexaoWhatsApp.objects.select_for_update().filter(conta=pedido.conta).first()
        if conexao:
            grupos = [g for g in conexao.grupos or [] if g.get("jid") != jid]
            grupos.append({"jid": jid, "nome": pedido.nome, "participantes": membros, "tipo": "grupo", "admin": True})
            conexao.grupos = sorted(grupos, key=lambda d: (d.get("tipo") != "grupo", str(d.get("nome", "")).lower()))
            conexao.save(update_fields=["grupos", "atualizado_em"])
        GrupoMonitorado.objects.get_or_create(conta=pedido.conta, jid=jid,
                                              defaults={"nome": pedido.nome, "admin": True, "membros": membros})
        config = ConfiguracaoOfertas.objects.select_for_update().filter(conta=pedido.conta).first()
        if config and pedido.sub_ids:
            # Mesmo fora da Automação: se o grupo entrar nela depois, o Sub ID já está lá.
            config.sub_ids_por_grupo = {**(config.sub_ids_por_grupo or {}), jid: pedido.sub_ids}
            config.save(update_fields=["sub_ids_por_grupo", "atualizado_em"])
        if pedido.incluir_na_automacao and config:
            limite = regras_do_plano(config)["grupos"]
            if len([g for g in config.grupos or [] if g.get("jid")]) >= limite:
                avisos.append(f"Não entrou na Automação: ela já está com {limite} grupos, o máximo do seu plano.")
            elif not any(g.get("jid") == jid for g in config.grupos or []):
                config.grupos = [*(config.grupos or []), {"jid": jid, "nome": pedido.nome}]
                if pedido.base_jid and (config.nichos or {}).get(pedido.base_jid):
                    config.nichos = {**config.nichos, jid: config.nichos[pedido.base_jid]}
                config.save(update_fields=["grupos", "nichos", "atualizado_em"])
        if pedido.link_entrada_id:
            from .entrada import grupo_criado

            grupo_criado(pedido, jid, link, agora)
        pedido.estado, pedido.jid, pedido.link_convite = PedidoGrupo.CRIADO, jid, link
        pedido.avisos, pedido.concluido_em = "\n".join(avisos), agora
        pedido.save(update_fields=["estado", "jid", "link_convite", "avisos", "concluido_em"])


def falhou(pedido: PedidoGrupo, erro: str, agora=None) -> None:
    pedido.estado, pedido.erro, pedido.concluido_em = PedidoGrupo.ERRO, erro[:500], agora or timezone.now()
    pedido.save(update_fields=["estado", "erro", "concluido_em"])
