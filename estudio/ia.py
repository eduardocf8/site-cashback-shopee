"""A IA do estúdio: monta um post inteiro (slides, legenda e hashtags) a partir de um pedido,
ou ajusta um post que já existe. Tudo o que ela devolve passa por limpar(), que só deixa
passar tipos, campos, fundos e tamanhos que o editor conhece."""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

import anthropic
from django.conf import settings

from .marcas import CAMPOS_TEXTO, FORMATOS, LIMITES_LISTA, MARCAS, tipos_para_ia

logger = logging.getLogger(__name__)
RAIZ = Path(settings.BASE_DIR)
MAX_SLIDES = 10


class ErroIA(Exception):
    pass


def _cliente():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY or None, max_retries=2, timeout=120)


def _sem_html(caminho: Path) -> str:
    t = caminho.read_text(encoding="utf-8")
    t = re.sub(r"{%.*?%}|{{.*?}}|{#.*?#}", "", t, flags=re.DOTALL)
    t = re.sub(r"<(script|style)\b.*?</\1>", "", t, flags=re.DOTALL)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).replace("&larr;", "").strip()


@lru_cache(maxsize=2)
def conhecimento(marca: str) -> str:
    """O que a IA precisa saber sobre o produto, tirado do próprio site."""
    if marca == "appfiliado":
        from atendimento.conhecimento import texto
        return texto()
    paginas = RAIZ / "paginas" / "templates" / "paginas"
    partes = [_sem_html(paginas / nome) for nome in ("faq.html", "regras_cashback.html", "e_confiavel.html")
              if (paginas / nome).exists()]
    return "Site: https://cash-b.com\n\n" + "\n\n".join(partes)


@lru_cache(maxsize=1)
def _voz() -> str:
    caminho = RAIZ / "VOZ.md"
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def _sistema(marca: str, formato: str) -> str:
    m = MARCAS[marca]
    nome_formato, largura, altura = FORMATOS[formato]
    limites = "; ".join(f"{campo} até {n} caracteres" for campo, (_, n) in CAMPOS_TEXTO.items())
    return f"""Você cria posts e stories do Instagram da marca {m['nome']}, em português do Brasil.

# Regras de texto (siga à risca)
- "pra/pro/pras/pros" só como contração de "para a/para o/para as/para os" ("pra Shopee", "pro grupo").
  Nos outros casos escreva "para": "para você", "para ver", "para cada", "para quem", "para um", "para todos".
- Sem vírgula antes do complemento em títulos.
- {m['voz']}
- Use só fatos que estão no material da marca abaixo. Não invente preço, número, prazo nem recurso.
- Frases curtas, que leiam bem no celular. Título forte e direto.
- Para destacar uma palavra ou expressão do título, coloque entre asteriscos: "Tudo num *painel só.*"
  No máximo um destaque por slide.

# Guia de voz completo
{_voz()}

# Formato
{nome_formato} ({largura}x{altura} px). {"Story: cada slide é um story separado." if formato == "story" else "Carrossel do feed: o primeiro slide é a capa que aparece na grade."}
Monte de 1 a {MAX_SLIDES} slides. Em carrossel, comece com uma capa e termine com uma chamada final.

# Tipos de slide
{tipos_para_ia(marca)}
Limites: {limites}. Listas: itens até {LIMITES_LISTA['itens']}, pares até {LIMITES_LISTA['pares']},
linhas até {LIMITES_LISTA['linhas']}, baloes até {LIMITES_LISTA['baloes']}.
Campo itens: [{{"titulo", "texto", "premium"}}]. pares: [{{"valor", "legenda"}}]. linhas: [{{"rotulo", "valor", "detalhe"}}].
baloes: [{{"texto", "meu"}}] (meu=true é a mensagem da pessoa, false é a resposta).

# Fundos
Cada slide tem fundo: {{"modo": "cor", "cor": um de {list(m['cores'])}}} ou
{{"modo": "arte", "arte": uma de {list(m['artes'])}, "tom": "escuro" ou "claro"}}.
Alterne fundos escuros e claros para dar ritmo. Capa e chamada final costumam ficar no escuro.
{f"Ícones (campo icone da capa): {', '.join(m['icones'])}." if m['icones'] else ""}
{f"Prints do painel (campo print do tipo tela): {', '.join(m['prints'])}. O campo recorte (0 a 1500) desce a tela do print." if m['prints'] else ""}

# Legenda
Escreva também a legenda do post: gancho na primeira linha, texto curto, chamada para o link na bio e de 5 a 8 hashtags no fim.

# Material da marca
{conhecimento(marca)}
"""


