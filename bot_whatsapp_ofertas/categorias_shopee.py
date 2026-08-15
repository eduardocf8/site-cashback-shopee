# -*- coding: utf-8 -*-
"""
Lista de categorias/nichos usadas no filtro de "Categoria" do Modo Shopee.

Como a API de afiliados da Shopee (productOfferV2) exige um ID numérico de
categoria que não é documentado publicamente e nem sempre filtra de forma
confiável, o filtro de categoria deste bot funciona de outra forma: ele
compara o NOME do produto retornado pela API com listas de palavras-chave
de cada categoria abaixo. Se o nome do produto contiver pelo menos uma
palavra-chave da categoria escolhida, a oferta passa no filtro.

Isso é o que garante que, ao marcar "Moda" na lista suspensa, só passem
ofertas cujo título realmente tenha a ver com roupas/calçados/moda, por
exemplo — em vez de depender de um ID que a Shopee pode ignorar.

Para ajustar a "precisão" de uma categoria, basta editar a lista de
palavras-chave correspondente (adicionar termos que estão passando batido,
ou remover termos genéricos demais que estão deixando passar produtos de
outros nichos).
"""

import unicodedata


def normalizar_texto(texto):
    """Remove acentos, baixa a caixa e limpa espaços extras de um texto."""

    texto = str(texto or "").strip().lower()
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return sem_acento


