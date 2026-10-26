"""Conteúdo das páginas de recursos de cada módulo (/bot-de-whatsapp/, /meu-site/, /gerador-de-carrosseis/ e, a
partir do lançamento do Instagram, /estudio-instagram/ e /automacoes-instagram/).

Tudo aqui foi levantado no código do produto (não nos textos de marketing). Os limites vêm de
licencas/planos.py, então mudar um número lá muda a página junto. Cada recurso é (nome, texto) e,
quando só o Premium tem, (nome, texto, "Premium")."""

from licencas import planos as plano

from . import planos as vendas


def _t(nome, texto, so=""):
    return {"nome": nome, "texto": texto, "plano": so, "chips": [], "cores": []}


def _grupo(titulo, intro, *itens):
    return {"titulo": titulo, "intro": intro, "itens": list(itens)}


def bot():
    s, p = plano.BOT[False], plano.BOT[True]
    return {
        "codigo": "bot", "slug": "bot-de-whatsapp", "url": "landing_bot", "nome": "Bot de WhatsApp",
        "titulo": "Bot de WhatsApp para afiliados da Shopee — Appfiliado",
        "descricao": "Ofertas da Shopee nos seus grupos e canais de WhatsApp no automático e com o seu link de afiliado: busca com filtros, modo campanha, alerta de preço e muito mais.",
        "h1": "Ofertas da Shopee nos seus grupos de WhatsApp no automático.",
        "texto": "O bot escolhe as ofertas, gera o seu link de afiliado e publica nos grupos e canais que você definir, no ritmo e nos horários que você quiser. Tudo configurado por um painel simples sem instalar nada.",
        "resumo": [
            ("Grupos e canais", f"até {s['grupos']}", f"até {p['grupos']}"),
            ("Ofertas por dia em cada grupo", f"até {s['ofertas_por_grupo_dia']}", f"até {p['ofertas_por_grupo_dia']}"),
            ("Alerta de preço", f"{s['alerta_produtos']} produtos", f"{p['alerta_produtos']} produtos"),
            ("Envio por nicho", "—", "Sim"),
            ("Copiar de outros grupos", "—", "Sim"),
            ("Revisão do texto com IA", "—", "Sim"),
        ],
        "grupos": [
            _grupo("Conecte o seu WhatsApp em minutos", "Sem instalar programa e sem deixar computador ligado.",
                   _t("Conexão por QR Code", "Você lê um QR Code em Aparelhos conectados, no seu celular, como no WhatsApp Web. O servidor do Appfiliado fica conectado como mais um aparelho."),
                   _t("Reconexão automática", "Se a conexão cair, o bot tenta voltar sozinho. O histórico da conexão mostra quando caiu, quando voltou e quando ficou instável."),
                   _t("Seus grupos e canais", "A lista traz todos os grupos e canais do seu número com o número de participantes ou seguidores. Um canal só entra como destino se você for dono ou administrador."),
                   _t("Mensagem de teste", "Mande uma mensagem de teste para um grupo ou canal com texto e imagem, para conferir tudo antes de ligar as ofertas.")),
            _grupo("Ofertas automáticas da Shopee com o seu link", "O bot escolhe o próximo produto que passa nos seus filtros e ainda não foi enviado e publica em cada grupo.",
                   _t("Quatro jeitos de buscar", "Ofertas em geral, por palavra-chave, de uma loja específica (pelo link da loja ou de um produto dela) ou por categoria."),
                   _t("15 categorias prontas", "Moda, Beleza e Cuidados Pessoais, Casa e Decoração, Eletrônicos e Celulares, Eletrodomésticos, Bebês e Infantil, Brinquedos e Games, Esporte e Lazer, Automotivo e Motos, Pet Shop, Papelaria e Escritório, Saúde e Bem-estar, Alimentos e Bebidas, Joias e Acessórios, Ferramentas e Construção."),
                   _t("Ordem das ofertas", "Mais vendidos, maior comissão ou maior desconto."),
                   _t("Filtros", "Comissão mínima, desconto mínimo, preço mínimo e máximo, número mínimo de vendas e avaliação mínima. Todos são opcionais."),
                   _t("Seu link em todas as ofertas", "Cada oferta sai com o seu link de afiliado, gerado na hora, pra comissão ser sua."),
                   _t("Mensagem pronta", "Nome do produto, número de vendidos, desconto, avaliação, preço e o convite para comprar com um fechamento que varia. Você pode somar um cupom."),
                   _t("Foto com texto ou prévia do link", "Você escolhe como a oferta aparece. Recomendamos a prévia do link: deixa o grupo mais leve e converte mais, pois muita gente não baixa imagens automaticamente. Os canais do WhatsApp não aceitam foto com legenda e sempre recebem a prévia."),
                   _t("Sem repetir produto", "O mesmo produto não volta ao mesmo grupo por quantos dias você definir, de 1 a 90 (o padrão é 7).")),
            _grupo("Você decide quando e quanto", "O ritmo é seu, dentro do limite do plano.",
                   _t("Intervalo entre ofertas", f"Escolha de quanto em quanto tempo sai uma oferta. O menor intervalo é de {s['intervalo_minimo']} minutos no Standard e de {p['intervalo_minimo']} minutos no Premium."),
                   _t("Horário e dias de envio", "Defina a janela (o padrão é das 7h às 23h e vale janela que passa da meia-noite) e os dias da semana em que o bot trabalha."),
                   _t("Limite por dia", f"O plano libera até {s['ofertas_por_grupo_dia']} ofertas por dia em cada grupo no Standard e até {p['ofertas_por_grupo_dia']} no Premium. Você pode escolher um limite menor."),
                   _t("Grupos que recebem", f"Marque os grupos e canais de destino, até {s['grupos']} no Standard e até {p['grupos']} no Premium."),
                   _t("Sub IDs para medir", "Até 5 Sub IDs padrão e um Sub ID próprio por grupo. Em Resultados você vê quanto cada grupo vende."),
                   _t("Mensagens avulsas", f"Escreva um aviso, com foto se quiser, e mande para todos os grupos, pros de um nicho ou pros que escolher: na hora, num dia e hora marcados ou toda semana. Os links da Shopee viram o seu link de afiliado. Até {s['mensagens_agendadas']} mensagens agendadas no Standard e {p['mensagens_agendadas']} no Premium.")),
            _grupo("Teste antes de enviar", "Veja o que vai sair sem mandar nada.",
                   _t("Testar busca", "Mostra as próximas ofertas que sairiam, já com a mensagem pronta, sem gerar link e sem enviar. Se nada serve, explica por quê."),
                   _t("Modo simulação", "O bot faz tudo, menos enviar, e registra como simulado. Depois de desligar, o que foi simulado não conta no limite do dia."),
                   _t("Últimas ofertas enviadas", "As 10 últimas com o status (na fila, enviada, com erro ou simulada) e a mensagem completa."),
                   _t("Por que não está enviando", "A tela mostra o motivo quando nada sai: fora do horário, limite do dia atingido ou nenhum produto novo.")),
            _grupo("Modo campanha para datas especiais", "Nas datas que você ligar, o bot muda de ritmo e de texto sozinho e volta ao normal no dia seguinte.",
                   _t("Datas da Shopee", "Dia do Consumidor, todas as datas duplas de 3.3 a 12.12 e Black Friday. Já vêm ligadas a 9.9, 10.10, 11.11, Black Friday e 12.12 e valem todo ano."),
                   _t("Suas próprias datas", "Adicione até 20 datas suas, com nome e dia e escolha se elas se repetem todo ano."),
                   _t("Ritmo da campanha", f"Intervalo, limite de ofertas no dia e horário próprios para os dias de campanha, dentro dos limites do seu plano."),
                   _t("Busca e filtros da campanha", "Uma palavra-chave, um desconto mínimo e uma comissão mínima só pros dias de campanha."),
                   _t("Texto da campanha", "Uma frase de abertura e o cupom da campanha nas ofertas."),
                   _t("Página da campanha", "Envie a página da campanha da Shopee com o seu link de afiliado, a cada 3 a 100 ofertas, em uma mensagem à parte com prévia grande."),
                   _t("Prévias e aviso", "Veja uma prévia de uma oferta e da mensagem da campanha antes. O painel avisa 7 dias antes de cada data.")),
            _grupo("Alerta de preço", "Acompanhe produtos e avise quando o preço cair.",
                   _t("Produtos acompanhados", f"Até {s['alerta_produtos']} produtos no Standard e até {p['alerta_produtos']} no Premium. Adicione por link (vários de uma vez), pela vitrine da Shopee ou entre as últimas ofertas do bot."),
                   _t("Conferência periódica", f"Escolha de quanto em quanto tempo conferir: a cada 1 hora, 3 horas ou 6 horas no Standard e também a cada 15 ou 30 minutos no Premium."),
                   _t("Queda mínima", "Você define a queda que vale um aviso (de 1% a 90%, o padrão é 10%). O mesmo desconto não avisa duas vezes."),
                   _t("Onde avisar", "Sempre no painel e, se você quiser, por e-mail e nos grupos do WhatsApp (com a foto e o seu link de afiliado)."),
                   _t("Mensagem sua", "Escreva o aviso do seu jeito com o produto, o preço antes, o preço agora, a queda e o link."),
                   _t("Histórico de preços", "Cada produto mostra o preço inicial, o menor preço visto e o último alerta. Produto sem estoque ou sem comissão fica marcado como indisponível.")),
            _grupo("Recursos que só o Premium tem", "Para quem quer mais alcance e mais automação.",
                   _t("Envio por nicho", "Escolha o nicho de cada grupo, como beleza, moda ou casa, ou “Todos” para ofertas em geral. A cada intervalo sai uma oferta em cada nicho, só pros grupos dele. Os filtros e o texto da mensagem valem para todos.", "Premium"),
                   _t("Copiar ofertas de outros grupos e canais", "Marque os grupos e canais que você quer copiar. Toda mensagem com link da Shopee que chegar vira uma oferta sua, com o seu link de afiliado. Os links de quem postou são removidos e só o seu entra. Mensagem sem link da Shopee é ignorada.", "Premium"),
                   _t("Revisão do texto com IA", "A IA revisa o texto das ofertas antes de enviar: só o português, corrigir frases que não combinam com o produto, ou deixar a chamada mais atraente. Link, preço e cupom nunca são alterados. Se algo der errado, a oferta sai com o texto original.", "Premium")),
            _grupo("Cuidado com o seu número", "O bot foi feito para enviar sem exagero.",
                   _t("Ritmo controlado", "No máximo uma mensagem a cada 3 segundos por número, para não sair em rajada."),
                   _t("Sem duplicar", "Mensagem presa durante um reinício do servidor não é reenviada, para ninguém receber duas vezes."),
                   _t("Links verificados", "O bot só aceita links que de fato são da Shopee. Endereços disfarçados, como shopee.com.br.golpe.com, são recusados."),
                   _t("Dados protegidos", "As credenciais da sua conta de afiliado ficam guardadas cifradas.")),
            _grupo("Tudo conectado ao resto do Appfiliado", "O bot trabalha junto com os outros módulos.",
                   _t("Resultados", "As vendas das ofertas aparecem em Resultados, separadas por Sub ID."),
                   _t("Relatório por e-mail", "O relatório diário diz quantas ofertas saíram ontem."),
                   _t("Vitrine do Meu site", "As ofertas que o bot envia podem alimentar a vitrine do seu site na bio.")),
        ],
        "tabela": [
            ("Grupos e canais", f"até {s['grupos']}", f"até {p['grupos']}"),
            ("Ofertas por dia em cada grupo", f"até {s['ofertas_por_grupo_dia']}", f"até {p['ofertas_por_grupo_dia']}"),
            ("Menor intervalo entre ofertas", f"{s['intervalo_minimo']} minutos", f"{p['intervalo_minimo']} minutos"),
            ("Produtos no alerta de preço", f"até {s['alerta_produtos']}", f"até {p['alerta_produtos']}"),
            ("Conferência do alerta de preço", "a partir de 1 hora", "a partir de 15 minutos"),
            ("Busca na Shopee com filtros e categorias", True, True),
            ("Modo campanha e datas próprias", True, True),
            ("Testar busca e modo simulação", True, True),
            ("Mensagens avulsas agendadas", f"até {s['mensagens_agendadas']}", f"até {p['mensagens_agendadas']}"),
            ("Horário, dias e Sub ID por grupo", True, True),
            ("Envio por nicho (ofertas de cada tema pros seus grupos)", False, True),
            ("Copiar ofertas de outros grupos e canais", False, True),
            ("Revisão do texto com IA", False, True),
        ],
        "perguntas": [
            ("Preciso deixar o computador ou o celular ligados?", "Não. O servidor do Appfiliado fica conectado ao seu WhatsApp como mais um aparelho, como no WhatsApp Web. Você só precisa do celular para ler o QR Code ao conectar."),
            ("Meu número pode ser bloqueado pelo WhatsApp?", "O WhatsApp não gosta de envio em excesso. O bot manda no máximo uma mensagem a cada 3 segundos, respeita o intervalo e o limite diário do seu plano e só envia pros grupos que você escolher. Mesmo assim, não há garantia contra bloqueio. Muita gente usa um número separado só pras divulgações."),
            ("Posso mandar para canais do WhatsApp?", "Pode, desde que o seu número seja dono ou administrador do canal. Como canais não aceitam foto com legenda, eles recebem o texto com a prévia do link."),
            ("As ofertas saem com o meu link de afiliado?", "Sim. Cada oferta sai com o seu link, gerado na hora com a sua conta da Shopee. Você precisa conectar a conta de afiliado no painel, com a API da Shopee liberada."),
            ("Dá para testar sem enviar nada?", "Dá. O \"Testar busca\" mostra as próximas ofertas com a mensagem pronta e o modo simulação faz todo o processo sem enviar."),
            ("O que acontece nas datas como 11.11 e Black Friday?", "Se a data estiver ligada no modo campanha, o bot usa o ritmo, o texto e o cupom da campanha o dia todo e volta à configuração normal no dia seguinte."),
            ("Qual é a diferença entre Standard e Premium?", f"O Premium libera mais grupos e canais (até {p['grupos']}), mais ofertas por dia (até {p['ofertas_por_grupo_dia']}), um intervalo menor entre ofertas ({p['intervalo_minimo']} minutos), alerta de preço para mais produtos, o envio por nicho, a cópia de ofertas de outros grupos e a revisão de texto com IA."),
            ("O que preciso para começar?", "Uma conta de afiliado da Shopee com a API liberada e um número de WhatsApp com os grupos ou canais para onde as ofertas vão."),
        ],
    }


