"""Estúdio Instagram do painel: o que cada plano pode salvar, como nasce um post (do link de um
produto da Shopee, de um pedido para a IA, de um modelo ou em branco) e as imagens do afiliado.

As telas ficam em painel/views_estudio.py. O desenho dos slides é do navegador
(static/estudio/marca-afiliado.js), igual ao estúdio do admin."""

import copy
import io
import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from carrosseis import servicos as carrosseis
from carrosseis.ia import brl
from carrosseis.models import UsoCarrossel

from . import ia
from .marcas import FORMATOS, MARCAS, TEMAS_AFILIADO
from .models import FONTES_AFILIADO, ImagemAfiliado, MarcaAfiliado, PostInstagram

MARCA = "afiliado"
MAX_SLIDES = 10
MAX_IMAGENS = 80
LADO_IMAGEM = 1600
LADO_LOGO = 600
MAX_ENVIO = 12 * 1024 * 1024
MAX_MINIATURA = 400 * 1024
COR = re.compile(r"^#[0-9a-fA-F]{6}$")
ARROBA = re.compile(r"^@?[A-Za-z0-9._]{1,30}$")
TEMAS_PRONTOS = list(TEMAS_AFILIADO)


class ErroEstudio(Exception):
    """Mensagem pronta para mostrar à pessoa."""


def eh_premium(conta) -> bool:
    return carrosseis.eh_premium(conta)


@lru_cache(maxsize=1)
def modelos() -> list[dict]:
    caminho = Path(__file__).parent / "modelos" / "afiliado.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def modelo(codigo: str) -> dict | None:
    return next((m for m in modelos() if m["codigo"] == codigo), None)


# --- cores ------------------------------------------------------------------------------------

def _mistura(a: str, b: str, p: float) -> str:
    x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x[k] * p + y[k] * (1 - p)):02X}" for k in range(3))


def temas(conta) -> dict:
    """As paletas que o editor usa. "marca" só existe no Premium e sai das cores da Minha marca."""
    saida = dict(TEMAS_AFILIADO)
    marca = MarcaAfiliado.objects.filter(conta=conta).first()
    if eh_premium(conta) and marca:
        saida["marca"] = {"a": marca.cor, "b": _mistura(marca.cor, "#FFFFFF", 0.07), "acc": marca.cor_destaque,
                          "ink": _mistura(marca.cor, "#111111", 0.25)}
    return saida


# --- o que pode ser salvo ---------------------------------------------------------------------

def com_produto(slides: list, produto: dict) -> list:
    """Foto, preço e desconto do produto nos slides (a IA e os modelos não inventam valores)."""
    if not produto or not produto.get("nome"):
        return slides
    desconto = f"-{produto['desconto']}%" if produto.get("desconto") else ""
    for s in slides:
        if s["tipo"] in ("capa", "produto") and not s.get("foto") and produto.get("imagem"):
            s["foto"] = produto["imagem"]
        if s["tipo"] == "capa" and "desconto" in s:
            s["desconto"] = desconto
        if s["tipo"] == "preco":
            s["preco"] = brl(produto.get("preco") or 0)
            s["de"] = brl(produto["de"]) if produto.get("de") else ""
            s["desconto"] = desconto
    return slides


def limpar_slides(slides, premium: bool) -> list:
    """Só tipos, campos e tamanhos que o editor conhece. No Standard, o visual é o do modelo:
    sem imagem de fundo nem ajustes finos."""
    saida = []
    for s in (slides if isinstance(slides, list) else [])[:MAX_SLIDES]:
        limpo = ia.limpar_slide(MARCA, s)
        if not limpo:
            continue
        if not premium:
            limpo.pop("ajustes", None)
            limpo.pop("capa", None)
            if limpo["fundo"]["modo"] == "imagem":
                limpo["fundo"] = {"modo": "cor", "cor": "tema"}
        saida.append(limpo)
    return saida


def limpar_tema(tema, premium: bool, atual: str = "verde") -> str:
    if tema in TEMAS_PRONTOS or (tema == "marca" and premium):
        return tema
    return atual if atual in TEMAS_PRONTOS else "verde"


