"""Organiza a página inicial e o menu lateral do admin em três níveis:
produto (Site Cash-B, Appfiliado, Automação Instagram) > assunto > tabela.

Só muda a arrumação: os endereços das tabelas e os dados continuam os mesmos. Tabela que
não estiver em GRUPOS aparece em "Outros", no fim, para nada sumir."""

from django.urls import NoReverseMatch, reverse

# (produto, [(assunto, [(tabela, nome na tela ou None para o nome do modelo)])])
GRUPOS = [
    ("🛒 Site Cash-B", [
        ("Usuários e indicações", [
            ("accounts.user", "Usuários"),
            ("accounts.indicacao", "Indicações"),
            ("accounts.configuracaoindicacao", None),
            ("accounts.eventofunil", None),
            ("accounts.pushsubscription", "Inscrições de notificação (push)"),
            ("accounts.comunicacaoemail", None),
        ]),
        ("Pedidos e saques", [
            ("pedidos.pedido", "Pedidos"),
            ("pedidos.reclamacaopedido", "Reclamações de compra"),
            ("pedidos.campanhacashback", None),
            ("saques.saque", "Saques"),
        ]),
        ("Ofertas e cliques", [
            ("ofertas.oferta", "Ofertas"),
            ("ofertas.ofertamanual", None),
            ("ofertas.ofertadestaquemanual", None),
            ("links.click", "Cliques"),
            ("ofertas.nomecurtocache", "Cache de nomes curtos"),
            ("ofertas.cashbackmaximocache", "Cache de cashback máximo"),
            ("ofertas.sincronizacaocatalogo", "Sincronização do catálogo"),
            ("ofertas.buscacatalogo", "Buscas do catálogo (categorias)"),
        ]),
        ("Instagram do site", [
            ("instagram_bot.registropublicacao", "Publicações"),
            ("instagram_bot.estadotokeninstagram", None),
        ]),
    ]),
    ("📱 Appfiliado", [
        ("Contas e assinaturas", [
            ("licencas.contaappfiliado", "Contas do Appfiliado"),
            ("licencas.produtozouti", "Produtos da Zouti"),
            ("licencas.eventowebhookzouti", "Eventos de webhook da Zouti"),
        ]),
        ("Agente de vendas no WhatsApp", [
            ("atendimento.conversa", "Conversas"),
            ("atendimento.respostaaprendida", "Respostas aprendidas"),
        ]),
        ("Painel", [
            ("painel.sincronizacaoresultados", "Sincronizações de resultados"),
            ("painel.vendaitem", "Itens vendidos"),
            ("painel.metamensal", "Metas mensais"),
            ("painel.regrasubid", "Regras de Sub ID"),
            ("painel.relatorioemail", "Relatórios por e-mail"),
            ("painel.textoemaildica", "E-mails de dicas (novos assinantes)"),
            ("painel.sugestao", "Sugestões dos afiliados"),
        ]),
        ("Bot de WhatsApp", [
            ("bot_whatsapp.conexaowhatsapp", "Conexões"),
            ("bot_whatsapp.enviowhatsapp", "Envios"),
            ("bot_whatsapp.ofertarecebida", "Ofertas recebidas (copiar de grupos)"),
            ("bot_whatsapp.eventowhatsapp", "Eventos"),
            ("bot_whatsapp.campanhabot", "Modo campanha"),
            ("bot_whatsapp.alertapreco", "Alertas de preço"),
            ("bot_whatsapp.produtoacompanhado", "Produtos acompanhados (alerta de preço)"),
            ("bot_whatsapp.alertadisparado", "Alertas disparados"),
        ]),
        ("Meu site", [
            ("meusite.siteafiliado", "Sites dos afiliados"),
            ("meusite.produtosite", "Produtos da vitrine"),
            ("meusite.cliquesite", "Cliques no site"),
        ]),
        ("Emissor NFS-e", [
            ("notas.empresanotas", "Empresas"),
            ("notas.notafiscal", "Notas fiscais"),
        ]),
    ]),
    ("📸 Automação Instagram", [
        ("Contas", [
            ("automacao_instagram.containstagramconectada", None),
        ]),
        ("Comentários", [
            ("automacao_instagram.automacaocomentario", None),
            ("automacao_instagram.comentarioprocessado", None),
        ]),
        ("Stories", [
            ("automacao_instagram.automacaostory", None),
            ("automacao_instagram.respostastoryprocessada", None),
        ]),
    ]),
    ("⚙️ Sistema", [
        ("Acesso", [
            ("auth.group", "Grupos de permissão"),
            ("axes.accessattempt", "Tentativas de login"),
            ("axes.accessfailurelog", "Logins que falharam"),
            ("axes.accesslog", "Registro de acessos"),
        ]),
    ]),
]

# Botões que aparecem embaixo do nome do produto, na página inicial do admin.
ACOES = {
    "🛒 Site Cash-B": [("📊 Ver analytics", "admin:pedidos_analytics"),
                      ("✉️ Enviar comunicação por e-mail", "admin:accounts_comunicacao")],
    "📱 Appfiliado": [("📈 Painel do dono", "admin:licencas_painel_do_dono")],
}


def _acoes(produto):
    botoes = []
    for texto, nome in ACOES.get(produto, []):
        try:
            botoes.append({"texto": texto, "url": reverse(nome)})
        except NoReverseMatch:
            pass
    return botoes


def agrupar(app_list: list[dict]) -> list[dict]:
    """Troca a lista do Django (uma seção por app) por uma seção por assunto, cada uma com o
    nome do produto em "produto". As tabelas que a pessoa não pode ver já vêm de fora."""
    por_tabela = {}
    for app in app_list:
        for modelo in app["models"]:
            por_tabela[modelo["model"]._meta.label_lower] = (app, modelo)
    usadas, secoes = set(), []
    for produto, assuntos in GRUPOS:
        primeira = True
        for assunto, tabelas in assuntos:
            modelos = []
            for tabela, nome in tabelas:
                if tabela not in por_tabela:
                    continue  # sem permissão ou não registrada
                _, modelo = por_tabela[tabela]
                modelos.append({**modelo, "name": nome or modelo["name"]})
                usadas.add(tabela)
            if not modelos:
                continue
            secoes.append({
                "name": assunto, "produto": produto, "app_label": modelos[0]["model"]._meta.app_label,
                "app_url": "", "has_module_perms": True, "models": modelos,
                "acoes": _acoes(produto) if primeira else [],
            })
            primeira = False
    sobra = [modelo for tabela, (_, modelo) in por_tabela.items() if tabela not in usadas]
    if sobra:
        secoes.append({"name": "Outros", "produto": "Outros", "app_label": "outros", "app_url": "",
                       "has_module_perms": True, "models": sorted(sobra, key=lambda m: str(m["name"])),
                       "acoes": []})
    return secoes


def instalar(site):
    """Liga a arrumação no admin. A página de um app só (/admin/<app>/) continua como é."""
    original = site.get_app_list

    def get_app_list(request, app_label=None):
        lista = original(request, app_label)
        return lista if app_label else agrupar(lista)

    site.get_app_list = get_app_list