def site():
    s, p = plano.SITE[False], plano.SITE[True]
    return {
        "codigo": "site", "slug": "meu-site", "url": "landing_site", "nome": "Meu site",
        "titulo": "Meu site: link na bio com vitrine de ofertas — Appfiliado",
        "descricao": "Seu link na bio em seunome.appfiliado.com.br com botões, redes sociais, conversor de links e vitrine de ofertas da Shopee. Cliques contados e Sub ID próprio.",
        "h1": "Seu link na bio com vitrine de ofertas e conversor de links.",
        "texto": "Uma página bonita em seunome.appfiliado.com.br para colocar na bio do Instagram, do TikTok e de onde mais você divulga. Seus botões, suas redes e as ofertas da Shopee, tudo com o seu link de afiliado.",
        "resumo": [
            ("Botões de link", f"até {s['botoes']}", f"até {p['botoes']}"),
            ("Vitrine do bot ou de uma busca", "Sim", "Sim"),
            ("Vitrine com produtos escolhidos", "—", "Sim"),
            ("Assinatura \"Feito com Appfiliado\"", "Aparece", "Sem"),
            ("Redes sociais e conversor", "Sim", "Sim"),
        ],
        "grupos": [
            _grupo("O seu endereço", "Um endereço só seu, no ar assim que você publicar.",
                   _t("seunome.appfiliado.com.br", "Escolha o seu nome. O painel sugere um a partir do seu nome ou e-mail e você pode trocar depois."),
                   _t("Publicar e tirar do ar", "Você liga e desliga o site quando quiser. Fora do ar, o visitante vê uma página não encontrada."),
                   _t("Prévia ao vivo", "Um celular na tela mostra o site enquanto você edita, antes de salvar. A visita da prévia não conta nas estatísticas.")),
            _grupo("Do seu jeito", "Nome, foto e cores para combinar com a sua marca.",
                   _t("Nome e frase curta", "O nome (até 60 caracteres) e a frase que aparece embaixo (até 140) com seletor de emoji. Eles também formam o título e a descrição quando o link é compartilhado."),
                   _t("Sua foto", "Envie e ajuste a foto com zoom e recorte circular. Sem foto, o site mostra a inicial do seu nome."),
                   _t("Cores", "15 cores prontas ou qualquer outra que você escolher. O texto troca entre claro e escuro sozinho para continuar legível."),
                   _t("Fundo colorido ou claro", "Dois estilos de página."),
                   _t("Vitrine em lista ou carrossel", "Mostre as ofertas em uma grade de duas colunas ou em um carrossel que o visitante arrasta pro lado.")),
            _grupo("Botões de link", "Os links que levam o visitante para onde você quer.",
                   _t("Botões com o seu texto", "Cada botão tem o texto (aceita emoji), o link e a opção de ficar em destaque na cor do site. Exemplo: \"💬 Entrar no grupo de ofertas\"."),
                   _t("Organize como quiser", "Adicione, edite, apague e mude a ordem com as setas."),
                   _t("Limite de botões", f"{s['botoes']} botões no Standard e {p['botoes']} no Premium.", ""),
                   _t("Cliques de cada botão", "O painel mostra quantos cliques cada botão recebeu nos últimos 30 dias.")),
            _grupo("Redes sociais", "Os ícones aparecem embaixo dos botões.",
                   _t("Sete redes", "Instagram, TikTok, YouTube, X (Twitter), Facebook, WhatsApp e Telegram."),
                   _t("Cole o link ou só o @", "O @ vira o link completo. O WhatsApp aceita link de grupo ou o seu número com DDD."),
                   _t("Sem limite", "Você pode preencher todas as redes nos dois planos. Só aparece o ícone da rede que você preencher e os cliques são contados.")),
            _grupo("Conversor de links pros seus visitantes", "Quem chega no seu site cola um link da Shopee e compra pelo seu link de afiliado.",
                   _t("Cole e compre", "O visitante cola o link de um produto da Shopee e o botão leva à Shopee pelo seu link com o Sub ID do seu site."),
                   _t("Textos seus", "Você escreve o título, o texto e o texto do botão do conversor, ou usa os que já vêm prontos. Também pode desligar o conversor."),
                   _t("Links curtos funcionam", "O Appfiliado abre links curtos da Shopee para achar o produto."),
                   _t("Proteção contra abuso", "Cada visitante converte até 20 links por hora.")),
            _grupo("Vitrine de ofertas", "Uma seção com as ofertas do dia com foto, preço e desconto.",
                   _t("As últimas ofertas do bot", "Cada oferta que o bot enviar entra no topo da vitrine, sem repetir. Ficam as 100 mais recentes. Disponível para quem tem o Bot de WhatsApp."),
                   _t("Uma busca na Shopee", "Ofertas em geral, por palavra-chave, de uma loja ou por categoria, ordenadas por mais vendidos, maior comissão ou maior desconto. A vitrine é atualizada a cada 3 horas com até 100 produtos."),
                   _t("Produtos que você escolher", "Cole os links dos produtos, um por linha e na ordem que quiser, até 60. A vitrine mostra só o que você escolheu.", "Premium"),
                   _t("Categorias", "Quando há produtos de mais de uma categoria, o visitante filtra por elas. Você pode corrigir a categoria de cada produto."),
                   _t("Seu link em cada produto", "Cada produto leva o visitante à Shopee pelo seu link de afiliado.")),
            _grupo("Cliques e vendas", "Veja o que o seu site está gerando.",
                   _t("Contador de cliques", "Visitas, cliques em botões e redes, cliques em produtos e conversões do conversor nos últimos 30 dias. Os produtos mais clicados aparecem em destaque."),
                   _t("Sub ID próprio", "O site tem um Sub ID pro conversor e outro opcional pra vitrine. As vendas aparecem separadas em Resultados, em \"Comissão por Sub ID\".")),
            _grupo("A marca Appfiliado", "O rodapé do seu site.",
                   _t("Assinatura no rodapé", "No Standard, o rodapé mostra \"Feito com Appfiliado\".", ""),
                   _t("Sem assinatura", "No Premium, o rodapé fica só com o seu aviso de que os links são de afiliado.", "Premium")),
        ],
        "tabela": [
            ("Botões de link", f"até {s['botoes']}", f"até {p['botoes']}"),
            ("Vitrine com as ofertas do bot ou de uma busca", True, True),
            ("Vitrine com produtos escolhidos por você (até 60)", False, True),
            ("\"Feito com Appfiliado\" no rodapé", "Aparece", "Sem"),
            ("Redes sociais (7)", True, True),
            ("Conversor de links para visitantes", True, True),
            ("Contador de cliques e Sub ID próprio", True, True),
            ("Prévia ao vivo, cores e foto", True, True),
        ],
        "perguntas": [
            ("Posso usar o meu próprio domínio?", "Por enquanto não. O seu endereço é seunome.appfiliado.com.br."),
            ("Preciso ter o Bot de WhatsApp?", "Não. A vitrine pode vir de uma busca na Shopee ou, no Premium, dos produtos que você escolher. A opção \"últimas ofertas que o bot enviou\" só aparece para quem tem o Bot."),
            ("O conversor de links gera comissão para mim?", "Sim. O visitante cola o link de um produto da Shopee e vai pra loja pelo seu link de afiliado com o Sub ID do seu site, para você acompanhar as vendas em Resultados."),
            ("A vitrine atualiza sozinha?", "A vitrine por busca é refeita a cada 3 horas e a das ofertas do bot, a cada oferta enviada. A vitrine com produtos escolhidos por você é refeita quando você salva."),
            ("O que muda do Standard pro Premium?", f"O Premium tem até {p['botoes']} botões (no Standard, {s['botoes']}), permite escolher os produtos da vitrine e tira a assinatura \"Feito com Appfiliado\" do rodapé. Todo o resto é igual."),
            ("O que acontece se eu voltar pro Standard?", f"O site continua no ar com os primeiros {s['botoes']} botões. A vitrine com produtos escolhidos fica vazia até você trocar a fonte."),
        ],
    }