def salvar(post: PostInstagram, dados: dict) -> None:
    premium = eh_premium(post.conta)
    post.nome = (str(dados.get("nome") or "").strip() or "Sem nome")[:120]
    if dados.get("formato") in FORMATOS:
        post.formato = dados["formato"]
    post.tema = limpar_tema(dados.get("tema"), premium, post.tema)
    post.slides = limpar_slides(dados.get("slides"), premium) or post.slides
    post.legenda = str(dados.get("legenda") or "")[:2200]
    miniatura = str(dados.get("miniatura") or "")
    if miniatura.startswith("data:image/jpeg;base64,"):
        import base64
        import binascii

        try:
            bruto = base64.b64decode(miniatura.split(",", 1)[1], validate=True)
        except (binascii.Error, ValueError):
            bruto = b""
        if 0 < len(bruto) <= MAX_MINIATURA and bruto[:3] == b"\xff\xd8\xff":
            post.miniatura = bruto
    post.save()


# --- a IA e o limite do dia (o mesmo do gerador de carrosséis) ----------------------------------

def restantes(conta) -> dict:
    return carrosseis.restantes(conta)


def _com_ia(conta, formato: str, pedido: str, produto: dict | None = None, atual: dict | None = None) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        raise ErroEstudio("A IA está desligada agora. Comece de um modelo.")
    limite = restantes(conta)["limite"]
    try:
        carrosseis._consumir(conta, "geracoes", limite)
    except carrosseis.ErroGerador as erro:
        raise ErroEstudio(str(erro)) from erro
    try:
        return ia.gerar(MARCA, formato, pedido, atual=atual, produto=produto, modelo=settings.ESTUDIO_MODELO_AFILIADOS)
    except ia.ErroIA as erro:
        UsoCarrossel.objects.filter(conta=conta, dia=timezone.localdate()).update(geracoes=F("geracoes") - 1)
        raise ErroEstudio(str(erro)) from erro


def ajustar_com_ia(post: PostInstagram, dados: dict) -> dict:
    """Pedido feito dentro do editor: cria um post novo ou ajusta o que está aberto."""
    formato = dados.get("formato") if dados.get("formato") in FORMATOS else post.formato
    atual = {"slides": dados.get("slides") or [], "legenda": dados.get("legenda") or ""} if dados.get("ajustar") else None
    feito = _com_ia(post.conta, formato, str(dados.get("pedido") or ""), produto=post.produto or None, atual=atual)
    slides = com_produto(limpar_slides(feito["slides"], eh_premium(post.conta)), post.produto)
    return {**feito, "slides": slides, "restantes": _texto_restantes(post.conta)}


def _texto_restantes(conta) -> str:
    r = restantes(conta)
    return f"Restam {r['geracoes']} de {r['limite']} criações com IA hoje."


# --- criar ----------------------------------------------------------------------------------------

def criar(conta, como: str, link: str = "", pedido: str = "", codigo_modelo: str = "", formato: str = "") -> PostInstagram:
    premium = eh_premium(conta)
    formato = formato if formato in FORMATOS else MARCAS[MARCA]["formato_padrao"]
    post = PostInstagram(conta=conta, formato=formato)
    if como == "produto":
        produto = carrosseis.produto_do_link(conta, link)  # levanta ErroGerador com o motivo
        produto.pop("item_id", None)
        produto.pop("link_original", None)
        post.produto = produto
        try:
            feito = _com_ia(conta, formato, pedido, produto=produto)
            post.nome, post.legenda, slides = feito["nome"], feito["legenda"], feito["slides"]
        except ErroEstudio:
            # Sem IA (limite do dia, fora do ar): o post sai do modelo de produto, com os dados da Shopee.
            m = modelo("achado-story" if formato == "story" else "achado")
            post.nome, post.legenda, slides, post.tema = ia._txt(produto["nome"], 120), m["legenda"], copy.deepcopy(m["slides"]), m["tema"]
        post.slides = com_produto(limpar_slides(slides, premium), produto)
    elif como == "ia":
        feito = _com_ia(conta, formato, pedido)
        post.nome, post.legenda, post.slides = feito["nome"], feito["legenda"], limpar_slides(feito["slides"], premium)
    elif como == "modelo":
        m = modelo(codigo_modelo)
        if not m:
            raise ErroEstudio("Escolha um modelo.")
        post.nome, post.formato, post.tema, post.legenda = m["nome"], m["formato"], m["tema"], m["legenda"]
        post.slides = limpar_slides(copy.deepcopy(m["slides"]), premium)
    else:
        post.nome, post.slides = "Novo post", limpar_slides([{"tipo": "capa", "fundo": {"modo": "cor", "cor": "tema"},
                                                               "chapeu": "Achado do dia", "titulo": "Seu título com *destaque*"}], premium)
    if premium and MarcaAfiliado.objects.filter(conta=conta).exists() and como != "modelo":
        post.tema = "marca"
    post.save()
    return post


