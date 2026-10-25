"""O que cada marca oferece no estúdio: formatos, tipos de slide, fundos, ícones e prints.

O desenho de cada slide fica no navegador (static/estudio/marca-*.js). Aqui fica só o que o
servidor precisa saber para validar o que a IA devolve e para montar o editor."""

from pathlib import Path

from django.conf import settings

# Tamanho final de cada formato, em pixels.
FORMATOS = {
    "quadrado": ("Post 1:1", 1080, 1080),
    "retrato": ("Post 4:5", 1080, 1350),
    "story": ("Story 9:16", 1080, 1920),
}

# Campos que cada tipo de slide usa. A ordem é a ordem do formulário no editor.
CAMPOS_TEXTO = {
    "chapeu": ("Chapéu (texto pequeno em cima)", 40),
    "titulo": ("Título", 90),
    "texto": ("Texto", 180),
    "nota": ("Nota", 140),
    "destaque": ("Caixa de destaque", 160),
    "botao": ("Botão", 28),
    "site": ("Selo do site", 30),
    "selo": ("Selo", 30),
}
LIMITES_LISTA = {"itens": 5, "pares": 4, "linhas": 6, "baloes": 4}

_PRINTS = sorted(p.name[:-7] for p in (Path(settings.BASE_DIR) / "landing" / "static" / "landing" / "prints").glob("*-m.webp"))

MARCAS = {
    "appfiliado": {
        "nome": "Appfiliado",
        "formato_padrao": "quadrado",
        "tipos": {
            "capa": ("Capa", ["chapeu", "titulo", "texto", "icone", "logo"]),
            "tela": ("Tela do painel no celular", ["chapeu", "titulo", "texto", "print", "recorte"]),
            "lista": ("Lista", ["chapeu", "titulo", "texto", "itens", "numerada"]),
            "numeros": ("Números", ["chapeu", "titulo", "pares"]),
            "precos": ("Preços", ["chapeu", "titulo", "linhas", "nota"]),
            "cta": ("Chamada final", ["titulo", "texto", "botao", "site", "logo"]),
            "conversa": ("Conversa de WhatsApp", ["chapeu", "titulo", "baloes"]),
        },
        "cores": {"verde": "Verde", "creme": "Creme", "amarelo": "Amarelo", "branco": "Branco", "areia": "Areia"},
        "artes": {"circulos": "Círculos", "canto": "Canto", "manchas": "Manchas", "ondas": "Ondas", "moldura": "Moldura", "halo": "Halo"},
        "tons": {"escuro": "Verde", "claro": "Creme"},
        "icones": ["bot", "site", "carrosseis", "notas", "radar", "conversor", "resultados", "chave", "duvidas", "planos", "sobre"],
        "prints": _PRINTS,
        "voz": ("Público: afiliados da Shopee. Diga 'para afiliados Shopee' ou 'para quem é afiliado Shopee', "
                "nunca 'para quem divulga a Shopee'. O Appfiliado é independente e não tem vínculo oficial com a Shopee."),
    },
    "cashb": {
        "nome": "cash-b",
        "formato_padrao": "retrato",
        "tipos": {
            "capa": ("Capa", ["chapeu", "titulo", "texto", "selo"]),
            "texto": ("Texto com destaque", ["chapeu", "titulo", "texto", "destaque"]),
            "lista": ("Lista", ["chapeu", "titulo", "texto", "itens", "numerada"]),
            "valores": ("Tabela de valores", ["chapeu", "titulo", "linhas", "nota"]),
            "numero": ("Número grande", ["chapeu", "titulo", "pares", "texto"]),
            "comparacao": ("Comparação de casos", ["chapeu", "titulo", "itens"]),
            "cta": ("Chamada final", ["titulo", "texto", "botao"]),
        },
        "cores": {"roxo": "Roxo", "claro": "Claro", "lilas": "Lilás", "escuro": "Escuro", "branco": "Branco"},
        "artes": {"canto": "Canto (padrão)", "manchas": "Manchas", "ondas": "Ondas", "moldura": "Moldura", "diagonal": "Diagonal", "halo": "Halo"},
        "tons": {"escuro": "Roxo", "claro": "Claro"},
        "icones": [],
        "prints": [],
        "voz": ("A marca se escreve sempre 'cash-b', minúsculo e com hífen, e é feminina: 'a cash-b', 'na cash-b'. "
                "Escreva 'Pix', nunca 'PIX'. O grifo (palavra entre asteriscos) aparece no máximo uma vez por slide. "
                "Todo valor em R$ ou em % é escrito com números. Não prometa cashback garantido: ele depende de a "
                "Shopee confirmar a compra."),
    },
}


def tipos_para_ia(marca: str) -> str:
    """Descrição dos tipos de slide para o prompt da IA."""
    linhas = []
    for codigo, (nome, campos) in MARCAS[marca]["tipos"].items():
        linhas.append(f"- {codigo} ({nome}): campos {', '.join(campos)}")
    return "\n".join(linhas)