def carrosseis():
    s, p = plano.CARROSSEIS[False], plano.CARROSSEIS[True]
    return {
        "codigo": "carrosseis", "slug": "gerador-de-carrosseis", "url": "landing_carrosseis", "nome": "Gerador de carrosséis",
        "titulo": "Gerador de carrosséis pro Instagram — Appfiliado",
        "descricao": "Cole um link da Shopee e receba um carrossel pronto pro Instagram, com roteiro, legenda e hashtags escritos por IA, 10 modelos, editor e download em PNG.",
        "h1": "Cole um link da Shopee e receba um carrossel pronto pro Instagram.",
        "texto": "O Appfiliado puxa os dados do produto, a IA escreve o roteiro dos slides, a legenda e as hashtags, e você ajusta tudo no editor e baixa as imagens já com o seu link de afiliado.",
        "resumo": [
            ("Carrosséis por dia", f"{s['geracoes']}", f"{p['geracoes']}"),
            ("Modelos", "6", "10"),
            ("Cores", "5 temas", "Livres"),
            ("Foto própria e remoção de fundo", "—", "Sim"),
            ("Reescrita de slides por IA", "—", f"até {p['reescritas']} por dia"),
        ],
        "grupos": [
            _grupo("Do link ao carrossel em segundos", "Você só precisa de um link de produto da Shopee.",
                   _t("Cole o link", "Se você colar um texto, o Appfiliado usa o primeiro link da Shopee que achar. A geração leva até 30 segundos."),
                   _t("Dados do produto", "O Appfiliado puxa o nome, o preço, a nota, as vendas, a foto e a loja direto da Shopee. O preço antigo é calculado a partir do desconto."),
                   _t("Seu link de afiliado", "O carrossel sai com o seu link de afiliado e o Sub ID \"instagram\", para você ver em Resultados as vendas que vêm do Instagram."),
                   _t("Preço sempre certo", "O preço vem da Shopee na hora da geração e não é editável, para ninguém anunciar um valor errado.")),
            _grupo("A IA escreve para você", "Roteiro, legenda e hashtags já saem prontos.",
                   _t("Roteiro dos slides", "A IA escreve os textos de cada slide a partir dos dados do produto, sem inventar medidas ou garantias, e destaca uma ou duas palavras-chave."),
                   _t("Legenda e hashtags", "A legenda do post e as hashtags, com #achadinhos e #shopee sempre incluídas."),
                   _t("Sempre sai um carrossel", "Se a IA estiver indisponível, o Appfiliado monta um roteiro simples e o carrossel é gerado do mesmo jeito.")),
            _grupo("Modelos e slides", "Cada slide tem uma função no carrossel, de 2 a 10 slides.",
                   _t("6 modelos Standard", "Destaque, Editorial, Promo, Neon, Polaroid e Bento."),
                   _t("4 modelos Premium", "Vitrine, Anotado, Etiqueta e Ficha com slides de vantagens, números e qualidades do produto.", "Premium"),
                   _t("Tipos de slide", "Capa, texto com arte, produto, preço, avaliações, chamada e final nos modelos Standard. Capa, vantagens, números, qualidades, preço e chamada nos modelos Premium."),
                   _t("Troque de modelo sem perder o texto", "Ao mudar entre as duas famílias de modelos, os textos são levados pro novo modelo, sempre que possível.")),
            _grupo("O seu visual", "Cores, fonte e o seu @ no carrossel.",
                   _t("5 temas de cor", "Verde, laranja, rosa, azul e preto nos dois planos."),
                   _t("Cores livres", "Escolha qualquer cor pro carrossel.", "Premium"),
                   _t("5 fontes à escolha", "Moderna, geométrica, impacto, elegante e serifa fina, além da fonte do modelo.", "Premium"),
                   _t("Seu @ do Instagram", "O seu @ aparece na capa e em outros pontos do carrossel nos dois planos."),
                   _t("Mostrar ou esconder detalhes", "Ligue ou desligue a nota e as vendas, o preço antigo com o desconto e o \"Arrasta\" no rodapé.", "Premium"),
                   _t("Salvar como meu padrão", "Guarde o seu modelo, cor, fonte, @ e as opções, e os próximos carrosséis já saem do seu jeito.", "Premium")),
            _grupo("Foto própria e remoção de fundo", "Pro produto aparecer do jeito que você quer.",
                   _t("Foto própria", "Troque a foto da Shopee por uma sua (JPG, PNG ou WebP de até 8 MB) e volte à da Shopee quando quiser.", "Premium"),
                   _t("Remoção de fundo", "Tire o fundo da foto com um clique e o produto aparece solto e com sombra no chão nos modelos Premium. Funciona no seu navegador e leva alguns segundos.", "Premium")),
            _grupo("Um editor completo", "Ajuste cada detalhe antes de baixar.",
                   _t("Edite os textos", "Cada campo tem contador de caracteres, seletor de emoji e a opção de destacar palavras com marca-texto."),
                   _t("Mova, remova e volte ao original", "Reordene os slides, remova os que não quiser (a capa fica sempre primeiro) e volte ao texto que a IA escreveu com um clique."),
                   _t("Adicione e duplique slides", "Crie slides novos e duplique os que funcionam bem, até 10 por carrossel.", "Premium"),
                   _t("Outra versão com IA", f"Peça à IA para reescrever um slide, até {p['reescritas']} vezes por dia. Ela mantém o preço e a arte e muda só o texto.", "Premium"),
                   _t("Alertas em tempo real", "O editor avisa quando um texto está longo demais, encostando ou com pouco contraste, antes de você baixar."),
                   _t("Salva sozinho", "Suas alterações são salvas automaticamente e você pode voltar ao carrossel quando quiser.")),
            _grupo("Legenda e download", "Pronto para postar.",
                   _t("Legenda e hashtags", "Edite a legenda (até 2.200 caracteres) e as hashtags e copie tudo com um clique."),
                   _t("Imagens em PNG", "Baixe cada slide em PNG de 1080 × 1350 pixels, no formato 4:5 do Instagram, ou todos juntos em um ZIP."),
                   _t("ZIP completo", "O ZIP traz as imagens, a legenda, as hashtags e o seu link de afiliado para colocar na bio.")),
        ],
        "tabela": [
            ("Carrosséis por dia", f"{s['geracoes']}", f"{p['geracoes']}"),
            ("Modelos", "6 Standard", "6 Standard + 4 Premium"),
            ("Cores", "5 temas", "5 temas + cores livres"),
            ("Fontes", "A do modelo", "A do modelo + 5 opções"),
            ("Foto própria e remoção de fundo", False, True),
            ("Adicionar e duplicar slides", False, True),
            ("Reescrita de slides por IA", False, f"até {p['reescritas']} por dia"),
            ("Mostrar ou esconder nota, preço antigo e \"Arrasta\"", False, True),
            ("Salvar o seu padrão visual", False, True),
            ("Roteiro, legenda e hashtags por IA", True, True),
            ("Editar, mover e remover slides", True, True),
            ("Download em PNG e ZIP", True, True),
        ],
        "perguntas": [
            ("Funciona com qualquer produto da Shopee?", "Com produtos liberados para afiliados. Se a Shopee não libera o produto para afiliados, o Appfiliado avisa que ele não tem comissão e a geração não conta no seu limite."),
            ("Preciso conectar a minha conta da Shopee?", "Sim. O Appfiliado usa a sua conta de afiliado, com a API da Shopee liberada, para buscar os dados do produto e gerar o seu link."),
            ("Os carrosséis têm marca d'água?", "Não. As imagens saem limpas, prontas para postar."),
            ("Posso editar o preço que aparece no carrossel?", "Não. O preço vem da Shopee na hora da geração, para você não anunciar um valor errado."),
            ("E se a IA estiver fora do ar?", "O Appfiliado monta um roteiro simples e o carrossel é gerado do mesmo jeito. Você pode editar os textos como de costume."),
            ("O limite diário reinicia quando?", "À meia-noite no horário de Brasília. Gerações que falham por link inválido ou produto sem comissão não gastam o seu limite."),
            ("A remoção de fundo funciona em qualquer foto?", "Funciona melhor em fotos de produto com bom contraste com o fundo. Em fotos de embalagem clara sobre fundo claro, a base do produto pode ficar um pouco apagada e você pode voltar pra foto inteira com um clique."),
            ("O que muda do Standard pro Premium?", f"O Premium gera {p['geracoes']} carrosséis por dia (no Standard, {s['geracoes']}), tem 4 modelos a mais, cores e fontes livres, foto própria com remoção de fundo, adiciona e duplica slides, reescreve slides com IA (até {p['reescritas']} por dia) e guarda o seu padrão visual."),
        ],
    }