def _ferramenta(marca: str) -> dict:
    m = MARCAS[marca]
    texto = {"type": "string"}
    slide = {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": list(m["tipos"])},
            "fundo": {"type": "object", "properties": {
                "modo": {"type": "string", "enum": ["cor", "arte"]},
                "cor": {"type": "string", "enum": list(m["cores"])},
                "arte": {"type": "string", "enum": list(m["artes"])},
                "tom": {"type": "string", "enum": ["escuro", "claro"]}}, "required": ["modo"]},
            **{campo: texto for campo in CAMPOS_TEXTO},
            "numerada": {"type": "boolean"},
            "itens": {"type": "array", "items": {"type": "object", "properties": {
                "titulo": texto, "texto": texto, "premium": {"type": "boolean"}}, "required": ["titulo"]}},
            "pares": {"type": "array", "items": {"type": "object", "properties": {"valor": texto, "legenda": texto}, "required": ["valor"]}},
            "linhas": {"type": "array", "items": {"type": "object", "properties": {"rotulo": texto, "valor": texto, "detalhe": texto}, "required": ["rotulo", "valor"]}},
            "baloes": {"type": "array", "items": {"type": "object", "properties": {"texto": texto, "meu": {"type": "boolean"}}, "required": ["texto"]}},
        },
        "required": ["tipo", "fundo"],
    }
    if m["icones"]:
        slide["properties"]["icone"] = {"type": "string", "enum": [""] + m["icones"]}
    if m["prints"]:
        slide["properties"]["print"] = {"type": "string", "enum": m["prints"]}
        slide["properties"]["recorte"] = {"type": "integer"}
    return {
        "name": "montar_post",
        "description": "Entrega o post pronto para o editor.",
        "input_schema": {"type": "object", "properties": {
            "nome": {"type": "string", "description": "Nome curto do post, para a lista do estúdio."},
            "legenda": {"type": "string"},
            "slides": {"type": "array", "items": slide},
        }, "required": ["nome", "legenda", "slides"]},
    }


def _txt(v, limite):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:limite]


def _num(v, minimo, maximo, padrao):
    try:
        return min(max(float(v), minimo), maximo)
    except (TypeError, ValueError):
        return padrao


def limpar_ajustes(a) -> dict:
    """Ajustes manuais do slide: tamanho do título e do texto (fator), margens extras (px na
    imagem final), alinhamento e posição do texto. Só guarda o que foi mudado."""
    if not isinstance(a, dict):
        return {}
    out = {
        "titulo": round(_num(a.get("titulo"), 0.6, 1.6, 1), 2),
        "texto": round(_num(a.get("texto"), 0.6, 1.6, 1), 2),
        "lateral": int(_num(a.get("lateral"), -60, 200, 0)),
        "vertical": int(_num(a.get("vertical"), -60, 200, 0)),
        "alinhar": a.get("alinhar") if a.get("alinhar") in ("esquerda", "centro") else "",
        "posicao": a.get("posicao") if a.get("posicao") in ("topo", "meio", "base") else "",
    }
    padrao = {"titulo": 1, "texto": 1, "lateral": 0, "vertical": 0, "alinhar": "", "posicao": ""}
    return {k: v for k, v in out.items() if v != padrao[k]}


