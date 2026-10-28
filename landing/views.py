from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from licencas import api_shopee, planos as planos_do_app
from painel.modulos import ICONES

from . import planos, recursos as conteudo

# Resumo de cada plano, no mesmo texto do guia da Zouti (marketing/appfiliado/gerar_guia_zouti.py).
RESUMOS = {
    "bot": {
        "icone": "whatsapp", "frase": "Ofertas da Shopee no automático nos seus grupos de WhatsApp sempre com o seu link de afiliado.",
        "itens": (
            [f"Até {planos_do_app.BOT[False]['grupos']} grupos e canais",
             f"Até {planos_do_app.BOT[False]['ofertas_por_grupo_dia']} ofertas por dia em cada grupo/canal",
             f"Alerta de preço para até {planos_do_app.BOT[False]['alerta_produtos']} produtos"],
            [f"Até {planos_do_app.BOT[True]['grupos']} grupos e canais",
             f"Até {planos_do_app.BOT[True]['ofertas_por_grupo_dia']} ofertas por dia em cada grupo/canal",
             f"Alerta de preço para até {planos_do_app.BOT[True]['alerta_produtos']} produtos",
             "Envio por nicho: cada grupo com as ofertas do seu tema",
             "Copia ofertas de outros grupos e troca pelo seu link", "Revisão de texto com IA"],
        ),
        # Ferramentas iguais nos dois planos, mostradas embaixo dos cartões.
        "comuns": ["Busca por palavra-chave, loja ou categoria, com filtros", "Modo campanha para datas específicas (como datas duplas)",
                   "Horário e dias de envio", "Sub ID por grupo", "Modo simulação para testar antes de enviar",
                   "Mensagens avulsas nos grupos na hora ou agendadas", "Painel de membros de até 500 grupos"],
    },
    "site": {
        "icone": "site", "frase": "Seu link na bio (seunome.appfiliado.com.br) com vitrine de ofertas e conversor de links.",
        "itens": (
            ["Até 3 botões", "Vitrine com as ofertas do bot ou de uma busca", "Com assinatura do Appfiliado no rodapé"],
            ["Até 10 botões", "Vitrine com os produtos que você escolher", "Sem assinatura do Appfiliado no rodapé"],
        ),
        "comuns": ["Conversor de links", "Contador de cliques", "SubID próprio", "Ícones de 7 redes sociais"],
    },
    "carrosseis": {
        "icone": "carrosseis", "frase": "Cole um link da Shopee e receba um carrossel pronto pro Instagram.",
        "itens": (
            ["3 carrosséis por dia", "6 modelos de carrossel", "5 temas de cor e 1 fonte"],
            ["10 carrosséis por dia", "6 modelos Standard + 4 Premium", "Cores livres e 5 fontes à escolha", "Foto própria e remoção de fundo",
             f"Reescrita de slides por IA (até {planos_do_app.CARROSSEIS[True]['reescritas']} por dia)"],
        ),
        "comuns": ["Roteiro, legendas e hashtags escritas por IA", "Ajuste manual dos textos gerados", "Edita, reordena e remove slides",
                   "Download de imagens", "SubID próprio"],
    },
    "estudio": {
        "icone": "instagram", "frase": "Crie posts e stories com o seu link de afiliado e publique direto no seu Instagram na hora ou agendado.",
        "itens": (
            [f"{planos_do_app.CARROSSEIS[False]['geracoes']} criações com IA por dia", "7 modelos prontos de post e story",
             "Edite os textos e a foto de cada slide"],
            [f"{planos_do_app.CARROSSEIS[True]['geracoes']} criações com IA por dia", "Cores, fundos e ajustes livres em cada slide",
             "Minha marca: logo, cores e fonte em todos os posts", "Remoção de fundo da foto", "Seus próprios modelos",
             "Adicione e duplique slides"],
        ),
        "comuns": ["Post a partir do link de um produto da Shopee com foto e preço", "Publicar no feed e nos stories na hora ou agendado",
                   "Formatos 1:1, 4:5 e 9:16", "Legenda escrita por IA", "Download em PNG e ZIP", "SubID próprio"],
        # Antes do lançamento: a lista do bloco "Chegando ao Appfiliado" e do quadro no topo da página.
        "breve": {"itens": ["Posts/stories a partir de links de produtos", "Publicação direto pelo Appfiliado",
                            "Formatos 1:1, 4:5 e 9:16", "Legenda escrita por IA", "Download em PNG e ZIP", "SubID próprio"]},
    },
    "automacoes": {
        "icone": "automacoes", "frase": "Respostas em posts e stories e envio de DMs de forma automatizada com seu link de afiliado.",
        "itens": (
            ["Respostas a comentários nos posts", "Até 5 automações ligadas ao mesmo tempo"],
            ["Respostas a comentários, stories e DMs com palavra-chave", "Automações ligadas sem limite",
             "Link num botão na DM", "Sub ID por automação, para ver quanto cada post vendeu"],
        ),
        "comuns": ["Sem limite de pessoas respondidas por mês", "Resposta no comentário e DM com o seu link",
                   "Um post específico ou todos os posts", "Palavras que disparam a resposta", "Cada pessoa recebe uma vez só",
                   "Histórico de quem foi respondido"],
        "breve": {"frase": "Respostas a comentários/stories e envio de DMs de forma automatizada, de acordo com suas configurações.",
                  "itens": ["Sem limite de respostas", "Envio do seu link de afiliado", "Escolha de post específico ou todos os posts",
                            "Histórico de automações", "SubIDs próprios por automação"],
                  "destaques": ["Sem limite de respostas", "Resposta por comentário e DM", "Um post específico ou todos os posts",
                                "Escolha de palavras-chave", "Apenas uma resposta por comentário", "Histórico de automações"]},
    },
}
INCLUSOS = [
    ("resultados", "Resultados e metas", "Vendas, comissões e ranking dos seus links num só lugar."),
    ("conversor", "Conversor de links", "Cole textos de terceiros e receba eles já com os seus links de afiliado, prontos para compartilhar."),
    ("radar", "Radar de ofertas", "Mais de 30 mil produtos para filtrar por comissão, desconto e categoria."),
    ("whatsapp", "Lia, sua assistente no WhatsApp", "Peça resultados, metas e vendas por mensagem e tire dúvidas sobre o Appfiliado a qualquer hora."),
]
PERGUNTAS = [
    ("Preciso ter conta de afiliado da Shopee?", "Sim, e com a API da Shopee liberada. O Appfiliado usa a sua conta de afiliado para gerar os links e a comissão das vendas cai direto na sua conta da Shopee. Você pede a API à Shopee uma vez (a resposta leva até 5 dias úteis) e conecta a conta no painel."),
    ("Como libero a API da Shopee?", "Envie o formulário de ajuda da Shopee escolhendo \"Quero ativar a API\" e acompanhe a página Open API do portal de afiliados. Quando o botão \"Aplicar\" aparecer, clique nele para gerar o AppID e o Secret. O passo a passo completo está na seção \"Antes de começar\", aqui na página."),
    ("Como recebo o acesso depois de pagar?", "Logo após a confirmação do pagamento, você recebe um e-mail com o link para criar a sua senha. É só criar a senha, entrar no painel (app.appfiliado.com.br) e conectar a sua conta da Shopee com o AppID e o Secret da API."),
    ("Qual é a diferença entre Standard e Premium?", "O Premium libera mais volume e mais recursos em cada módulo (mais grupos e ofertas por dia no bot, mais botões no site, mais carrosséis por dia). As listas completas estão nos cartões de cada plano."),
    ("Preciso de um número de WhatsApp só pro bot?", "Você conecta pelo QR Code o número que quiser. Muita gente prefere um número separado do pessoal, só para divulgar as ofertas nos grupos."),
    ("Quem é a Lia?", "É a assistente do Appfiliado no WhatsApp, incluída em todos os planos. Ela tira dúvidas sobre o Appfiliado a qualquer hora e, depois que você vincula o seu número no painel, manda os seus resultados, metas, vendas e a comissão validada do dia por mensagem."),
    ("Posso pagar por ano?", "Pode. No checkout você escolhe mensal ou anual e o plano anual tem 17% de desconto."),
    ("Posso cancelar quando quiser?", "Pode. O cancelamento é feito pela Zouti, a plataforma de pagamento. O acesso segue até o fim do período já pago."),
    ("E se eu não gostar?", "Você tem 7 dias, a partir da compra, para pedir o reembolso integral pela Zouti."),
    ("O que preciso para emitir notas fiscais?", "A emissão é só para afiliados pessoa jurídica: é preciso uma empresa MEI ou do Simples Nacional e o certificado digital A1 (e-CNPJ). O Appfiliado importa o relatório mensal da Shopee e emite uma nota por loja no Emissor Nacional do governo."),
    ("O Appfiliado garante vendas ou comissão?", "Não. O Appfiliado automatiza e organiza a sua divulgação, mas as vendas e as comissões dependem do seu trabalho e das regras da Shopee."),
]