def estudio():
    s, p = plano.CARROSSEIS[False], plano.CARROSSEIS[True]
    return {
        "codigo": "estudio", "slug": "estudio-instagram", "url": "landing_estudio", "nome": "Estúdio Instagram",
        "titulo": "Estúdio Instagram para afiliado Shopee — Appfiliado",
        "descricao": "Crie posts e stories com o seu link de afiliado a partir do link de um produto da Shopee com textos por IA e publique direto no seu Instagram na hora ou agendado.",
        "h1": "Do link da Shopee ao post publicado no seu Instagram.",
        "texto": "Cole o link de um produto e a IA monta o post com a foto, o preço e a legenda. Você ajusta no editor e publica no feed ou nos stories na hora ou no horário que escolher.",
        "resumo": [
            ("Criações com IA por dia", f"{s['geracoes']}", f"{p['geracoes']}"),
            ("Modelos prontos", "7", "7 + os seus"),
            ("Cores, fundos e ajustes", "Os do modelo", "Livres"),
            ("Minha marca", "O seu @", "@, logo, cores e fonte"),
            ("Publicar e agendar no Instagram", "Sim", "Sim"),
        ],
        "grupos": [
            _grupo("Quatro jeitos de começar", "Escolha como o post nasce. Depois, tudo continua editável.",
                   _t("Do link de um produto", "Cole o link da Shopee e a IA monta o post com a foto, o preço, o preço antigo e o desconto, já com o seu link de afiliado e o Sub ID \"instagram\"."),
                   _t("De um modelo", "Escolha um dos 7 modelos prontos e troque os textos."),
                   _t("Com IA", "Descreva o post que você quer e a IA escreve os slides e a legenda."),
                   _t("Em branco", "Comece do zero. No Standard, o post começa com uma capa. No Premium, você monta slide por slide.")),
            _grupo("A IA escreve com você", "Textos de afiliado prontos para postar.",
                   _t("Slides e legenda", "A IA escreve como afiliado sem inventar medidas ou garantias e sem fazer conta de preço: o preço vem da Shopee."),
                   _t("Ajuste com IA", "Peça mudanças com as suas palavras, como \"deixe os textos mais curtos\", ou crie os slides de novo."),
                   _t("Limite por dia", f"{s['geracoes']} criações com IA por dia no Standard e {p['geracoes']} no Premium. Quando acabam, o post de produto sai do modelo com a foto e o preço.")),
            _grupo("Posts e stories", "Três formatos no tamanho certo do Instagram.",
                   _t("Post 1:1 e 4:5", "Carrossel de até 10 slides ou post de uma imagem em 1080 × 1080 ou 1080 × 1350 pixels."),
                   _t("Story 9:16", "Sequência de stories em 1080 × 1920 pixels."),
                   _t("Tipos de slide", "Capa, produto, preço, lista, texto, cupom e chamada."),
                   _t("Margens de segurança", "O editor mostra as margens e avisa quando um texto fica pequeno demais ou sai da área segura.")),
            _grupo("O seu visual", "No Premium, o post fica com a cara da sua marca.",
                   _t("Seu @ nos posts", "O seu @ do Instagram aparece nos slides nos dois planos."),
                   _t("5 temas de cor", "Verde, laranja, rosa, azul e preto em qualquer post.", "Premium"),
                   _t("Minha marca", "Logo, nome, cor principal, cor de destaque e uma de 6 fontes em todos os posts.", "Premium"),
                   _t("Fundos e ajustes", "Fundo de cor, arte ou imagem e o tamanho dos textos, as margens, o alinhamento e a posição de cada slide.", "Premium"),
                   _t("Mais slides", "Adicione, duplique e troque o tipo dos slides.", "Premium"),
                   _t("Seus modelos", "Salve um post como modelo e comece os próximos por ele.", "Premium")),
            _grupo("Fotos", "Para o produto aparecer do jeito que você quer.",
                   _t("Foto do produto", "A foto da Shopee entra sozinha nos posts de produto."),
                   _t("Suas fotos", "Envie fotos (JPG, PNG ou WebP, até 12 MB) e use nos slides."),
                   _t("Remoção de fundo", "Tire o fundo da foto com um clique e o produto aparece solto no slide. Funciona no seu navegador.", "Premium")),
            _grupo("Publicar no Instagram", "Sem baixar e subir imagem por imagem.",
                   _t("Conecte o seu Instagram", "Conta profissional (comercial ou de criador) pelo login oficial do Instagram."),
                   _t("Na hora ou agendado", "Publique agora ou escolha o dia e a hora até 60 dias para frente."),
                   _t("Feed e stories", "Posts 1:1 e 4:5 vão para o feed com a legenda. Posts 9:16 viram stories, um por slide."),
                   _t("Acompanhe tudo", "A página de Publicações mostra o que está agendado e o que já foi com o link para ver no Instagram. Dá para cancelar um agendamento.")),
            _grupo("Baixar e copiar", "Para postar onde você quiser.",
                   _t("PNG e ZIP", "Baixe um slide ou todos num ZIP com a legenda junto."),
                   _t("Legenda e link", "Copie a legenda (até 2.200 caracteres) e o seu link de afiliado com um clique.")),
        ],
        "tabela": [
            ("Criações com IA por dia", f"{s['geracoes']}", f"{p['geracoes']}"),
            ("7 modelos prontos de post e story", True, True),
            ("Publicar no feed e nos stories na hora ou agendado", True, True),
            ("Editar os textos e a foto dos slides", True, True),
            ("Download em PNG e ZIP", True, True),
            ("Adicionar, duplicar e trocar o tipo dos slides", False, True),
            ("Temas de cor e Minha marca completa", False, True),
            ("Fundos e ajustes de cada slide", False, True),
            ("Remoção de fundo da foto", False, True),
            ("Salvar os seus modelos", False, True),
        ],
        "perguntas": [
            ("Preciso de uma conta profissional no Instagram?", "Para publicar pelo Appfiliado, sim: comercial ou de criador. Para criar e baixar os posts, não precisa conectar nada."),
            ("Dá para colocar o link no story?", "A Meta não deixa colocar o adesivo de link na publicação automática. Para mandar o link, use as Automações Instagram: no Premium delas, quem responder o story recebe o link por DM."),
            ("Preciso conectar a minha conta da Shopee?", "Para criar posts a partir do link de um produto, sim, com a API da Shopee liberada. Os modelos, a IA e o post em branco funcionam sem."),
            ("Os posts têm marca d'água?", "Não. As imagens saem limpas, só com o seu @ e, no Premium, a sua marca."),
            ("O limite diário reinicia quando?", "À meia-noite, no horário de Brasília."),
            ("O que muda do Standard pro Premium?", f"O Premium cria {p['geracoes']} posts com IA por dia (no Standard, {s['geracoes']}), deixa mudar cores, fundos e ajustes de cada slide, usa a sua marca completa, remove o fundo das fotos e guarda os seus modelos. Publicar e agendar é igual nos dois."),
        ],
    }


