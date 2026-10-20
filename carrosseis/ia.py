"""Textos dos carrosséis com IA (Gemini, chave única do Appfiliado - a mesma do bot).

A IA escreve só os textos; o desenho é do navegador. O que ela devolve passa pelas
regras de roteiro.py (campos e tamanhos) e por uma regra a mais: número que aparece no
slide "Em números" precisa existir no nome do produto ou nos dados da Shopee (preço,
desconto, nota, vendas) - a IA não pode inventar "24h gelado" para uma garrafa.

Se a IA falhar ou devolver algo inaproveitável, sai um roteiro simples montado aqui
mesmo: o carrossel nunca deixa de ser gerado por causa dela."""

import json
import logging
import re

from bot_whatsapp import ia as gemini

from . import roteiro as R

logger = logging.getLogger(__name__)
TEMPERATURA = 0.7
HASHTAGS_FIXAS = ["#achadinhos", "#shopee"]


# --- dados do produto em texto --------------------------------------------------------

def brl(valor: float) -> str:
    return "R$ " + f"{float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def vendidos(vendas: int) -> str:
    if vendas >= 1000:
        return f"{vendas / 1000:.1f}".replace(".0", "").replace(".", ",") + " mil"
    return str(vendas)


def nome_curto(nome: str, maximo: int = 34) -> str:
    """"Garrafa Térmica 1 Litro Aço Inox [ENVIO IMEDIATO]" -> "Garrafa Térmica 1 Litro"."""
    nome = re.sub(r"[\[\(\{].*?[\]\)\}]", " ", nome or "")
    nome = re.sub(r"[|/\\,;:–—-].*$", "", nome) or nome
    palavras, saida = nome.split(), ""
    for p in palavras:
        if len(saida) + len(p) + 1 > maximo:
            break
        saida = f"{saida} {p}".strip()
    return saida or (palavras[0][:maximo] if palavras else "Produto")


def _numeros_permitidos(produto: dict) -> set[str]:
    textos = [produto.get("nome", ""), str(produto.get("desconto") or ""), brl(produto.get("preco") or 0),
              brl(produto.get("de") or 0), f"{produto.get('nota') or 0:.1f}".replace(".", ","),
              str(produto.get("vendas") or ""), vendidos(int(produto.get("vendas") or 0))]
    return set(re.findall(r"\d+", " ".join(textos)))


def numero_confere(valor: str, permitidos: set[str]) -> bool:
    achados = re.findall(r"\d+", valor or "")
    return bool(achados) and all(n in permitidos for n in achados)


def numeros_dos_dados(produto: dict) -> list[dict]:
    """Números garantidos (vêm da Shopee), para completar o slide "Em números"."""
    saida = []
    if (produto.get("desconto") or 0) >= 5:
        saida.append({"valor": f"-{int(produto['desconto'])}%", "legenda": "de desconto hoje"})
    if (produto.get("nota") or 0) > 0:
        saida.append({"valor": f"{produto['nota']:.1f}".replace(".", ","), "legenda": "de nota na Shopee"})
    if (produto.get("vendas") or 0) > 0:
        saida.append({"valor": vendidos(int(produto["vendas"])), "legenda": "vendidos"})
    return saida


# --- roteiro simples (sem IA) ---------------------------------------------------------