# No lançamento do Instagram: o texto que fala de carrosséis muda e entra a pergunta dos pacotes.
NIVEIS_LANCAMENTO = ("Qual é a diferença entre Standard e Premium?", "O Premium libera mais volume e mais recursos em cada módulo (mais grupos e ofertas por dia no bot, mais botões no site, mais criações com IA e a sua marca no Estúdio, stories e DMs nas Automações). As listas completas estão nos cartões de cada plano.")
PACOTES_LANCAMENTO = ("Posso assinar mais de um módulo?", "Pode. Assine cada módulo separado ou escolha um pacote: o Pacote Ofertas (Bot de WhatsApp e Meu site) e o Pacote Instagram (Estúdio e Automações) saem cerca de 10% mais baratos e o Pacote Completo, com os 4 módulos, sai cerca de 15% mais barato. Os módulos de todas as suas assinaturas ficam liberados na mesma conta.")


# Antes do lançamento: o Estúdio e as Automações aparecem como "Em breve", sem preço e sem planos.
NIVEIS_PRE_LANCAMENTO = ("Qual é a diferença entre Standard e Premium?", "O Premium libera mais volume e mais recursos em cada módulo (mais grupos e ofertas por dia no bot e mais botões no site, por exemplo). As listas completas estão nos cartões de cada plano.")
PACOTES_PRE_LANCAMENTO = ("Posso assinar mais de um módulo?", "Pode. Assine cada módulo separado ou escolha o Pacote Ofertas (Bot de WhatsApp e Meu site), que sai cerca de 10% mais barato. Os módulos de todas as suas assinaturas ficam liberados na mesma conta. Com o lançamento do Estúdio Instagram e das Automações Instagram, chegam também o Pacote Instagram e o Pacote Completo.")
QUANDO_LANCA = ("Quando chegam o Estúdio Instagram e as Automações Instagram?", "Em breve. Os dois estão na reta final e os planos e preços aparecem aqui no site no dia do lançamento. Enquanto isso, conheça tudo o que eles vão fazer nas páginas de cada um.")