# Cada entrada: chave interna -> {"label": nome exibido na lista suspensa,
# "palavras": lista de palavras/trechos (já sem acento) usados no filtro}.
CATEGORIAS_SHOPEE = {
    "moda": {
        "label": "Moda (roupas, calçados e acessórios)",
        "palavras": [
            "camiseta", "camisa", "blusa", "vestido", "saia", "short", "bermuda",
            "calca", "calca jeans", "jeans", "jaqueta", "casaco", "moletom",
            "regata", "top", "conjunto feminino", "conjunto masculino", "legging",
            "sunga", "biquini", "maio", "roupa", "roupas", "moda feminina",
            "moda masculina", "moda praia", "tenis", "sapato", "sapatenis",
            "sandalia", "chinelo", "bota", "sapatilha", "mocassim", "salto",
            "calcado", "calcados", "bone", "chapeu", "cinto", "carteira",
            "bolsa", "mochila", "oculos de sol", "lingerie", "sutia", "calcinha",
            "cueca", "meia", "pijama", "roupa intima",
        ],
    },
    "beleza": {
        "label": "Beleza e Cuidados Pessoais",
        "palavras": [
            "maquiagem", "batom", "base liquida", "corretivo", "pó facial",
            "sombra", "delineador", "rimel", "mascara de cilios", "gloss",
            "perfume", "colonia", "desodorante", "shampoo", "condicionador",
            "creme para cabelo", "hidratante", "protetor solar", "sabonete",
            "skincare", "serum facial", "esfoliante", "mascara facial",
            "escova de cabelo", "secador de cabelo", "chapinha", "modelador de cachos",
            "prancha de cabelo", "depilador", "barbeador", "aparador de pelos",
            "cortador de cabelo", "kit manicure", "esmalte", "unha de gel",
            "cilios postiços", "pinca", "creme dental", "fio dental",
        ],
    },
    "casa": {
        "label": "Casa e Decoração",
        "palavras": [
            "panela", "frigideira", "jogo de panelas", "talher", "prato",
            "copo", "taca", "xicara", "cama", "colchao", "travesseiro",
            "edredom", "lencol", "cortina", "tapete", "almofada", "toalha",
            "organizador", "caixa organizadora", "cabide", "luminaria",
            "vela aromatica", "difusor de aromas", "quadro decorativo",
            "vaso de planta", "utensilio de cozinha", "potes hermeticos",
            "escorredor de louca", "lixeira", "varal", "kit banheiro",
            "jogo de cama", "cesto", "porta treco", "decoracao",
        ],
    },
    "eletronicos": {
        "label": "Eletrônicos e Celulares",
        "palavras": [
            "smartphone", "celular", "iphone", "capinha", "capa de celular",
            "pelicula de vidro", "carregador", "cabo usb", "fone de ouvido",
            "fone bluetooth", "caixa de som", "power bank", "smartwatch",
            "relogio inteligente", "tablet", "notebook", "mouse", "teclado",
            "webcam", "hd externo", "pendrive", "cartao de memoria",
            "adaptador", "roteador", "carregador portatil", "suporte de celular",
            "tripe de celular", "microfone", "câmera", "camera digital",
            "console de video game", "controle de video game",
        ],
    },
    "eletrodomesticos": {
        "label": "Eletrodomésticos",
        "palavras": [
            "liquidificador", "air fryer", "fritadeira eletrica", "cafeteira",
            "microondas", "geladeira", "freezer", "maquina de lavar",
            "ferro de passar", "aspirador de po", "ventilador", "climatizador",
            "aquecedor", "sanduicheira", "grill eletrico", "batedeira",
            "espremedor de frutas", "processador de alimentos", "torradeira",
            "purificador de agua", "panela eletrica", "panela de pressao eletrica",
            "umidificador",
        ],
    },
    "bebes": {
        "label": "Bebês e Infantil",
        "palavras": [
            "fralda", "mamadeira", "chupeta", "carrinho de bebe", "cadeirinha de bebe",
            "bebe conforto", "roupa de bebe", "body infantil", "berco",
            "kit enxoval", "banheira de bebe", "babador", "andador infantil",
            "mochila maternidade", "aquecedor de mamadeira", "protetor de berco",
            "brinquedo de bebe", "chocalho",
        ],
    },
    "brinquedos": {
        "label": "Brinquedos e Games",
        "palavras": [
            "brinquedo", "boneca", "boneco", "carrinho de brinquedo", "quebra-cabeca",
            "quebra cabeca", "lego", "pelucia", "jogo de tabuleiro", "video game",
            "console de video game", "controle de video game", "jogo de video game",
            "patinete", "bicicleta infantil", "piscina de bolinha", "massinha",
            "carrinho de controle remoto", "drone",
        ],
    },
    "esporte": {
        "label": "Esporte e Lazer",
        "palavras": [
            "bicicleta", "bola de futebol", "tenis de corrida", "halteres",
            "faixa elastica", "corda de pular", "colchonete", "tapete de yoga",
            "luva de boxe", "mochila de academia", "squeeze", "garrafa termica",
            "barraca de camping", "saco de dormir", "mochila de trilha",
            "equipamento de pesca", "vara de pesca", "patins", "skate",
            "protetor bucal", "joelheira", "tornozeleira esportiva",
        ],
    },
    "automotivo": {
        "label": "Automotivo e Motos",
        "palavras": [
            "capa de carro", "tapete automotivo", "som automotivo", "farol de carro",
            "lampada automotiva", "aspirador automotivo", "cera automotiva",
            "acessorio para carro", "suporte veicular", "carregador veicular",
            "capacete", "luva de moto", "acessorio para moto", "oleo automotivo",
            "pastilha de freio", "pneu", "calibrador de pneu",
        ],
    },
    "pet": {
        "label": "Pet Shop",
        "palavras": [
            "racao para cachorro", "racao para gato", "coleira", "guia para cachorro",
            "cama de cachorro", "cama de gato", "arranhador", "caixa de areia",
            "comedouro", "bebedouro pet", "brinquedo para cachorro", "brinquedo para gato",
            "roupinha de cachorro", "tapete higienico", "shampoo pet", "petisco",
            "aquario", "gaiola",
        ],
    },
    "papelaria": {
        "label": "Papelaria e Escritório",
        "palavras": [
            "caderno", "caneta", "lapis", "mochila escolar", "estojo",
            "agenda", "marcador de texto", "cola escolar", "tesoura escolar",
            "borracha", "apontador", "papel sulfite", "organizador de mesa",
            "calculadora", "impressora", "cartucho de tinta", "grampeador",
            "pasta escolar", "mochila de notebook",
        ],
    },
    "saude": {
        "label": "Saúde e Bem-estar",
        "palavras": [
            "vitamina", "suplemento", "whey protein", "termometro", "oximetro",
            "medidor de pressao", "balanca digital", "mascara facial de protecao",
            "alcool em gel", "faixa de compressao", "meia de compressao",
            "massageador", "almofada ortopedica", "colchao ortopedico",
            "kit primeiros socorros",
        ],
    },
    "alimentos": {
        "label": "Alimentos e Bebidas",
        "palavras": [
            "cafe em po", "cha", "chocolate", "biscoito", "snack", "achocolatado",
            "suco em po", "energetico", "barra de cereal", "azeite", "temperos",
            "condimento", "adocante", "farinha",
        ],
    },
    "joias": {
        "label": "Joias e Acessórios",
        "palavras": [
            "colar", "brinco", "pulseira", "anel", "piercing", "relogio feminino",
            "relogio masculino", "aliança", "pingente", "conjunto de bijuteria",
            "corrente masculina",
        ],
    },
    "ferramentas": {
        "label": "Ferramentas e Construção",
        "palavras": [
            "furadeira", "parafusadeira", "chave de fenda", "jogo de chaves",
            "trena", "nivel a laser", "serra eletrica", "lixadeira",
            "kit ferramentas", "escada", "capacete de seguranca", "luva de trabalho",
            "fita isolante", "silicone para construcao",
        ],
    },
}


def opcoes_categoria():
    """Lista (chave, label) pronta para popular a lista suspensa da interface."""

    return [(chave, dado["label"]) for chave, dado in CATEGORIAS_SHOPEE.items()]


def produto_pertence_as_categorias(nome_produto, categorias_selecionadas):
    """
    Verifica se o nome do produto bate com pelo menos uma palavra-chave de
    QUALQUER uma das categorias selecionadas (comparação "OU" entre categorias).

    Se nenhuma categoria estiver selecionada, retorna True (sem filtro aplicado).
    """

    categorias_validas = [c for c in (categorias_selecionadas or []) if c in CATEGORIAS_SHOPEE]
    if not categorias_validas:
        return True

    nome_normalizado = normalizar_texto(nome_produto)
    if not nome_normalizado:
        return False

    for chave in categorias_validas:
        palavras = CATEGORIAS_SHOPEE[chave]["palavras"]
        for palavra in palavras:
            if normalizar_texto(palavra) in nome_normalizado:
                return True

    return False