def roteiro_simples(produto: dict, curto: str) -> dict:
    desconto = int(produto.get("desconto") or 0)
    capa_titulo = f"{curto} com *{desconto}% off*" if desconto >= 5 else f"Achei: *{curto}*"
    passos = ["Toque no link da bio", f"Procure: {curto}"]
    padrao = [
        {"tipo": "capa", "selo": "Achado do dia", "titulo": capa_titulo},
        {"tipo": "produto", "rotulo": "Conheça", "titulo": produto.get("nome", curto), "chips": []},
        {"tipo": "preco"},
        {"tipo": "prova", "titulo": "Quem comprou *aprovou*", "texto": "Nota alta e muitas vendas na Shopee."},
        {"tipo": "cta", "titulo": "Quer o seu?", "botao": "LINK NA BIO", "passos": passos},
        {"tipo": "final", "titulo": "Gostou? *Salva* e compartilha", "texto": "Siga para mais achadinhos todo dia"},
    ]
    premium = [
        {"tipo": "capa", "selo": "Achado do dia", "titulo": capa_titulo},
        {"tipo": "numeros", "rotulo": "Em números", "titulo": "Por que *vale* a pena", "numeros": numeros_dos_dados(produto)},
        {"tipo": "preco"},
        {"tipo": "cta", "titulo": "Quer o seu?", "botao": "LINK NA BIO", "passos": passos},
    ]
    if not premium[1]["numeros"]:
        premium.pop(1)
    return {"padrao": padrao, "premium": premium, "arte": "presente", "nome_curto": curto,
            "legenda": legenda_simples(produto, capa_titulo), "hashtags": " ".join(HASHTAGS_FIXAS + ["#achadosdashopee"])}


def legenda_simples(produto: dict, titulo: str) -> str:
    preco = f"{produto.get('nome', '')} por {brl(produto.get('preco') or 0)}"
    if (produto.get("de") or 0) > (produto.get("preco") or 0):
        preco += f" (antes {brl(produto['de'])})"
    return f"{titulo.replace('*', '')} ✨\n\n{preco}.\n\n👉 Link na bio\n💾 Salva para não perder!"


# --- com IA ---------------------------------------------------------------------------

def _dados_para_ia(produto: dict) -> str:
    dados = {
        "nome": produto.get("nome", ""), "preco": brl(produto.get("preco") or 0),
        "preco_antigo": brl(produto["de"]) if (produto.get("de") or 0) > (produto.get("preco") or 0) else "",
        "desconto": f"{int(produto.get('desconto') or 0)}%" if (produto.get("desconto") or 0) >= 5 else "",
        "nota": f"{produto.get('nota') or 0:.1f}".replace(".", ",") if produto.get("nota") else "",
        "vendas": vendidos(int(produto.get("vendas") or 0)) if produto.get("vendas") else "", "loja": produto.get("loja", ""),
    }
    return json.dumps(dados, ensure_ascii=False)


REGRAS = """Você escreve carrosséis de Instagram para afiliados da Shopee, em português do Brasil.
Tom: amiga indicando um achado, direto, sem exagero e sem clichê de anúncio.
Regras obrigatórias:
- Use só informações do nome do produto e dos dados abaixo. Não invente medidas, materiais,
  duração de bateria, garantia, frete, brindes ou qualquer característica que não esteja ali.
- Todo número que você escrever precisa aparecer no nome do produto ou nos dados.
- Não escreva preço em nenhum texto (o preço entra sozinho no slide de preço).
- Marque com *asteriscos* uma ou duas palavras de destaque por título (ex: "Café quente o dia *inteiro*").
- Respeite os tamanhos máximos de caracteres de cada campo.
- Emojis: no máximo um por texto, e só se combinar.
Responda somente com o JSON pedido, sem comentários."""

FORMATO = """Formato da resposta (JSON):
{
 "nome_curto": "nome curto do produto, até 34 caracteres",
 "arte": "uma destas: cozinha, natal, festa, tech, presente (a que mais combina)",
 "capa": {"selo": "até 28 caracteres, ex: Achado da semana", "titulo": "gancho até 60 caracteres"},
 "problema": {"rotulo": "até 24", "titulo": "pergunta ou dor até 60", "texto": "até 110"},
 "chips": ["3 destaques do produto, até 18 caracteres cada"],
 "prova": {"titulo": "até 50", "texto": "até 90, pode citar nota e vendas"},
 "cta": {"titulo": "chamada até 40, ex: Quer o seu?"},
 "final": {"titulo": "até 50", "texto": "até 80"},
 "vantagens": {"rotulo": "até 24", "titulo": "até 40", "itens": ["3 vantagens, até 40 caracteres cada"]},
 "numeros": {"rotulo": "até 24", "titulo": "até 40", "numeros": [{"valor": "até 9 caracteres", "legenda": "até 32"}]},
 "qualidades": {"rotulo": "até 24", "titulo": "até 40", "itens": ["4 qualidades curtas, até 24 caracteres cada"]},
 "legenda": "legenda do post, até 400 caracteres, terminando com uma chamada para o link na bio",
 "hashtags": ["até 5 hashtags sem acento"]
}"""