def perguntas() -> list:
    niveis, pacotes = (NIVEIS_LANCAMENTO, PACOTES_LANCAMENTO) if planos.lancado() else (NIVEIS_PRE_LANCAMENTO, PACOTES_PRE_LANCAMENTO)
    saida = []
    for q, r in PERGUNTAS:
        if q == niveis[0]:
            saida += [niveis, pacotes] + ([] if planos.lancado() else [QUANDO_LANCA])
        else:
            saida.append((q, r))
    return saida


PERGUNTAS_NOTAS = [
    ("Posso usar se sou afiliado pessoa física?", "Não. A emissão de notas é só para afiliados pessoa jurídica: é preciso ter uma empresa MEI ou do Simples Nacional (ME/EPP) com CNPJ e o certificado digital A1 dela. A nota sai sempre no CNPJ da empresa."),
    ("Para que serve essa nota?", "Quando a Shopee paga ao afiliado a comissão extra de um vendedor, o afiliado presta um serviço a esse vendedor e emite a nota fiscal dele. O Appfiliado monta e emite essas notas a partir do relatório mensal da Shopee."),
    ("O que é o certificado A1 e onde consigo?", "É o certificado digital da empresa (e-CNPJ) em formato de arquivo, com extensão .pfx ou .p12 e uma senha. Você compra em uma certificadora. O certificado em cartão ou token (A3) não serve, porque não dá para exportar o arquivo."),
    ("Como as notas são contadas no plano?", "Conta cada nota emitida de verdade no mês. As notas de teste não contam e a nota cancelada libera a vaga no mesmo mês. Escolha a faixa pela quantidade de notas que você costuma emitir."),
    ("E se eu tentar emitir mais notas do que o meu plano permite?", "O Appfiliado barra antes de enviar: o lote inteiro fica de fora, sem emitir só uma parte. A tela mostra quantas notas ainda restam no mês e quantas faltam. É só passar para um plano maior e emitir todas de uma vez. A contagem recomeça a cada mês e as notas de teste não entram nela."),
    ("Posso testar antes de emitir de verdade?", "Pode. O Appfiliado tem o ambiente de testes do governo, igual ao de verdade, mas sem valor fiscal. Comece por ele e, quando estiver tudo certo, passe pra emissão real."),
    ("E se uma nota sair errada?", "Dá para cancelar pelo painel do Appfiliado, que faz o cancelamento no Emissor Nacional."),
    ("O vendedor recebe a nota?", "Recebe. O Appfiliado manda um e-mail para cada vendedor com o PDF e o XML da nota no horário que você escolher."),
    ("O Appfiliado cuida dos impostos?", "Não. O Appfiliado emite as notas, mas a orientação tributária e contábil da sua empresa é com o seu contador. Em caso de dúvida sobre código de serviço ou tributação, fale com ele antes de emitir."),
]