def automacoes():
    return {
        "codigo": "automacoes", "slug": "automacoes-instagram", "url": "landing_automacoes", "nome": "Automações Instagram",
        "titulo": "Automações Instagram para afiliado Shopee — Appfiliado",
        "descricao": "Quem comentar a palavra certa no seu post recebe o seu link de afiliado por DM na hora. Respostas a comentários, stories e DMs no automático e sem limite por mês.",
        "h1": "Comentou a palavra-chave correta, recebeu link na DM.",
        "texto": "Escolha o post ou story e as palavras-chave que você quiser e pronto: quem comentar recebe o seu link de afiliado por DM, sem precisar responder um a um.",
        "resumo": [
            ("Pessoas respondidas por mês", "Sem limite", "Sem limite"),
            ("Automações ligadas", "Até 5", "Sem limite"),
            ("Stories e DMs com palavra-chave", "—", "Sim"),
            ("Link num botão e Sub ID por automação", "—", "Sim"),
        ],
        "grupos": [
            _grupo("Como funciona", "Três passos e a automação fica ligada.",
                   _t("Conecte o seu Instagram", "Conta profissional (comercial ou de criador) pelo login oficial do Instagram sem passar a sua senha para o Appfiliado."),
                   _t("Escolha o post e a palavra", "Um post específico ou todos os posts e as palavras que disparam, como QUERO ou LINK. Maiúsculas e acentos não importam."),
                   _t("Escreva a resposta e a DM", "A resposta que aparece no comentário e a DM com o seu link de afiliado.")),
            _grupo("Comentários nos posts", "O jeito mais usado pelos afiliados.",
                   _t("Resposta no comentário", "Escreva algumas respostas: sai uma delas, sorteada, para não parecer robô. Use {nome} para marcar a pessoa."),
                   _t("DM com o link", "A pessoa recebe o seu link na DM logo depois de comentar."),
                   _t("Do Estúdio para a automação", "Criou o post no Estúdio Instagram? Um clique cria a automação com o nome e o link do produto.")),
            _grupo("Só no Premium", "Mais lugares para responder e mais controle das vendas.",
                   _t("Respostas aos stories", "Quem responder o seu story recebe o link por DM. Vale para um story específico ou para todos.", "Premium"),
                   _t("DM com palavra-chave", "Quem mandar uma DM com a palavra, como CUPOM, recebe a resposta na hora.", "Premium"),
                   _t("Link num botão", "A DM chega com o seu texto e um botão, como \"Ver produto\", que abre o link.", "Premium"),
                   _t("Sub ID por automação", "Cada automação gera o link com o seu próprio Sub ID e em Resultados você vê quanto cada post vendeu.", "Premium"),
                   _t("Automações sem limite", "Deixe ligadas quantas automações quiser, uma para cada post. No Standard, ficam até 5 ligadas ao mesmo tempo.", "Premium")),
            _grupo("Seguro para a sua conta", "Regras para não parecer spam.",
                   _t("Uma vez por pessoa", "Cada pessoa recebe a resposta uma vez só em cada automação, mesmo se comentar de novo."),
                   _t("Post viralizou? Ninguém fica sem resposta", "Não há limite por mês. O Instagram aceita até 750 respostas por hora em cada conta: passando disso, as respostas entram numa fila e saem na hora seguinte por ordem de chegada."),
                   _t("API oficial", "O Appfiliado usa a API oficial do Instagram (Meta). Nada de senha nem de extensão no navegador."),
                   _t("No seu controle", "Pause, edite ou exclua cada automação no painel quando quiser.")),
            _grupo("Histórico", "Veja quem foi respondido.",
                   _t("Quem recebeu", "Data, pessoa, o que ela escreveu e se a resposta e a DM saíram."),
                   _t("Resumo do mês", "O painel mostra quantas pessoas foram respondidas no mês e quantas estão na fila quando o post viraliza.")),
        ],
        "tabela": [
            ("Pessoas respondidas por mês", "Sem limite", "Sem limite"),
            ("Automações ligadas ao mesmo tempo", "Até 5", "Sem limite"),
            ("Respostas a comentários nos posts", True, True),
            ("Resposta no comentário e DM com o link", True, True),
            ("Histórico de quem foi respondido", True, True),
            ("Respostas aos stories", False, True),
            ("DMs com palavra-chave", False, True),
            ("Link num botão na DM", False, True),
            ("Sub ID por automação", False, True),
        ],
        "perguntas": [
            ("Preciso de uma conta profissional no Instagram?", "Sim: comercial ou de criador. Você conecta pelo login oficial do Instagram sem passar a sua senha para o Appfiliado."),
            ("A DM chega para quem não me segue?", "Chega. A DM em resposta a um comentário vai para quem comentou, mesmo que a pessoa não siga você. Nesse caso, ela aparece nas solicitações de mensagem."),
            ("Tem limite de respostas?", "Não por mês. O Instagram aceita até 750 respostas por hora em cada conta: se um post viralizar e passar disso, as respostas entram numa fila e saem na hora seguinte por ordem de chegada. A resposta a um comentário pode sair até 7 dias depois dele; a de uma DM ou resposta de story, até 24 horas depois."),
            ("Preciso deixar o painel aberto?", "Não. As automações rodam no servidor do Appfiliado 24 horas por dia."),
            ("O que muda do Standard pro Premium?", "O Standard responde comentários nos posts com até 5 automações ligadas ao mesmo tempo. O Premium também responde stories e DMs com palavra-chave, não tem limite de automações ligadas, manda o link num botão e gera um Sub ID para cada automação. Nos dois, sem limite de pessoas respondidas por mês."),
        ],
    }


# ---- ferramentas incluídas em todos os planos (sem Standard × Premium) ----

