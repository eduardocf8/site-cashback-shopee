"""Conteúdo das páginas de recursos de cada módulo (/bot-de-whatsapp/, /meu-site/, /gerador-de-carrosseis/).

Tudo aqui foi levantado no código do produto (não nos textos de marketing). Os limites vêm de
licencas/planos.py, então mudar um número lá muda a página junto. Cada recurso é (nome, texto) e,
quando só o Premium tem, (nome, texto, "Premium")."""

from licencas import planos as plano


def _t(nome, texto, so=""):
    return {"nome": nome, "texto": texto, "plano": so, "chips": [], "cores": []}


def _grupo(titulo, intro, *itens):
    return {"titulo": titulo, "intro": intro, "itens": list(itens)}


def bot():
    s, p = plano.BOT[False], plano.BOT[True]
    return {
        "codigo": "bot", "slug": "bot-de-whatsapp", "url": "landing_bot", "nome": "Bot de WhatsApp",
        "titulo": "Bot de WhatsApp para afiliados da Shopee — Appfiliado",
        "descricao": "Ofertas da Shopee nos seus grupos e canais de WhatsApp, no automático e com o seu link de afiliado: busca com filtros, modo campanha, alerta de preço e muito mais.",
        "h1": "Ofertas da Shopee nos seus grupos de WhatsApp no automático.",
        "texto": "O bot escolhe as ofertas, gera o seu link de afiliado e publica nos grupos e canais que você definir, no ritmo e nos horários que você quiser. Tudo configurado por um painel simples, sem instalar nada.",
        "resumo": [
            ("Grupos e canais", f"até {s['grupos']}", f"até {p['grupos']}"),
            ("Ofertas por dia, em cada grupo", f"até {s['ofertas_por_grupo_dia']}", f"até {p['ofertas_por_grupo_dia']}"),
            ("Alerta de preço", f"{s['alerta_produtos']} produtos", f"{p['alerta_produtos']} produtos"),
            ("Copiar de outros grupos", "—", "Sim"),
            ("Revisão do texto com IA", "—", "Sim"),
        ],
        "grupos": [
            _grupo("Conecte o seu WhatsApp em minutos", "Sem instalar programa e sem deixar computador ligado.",
                   _t("Conexão por QR Code", "Você lê um QR Code em Aparelhos conectados, no seu celular, como no WhatsApp Web. O servidor do Appfiliado fica conectado como mais um aparelho."),
                   _t("Reconexão automática", "Se a conexão cair, o bot tenta voltar sozinho. O histórico da conexão mostra quando caiu, quando voltou e quando ficou instável."),
                   _t("Seus grupos e canais", "A lista traz todos os grupos e canais do seu número, com o número de participantes ou seguidores. Um canal só entra como destino se você for dono ou administrador."),
                   _t("Mensagem de teste", "Mande uma mensagem de teste para um grupo ou canal, com texto e imagem, para conferir tudo antes de ligar as ofertas.")),
            _grupo("Ofertas automáticas da Shopee com o seu link", "O bot escolhe o próximo produto que passa nos seus filtros e ainda não foi enviado, e publica em cada grupo.",
                   _t("Quatro jeitos de buscar", "Ofertas em geral, por palavra-chave, de uma loja específica (pelo link da loja ou de um produto dela) ou por categoria."),
                   _t("15 categorias prontas", "Moda, Beleza e Cuidados Pessoais, Casa e Decoração, Eletrônicos e Celulares, Eletrodomésticos, Bebês e Infantil, Brinquedos e Games, Esporte e Lazer, Automotivo e Motos, Pet Shop, Papelaria e Escritório, Saúde e Bem-estar, Alimentos e Bebidas, Joias e Acessórios, Ferramentas e Construção."),
                   _t("Ordem das ofertas", "Mais vendidos, maior comissão ou maior desconto."),
                   _t("Filtros", "Comissão mínima, desconto mínimo, preço mínimo e máximo, número mínimo de vendas e avaliação mínima. Todos são opcionais."),
                   _t("Seu link em todas as ofertas", "Cada oferta sai com o seu link de afiliado, gerado na hora, pra comissão ser sua."),
                   _t("Mensagem pronta", "Nome do produto, número de vendidos, desconto, avaliação, preço e o convite para comprar, com um fechamento que varia. Você pode somar um cupom."),
                   _t("Foto com texto ou prévia do link", "Você escolhe como a oferta aparece. Recomendamos a prévia do link: deixa o grupo mais leve e converte mais, pois muita gente não baixa imagens automaticamente. Os canais do WhatsApp não aceitam foto com legenda e sempre recebem a prévia."),
                   _t("Sem repetir produto", "O mesmo produto não volta ao mesmo grupo por quantos dias você definir, de 1 a 90 (o padrão é 7).")),
            _grupo("Você decide quando e quanto", "O ritmo é seu, dentro do limite do plano.",
                   _t("Intervalo entre ofertas", f"Escolha de quanto em quanto tempo sai uma oferta. O menor intervalo é de {s['intervalo_minimo']} minutos no Standard e de {p['intervalo_minimo']} minutos no Premium."),
                   _t("Horário e dias de envio", "Defina a janela (o padrão é das 7h às 23h, e vale janela que passa da meia-noite) e os dias da semana em que o bot trabalha."),
                   _t("Limite por dia", f"O plano libera até {s['ofertas_por_grupo_dia']} ofertas por dia em cada grupo no Standard e até {p['ofertas_por_grupo_dia']} no Premium. Você pode escolher um limite menor."),
                   _t("Grupos que recebem", f"Marque os grupos e canais de destino, até {s['grupos']} no Standard e até {p['grupos']} no Premium."),
                   _t("Sub IDs para medir", "Até 5 Sub IDs padrão e um Sub ID próprio por grupo. Em Resultados você vê quanto cada grupo vende.")),
            _grupo("Teste antes de enviar", "Veja o que vai sair sem mandar nada.",
                   _t("Testar busca", "Mostra as próximas ofertas que sairiam, já com a mensagem pronta, sem gerar link e sem enviar. Se nada serve, explica por quê."),
                   _t("Modo simulação", "O bot faz tudo, menos enviar, e registra como simulado. Depois de desligar, o que foi simulado não conta no limite do dia."),
                   _t("Últimas ofertas enviadas", "As 10 últimas, com o status (na fila, enviada, com erro ou simulada) e a mensagem completa."),
                   _t("Por que não está enviando", "A tela mostra o motivo quando nada sai: fora do horário, limite do dia atingido ou nenhum produto novo.")),
            _grupo("Modo campanha para datas especiais", "Nas datas que você ligar, o bot muda de ritmo e de texto sozinho e volta ao normal no dia seguinte.",
                   _t("Datas da Shopee", "Dia do Consumidor, todas as datas duplas de 3.3 a 12.12 e Black Friday. Já vêm ligadas a 9.9, 10.10, 11.11, Black Friday e 12.12, e valem todo ano."),
                   _t("Suas próprias datas", "Adicione até 20 datas suas, com nome e dia, e escolha se repetem todo ano."),
                   _t("Ritmo da campanha", f"Intervalo, limite de ofertas no dia e horário próprios para os dias de campanha, dentro dos limites do seu plano."),
                   _t("Busca e filtros da campanha", "Uma palavra-chave, um desconto mínimo e uma comissão mínima só pros dias de campanha."),
                   _t("Texto da campanha", "Uma frase de abertura e o cupom da campanha nas ofertas."),
                   _t("Página da campanha", "Envie a página da campanha da Shopee, com o seu link de afiliado, a cada 3 a 100 ofertas, em uma mensagem à parte com prévia grande."),
                   _t("Prévias e aviso", "Veja uma prévia de uma oferta e da mensagem da campanha antes. O painel avisa 7 dias antes de cada data.")),
            _grupo("Alerta de preço", "Acompanhe produtos e avise quando o preço cair.",
                   _t("Produtos acompanhados", f"Até {s['alerta_produtos']} produtos no Standard e até {p['alerta_produtos']} no Premium. Adicione por link (vários de uma vez), pela vitrine da Shopee ou entre as últimas ofertas do bot."),
                   _t("Conferência periódica", f"Escolha de quanto em quanto tempo conferir: a cada 1 hora, 3 horas ou 6 horas no Standard, e também a cada 15 ou 30 minutos no Premium."),
                   _t("Queda mínima", "Você define a queda que vale um aviso (de 1% a 90%, o padrão é 10%). O mesmo desconto não avisa duas vezes."),
                   _t("Onde avisar", "Sempre no painel e, se você quiser, por e-mail e nos grupos do WhatsApp (com a foto e o seu link de afiliado)."),
                   _t("Mensagem sua", "Escreva o aviso do seu jeito, com o produto, o preço antes, o preço agora, a queda e o link."),
                   _t("Histórico de preços", "Cada produto mostra o preço inicial, o menor preço visto e o último alerta. Produto sem estoque ou sem comissão fica marcado como indisponível.")),
            _grupo("Recursos que só o Premium tem", "Para quem quer mais alcance e mais automação.",
                   _t("Copiar ofertas de outros grupos e canais", "Marque os grupos e canais que você quer copiar. Toda mensagem com link da Shopee que chegar vira uma oferta sua, com o seu link de afiliado. Os links de quem postou são removidos, e só o seu entra. Mensagem sem link da Shopee é ignorada.", "Premium"),
                   _t("Revisão do texto com IA", "A IA revisa o texto das ofertas antes de enviar: só o português, corrigir frases que não combinam com o produto, ou deixar a chamada mais atraente. Link, preço e cupom nunca são alterados, e se algo der errado a oferta sai com o texto original.", "Premium")),
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
            ("Busca na Shopee, com filtros e categorias", True, True),
            ("Modo campanha e datas próprias", True, True),
            ("Testar busca e modo simulação", True, True),
            ("Horário, dias e Sub ID por grupo", True, True),
            ("Copiar ofertas de outros grupos e canais", False, True),
            ("Revisão do texto com IA", False, True),
        ],
        "perguntas": [
            ("Preciso deixar o computador ou o celular ligados?", "Não. O servidor do Appfiliado fica conectado ao seu WhatsApp como mais um aparelho, como no WhatsApp Web. Você só precisa do celular para ler o QR Code ao conectar."),
            ("Meu número pode ser bloqueado pelo WhatsApp?", "O WhatsApp não gosta de envio em excesso. O bot manda no máximo uma mensagem a cada 3 segundos, respeita o intervalo e o limite diário do seu plano e só envia pros grupos que você escolher. Mesmo assim, não há garantia contra bloqueio. Muita gente usa um número separado só pras divulgações."),
            ("Posso mandar para canais do WhatsApp?", "Pode, desde que o seu número seja dono ou administrador do canal. Como canais não aceitam foto com legenda, eles recebem o texto com a prévia do link."),
            ("As ofertas saem com o meu link de afiliado?", "Sim. Cada oferta sai com o seu link, gerado na hora com a sua conta da Shopee. Você precisa conectar a conta de afiliado no painel."),
            ("Dá para testar sem enviar nada?", "Dá. O \"Testar busca\" mostra as próximas ofertas com a mensagem pronta, e o modo simulação faz todo o processo sem enviar."),
            ("O que acontece nas datas como 11.11 e Black Friday?", "Se a data estiver ligada no modo campanha, o bot usa o ritmo, o texto e o cupom da campanha o dia todo e volta à configuração normal no dia seguinte."),
            ("Qual é a diferença entre Standard e Premium?", f"O Premium libera mais grupos e canais (até {p['grupos']}), mais ofertas por dia (até {p['ofertas_por_grupo_dia']}), um intervalo menor entre ofertas ({p['intervalo_minimo']} minutos), alerta de preço para mais produtos, a cópia de ofertas de outros grupos e a revisão de texto com IA."),
            ("O que preciso para começar?", "Uma conta de afiliado da Shopee e um número de WhatsApp com os grupos ou canais para onde as ofertas vão."),
        ],
    }


