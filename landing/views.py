from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.http import require_GET

from licencas import planos as planos_do_app
from painel.modulos import ICONES

from . import planos

# Resumo de cada plano, no mesmo texto do guia da Zouti (marketing/appfiliado/gerar_guia_zouti.py).
RESUMOS = {
    "bot": {
        "icone": "whatsapp", "frase": "Ofertas da Shopee no automático nos seus grupos de WhatsApp, sempre com o seu link de afiliado.",
        "itens": (
            ["Até 10 grupos e canais", "Até 60 ofertas por dia em cada grupo/canal", "Alerta de preço para até 10 produtos"],
            ["Até 50 grupos ou canais", "Até 300 ofertas por dia em cada grupo/canal", "Alerta de preço para até 50 produtos",
             "Copia ofertas de outros grupos e troca pelo seu link", "Revisão de texto com IA"],
        ),
        # Itens do Premium que o Standard não tem: a bolinha muda de cor para destacar.
        "extras": ("Copia ofertas de outros grupos e troca pelo seu link", "Revisão de texto com IA"),
        # Ferramentas iguais nos dois planos, mostradas embaixo dos cartões.
        "comuns": ["Busca por palavra-chave, loja ou categoria, com filtros", "Modo campanha para datas específicas (como datas duplas)",
                   "Horário e dias de envio", "Sub ID por grupo", "Modo simulação para testar antes de enviar"],
    },
    "site": {
        "icone": "site", "frase": "Seu link na bio (seunome.appfiliado.com.br) com vitrine de ofertas e conversor de links.",
        "itens": (
            ["Até 3 botões", "Vitrine de ofertas padrão", "Com assinatura do Appfiliado no rodapé"],
            ["Até 10 botões", "Vitrine de ofertas personalizável", "Sem assinatura do Appfiliado no rodapé"],
        ),
        "comuns": ["Conversor de links", "Contador de cliques", "SubID próprio", "Ícones de todas as redes sociais"],
    },
    "carrosseis": {
        "icone": "carrosseis", "frase": "Cole um link da Shopee e receba um carrossel pronto para o Instagram.",
        "itens": (
            ["3 carrosséis por dia", "6 modelos de carrossel", "5 temas de cor e 1 fonte"],
            ["10 carrosséis por dia", "6 modelos Standard + 4 Premium", "Cores e fontes livres", "Foto própria e remoção de fundo",
             f"Reescrita de slides por IA (até {planos_do_app.CARROSSEIS[True]['reescritas']} por dia)"],
        ),
        "comuns": ["Roteiro, legendas e hashtags escritas por IA", "Ajuste manual dos textos gerados", "Edita, reordena e remove slides",
                   "Download de imagens", "SubID próprio"],
    },
}
INCLUSOS = [
    ("resultados", "Resultados e metas", "Vendas, comissões e ranking dos seus links num só lugar."),
    ("conversor", "Conversor de links", "Cole textos de terceiros e receba eles já com os seus links de afiliado, prontos para compartilhar."),
    ("radar", "Radar de ofertas", "Mais de 30 mil produtos para filtrar por comissão, desconto e categoria."),
]
PERGUNTAS = [
    ("Preciso ter conta de afiliado da Shopee?", "Sim. O Appfiliado usa a sua conta de afiliado para gerar os links, e a comissão das vendas cai direto na sua conta da Shopee. Você conecta a conta uma vez, no painel."),
    ("Como recebo o acesso depois de pagar?", "Logo após a confirmação do pagamento você recebe um e-mail com o link para criar a sua senha. É só criar a senha, entrar no painel (app.appfiliado.com.br) e conectar a sua conta da Shopee."),
    ("Qual é a diferença entre Standard e Premium?", "O Premium libera mais volume e mais recursos em cada módulo (mais grupos e ofertas por dia no bot, mais botões no site, mais carrosséis por dia). As listas completas estão nos cartões de cada plano."),
    ("Preciso de um número de WhatsApp só para o bot?", "Você conecta pelo QR Code o número que quiser. Muita gente prefere um número separado do pessoal, só para divulgar as ofertas nos grupos."),
    ("Posso pagar por ano?", "Pode. No checkout você escolhe mensal ou anual, e o plano anual tem 17% de desconto."),
    ("Posso cancelar quando quiser?", "Pode. O cancelamento é feito pela Zouti, a plataforma de pagamento. O acesso segue até o fim do período já pago."),
    ("E se eu não gostar?", "Você tem 7 dias, a partir da compra, para pedir o reembolso integral pela Zouti."),
    ("O que preciso para emitir notas fiscais?", "A emissão é só para afiliados pessoa jurídica: é preciso uma empresa MEI ou do Simples Nacional e o certificado digital A1 (e-CNPJ). O Appfiliado importa o relatório mensal da Shopee e emite uma nota por loja no Emissor Nacional do governo."),
    ("O Appfiliado garante vendas ou comissão?", "Não. O Appfiliado automatiza e organiza a sua divulgação, mas as vendas e as comissões dependem do seu trabalho e das regras da Shopee."),
]


