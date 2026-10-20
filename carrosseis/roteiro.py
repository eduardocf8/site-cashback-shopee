"""O roteiro de um carrossel: a lista de slides e os textos de cada um. Tudo que chega do
navegador ou da IA passa por aqui antes de ser salvo, para o slide nunca receber campo
desconhecido, texto maior que o que cabe ou recurso que o plano da pessoa não tem.

Os limites de tamanho são os mesmos do editor (static/painel/carrossel/editor.js)."""

import re

PADRAO, PREMIUM = "padrao", "premium"

# tipo -> {campo: (tipo do campo, máximo de caracteres, quantos itens se for lista)}
CAMPOS = {
    "capa": {"selo": ("texto", 28, 0), "titulo": ("texto", 60, 0)},
    "texto": {"rotulo": ("texto", 24, 0), "titulo": ("texto", 60, 0), "texto": ("texto", 110, 0), "arte": ("arte", 0, 0)},
    "produto": {"rotulo": ("texto", 24, 0), "titulo": ("texto", 70, 0), "chips": ("lista", 18, 3)},
    "preco": {},
    "prova": {"titulo": ("texto", 50, 0), "texto": ("texto", 90, 0)},
    "cta": {"titulo": ("texto", 40, 0), "botao": ("texto", 18, 0), "passos": ("lista", 42, 3)},
    "final": {"titulo": ("texto", 50, 0), "texto": ("texto", 80, 0)},
    "vantagens": {"rotulo": ("texto", 24, 0), "titulo": ("texto", 40, 0), "itens": ("lista", 40, 4)},
    "numeros": {"rotulo": ("texto", 24, 0), "titulo": ("texto", 40, 0), "numeros": ("numeros", 0, 3)},
    "anotado": {"rotulo": ("texto", 24, 0), "titulo": ("texto", 40, 0), "rotulos": ("lista", 24, 4)},
}
TIPOS = {
    PADRAO: ["capa", "texto", "produto", "preco", "prova", "cta", "final"],
    PREMIUM: ["capa", "vantagens", "numeros", "anotado", "preco", "cta"],
}
ARTES = ["cozinha", "natal", "festa", "tech", "presente"]
MAXIMO_SLIDES, MINIMO_SLIDES = 10, 2
POSICOES, ALINHAMENTOS = ("topo", "meio", "base"), ("esq", "centro")
CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def limpar_texto(valor, maximo: int) -> str:
    """Uma linha só, sem caracteres de controle e cortada no máximo (sem partir emoji)."""
    texto = CONTROLE.sub("", str(valor or "")).replace("\n", " ").strip()
    texto = re.sub(r"\s+", " ", texto)
    if len(texto) > maximo:
        texto = texto[:maximo].rstrip()
    return texto


def limpar_slide(slide, familia: str, premium: bool, com_origem: bool = True) -> dict | None:
    """Só os campos conhecidos do tipo, já no tamanho certo. None se o tipo não existe
    nessa família de modelos."""
    if not isinstance(slide, dict) or slide.get("tipo") not in TIPOS[familia]:
        return None
    tipo = slide["tipo"]
    limpo = {"tipo": tipo}
    for campo, (genero, maximo, quantos) in CAMPOS[tipo].items():
        valor = slide.get(campo)
        if genero == "texto":
            if valor is not None:
                limpo[campo] = limpar_texto(valor, maximo)
        elif genero == "lista":
            itens = [limpar_texto(v, maximo) for v in (valor if isinstance(valor, list) else [])]
            limpo[campo] = [v for v in itens if v][:quantos]
        elif genero == "numeros":
            numeros = []
            for n in valor if isinstance(valor, list) else []:
                if isinstance(n, dict) and limpar_texto(n.get("valor"), 9):
                    numeros.append({"valor": limpar_texto(n.get("valor"), 9), "legenda": limpar_texto(n.get("legenda"), 32)})
            limpo[campo] = numeros[:quantos]
        elif genero == "arte" and valor in ARTES:
            limpo[campo] = valor
    if premium and familia == PREMIUM:
        if slide.get("semFoto") is True:
            limpo["semFoto"] = True
            limpo["posicao"] = slide.get("posicao") if slide.get("posicao") in POSICOES else "meio"
            limpo["alinhar"] = slide.get("alinhar") if slide.get("alinhar") in ALINHAMENTOS else "esq"
    if com_origem:
        for chave in ("_id", "_orig"):
            if isinstance(slide.get(chave), int) and 0 < slide[chave] < 10**6:
                limpo[chave] = slide[chave]
        # Ao trocar de família de modelos o editor guarda a versão de origem (ida e volta).
        de = slide.get("_de")
        if isinstance(de, dict):
            outra = PREMIUM if familia == PADRAO else PADRAO
            origem = limpar_slide(de, outra, premium, com_origem=False) or limpar_slide(de, familia, premium, com_origem=False)
            if origem:
                limpo["_de"] = origem
    return limpo


def limpar_roteiro(slides, familia: str, premium: bool, maximo: int = MAXIMO_SLIDES) -> list[dict]:
    """Levanta ValueError se o roteiro não serve (sem capa no começo, poucos slides...)."""
    if not isinstance(slides, list):
        raise ValueError("Roteiro inválido.")
    limpos = [s for s in (limpar_slide(s, familia, premium) for s in slides[:maximo]) if s]
    if len(limpos) < MINIMO_SLIDES:
        raise ValueError(f"O carrossel precisa de pelo menos {MINIMO_SLIDES} slides.")
    if limpos[0]["tipo"] != "capa":
        raise ValueError("O primeiro slide precisa ser a capa.")
    return limpos


def numerar(slides: list[dict], inicio: int = 1) -> list[dict]:
    """_id (slide) e _orig (de qual texto original ele veio) para o editor."""
    for i, slide in enumerate(slides, start=inicio):
        slide["_id"] = slide["_orig"] = i
    return slides
