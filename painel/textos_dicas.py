"""Textos padrão dos e-mails de dicas (o ponto de partida; depois você edita no admin, em
Painel > E-mails de dicas). Formato simples, sem HTML:

- Parágrafos separados por uma linha em branco; linhas seguidas viram quebra de linha.
- **negrito**   ·   linha começando com ↳ vira item da lista   ·   parágrafo começando com "Dica:" ou
  "Minha dica:" vira a caixinha bege.
- {nome} = primeiro nome · {imagem} = o print do e-mail · {botao} = o botão amarelo · {numeros} = os
  números da pessoa nos últimos 30 dias (só no e-mail do dia 21).
- [texto](destino) vira link. Destinos: planos, automacao, campanhas, mensagens, alerta, resultados,
  radar, conversor, site, carrosseis, notas, configuracoes, sugestoes, inicio, ou um endereço https://.
- Uma linha começando com [bot], [premium], [site], [carrosséis], [carrosséis premium], [notas], [api]
  ou [emissor] só aparece pra quem tem isso; com [sem ...] na frente (ex: [sem premium]), só pra quem
  não tem. [api] = conectou a API da Shopee; [emissor] = vende bem e ainda não tem o Emissor NFS-e."""

TEXTOS = {
    "historia": {
        "assunto": "Por que eu criei o Appfiliado",
        "ativo": False,  # espera o texto do Eduardo
        "texto": "[Escreva aqui a sua história. Este e-mail só sai depois que você marcar \"enviar este e-mail\".]",
    },
    "bot": {
        "assunto": "O grupo que vende todo dia não é sorte",
        "texto": """Uma coisa que eu aprendi divulgando oferta em grupo: quem vende todo dia não é quem posta mais. É quem posta **no ritmo certo**, sem cansar o grupo.

Foi pensando nisso que eu montei o Bot do Appfiliado:

↳ **Intervalo e horário:** uma oferta a cada X minutos, só na janela em que o seu público está acordado
↳ **Não repetir:** o mesmo produto não volta pro mesmo grupo por quantos dias você escolher
↳ **Filtros:** comissão, desconto, preço e avaliação mínimos, para só passar o que vale a pena
↳ **Modo simulação:** você vê o que sairia antes de mandar de verdade

{imagem}

Minha dica: comece com uma oferta a cada 15 ou 20 minutos, das 8h às 22h, e comissão mínima de 10%. Depois de uma semana, veja em Resultados quais grupos venderam mais e ajuste.

{botao}

[sem premium] No Premium, cada grupo pode receber as ofertas do seu nicho (beleza, casa, pet…), a IA revisa o texto antes de enviar e dá para copiar ofertas de outros grupos com o seu link. [Ver o Premium](planos)""",
        "texto_sem": """Converter link de afiliado um por um cansa. E quem copia oferta de outros canais ainda precisa tirar o link de quem postou e pôr o seu.

O **Conversor de links** do Appfiliado faz isso de uma vez:

↳ Cole o texto inteiro (aquela mensagem da Shopee ou de outro canal)
↳ Todos os links da Shopee viram os seus, com o Sub ID que você quiser
↳ Os links de outras pessoas saem do texto

{imagem}

{botao}

Se você divulga em grupos de WhatsApp, o Bot faz isso sozinho o dia todo, com o seu link. [Conhecer o Bot](planos)""",
    },
    "resultados": {
        "assunto": "Você sabe qual grupo te dá mais comissão?",
        "texto": """A maioria dos afiliados olha só o total do mês no painel da Shopee. Mas o total não conta **de onde** veio cada venda.

Em **Resultados**, no Appfiliado, você vê:

↳ Comissão estimada e validada por dia, semana ou mês
↳ **Vendas por Sub ID:** cada grupo, canal ou rede com o seu número
↳ Os produtos que mais venderam
↳ A meta do mês, com as faixas de bônus

{imagem}

E se quiser, recebe tudo isso por e-mail toda manhã: é só ligar o relatório diário em [Configurações](configuracoes).

Minha dica: use um Sub ID diferente para cada lugar onde você divulga (ex: grupovip, instagram, site).
[bot] No Bot, cada grupo pode ter o seu Sub ID próprio.

[sem api] **Importante:** pros números aparecerem, conecte a API da Shopee em [Configurações](configuracoes).

{botao}""",
    },
    "radar": {
        "assunto": "Onde achar o produto que vende antes de todo mundo",
        "texto": """Todo afiliado já passou por isso: você divulga um produto e descobre que metade dos grupos já tinha postado ele ontem.

O **Radar de ofertas** do Appfiliado mostra os produtos da Shopee que estão vendendo agora:

↳ Comissão, desconto, preço e vendas de cada produto
↳ Filtro por categoria e ordem por mais vendidos, maior comissão ou maior desconto
↳ Achou um bom? Um clique gera o seu link ou manda direto pros seus grupos

{imagem}

[bot] E tem o **Alerta de preço**, na aba do Bot: você acompanha produtos e, quando o preço cai, o bot avisa nos seus grupos. Promoção de verdade vende muito mais.

{botao}""",
    },
    "campanhas": {
        "assunto": "Datas duplas e Black Friday no piloto automático",
        "texto": """Nas datas duplas (9.9, 10.10, 11.11, 12.12) e na Black Friday, a Shopee vende em poucas horas o que vende num mês. E é justo quando a gente está cansado, de madrugada.

Por isso o Bot tem:

↳ **Modo campanha:** nas datas que você ligar, o bot muda o ritmo, o cupom e a frase de abertura sozinho, e volta ao normal no dia seguinte
↳ **Página da campanha:** a cada N ofertas, ele manda o link da página da campanha com o seu link
↳ **Mensagens agendadas:** avisos como "meia-noite começa o 11.11" marcados pra hora certa

{imagem}

Minha dica: ligue as próximas datas no modo campanha agora e agende um aviso nos grupos pra noite anterior. Na hora, o bot cuida do resto.

{botao}""",
        "texto_sem": """Nas datas duplas (9.9, 10.10, 11.11, 12.12) e na Black Friday, a Shopee vende em poucas horas o que vende num mês. E é justo quando a gente está cansado, de madrugada.

Três coisas que ajudam nessas datas:

↳ No **Radar**, ordene por **maior desconto** para achar as melhores ofertas do dia
↳ No **Conversor**, cole a mensagem da Shopee com os links da campanha e saia com tudo no seu link
↳ Deixe a página da campanha no seu link na bio

{botao}

Com o Bot de WhatsApp, o modo campanha faz isso tudo sozinho nos seus grupos, inclusive de madrugada. [Conhecer o Bot](planos)""",
    },
    "site_carrosseis": {
        "assunto": "Seu link na bio e seu Instagram trabalhando junto",
        "texto": """Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.

[site] **No seu site** (o seu link na bio):
[site] ↳ Deixe o botão mais importante em destaque, como o link do seu grupo VIP
[site] ↳ Use a vitrine com as ofertas que combinam com o seu público (com o Bot, ela mostra as últimas que ele enviou)
[site] ↳ Acompanhe os cliques de cada botão e produto no painel

{imagem}

[carrosséis] **Nos carrosséis:** cole o link de um produto e o Appfiliado monta o carrossel com textos feitos por IA e o seu link.
[carrosséis premium] Minha dica: salve o seu modelo, cor e @ como padrão, e os próximos já saem com a sua cara.

{botao}

[sem site] Quer um link na bio com vitrine e conversor pro seu público? Conheça o [Meu site](planos).
[sem carrosséis] Quer posts prontos pro Instagram a partir de um link? Conheça os [Carrosséis](planos).""",
        "texto_sem": """Grupo de WhatsApp vende muito, mas quem chega pelo Instagram também compra. O segredo é ter um caminho fácil do post até o link.

No Appfiliado, dois módulos fazem esse caminho:

↳ **Meu site:** o seu link na bio, com botões, conversor de links pro seu público e vitrine de ofertas
↳ **Carrosséis:** cole o link de um produto e receba um carrossel pronto pro Instagram, com textos feitos por IA

{imagem}

Juntando com o que você já tem, sai com desconto de combo: 10% com 2 módulos e 20% com 3.

{botao}""",
    },
    "como_vai": {
        "assunto": "Como estão indo as suas vendas?",
        "texto": """Já faz três semanas que você está com o Appfiliado, e eu queria saber como está sendo.

{numeros}

**Me conta:** o que está funcionando e o que falta no Appfiliado para você vender mais? Responda este e-mail ou mande a sua ideia no formulário de sugestões. Eu leio todas.

{botao}

[notas] Lembrete: no Emissor NFS-e, você importa o relatório da Shopee e emite as notas do mês em lote, cada uma já com o e-mail pro vendedor.
[emissor] Vendendo nesse ritmo, vale pensar nas notas fiscais das suas comissões. O Emissor NFS-e do Appfiliado importa o relatório da Shopee e emite as notas do mês em lote. [Conhecer o Emissor](planos)""",
    },
}