def radar():
    return {
        "codigo": "radar", "slug": "radar-de-ofertas", "url": "landing_radar", "nome": "Radar de ofertas", "incluso": True,
        "titulo": "Radar de ofertas para afiliados da Shopee — Appfiliado",
        "descricao": "Mais de 30 mil produtos da Shopee com comissão de afiliado, atualizados todo dia. Filtre por comissão, desconto, preço e categoria e copie o seu link de afiliado em um clique.",
        "h1": "Ache o produto certo para divulgar em segundos.",
        "texto": "Mais de 30 mil produtos da Shopee com comissão de afiliado, atualizados todo dia. Filtre por comissão, desconto, preço e categoria e copie o seu link de afiliado em um clique.",
        "grupos": [
            _grupo("Do catálogo ao link", "Três passos e o produto está pronto para divulgar.",
                   _t("Busque", "Digite uma palavra-chave, escolha uma categoria ou só veja os mais vendidos."),
                   _t("Filtre", "Refine por comissão, desconto, preço e avaliação até sobrar só o que vale a pena."),
                   _t("Divulgue", "Copie o seu link de afiliado ou mande o produto direto pro grupo, com o Bot de WhatsApp.")),
            _grupo("Filtros de verdade", "Encontre exatamente o tipo de produto que o seu público compra.",
                   _t("Três ordens", "Mais vendidos, maior comissão ou maior desconto."),
                   _t("Palavra-chave e categoria", "Busque por fone, air fryer ou vestido. Ou escolha entre as 27 categorias principais da Shopee."),
                   _t("Mais filtros", "Preço mínimo e máximo, comissão de referência mínima, desconto mínimo e avaliação mínima."),
                   _t("Comissão extra do vendedor", "Marque para ver só os produtos com comissão extra, que rendem mais por venda.")),
            _grupo("Tudo sobre o produto num cartão", "Você decide sem abrir a Shopee.",
                   _t("Foto e selos", "Foto grande, selo de desconto e selo de comissão extra quando o produto tem."),
                   _t("Preço e comissão", "Preço atual, comissão de referência em porcentagem e quanto isso dá em reais."),
                   _t("Prova social", "Quantidade de vendidos, avaliação e nome da loja."),
                   _t("Link de afiliado na hora", "O link sai com a sua conta da Shopee e com o Sub ID \"radar\", para você ver em Resultados as vendas que vieram daqui.")),
            _grupo("O que fazer com o produto", "Cada cartão tem os atalhos pro próximo passo.",
                   _t("Copiar link", "Copia o seu link de afiliado, em todos os planos."),
                   _t("Mandar no grupo", "Envia o produto, com foto e texto, para um grupo ou canal de WhatsApp.", "Bot de WhatsApp"),
                   _t("Acompanhar o preço", "Coloca o produto no alerta de preço para você ser avisada quando ele cair.", "Bot de WhatsApp"),
                   _t("Criar post", "Leva o produto pro Estúdio Instagram e já começa o post, com a foto, o preço e o seu link.",
                      "Estúdio Instagram" if vendas.lancado() else "Estúdio Instagram · em breve")),
            _grupo("Sempre atualizado", "O catálogo é renovado todo dia.",
                   _t("Atualização diária", "Uma rodada por dia e uma completa por semana, com até 30 mil produtos."),
                   _t("Preço de agora", "Ao mandar no grupo ou acompanhar o preço, o Radar consulta o preço de agora na Shopee."),
                   _t("Busca rápida", "Os produtos ficam guardados no Appfiliado, então a busca é instantânea."),
                   _t("Resultados por página", "24 produtos por página, com navegação numerada.")),
        ],
        "perguntas": [
            ("O Radar custa a mais?", "Não. O Radar de ofertas está incluso em todos os planos do Appfiliado."),
            ("De onde vêm os produtos?", "Do catálogo de produtos da Shopee que têm comissão de afiliado. O Appfiliado atualiza esse catálogo todo dia."),
            ("O preço que aparece é o de agora?", "O catálogo é atualizado todo dia. Na hora de mandar no grupo ou acompanhar o preço, o Radar consulta o preço de agora na Shopee."),
            ("Preciso do Bot de WhatsApp?", "Não. Copiar o link de afiliado funciona em todos os planos. Mandar no grupo e acompanhar o preço precisam do Bot de WhatsApp, e criar o post precisa do Estúdio Instagram" + ("." if vendas.lancado() else ", que chega em breve.")),
            ("Não achei um produto que está na Shopee. E agora?", "A Shopee limita quantos produtos libera para afiliados, então nem todo produto do site aparece no Radar. Cole o link dele no Conversor de links e gere o seu link do mesmo jeito."),
        ],
    }


def conversor():
    return {
        "codigo": "conversor", "slug": "conversor-de-links", "url": "landing_conversor", "nome": "Conversor de links", "incluso": True,
        "titulo": "Conversor de links de afiliado da Shopee — Appfiliado",
        "descricao": "Cole um texto com links da Shopee e troque tudo pelo seu link de afiliado. O texto fica pronto para encaminhar ou para mandar direto num grupo de WhatsApp.",
        "h1": "Troque os links de qualquer texto pelo seu link de afiliado.",
        "texto": "Cole a mensagem de um canal, uma lista de ofertas ou links soltos. O Appfiliado troca todos os links da Shopee pelo seu link de afiliado e devolve o texto pronto para encaminhar.",
        "grupos": [
            _grupo("Cole, converta, encaminhe", "Menos de um minuto do texto original ao texto com o seu link.",
                   _t("Cole o texto", "Pode ser a mensagem que a Shopee mandou no canal dela ou uma lista de links de qualquer lugar."),
                   _t("Escolha como sai", "Mantenha o texto e troque só os links, ou receba só a lista dos links convertidos."),
                   _t("Converta e copie", "Clique em Converter, ajuste o texto se quiser e copie o resultado.")),
            _grupo("Dois jeitos de sair", "O mesmo texto, no formato que você precisar.",
                   _t("Manter o texto e trocar os links", "O texto fica igual e só os links da Shopee são trocados. Links que não são da Shopee, como convite de grupo, saem do texto."),
                   _t("Só os links convertidos", "Sai a lista dos links, um por linha, pronta para colar onde precisar.")),
            _grupo("Feito para afiliado", "Detalhes que fazem diferença no dia a dia.",
                   _t("Links curtos funcionam", "Os links curtos da Shopee são abertos para achar o produto certo."),
                   _t("Link limpo do produto", "Cada link vira o link do produto antes de receber o seu link, sem o rastreio de quem divulgou antes."),
                   _t("Sub ID opcional", "Escolha um Sub ID para medir a divulgação. Em branco, as vendas aparecem em Resultados como \"conversor\"."),
                   _t("Aviso quando não converte", "Se a Shopee não converter algum link, ele fica como estava e o painel diz qual foi.")),
            _grupo("Encaminhe para grupos do WhatsApp", "Para quem tem o Bot de WhatsApp.",
                   _t("Enviar no grupo", "Escolha o grupo ou o canal e envie o texto convertido sem sair da tela.", "Bot de WhatsApp"),
                   _t("Ajuste antes de enviar", "O texto convertido fica editável, então você acerta a frase antes de mandar.")),
            _grupo("Também no seu site", "O conversor chega aos seus seguidores.",
                   _t("Conversor no Meu site", "Quem visita o seu link na bio cola um link da Shopee e vai pra loja pelo seu link de afiliado.", "Meu site"),
                   _t("Limite por visitante", "Cada visitante converte até 20 links por hora, para proteger o seu site.", "Meu site")),
        ],
        "perguntas": [
            ("O Conversor custa a mais?", "Não. O Conversor de links está incluso em todos os planos do Appfiliado."),
            ("Quantos links dá para converter por vez?", "Até 20 links da Shopee em cada texto."),
            ("E os links de outras pessoas?", "No modo que mantém o texto, links que não são da Shopee e links de afiliado de outra pessoa saem do texto. Só ficam os seus."),
            ("Preciso conectar a minha conta da Shopee?", "Sim. O Conversor usa a sua conta de afiliado, com a API da Shopee liberada, para gerar os links, e a comissão cai na sua conta."),
            ("Dá para mandar o texto direto num grupo?", "Dá, com o Bot de WhatsApp conectado. Sem o Bot, você copia o resultado e encaminha."),
        ],
    }


def resultados():
    return {
        "codigo": "resultados", "slug": "resultados-e-metas", "url": "landing_resultados", "nome": "Resultados e metas", "incluso": True, "duvidas": "Resultados e metas",
        "titulo": "Resultados e metas de afiliado da Shopee — Appfiliado",
        "descricao": "Veja faturamento, comissão e pedidos da sua conta da Shopee por dia, semana ou mês, descubra qual divulgação vende mais e acompanhe quanto falta pras metas de bônus.",
        "h1": "Veja quanto vendeu, de onde veio e quanto falta pro bônus.",
        "texto": "Faturamento, comissão e pedidos da sua conta da Shopee por dia, semana ou mês, com Sub IDs que mostram qual grupo, site ou post vende mais. Cadastre as metas do mês e acompanhe quanto falta para cada faixa de bônus.",
        "grupos": [
            _grupo("Conecte uma vez", "Os números chegam sozinhos, sem planilha.",
                   _t("Conecte a sua conta", "Em Configurações, informe o AppID e o Secret da Shopee. O Secret é guardado criptografado."),
                   _t("O Appfiliado busca os números", "Faturamento, comissão e pedidos vêm direto da Shopee, e você pode atualizar quando quiser."),
                   _t("Veja no painel e no e-mail", "Tudo no painel, e o resumo do dia chega no seu e-mail se você quiser.")),
            _grupo("Resultados do jeito que você pergunta", "Escolha o período e veja só o que importa.",
                   _t("Períodos prontos", "Hoje, ontem, últimos 7 dias, esta semana, semana passada, este mês, mês passado e últimos 30 dias. Ou escolha um período seu."),
                   _t("Quatro números", "Faturamento, comissão estimada, comissão validada e pedidos, sem contar os cancelados."),
                   _t("Gráfico por dia, semana ou mês", "Compare faturamento, comissão e pedidos com um clique."),
                   _t("Produtos mais vendidos", "O ranking do período, com unidades, faturamento e comissão. A lista completa sai em Excel."),
                   _t("Vendas do período", "Cada venda com produto, quantidade, valor, comissão, status e Sub ID. Busque, filtre e exporte pro Excel.")),
            _grupo("Qual divulgação vende", "O Sub ID mostra de onde cada venda veio.",
                   _t("Comissão por Sub ID", "Veja quanto cada grupo, site ou post rendeu. O Bot, o Conversor, o Radar e o Meu site já usam Sub IDs próprios."),
                   _t("Agrupe do seu jeito", "Junte vários Sub IDs num nome só. Por exemplo, tudo que começa com \"grupo\" aparece como \"Grupos de WhatsApp\"."),
                   _t("Vendas sem Sub ID", "Dê um nome pras vendas que vieram sem Sub ID, como \"Orgânico\".")),
            _grupo("Metas da Shopee", "Saiba exatamente quanto falta pro bônus.",
                   _t("Cadastre as faixas", "Informe a meta de 100%, 125% e 150% e o bônus de cada uma. Se deixar 125% e 150% em branco, o Appfiliado calcula."),
                   _t("Quanto falta", "Para cada faixa, quanto falta faturar e quanto vale o bônus."),
                   _t("Quanto por dia", "O valor por dia pros dias que restam para chegar na próxima faixa."),
                   _t("Projeção do mês", "No ritmo atual, em que faixa o mês fecha. E o bônus que já está garantido.")),
            _grupo("Sempre à mão", "Os números aparecem onde você já está.",
                   _t("Resumo no Início", "O mês atual, o dia de ontem e a meta do mês na primeira tela do painel."),
                   _t("Relatório diário por e-mail", "No horário que você escolher, com resultados de ontem e do mês, Sub IDs e produtos mais vendidos."),
                   _t("Mesmas regras da Shopee", "Faturamento e pedidos pela data da compra, comissão validada pela data em que a Shopee confirmou o pedido."),
                   _t("Histórico guardado", "Os dias ficam guardados desde a conexão. A Shopee só deixa buscar uns 3 meses para trás.")),
        ],
        "perguntas": [
            ("Resultados e metas custam a mais?", "Não. Estão inclusos em todos os planos do Appfiliado."),
            ("Os números batem com os da Shopee?", "As regras são as mesmas dos relatórios da Shopee. Faturamento e pedidos contam pela data da compra, sem os cancelados. A comissão validada conta pela data em que a Shopee confirmou o pedido."),
            ("Por que de hoje só aparece a comissão validada?", "A Shopee libera faturamento, comissão estimada e pedidos no dia seguinte. A comissão validada vai entrando ao longo do dia."),
            ("Preciso cadastrar as metas?", "Não, é opcional. Se a Shopee te deu metas com bônus no mês, cadastre para acompanhar quanto falta."),
            ("Dá para exportar as vendas?", "Dá. As vendas do período saem em Excel, com os filtros que você aplicou."),
        ],
    }