def site():
    s, p = plano.SITE[False], plano.SITE[True]
    return {
        "codigo": "site", "slug": "meu-site", "url": "landing_site", "nome": "Meu site",
        "titulo": "Meu site: link na bio com vitrine de ofertas — Appfiliado",
        "descricao": "Seu link na bio em seunome.appfiliado.com.br, com botões, redes sociais, conversor de links e vitrine de ofertas da Shopee. Cliques contados e Sub ID próprio.",
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
                   _t("seunome.appfiliado.com.br", "Escolha o seu nome. O painel sugere um a partir do seu nome ou e-mail, e você pode trocar depois."),
                   _t("Publicar e tirar do ar", "Você liga e desliga o site quando quiser. Fora do ar, o visitante vê uma página não encontrada."),
                   _t("Prévia ao vivo", "Um celular na tela mostra o site enquanto você edita, antes de salvar. A visita da prévia não conta nas estatísticas.")),
            _grupo("Do seu jeito", "Nome, foto e cores para combinar com a sua marca.",
                   _t("Nome e frase curta", "O nome (até 60 caracteres) e a frase que aparece embaixo (até 140), com seletor de emoji. Eles também formam o título e a descrição quando o link é compartilhado."),
                   _t("Sua foto", "Envie e ajuste a foto, com zoom e recorte circular. Sem foto, o site mostra a inicial do seu nome."),
                   _t("Cores", "15 cores prontas ou qualquer outra que você escolher. O texto troca entre claro e escuro sozinho para continuar legível."),
                   _t("Fundo colorido ou claro", "Dois estilos de página."),
                   _t("Vitrine em lista ou carrossel", "Mostre as ofertas em uma grade de duas colunas ou em um carrossel que o visitante arrasta pro lado.")),
            _grupo("Botões de link", "Os links que levam o visitante para onde você quer.",
                   _t("Botões com o seu texto", "Cada botão tem o texto (aceita emoji), o link e a opção de ficar em destaque, na cor do site. Exemplo: \"💬 Entrar no grupo de ofertas\"."),
                   _t("Organize como quiser", "Adicione, edite, apague e mude a ordem com as setas."),
                   _t("Limite de botões", f"{s['botoes']} botões no Standard e {p['botoes']} no Premium.", ""),
                   _t("Cliques de cada botão", "O painel mostra quantos cliques cada botão recebeu nos últimos 30 dias.")),
            _grupo("Redes sociais", "Os ícones aparecem embaixo dos botões.",
                   _t("Sete redes", "Instagram, TikTok, YouTube, X (Twitter), Facebook, WhatsApp e Telegram."),
                   _t("Cole o link ou só o @", "O @ vira o link completo. O WhatsApp aceita link de grupo ou o seu número com DDD."),
                   _t("Sem limite", "Você pode preencher todas as redes nos dois planos. Só aparece o ícone da rede que você preencher, e os cliques são contados.")),
            _grupo("Conversor de links pros seus visitantes", "Quem chega no seu site cola um link da Shopee e compra pelo seu link de afiliado.",
                   _t("Cole e compre", "O visitante cola o link de um produto da Shopee, e o botão leva à Shopee pelo seu link, com o Sub ID do seu site."),
                   _t("Textos seus", "Você escreve o título, o texto e o texto do botão do conversor, ou usa os que já vêm prontos. Também pode desligar o conversor."),
                   _t("Links curtos funcionam", "O Appfiliado abre links curtos da Shopee para achar o produto."),
                   _t("Proteção contra abuso", "Cada visitante converte até 20 links por hora.")),
            _grupo("Vitrine de ofertas", "Uma seção com as ofertas do dia, com foto, preço e desconto.",
                   _t("As últimas ofertas do bot", "Cada oferta que o bot enviar entra no topo da vitrine, sem repetir, e ficam as 100 mais recentes. Disponível para quem tem o Bot de WhatsApp."),
                   _t("Uma busca na Shopee", "Ofertas em geral, por palavra-chave, de uma loja ou por categoria, ordenadas por mais vendidos, maior comissão ou maior desconto. A vitrine é atualizada a cada 3 horas, com até 100 produtos."),
                   _t("Produtos que você escolher", "Cole os links dos produtos, um por linha e na ordem que quiser, até 60. A vitrine mostra só o que você escolheu.", "Premium"),
                   _t("Categorias", "Quando há produtos de mais de uma categoria, o visitante filtra por elas. Você pode corrigir a categoria de cada produto."),
                   _t("Seu link em cada produto", "Cada produto leva o visitante à Shopee pelo seu link de afiliado.")),
            _grupo("Cliques e vendas", "Veja o que o seu site está gerando.",
                   _t("Contador de cliques", "Visitas, cliques em botões e redes, cliques em produtos e conversões do conversor, nos últimos 30 dias. Os produtos mais clicados aparecem em destaque."),
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
            ("O conversor de links gera comissão para mim?", "Sim. O visitante cola o link de um produto da Shopee e vai pra loja pelo seu link de afiliado, com o Sub ID do seu site, para você acompanhar as vendas em Resultados."),
            ("A vitrine atualiza sozinha?", "A vitrine por busca é refeita a cada 3 horas, e a das ofertas do bot, a cada oferta enviada. A vitrine com produtos escolhidos por você é refeita quando você salva."),
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
        "texto": "O Appfiliado puxa os dados do produto, a IA escreve o roteiro dos slides, a legenda e as hashtags, e você ajusta tudo no editor e baixa as imagens, já com o seu link de afiliado.",
        "resumo": [
            ("Carrosséis por dia", f"{s['geracoes']}", f"{p['geracoes']}"),
            ("Modelos", "6", "10"),
            ("Cores", "5 temas", "Livres"),
            ("Foto própria e remoção de fundo", "—", "Sim"),
            ("Reescrita de slides por IA", "—", f"até {p['reescritas']} por dia"),
        ],
        "grupos": [
            _grupo("Do link ao carrossel em segundos", "Você só precisa de um link de produto da Shopee.",
                   _t("Cole o link", "Aceita links shopee.com.br e s.shopee.com.br. Se você colar um texto, o Appfiliado usa o primeiro link da Shopee que achar. A geração leva até 30 segundos."),
                   _t("Dados do produto", "O Appfiliado puxa o nome, o preço, a nota, as vendas, a foto e a loja direto da Shopee. O preço antigo é calculado a partir do desconto."),
                   _t("Seu link de afiliado", "O carrossel sai com o seu link de afiliado, com o Sub ID \"instagram\", para você ver em Resultados as vendas que vêm do Instagram."),
                   _t("Preço sempre certo", "O preço vem da Shopee na hora da geração e não é editável, para ninguém anunciar um valor errado.")),
            _grupo("A IA escreve para você", "Roteiro, legenda e hashtags já saem prontos.",
                   _t("Roteiro dos slides", "A IA escreve os textos de cada slide a partir dos dados do produto, sem inventar medidas ou garantias, e destaca uma ou duas palavras-chave."),
                   _t("Legenda e hashtags", "A legenda do post e as hashtags, com #achadinhos e #shopee sempre incluídas."),
                   _t("Sempre sai um carrossel", "Se a IA estiver indisponível, o Appfiliado monta um roteiro simples e o carrossel é gerado do mesmo jeito.")),
            _grupo("Modelos e slides", "Cada slide tem uma função no carrossel, de 2 a 10 slides.",
                   _t("6 modelos Standard", "Destaque, Editorial, Promo, Neon, Polaroid e Bento."),
                   _t("4 modelos Premium", "Vitrine, Anotado, Etiqueta e Ficha, com slides de vantagens, números e qualidades do produto.", "Premium"),
                   _t("Tipos de slide", "Capa, texto com arte, produto, preço, avaliações, chamada e final nos modelos Standard. Capa, vantagens, números, qualidades, preço e chamada nos modelos Premium."),
                   _t("Troque de modelo sem perder o texto", "Ao mudar entre as duas famílias de modelos, os textos são levados pro novo modelo, sempre que possível.")),
            _grupo("O seu visual", "Cores, fonte e o seu @ no carrossel.",
                   _t("5 temas de cor", "Verde, laranja, rosa, azul e preto, nos dois planos."),
                   _t("Cores livres", "Escolha qualquer cor pro carrossel.", "Premium"),
                   _t("5 fontes à escolha", "Moderna, geométrica, impacto, elegante e serifa fina, além da fonte do modelo.", "Premium"),
                   _t("Seu @ do Instagram", "O seu @ aparece na capa e em outros pontos do carrossel, nos dois planos."),
                   _t("Mostrar ou esconder detalhes", "Ligue ou desligue a nota e as vendas, o preço antigo com o desconto e o \"Arrasta\" no rodapé.", "Premium"),
                   _t("Salvar como meu padrão", "Guarde o seu modelo, cor, fonte, @ e as opções, e os próximos carrosséis já saem do seu jeito.", "Premium")),
            _grupo("Foto própria e remoção de fundo", "Pro produto aparecer do jeito que você quer.",
                   _t("Foto própria", "Troque a foto da Shopee por uma sua (JPG, PNG ou WebP de até 8 MB) e volte à da Shopee quando quiser.", "Premium"),
                   _t("Remoção de fundo", "Tire o fundo da foto com um clique, e o produto aparece solto, com sombra no chão, nos modelos Premium. Funciona no seu navegador e leva alguns segundos.", "Premium")),
            _grupo("Um editor completo", "Ajuste cada detalhe antes de baixar.",
                   _t("Edite os textos", "Cada campo tem contador de caracteres, seletor de emoji e a opção de destacar palavras com marca-texto."),
                   _t("Mova, remova e volte ao original", "Reordene os slides, remova os que não quiser (a capa fica sempre primeiro) e volte ao texto que a IA escreveu com um clique."),
                   _t("Adicione e duplique slides", "Crie slides novos e duplique os que funcionam bem, até 10 por carrossel.", "Premium"),
                   _t("Outra versão com IA", f"Peça à IA para reescrever um slide, até {p['reescritas']} vezes por dia. Ela mantém o preço e a arte e muda só o texto.", "Premium"),
                   _t("Alertas em tempo real", "O editor avisa quando um texto está longo demais, encostando ou com pouco contraste, antes de você baixar."),
                   _t("Salva sozinho", "Suas alterações são salvas automaticamente, e você pode voltar ao carrossel quando quiser.")),
            _grupo("Legenda e download", "Pronto para postar.",
                   _t("Legenda e hashtags", "Edite a legenda (até 2.200 caracteres) e as hashtags, e copie tudo com um clique."),
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
            ("Preciso conectar a minha conta da Shopee?", "Sim. O Appfiliado usa a sua conta de afiliado para buscar os dados do produto e gerar o seu link."),
            ("Os carrosséis têm marca d'água?", "Não. As imagens saem limpas, prontas para postar."),
            ("Posso editar o preço que aparece no carrossel?", "Não. O preço vem da Shopee na hora da geração, para você não anunciar um valor errado."),
            ("E se a IA estiver fora do ar?", "O Appfiliado monta um roteiro simples e o carrossel é gerado do mesmo jeito. Você pode editar os textos como de costume."),
            ("O limite diário reinicia quando?", "À meia-noite, no horário de Brasília. Gerações que falham por link inválido ou produto sem comissão não gastam o seu limite."),
            ("A remoção de fundo funciona em qualquer foto?", "Funciona melhor em fotos de produto com bom contraste com o fundo. Em fotos de embalagem clara sobre fundo claro, a base do produto pode ficar um pouco apagada, e você pode voltar pra foto inteira com um clique."),
            ("O que muda do Standard pro Premium?", f"O Premium gera {p['geracoes']} carrosséis por dia (no Standard, {s['geracoes']}), tem 4 modelos a mais, cores e fontes livres, foto própria com remoção de fundo, adiciona e duplica slides, reescreve slides com IA (até {p['reescritas']} por dia) e guarda o seu padrão visual."),
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
                            (f"{plano.BOT[False]['ofertas_por_grupo_dia']} a {plano.BOT[True]['ofertas_por_grupo_dia']}", "ofertas por dia, em cada grupo"),
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


def _apresentar(modulo, pagina):
    ap = APRESENTACAO[modulo]
    fundo = ""
    for g, layout, curto in zip(pagina["grupos"], ap["layouts"], ap["curtos"]):
        g["layout"], g["curto"] = layout, curto
        if layout == "premium":
            g["fundo"] = "verde"
        else:  # alterna branco e creme, para duas seções vizinhas nunca terem a mesma cor
            fundo = "creme" if fundo != "creme" else ""
            g["fundo"] = fundo
        for item in g["itens"]:
            item["chips"] = ap.get("chips", {}).get(item["nome"], [])
            item["cores"] = ap.get("cores", {}).get(item["nome"], [])
    pagina["numeros"] = ap["numeros"]()
    return pagina


PAGINAS = {m: (lambda m=m, f=f: _apresentar(m, f())) for m, f in {"bot": bot, "site": site, "carrosseis": carrosseis}.items()}