def duplicar(post: PostInstagram) -> PostInstagram:
    return PostInstagram.objects.create(conta=post.conta, formato=post.formato, tema=post.tema, nome=f"{post.nome} (cópia)"[:120],
                                        slides=post.slides, legenda=post.legenda, produto=post.produto, miniatura=post.miniatura)


# --- imagens ----------------------------------------------------------------------------------------

def _abrir(arquivo):
    from PIL import Image, ImageOps

    if arquivo.size > MAX_ENVIO:
        raise ErroEstudio("A imagem passa de 12 MB.")
    try:
        imagem = Image.open(arquivo)
        if imagem.format not in ("JPEG", "PNG", "WEBP"):
            raise ErroEstudio("Use uma imagem JPG, PNG ou WebP.")
        if imagem.size[0] * imagem.size[1] > 40_000_000:
            raise ErroEstudio("Essa imagem é grande demais. Use uma de até 40 megapixels.")
        imagem.load()
        return ImageOps.exif_transpose(imagem)
    except ErroEstudio:
        raise
    except Exception as erro:  # Pillow levanta vários tipos para arquivo quebrado
        raise ErroEstudio("Esse arquivo não é uma imagem válida.") from erro


def _gravar(imagem, lado: int, sempre_png: bool = False) -> tuple[bytes, str]:
    from PIL import Image

    transparente = imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info)
    imagem = imagem.convert("RGBA" if transparente else "RGB")
    imagem.thumbnail((lado, lado), Image.LANCZOS)
    saida = io.BytesIO()
    if transparente or sempre_png:
        imagem.save(saida, "PNG", optimize=True)
        return saida.getvalue(), "image/png"
    imagem.save(saida, "JPEG", quality=88, optimize=True)
    return saida.getvalue(), "image/jpeg"


def guardar_imagem(conta, arquivo) -> ImagemAfiliado:
    if ImagemAfiliado.objects.filter(conta=conta).count() >= MAX_IMAGENS:
        raise ErroEstudio(f"Você chegou a {MAX_IMAGENS} imagens. Apague algumas para enviar outras.")
    dados, tipo = _gravar(_abrir(arquivo), LADO_IMAGEM)
    return ImagemAfiliado.objects.create(conta=conta, dados=dados, tipo=tipo, nome=str(arquivo.name or "")[:120])


def salvar_marca(conta, dados: dict, logo=None, tirar_logo: bool = False) -> MarcaAfiliado:
    """O @ vale para todos os planos; nome, cores, fonte e logo são do Premium."""
    marca, _ = MarcaAfiliado.objects.get_or_create(conta=conta)
    arroba = str(dados.get("arroba") or "").strip()
    if arroba and not ARROBA.match(arroba):
        raise ErroEstudio("O @ só pode ter letras, números, ponto e sublinhado.")
    marca.arroba = ("@" + arroba.lstrip("@")) if arroba else ""
    if eh_premium(conta):
        marca.nome = str(dados.get("nome") or "").strip()[:60]
        for campo in ("cor", "cor_destaque"):
            valor = str(dados.get(campo) or "")
            if COR.match(valor):
                setattr(marca, campo, valor.upper())
        if dados.get("fonte") in dict(FONTES_AFILIADO):
            marca.fonte = dados["fonte"]
        if tirar_logo:
            marca.logo = None
        elif logo:
            marca.logo, _ = _gravar(_abrir(logo), LADO_LOGO, sempre_png=True)
    marca.save()
    return marca