def _cartao(modulo, nivel):
    # No Premium todas as bolinhas são verdes.
    return {"nivel": planos.NIVEIS[nivel], "preco": planos.brl(planos.PRECOS[modulo][nivel]),
            "itens": [{"texto": t, "extra": bool(nivel)} for t in RESUMOS[modulo]["itens"][nivel]],
            "link": planos.LINKS[f"{modulo}{nivel}"]}  # vazio: produto ainda não criado na Zouti ("Em breve")


FRASE_CURTA = {"bot": "Ofertas no automático nos seus grupos", "site": "Link na bio com vitrine e conversor", "carrosseis": "Carrosséis prontos pro Instagram",
               "estudio": "Posts e stories publicados no seu Instagram", "automacoes": "Comentou, recebeu o link na DM"}
PAGINA_DO_MODULO = {"bot": "landing_bot", "site": "landing_site", "carrosseis": "landing_carrosseis",
                    "estudio": "landing_estudio", "automacoes": "landing_automacoes"}
URL_DO_INCLUSO = {"resultados": "landing_resultados", "conversor": "landing_conversor", "radar": "landing_radar",
                  "whatsapp": "landing_resultados"}
ANCORA_DO_INCLUSO = {"whatsapp": "#lia"}  # a Lia é uma seção da página de Resultados e metas
# Ferramentas incluídas em todos os planos, que também têm página própria.
INCLUIDOS_COM_PAGINA = [("resultados", "Resultados e metas", "landing_resultados"), ("radar", "Radar de ofertas", "landing_radar"),
                        ("conversor", "Conversor de links", "landing_conversor")]


def _modulo(m):
    """Os dados de um módulo para os cartões de plano (landing e páginas de recursos). Módulo "Em breve"
    vai sem preço e sem os cartões Standard/Premium."""
    breve = planos.em_breve(m)
    return {"codigo": m, "nome": planos.NOMES[m], "icone": ICONES[RESUMOS[m]["icone"]], "frase": RESUMOS[m]["frase"], "curta": FRASE_CURTA[m],
            "em_breve": breve, "a_partir": None if breve else planos.brl(planos.PRECOS[m][0]),
            "breve_frase": RESUMOS[m].get("breve", {}).get("frase") or RESUMOS[m]["frase"],
            "breve_itens": RESUMOS[m].get("breve", {}).get("itens") or RESUMOS[m].get("comuns", []),
            "destaques": (RESUMOS[m].get("breve", {}).get("destaques") or RESUMOS[m].get("breve", {}).get("itens")
                          or RESUMOS[m].get("comuns", [])),
            "comuns": RESUMOS[m].get("comuns", []), "pagina": PAGINA_DO_MODULO[m],
            "planos": [] if breve else [_cartao(m, 0), _cartao(m, 1)]}