# ---- apresentação: o formato de cada seção, os rótulos do índice, os chips e as amostras de cor ----
# Formatos: passos (etapas numeradas), split (título fixo à esquerda e lista à direita), destaque (um item
# grande e os outros ao lado), lista (linhas compactas em duas colunas), cartoes (grade), faixa (itens
# lado a lado) e premium (bloco escuro para o que é só do plano Premium).
APRESENTACAO = {
    "bot": {
        "layouts": ["passos", "split", "lista", "destaque", "split", "cartoes", "premium", "faixa", "cartoes"],
        "curtos": ["Conexão", "Ofertas", "Ritmo", "Testes", "Campanhas", "Alerta de preço", "Só no Premium", "Segurança", "Integrações"],
        "chips": {"15 categorias prontas": ["Moda", "Beleza", "Casa e Decoração", "Eletrônicos e Celulares", "Eletrodomésticos", "Bebês e Infantil",
                                           "Brinquedos e Games", "Esporte e Lazer", "Automotivo e Motos", "Pet Shop", "Papelaria e Escritório",
                                           "Saúde e Bem-estar", "Alimentos e Bebidas", "Joias e Acessórios", "Ferramentas e Construção"],
                  "Datas da Shopee": ["Dia do Consumidor", "3.3", "4.4", "5.5", "6.6", "7.7", "8.8", "9.9", "10.10", "11.11", "12.12", "Black Friday"]},
        "numeros": lambda: [(f"{plano.BOT[False]['grupos']} a {plano.BOT[True]['grupos']}", "grupos e canais"),
                            (f"{plano.BOT[False]['ofertas_por_grupo_dia']} a {plano.BOT[True]['ofertas_por_grupo_dia']}", "ofertas por dia em cada grupo"),
                            (f"{plano.BOT[True]['intervalo_minimo']} a {plano.BOT[False]['intervalo_minimo']} min", "entre uma oferta e outra"),
                            (f"{plano.BOT[False]['alerta_produtos']} a {plano.BOT[True]['alerta_produtos']}", "produtos no alerta de preço")],
    },
    "site": {
        "layouts": ["passos", "split", "destaque", "cartoes", "lista", "split", "faixa", "cartoes"],
        "curtos": ["Endereço", "Aparência", "Botões", "Redes", "Conversor", "Vitrine", "Cliques", "Marca"],
        "chips": {"Sete redes": ["Instagram", "TikTok", "YouTube", "X (Twitter)", "Facebook", "WhatsApp", "Telegram"]},
        "cores": {"Cores": ["#E8541E", "#D92D20", "#D6336C", "#F783AC", "#7048E8", "#B197FC", "#2F6FDE", "#1E3A8A", "#0E9AA7", "#2F9E44",
                            "#1F3A2E", "#F2B705", "#8B5E3C", "#5F6B7A", "#111111"]},
        "numeros": lambda: [(f"{plano.SITE[False]['botoes']} a {plano.SITE[True]['botoes']}", "botões de link"),
                            ("7", "redes sociais"), ("100", "produtos na vitrine"), ("20/h", "conversões por visitante")],
    },
    "radar": {
        "layouts": ["passos", "split", "cartoes", "lista", "faixa"],
        "curtos": ["Como funciona", "Filtros", "Cartão", "Atalhos", "Atualização"],
        "numeros": lambda: [("30 mil", "produtos no catálogo"), ("27", "categorias"), ("1x ao dia", "atualização"), ("24", "produtos por página")],
    },
    "conversor": {
        "layouts": ["passos", "split", "cartoes", "lista", "faixa"],
        "curtos": ["Como funciona", "Dois jeitos", "Detalhes", "Direto pro grupo", "No seu site"],
        "numeros": lambda: [("20", "links por vez"), ("2", "jeitos de sair"), ("1 clique", "para copiar"), ("Sub ID", "para medir cada divulgação")],
    },
    "resultados": {
        "layouts": ["passos", "split", "destaque", "cartoes", "faixa"],
        "curtos": ["Conexão", "Resultados", "Sub IDs", "Metas", "No dia a dia"],
        "numeros": lambda: [("8", "períodos prontos"), ("3", "faixas de meta"), ("Excel", "pras vendas do período"), ("1x ao dia", "relatório por e-mail")],
    },
    "estudio": {
        "layouts": ["passos", "destaque", "split", "cartoes", "lista", "split", "faixa"],
        "curtos": ["Começar", "IA", "Formatos", "Visual", "Fotos", "Publicar", "Baixar"],
        "chips": {"De um modelo": ["Achado do dia", "Oferta relâmpago", "Top 3 achados", "Dica de compra", "Cupom do dia",
                                   "Story de achado", "Story de cupom"]},
        "cores": {"5 temas de cor": ["#1F3A2E", "#E8541E", "#D6336C", "#2F6FDE", "#141414"]},
        "numeros": lambda: [(f"{plano.CARROSSEIS[False]['geracoes']} a {plano.CARROSSEIS[True]['geracoes']}", "criações com IA por dia"),
                            ("7", "modelos prontos"), ("3", "formatos: 1:1, 4:5 e 9:16"), ("60 dias", "para agendar")],
    },
    "automacoes": {
        "layouts": ["passos", "destaque", "premium", "cartoes", "faixa"],
        "curtos": ["Como funciona", "Comentários", "Só no Premium", "Segurança", "Histórico"],
        "numeros": lambda: [("Sem limite", "de pessoas respondidas por mês"), ("3", "gatilhos: comentário, story e DM"),
                            ("750/h", "e o que passar vai para a fila"), ("1 vez", "por pessoa em cada automação")],
    },
    "carrosseis": {
        "layouts": ["passos", "destaque", "split", "cartoes", "premium", "lista", "faixa"],
        "curtos": ["Criação", "IA", "Modelos", "Visual", "Fundo e foto", "Editor", "Download"],
        "chips": {"6 modelos Standard": ["Destaque", "Editorial", "Promo", "Neon", "Polaroid", "Bento"],
                  "4 modelos Premium": ["Vitrine", "Anotado", "Etiqueta", "Ficha"]},
        "cores": {"5 temas de cor": ["#1F3A2E", "#E8541E", "#D6336C", "#2F6FDE", "#141414"]},
        "numeros": lambda: [(f"{plano.CARROSSEIS[False]['geracoes']} a {plano.CARROSSEIS[True]['geracoes']}", "carrosséis por dia"),
                            ("10", "modelos"), ("2 a 10", "slides por carrossel"), ("1080×1350", "PNG pronto pro Instagram")],
    },
}