def _json_da_resposta(texto: str) -> dict:
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
    dados = json.loads(texto)
    if not isinstance(dados, dict):
        raise ValueError("resposta não é um objeto")
    return dados


def _hashtags(lista) -> str:
    tags = []
    for t in (lista if isinstance(lista, list) else []) + HASHTAGS_FIXAS:
        t = "#" + re.sub(r"\W", "", str(t).lower().lstrip("#"))  # o Instagram aceita acento (#café)
        if len(t) > 2 and t not in tags:
            tags.append(t)
    return " ".join(tags[:7])


def _montar(dados: dict, produto: dict, simples: dict) -> dict:
    """Monta os dois roteiros com o que a IA mandou, completando o que faltar com o simples."""
    g = lambda chave, campo, padrao="": str(((dados.get(chave) or {}) if isinstance(dados.get(chave), dict) else {}).get(campo) or padrao)
    curto = R.limpar_texto(dados.get("nome_curto"), 34) or simples["nome_curto"]
    passos = ["Toque no link da bio", f"Procure: {curto}"]
    capa = {"tipo": "capa", "selo": g("capa", "selo", "Achado do dia"), "titulo": g("capa", "titulo") or simples["padrao"][0]["titulo"]}
    cta = {"tipo": "cta", "titulo": g("cta", "titulo", "Quer o seu?"), "botao": "LINK NA BIO", "passos": passos}
    arte = dados.get("arte") if dados.get("arte") in R.ARTES else "presente"
    padrao = [capa]
    if g("problema", "titulo"):
        padrao.append({"tipo": "texto", "rotulo": g("problema", "rotulo", "Sabe quando"), "titulo": g("problema", "titulo"),
                       "texto": g("problema", "texto"), "arte": arte})
    padrao += [
        {"tipo": "produto", "rotulo": "Conheça", "titulo": produto.get("nome") or curto,
         "chips": [str(c) for c in (dados.get("chips") or []) if c][:3]},
        {"tipo": "preco"},
        {"tipo": "prova", "titulo": g("prova", "titulo", "Quem comprou *aprovou*"), "texto": g("prova", "texto", "Nota alta e muitas vendas.")},
        dict(cta),
        {"tipo": "final", "titulo": g("final", "titulo", "Gostou? *Salva* e compartilha"), "texto": g("final", "texto", "Siga para mais achadinhos todo dia")},
    ]
    permitidos = _numeros_permitidos(produto)
    numeros = [n for n in ((dados.get("numeros") or {}).get("numeros") or []) if isinstance(n, dict) and numero_confere(str(n.get("valor")), permitidos)]
    for extra in numeros_dos_dados(produto):  # completa até 3 com o que vem da Shopee
        if len(numeros) >= 3:
            break
        if all(extra["valor"] != n.get("valor") for n in numeros):
            numeros.append(extra)
    premium = [dict(capa)]
    if (dados.get("vantagens") or {}).get("itens"):
        premium.append({"tipo": "vantagens", "rotulo": g("vantagens", "rotulo", "Por que vale a pena"), "titulo": g("vantagens", "titulo", "Vale a *pena*"),
                        "itens": [str(i) for i in dados["vantagens"]["itens"]][:4]})
    if len(numeros) >= 2:
        premium.append({"tipo": "numeros", "rotulo": g("numeros", "rotulo", "Em números"), "titulo": g("numeros", "titulo", "Em *números*"), "numeros": numeros[:3]})
    if (dados.get("qualidades") or {}).get("itens"):
        premium.append({"tipo": "anotado", "rotulo": g("qualidades", "rotulo", "Em detalhes"), "titulo": g("qualidades", "titulo", "Os *detalhes*"),
                        "rotulos": [str(i) for i in dados["qualidades"]["itens"]][:4]})
    premium += [{"tipo": "preco"}, dict(cta)]
    legenda = str(dados.get("legenda") or "").strip()[:600] or simples["legenda"]
    return {"padrao": padrao, "premium": premium, "arte": arte, "nome_curto": curto, "legenda": legenda,
            "hashtags": _hashtags(dados.get("hashtags"))}