def _comum(request):
    return {
        "painel_url": settings.APPFILIADO_PAINEL_URL,
        "whatsapp": "".join(ch for ch in settings.APPFILIADO_WHATSAPP_SUPORTE if ch.isdigit()),
        "email_suporte": settings.APPFILIADO_EMAIL_SUPORTE,
        "endereco": f"https://{request.get_host()}",
        "icones": ICONES,
        "lancado": planos.lancado(),
    }


def _faixas_de_notas():
    return [{"nome": nome, "preco": planos.brl(preco), "link": link}
            for (nome, preco), link in zip(planos.NOTAS, planos.LINKS_NOTAS.values())]


@require_GET
def notas(request):
    return render(request, "landing/notas.html", {**_comum(request), "notas": _faixas_de_notas(), "perguntas": PERGUNTAS_NOTAS,
                                                   "prints": conteudo.prints_de("notas", 1) + conteudo.prints_de("notas", 0)})


@require_GET
def privacidade(request):
    return render(request, "landing/privacidade.html", _comum(request))


@require_GET
def termos(request):
    return render(request, "landing/termos.html", _comum(request))


def _pacotes():
    return [{**p, "niveis": [{**n, "preco": planos.brl(n["preco"]), "separado": planos.brl(n["separado"])} for n in p["niveis"]]}
            for p in planos.pacotes()]


@require_GET
def pagina(request):
    modulos = [_modulo(m) for m in planos.modulos()]
    return render(request, "landing/index.html", {
        "modulos": modulos, "a_venda": [m for m in modulos if not m["em_breve"]],
        "em_breve": [m for m in modulos if m["em_breve"]], "pacotes": _pacotes(),
        "inclusos": [{"icone": ICONES[i], "nome": n, "frase": f, "url": URL_DO_INCLUSO[i], "ancora": ANCORA_DO_INCLUSO.get(i, "")}
                     for i, n, f in INCLUSOS],
        "notas": _faixas_de_notas(), "perguntas": perguntas(), "api": api_shopee, **_comum(request),
    })


@require_GET
def robots(request):
    return HttpResponse(f"User-agent: *\nAllow: /\n\nSitemap: https://{request.get_host()}/sitemap.xml\n", content_type="text/plain")


@require_GET
def sitemap(request):
    caminhos = ["/", "/emissao-de-notas/", "/privacidade/", "/termos-de-uso/"] + [f"/{conteudo.PAGINAS[m]()['slug']}/" for m in list(planos.modulos()) + [i[0] for i in INCLUIDOS_COM_PAGINA]]
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>https://{request.get_host()}{c}</loc></url>" for c in caminhos) + "</urlset>")
    return HttpResponse(xml, content_type="application/xml")


def nao_encontrada(request, exception=None):
    return HttpResponseNotFound("Página não encontrada.", content_type="text/plain; charset=utf-8")


@require_GET
def recursos(request, modulo):
    """Página com todos os recursos de uma ferramenta (conteúdo em landing/recursos.py)."""
    if modulo == "carrosseis":
        # O Estúdio Instagram toma o lugar do gerador (definitivo só depois do lançamento).
        return redirect("landing_estudio", permanent=planos.lancado())
    pagina = conteudo.PAGINAS[modulo]()
    outros = [{"nome": planos.NOMES[m], "url": PAGINA_DO_MODULO[m]} for m in planos.modulos() if m != modulo]
    outros += [{"nome": nome, "url": url} for chave, nome, url in INCLUIDOS_COM_PAGINA if chave != modulo]
    contexto = {**_comum(request), "r": pagina, "outros": outros,
                "m": None if pagina.get("incluso") else _modulo(modulo), "notas": _faixas_de_notas()}
    return render(request, "landing/recurso.html", contexto)