PERGUNTAS_NOTAS = [
    ("Posso usar se sou afiliado pessoa física?", "Não. A emissão de notas é só para afiliados pessoa jurídica: é preciso ter uma empresa MEI ou do Simples Nacional (ME/EPP) com CNPJ e o certificado digital A1 dela. A nota sai sempre no CNPJ da empresa."),
    ("Para que serve essa nota?", "Quando a Shopee paga ao afiliado a comissão extra de um vendedor, o afiliado presta um serviço a esse vendedor e emite a nota fiscal dele. O Appfiliado monta e emite essas notas a partir do relatório mensal da Shopee."),
    ("O que é o certificado A1 e onde consigo?", "É o certificado digital da empresa (e-CNPJ) em formato de arquivo, com extensão .pfx ou .p12, e uma senha. Você compra em uma certificadora. O certificado em cartão ou token (A3) não serve, porque não dá para exportar o arquivo."),
    ("Como as notas são contadas no plano?", "Conta cada nota emitida de verdade no mês. As notas de teste não contam, e a nota cancelada libera a vaga no mesmo mês. Escolha a faixa pela quantidade de notas que você costuma emitir."),
    ("Posso testar antes de emitir de verdade?", "Pode. O Appfiliado tem o ambiente de testes do governo, igual ao de verdade mas sem valor fiscal. Comece por ele e, quando estiver tudo certo, passe para a emissão real."),
    ("E se uma nota sair errada?", "Dá para cancelar pelo painel do Appfiliado, que faz o cancelamento no Emissor Nacional."),
    ("O vendedor recebe a nota?", "Recebe. O Appfiliado manda um e-mail para cada vendedor, com o PDF e o XML da nota, no horário que você escolher."),
    ("O Appfiliado cuida dos impostos?", "Não. O Appfiliado emite as notas, mas a orientação tributária e contábil da sua empresa é com o seu contador. Em caso de dúvida sobre código de serviço ou tributação, fale com ele antes de emitir."),
]


def _cartao(modulo, nivel):
    extras = RESUMOS[modulo].get("extras", ()) if nivel else ()
    return {"nivel": planos.NIVEIS[nivel], "preco": planos.brl(planos.PRECOS[modulo][nivel]),
            "itens": [{"texto": t, "extra": t in extras} for t in RESUMOS[modulo]["itens"][nivel]],
            "tem_extras": bool(extras), "link": planos.LINKS[f"{modulo}{nivel}"]}


def _comum(request):
    return {
        "painel_url": settings.APPFILIADO_PAINEL_URL,
        "whatsapp": "".join(ch for ch in settings.APPFILIADO_WHATSAPP_SUPORTE if ch.isdigit()),
        "email_suporte": settings.APPFILIADO_EMAIL_SUPORTE,
        "endereco": f"https://{request.get_host()}",
        "icones": ICONES,
    }


def _faixas_de_notas():
    return [{"nome": nome, "preco": planos.brl(preco), "link": link}
            for (nome, preco), link in zip(planos.NOTAS, planos.LINKS_NOTAS.values())]


@require_GET
def notas(request):
    return render(request, "landing/notas.html", {**_comum(request), "notas": _faixas_de_notas(), "perguntas": PERGUNTAS_NOTAS})


@require_GET
def pagina(request):
    combos = planos.todos_os_combos()
    contexto = {
        "modulos": [{"codigo": m, "nome": planos.NOMES[m], "icone": ICONES[RESUMOS[m]["icone"]], "frase": RESUMOS[m]["frase"],
                     "a_partir": planos.brl(planos.PRECOS[m][0]), "comuns": RESUMOS[m].get("comuns", []),
                     "planos": [_cartao(m, 0), _cartao(m, 1)]} for m in planos.MODULOS],
        "inclusos": [{"icone": ICONES[i], "nome": n, "frase": f} for i, n, f in INCLUSOS],
        "notas": _faixas_de_notas(),
        "montador": {"combos": combos, "modulos": [{"codigo": m, "nome": planos.NOMES[m]} for m in planos.MODULOS]},
        "combo_standard": {"preco": planos.brl(combos["bot0+site0+carrosseis0"]["preco"]), "separado": planos.brl(combos["bot0+site0+carrosseis0"]["separado"]),
                           "link": combos["bot0+site0+carrosseis0"]["link"]},
        "combo_premium": {"preco": planos.brl(combos["bot1+site1+carrosseis1"]["preco"]), "separado": planos.brl(combos["bot1+site1+carrosseis1"]["separado"]),
                          "link": combos["bot1+site1+carrosseis1"]["link"]},
        "perguntas": PERGUNTAS,
        **_comum(request),
    }
    return render(request, "landing/index.html", contexto)


@require_GET
def robots(request):
    return HttpResponse(f"User-agent: *\nAllow: /\n\nSitemap: https://{request.get_host()}/sitemap.xml\n", content_type="text/plain")


@require_GET
def sitemap(request):
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           f"<url><loc>https://{request.get_host()}/</loc></url>"
           f"<url><loc>https://{request.get_host()}/emissao-de-notas/</loc></url></urlset>")
    return HttpResponse(xml, content_type="application/xml")


def nao_encontrada(request, exception=None):
    return HttpResponseNotFound("Página não encontrada.", content_type="text/plain; charset=utf-8")