def gerar(produto: dict) -> tuple[dict, bool]:
    """(roteiros, usou_ia). Os roteiros já saem limpos e numerados."""
    simples = roteiro_simples(produto, nome_curto(produto.get("nome", "")))
    resultado, usou_ia = simples, False
    if gemini.disponivel():
        prompt = f"{REGRAS}\n\nDados do produto: {_dados_para_ia(produto)}\n\n{FORMATO}"
        try:
            dados = _json_da_resposta(gemini._chamar(prompt, TEMPERATURA, max_tokens=2500, json_saida=True, timeout=30))
            resultado, usou_ia = _montar(dados, produto, simples), True
        except (gemini.ErroDaIA, ValueError, TypeError, AttributeError) as erro:  # json.JSONDecodeError é ValueError
            logger.warning("Carrossel: IA falhou, usando o roteiro simples (%s)", erro)
    for familia, inicio in ((R.PADRAO, 1), (R.PREMIUM, 101)):  # números diferentes nas duas famílias
        try:
            resultado[familia] = R.numerar(R.limpar_roteiro(resultado[familia], familia, premium=True), inicio)
        except ValueError:
            resultado[familia] = R.numerar(R.limpar_roteiro(simples[familia], familia, premium=True), inicio)
    return resultado, usou_ia


def reescrever(produto: dict, slide: dict, familia: str) -> dict:
    """Outra versão dos textos de um slide (premium). Levanta gemini.ErroDaIA ou ValueError."""
    campos = {k: v for k, v in slide.items() if k in R.CAMPOS.get(slide.get("tipo"), {}) and k != "arte"}
    if not campos:
        raise ValueError("Este slide não tem texto para reescrever.")
    limites = {k: R.CAMPOS[slide["tipo"]][k][1] for k in campos if R.CAMPOS[slide["tipo"]][k][1]}
    prompt = (f"{REGRAS}\n\nDados do produto: {_dados_para_ia(produto)}\n\n"
              f"Escreva outra versão, diferente da atual, para os textos deste slide. Mesmas chaves, mesmos tipos, "
              f"mesma quantidade de itens. Tamanhos máximos: {json.dumps(limites)}.\n"
              f"Slide atual: {json.dumps(campos, ensure_ascii=False)}")
    dados = _json_da_resposta(gemini._chamar(prompt, 0.9, max_tokens=800, json_saida=True, timeout=25))
    novo = R.limpar_slide({**slide, **{k: v for k, v in dados.items() if k in campos}}, familia, premium=True)
    if not novo:
        raise ValueError("A IA devolveu um slide inválido.")
    if novo["tipo"] == "numeros":
        permitidos = _numeros_permitidos(produto)
        novo["numeros"] = [n for n in novo.get("numeros", []) if numero_confere(n["valor"], permitidos)] or campos.get("numeros", [])
    for k in ("_id", "_orig", "semFoto", "posicao", "alinhar"):
        if k in slide:
            novo[k] = slide[k]
    return novo