# Antes do lançamento, as páginas do Estúdio e das Automações ficam no ar sem falar de planos: sem os
# selos de Premium, sem a tabela Standard × Premium e com os textos abaixo no lugar dos que citam plano.
SEM_PLANOS = {
    "estudio": {
        "aviso": "O Estúdio Instagram será lançado em breve.",
        "itens": {"Em branco": "Comece do zero e monte o post slide por slide.",
                  "Limite por dia": "A IA tem um limite de criações por dia. Quando ele acaba, o post de produto sai do modelo com a foto e o preço.",
                  "Seu @ nos posts": "O seu @ do Instagram aparece nos slides."},
        "intros": {"O seu visual": "O post com a cara da sua marca."},
        "perguntas": {"Dá para colocar o link no story?": "A Meta não deixa colocar o adesivo de link na publicação automática. Para mandar o link, use as Automações Instagram: quem responder o story recebe o link por DM.",
                      "Os posts têm marca d'água?": "Não. As imagens saem limpas, só com o seu @ e a sua marca."},
        "numeros": [("4", "jeitos de começar um post"), ("7", "modelos prontos"), ("3", "formatos: 1:1, 4:5 e 9:16"), ("60 dias", "para agendar")],
    },
    "automacoes": {
        "aviso": "As Automações Instagram serão lançadas em breve.",
        "fora": {"Automações sem limite"},
        "grupos": {"Só no Premium": ("Stories, DMs e Sub ID", "Stories e DMs")},
    },
}


def _sem_planos(modulo, pagina):
    troca = SEM_PLANOS.get(modulo, {})
    for g in pagina["grupos"]:
        if g["titulo"] in troca.get("grupos", {}):
            g["titulo"], g["curto_breve"] = troca["grupos"][g["titulo"]]
        g["intro"] = troca.get("intros", {}).get(g["titulo"], g["intro"])
        g["itens"] = [i for i in g["itens"] if i["nome"] not in troca.get("fora", set())]
        for item in g["itens"]:
            item["plano"] = ""
            item["texto"] = troca.get("itens", {}).get(item["nome"], item["texto"])
    pagina["perguntas"] = [(q, troca.get("perguntas", {}).get(q, r)) for q, r in pagina["perguntas"] if "Standard" not in q]
    pagina["resumo"], pagina["tabela"], pagina["em_breve"] = [], [], True
    pagina["aviso_breve"] = troca.get("aviso", f"{pagina['nome']}: lançamento em breve.")
    return pagina


def _apresentar(modulo, pagina):
    ap = APRESENTACAO[modulo]
    breve = vendas.em_breve(modulo)
    if breve:
        pagina = _sem_planos(modulo, pagina)
    fundo = ""
    for n, (g, layout, curto) in enumerate(zip(pagina["grupos"], ap["layouts"], ap["curtos"])):
        if breve and layout == "premium":
            layout, curto = "cartoes", g.pop("curto_breve", curto)
        g["layout"], g["curto"] = layout, curto
        g["prints"] = [] if breve else prints_de(modulo, n)
        if layout == "premium":
            g["fundo"] = "verde"
        else:  # alterna branco e creme, para duas seções vizinhas nunca terem a mesma cor
            fundo = "creme" if fundo != "creme" else ""
            g["fundo"] = fundo
        for item in g["itens"]:
            item["chips"] = ap.get("chips", {}).get(item["nome"], [])
            item["cores"] = ap.get("cores", {}).get(item["nome"], [])
    pagina["numeros"] = (SEM_PLANOS.get(modulo, {}).get("numeros") if breve else None) or ap["numeros"]()
    pagina["print_do_topo"] = next((pr for g in pagina["grupos"] for pr in g["prints"] if not pr["celular"]), None)
    return pagina


PAGINAS = {m: (lambda m=m, f=f: _apresentar(m, f())) for m, f in {"bot": bot, "site": site, "carrosseis": carrosseis,
                                                                  "estudio": estudio, "automacoes": automacoes,
                                                                  "radar": radar, "conversor": conversor, "resultados": resultados}.items()}

# Prints do painel (landing/static/landing/prints/), mostrados dentro da seção que explica cada recurso:
# {ferramenta: {número da seção: [(arquivo, legenda, texto alternativo)]}}. São telas reais do painel com dados de exemplo.
PRINTS = {
    "bot": {0: [("bot-conexao", "Conectado como mais um aparelho, com o histórico da conexão.", "Tela de conexão do Bot de WhatsApp")],
            1: [("bot-ofertas", "De onde vêm as ofertas, os filtros e o histórico do que foi enviado.", "Tela de ofertas automáticas do Bot de WhatsApp")],
            4: [("bot-campanhas", "Marque as datas da Shopee e o bot muda de ritmo e de texto sozinho.", "Tela do modo campanha do Bot de WhatsApp")],
            5: [("bot-alerta", "Produtos acompanhados, últimos alertas e a mensagem que vai pros grupos.", "Tela do alerta de preço do Bot de WhatsApp")]},
    "site": {0: [("site-pronto", "O editor e, ao lado, o site pronto: 3 botões, 4 redes sociais, o conversor de links e a vitrine de ofertas em carrossel.",
                  "Exemplo de site pronto no celular, com botões, redes sociais, conversor de links e vitrine de ofertas")],
             2: [("site-botoes", "Seus botões, o conversor de links e a prévia ao lado.", "Botões e conversor de links do Meu site")]},
    "carrosseis": {5: [("carrossel-editor", "O carrossel pronto, com os textos de cada slide para ajustar.", "Editor de carrosséis com o primeiro slide pronto")]},
    "radar": {1: [("radar", "Busca por palavra-chave, categoria, preço, comissão e desconto.", "Tela de filtros do Radar de ofertas")],
              2: [("radar-produtos", "Cada produto com foto, desconto, comissão e atalhos para divulgar.", "Produtos do Radar de ofertas com comissão e desconto")]},
    "conversor": {0: [("conversor", "Do texto original ao texto pronto, com o seu link no lugar dos links da Shopee.", "Tela do Conversor de links com o texto convertido")]},
    "resultados": {1: [("resultados", "Faturamento, comissão e pedidos do período, com gráfico e meta do mês.", "Tela de resultados do mês"),
                       ("resultados-produtos", "O ranking de produtos e a lista de vendas, com filtros e Excel.", "Produtos mais vendidos e vendas do período")],
                   3: [("metas", "Quanto falta para cada faixa de bônus e a projeção do mês.", "Tela de metas da Shopee")],
                   4: [("inicio", "A primeira tela do painel, com o mês, o dia anterior e a meta.", "Tela inicial do painel do Appfiliado")]},
    "notas": {0: [("notas-lote", "Notas autorizadas e e-mails indo pros vendedores, com o andamento de cada etapa.", "Lote de notas fiscais do Emissor NFS-e")],
              1: [("notas", "Cadastro da empresa, certificado e o uso do seu plano no mês.", "Tela inicial do Emissor NFS-e")]},
}


# Tamanhos (largura, altura) de cada imagem no computador e no celular, em pixels de tela. Saem do final.py.
TAMANHOS = {
    "bot-alerta": (1100, 2136, 420, 2300),
    "bot-campanhas": (1100, 1345, 420, 2300),
    "bot-conexao": (1100, 972, 420, 1329),
    "bot-ofertas": (1100, 2361, 420, 2300),
    "carrossel-editor": (1100, 1726, 420, 1757),
    "conversor": (1100, 1088, 420, 1746),
    "inicio": (1100, 1049, 420, 2179),
    "metas": (1100, 900, 420, 1251),
    "notas": (1100, 1102, 420, 1710),
    "notas-lote": (1100, 1250, 420, 1700),
    "radar": (1100, 577, 420, 703),
    "radar-produtos": (1100, 1033, 420, 1785),
    "resultados": (1100, 861, 442, 2144),
    "resultados-produtos": (1100, 2044, 442, 2300),
    "site-pronto": (380, 1129, 300, 891),  # o site visto pelo visitante, num celular (marketing/appfiliado/prints/site_pronto.py)
    "site-botoes": (1100, 1206, 420, 1387),
    "site-editor": (1100, 1249, 420, 2300),
    "site-editor-form": (712, 1159, 420, 1462),  # recorte do site-editor só com a coluna do formulário
}


# O site pronto (o que o visitante vê) num celular ao lado do editor do painel, como no Appfiliado.
# {print do celular: (print do editor, legenda do celular, legenda do editor)}. No computador vale a legenda
# do PRINTS. No celular, um fica embaixo do outro, cada um com a sua legenda.
AO_LADO_DO_EDITOR = {"site-pronto": ("site-editor-form",
                                     "O site pronto: 3 botões, 4 redes sociais, o conversor de links e a vitrine de ofertas em carrossel.",
                                     "No editor você escolhe o endereço, a foto, o nome, as cores e as redes sociais.")}


def _print(a, leg, alt):
    w, h, wm, hm = TAMANHOS[a]
    p = {"arquivo": f"landing/prints/{a}.webp", "arquivo_m": f"landing/prints/{a}-m.webp",
         "legenda": leg, "alt": alt, "largura": w, "altura": h, "largura_m": wm, "altura_m": hm, "celular": None}
    if a in AO_LADO_DO_EDITOR:
        e, leg_celular, leg_editor = AO_LADO_DO_EDITOR[a]
        p["celular"] = {"legenda": leg_celular, "editor": _print(e, leg_editor, "Editor do Meu site: endereço, perfil, cores e redes sociais")}
    return p


def prints_de(modulo, secao):
    """As telas do painel que ilustram a seção `secao` (0, 1, ...) da página da ferramenta."""
    return [_print(*p) for p in PRINTS.get(modulo, {}).get(secao, [])]