def limpar_slide(marca: str, s: dict) -> dict | None:
    """Deixa o slide só com o que o editor conhece."""
    m = MARCAS[marca]
    if not isinstance(s, dict) or s.get("tipo") not in m["tipos"]:
        return None
    campos = m["tipos"][s["tipo"]][1]
    f = s.get("fundo") if isinstance(s.get("fundo"), dict) else {}
    if f.get("modo") == "arte" and f.get("arte") in m["artes"]:
        fundo = {"modo": "arte", "arte": f["arte"], "tom": "claro" if f.get("tom") == "claro" else "escuro"}
    elif f.get("modo") == "imagem" and str(f.get("imagem", "")).startswith(("/", "http")):
        fundo = {"modo": "imagem", "imagem": str(f["imagem"])[:500], "veu": min(max(float(f.get("veu") or 0), 0), 0.85)}
    else:
        fundo = {"modo": "cor", "cor": f.get("cor") if f.get("cor") in m["cores"] else next(iter(m["cores"]))}
    out = {"tipo": s["tipo"], "fundo": fundo}
    if isinstance(s.get("capa"), bool):
        out["capa"] = s["capa"]
    ajustes = limpar_ajustes(s.get("ajustes"))
    if ajustes:
        out["ajustes"] = ajustes
    for campo in campos:
        if campo in CAMPOS_TEXTO:
            out[campo] = _txt(s.get(campo), CAMPOS_TEXTO[campo][1])
        elif campo == "itens":
            out["itens"] = [{"titulo": _txt(i.get("titulo"), 60), "texto": _txt(i.get("texto"), 110), "premium": bool(i.get("premium"))}
                            for i in (s.get("itens") or [])[:LIMITES_LISTA["itens"]] if isinstance(i, dict)]
        elif campo == "pares":
            out["pares"] = [{"valor": _txt(p.get("valor"), 14), "legenda": _txt(p.get("legenda"), 50)}
                            for p in (s.get("pares") or [])[:LIMITES_LISTA["pares"]] if isinstance(p, dict)]
        elif campo == "linhas":
            out["linhas"] = [{"rotulo": _txt(r.get("rotulo"), 40), "valor": _txt(r.get("valor"), 20), "detalhe": _txt(r.get("detalhe"), 40)}
                             for r in (s.get("linhas") or [])[:LIMITES_LISTA["linhas"]] if isinstance(r, dict)]
        elif campo == "baloes":
            out["baloes"] = [{"texto": _txt(b.get("texto"), 160), "meu": bool(b.get("meu"))}
                             for b in (s.get("baloes") or [])[:LIMITES_LISTA["baloes"]] if isinstance(b, dict)]
        elif campo == "numerada":
            out["numerada"] = bool(s.get("numerada"))
        elif campo == "logo":
            out["logo"] = s.get("logo") is not False
        elif campo == "icone":
            out["icone"] = s.get("icone") if s.get("icone") in m["icones"] else ""
        elif campo == "print":
            out["print"] = s.get("print") if s.get("print") in m["prints"] else (m["prints"][0] if m["prints"] else "")
        elif campo == "recorte":
            try:
                out["recorte"] = min(max(int(s.get("recorte") or 0), 0), 3000)
            except (TypeError, ValueError):
                out["recorte"] = 0
    return out


def limpar(marca: str, dados: dict) -> dict:
    slides = [x for x in (limpar_slide(marca, s) for s in (dados.get("slides") or [])[:MAX_SLIDES]) if x]
    if not slides:
        raise ErroIA("A IA não devolveu nenhum slide válido. Tente pedir de outro jeito.")
    return {"nome": _txt(dados.get("nome"), 120) or "Post da IA", "legenda": str(dados.get("legenda") or "").strip()[:2200],
            "slides": slides}


def gerar(marca: str, formato: str, pedido: str, atual: dict | None = None, cliente=None) -> dict:
    """atual: {"slides", "legenda"} quando é para ajustar um post que já existe."""
    if marca not in MARCAS or formato not in FORMATOS:
        raise ErroIA("Marca ou formato desconhecido.")
    pedido = (pedido or "").strip()[:3000]
    if not pedido:
        raise ErroIA("Escreva o que você quer no post.")
    if atual:
        conteudo = ("Ajuste o post abaixo seguindo o pedido. Mantenha o que o pedido não mandar mudar.\n\n"
                    f"Pedido: {pedido}\n\nPost atual (JSON):\n"
                    + json.dumps({"slides": atual.get("slides", []), "legenda": atual.get("legenda", "")}, ensure_ascii=False))
    else:
        conteudo = f"Crie um post com este pedido: {pedido}"
    cliente = cliente or _cliente()
    try:
        resposta = cliente.beta.messages.create(
            model=settings.ESTUDIO_MODELO,
            max_tokens=12000,
            system=_sistema(marca, formato),
            messages=[{"role": "user", "content": conteudo}],
            tools=[_ferramenta(marca)],
            tool_choice={"type": "tool", "name": "montar_post"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as erro:
        logger.warning("Estúdio: erro da IA (%s)", erro)
        raise ErroIA("A IA não respondeu agora. Tente de novo em instantes.") from erro
    chamada = next((b for b in resposta.content if b.type == "tool_use"), None)
    if not chamada:
        raise ErroIA("A IA não montou o post. Tente pedir de outro jeito.")
    dados = chamada.input if isinstance(chamada.input, dict) else json.loads(chamada.input)
    return limpar(marca, dados)
