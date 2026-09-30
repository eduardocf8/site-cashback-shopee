"""Planilha semanal de Pins pro "Importar conteúdo" do Pinterest (caminho A do plano).

Por que planilha e não API: a API v5 só publica Pin visível pra outras pessoas depois
do acesso Standard, que passa por revisão manual demorada e sem garantia. A planilha
é o caminho oficial que funciona hoje, com a conta business, sem aprovação nenhuma -
o custo é um upload manual por semana. O mesmo gerador de linhas serve pra API depois,
se o acesso sair: só muda quem entrega.

Nada aqui publica sozinho. Quem sobe o arquivo e confere os Pins é o dono - o que
também deixa o fluxo do lado certo da regra do Pinterest contra ação automática sem
revisão humana.
"""
import csv
import io
import random
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from ofertas import services as ofertas_services
from ofertas.models import Oferta

# O modelo que o painel do Pinterest oferece pra baixar em "Importar conteúdo" é a
# referência: se ele mudar de nome ou ordem de coluna, é só aqui que muda. A pesquisa
# que originou isto não teve acesso à página oficial - conferir com o modelo do
# painel antes do primeiro upload.
COLUNAS_CSV = [
    "Title", "Media URL", "Pinterest board", "Thumbnail",
    "Description", "Link", "Publish date", "Keywords",
]

# 14 = 2 Pins por dia numa semana. As fontes divergem sobre o teto do arquivo (100 a
# 200 linhas), e a gente fica muito abaixo de qualquer um dos dois.
PINS_POR_SEMANA = 14
HORARIOS_PUBLICACAO = (time(12, 0), time(20, 0))  # hora de Brasília

# Sorteia as 4 fotos entre os N mais vendidos da categoria, e não sempre os 4
# primeiros - o ranking quase não muda de uma semana pra outra, e 14 Pins/semana com
# as mesmas fotos virava imagem repetida (mesmo motivo de
# instagram_bot/services.py::TAMANHO_POOL_PRODUTOS_POR_CATEGORIA).
TAMANHO_POOL_FOTOS = 20
FOTOS_POR_PIN = 4

TITULO_MAXIMO = 100  # limite do Pinterest
SALT_ASSINATURA = "pinterest.pin"


def _assinatura(categoria_id: int, chave: str) -> str:
    # Assinada porque a imagem é gerada na hora do primeiro pedido e baixa 4 fotos da
    # Shopee: sem isso qualquer um geraria arquivo novo no disco trocando a data da URL.
    return signing.Signer(salt=SALT_ASSINATURA).sign(f"{categoria_id}-{chave}").rsplit(":", 1)[1]


def assinatura_valida(categoria_id: int, chave: str, assinatura: str) -> bool:
    return signing.constant_time_compare(_assinatura(categoria_id, chave), assinatura)


def url_imagem_pin(categoria_id: int, chave: str) -> str:
    """Mesmo cuidado de instagram_bot/services.py::_url_publica_da_midia: o endereço
    direto do Render, não o domínio com Cloudflare na frente, pra o rastreador do
    Pinterest não esbarrar em proteção contra bot na hora de buscar a imagem."""
    caminho = reverse(
        "pinterest_imagem_pin",
        kwargs={"categoria_id": categoria_id, "chave": chave, "assinatura": _assinatura(categoria_id, chave)},
    )
    host = settings.RENDER_EXTERNAL_HOSTNAME
    return f"https://{host}{caminho}" if host else f"{settings.PINTEREST_SITE_URL}{caminho}"


def url_destino(categoria_id: int, categoria_nome: str) -> str:
    """Domínio próprio, nunca o link curto da Shopee: link que esconde o destino ou
    passa por cadeia de redirecionamento é o que o Pinterest trata como spam. E a
    página da categoria, não a de uma oferta, porque o id da oferta muda todo dia.

    utm_source=pinterest é o que accounts/middleware.py grava como origem do cadastro -
    é assim que o funil (funil_cadastros --origem pinterest) separa quem veio daqui."""
    parametros = urlencode({
        "categoria": categoria_id,
        "utm_source": "pinterest",
        "utm_medium": "pin",
        "utm_campaign": slugify(categoria_nome),
    })
    return f"{settings.PINTEREST_SITE_URL}{reverse('ofertas_lista')}?{parametros}"


def escolher_fotos(categoria_id: int, chave: str) -> list[Oferta]:
    """Sorteio com semente fixa (categoria + chave): a mesma URL de imagem sempre
    monta as mesmas fotos, então o arquivo pode ser gerado de novo se o disco perder
    o cache sem virar outra arte."""
    candidatas = list(Oferta.objects.filter(categoria_id=categoria_id).exclude(imagem_url="")[:TAMANHO_POOL_FOTOS])
    random.Random(f"{categoria_id}-{chave}").shuffle(candidatas)
    escolhidas, nomes = [], set()
    for oferta in candidatas:
        nome = ofertas_services.normalizar_nome_produto(oferta.nome)
        if nome in nomes:
            continue
        nomes.add(nome)
        escolhidas.append(oferta)
        if len(escolhidas) == FOTOS_POR_PIN:
            break
    return escolhidas


def _titulo(categoria_nome: str) -> str:
    return f"{categoria_nome}: os mais vendidos da Shopee com cashback"[:TITULO_MAXIMO]


def _descricao(categoria_nome: str) -> str:
    # "Contém link de afiliado" é a divulgação que o Pinterest exige pra link de
    # afiliado. Voz: ver VOZ.md (cashback afirmativo, "você", "a cash-b", "Pix").
    return (
        f"Os produtos mais vendidos de {categoria_nome} na Shopee, reunidos na cash-b. "
        "Você compra normalmente na Shopee e parte do valor volta para você via Pix: "
        "toda compra gera cashback. Contém link de afiliado."
    )


def _palavras_chave(categoria_nome: str) -> str:
    return ", ".join(["shopee", "cashback", "ofertas shopee", categoria_nome.lower()])


def _horarios(inicio, quantidade: int) -> list[datetime]:
    """Espalha os Pins a partir do dia seguinte a `inicio`, nos HORARIOS_PUBLICACAO de
    cada dia. Em UTC, que é o que a importação espera."""
    fuso = timezone.get_current_timezone()
    horarios, dia = [], inicio + timedelta(days=1)
    while len(horarios) < quantidade:
        for hora in HORARIOS_PUBLICACAO:
            horarios.append(timezone.make_aware(datetime.combine(dia, hora), fuso))
        dia += timedelta(days=1)
    return [h.astimezone(dt_timezone.utc) for h in horarios[:quantidade]]


def montar_linhas(quantidade: int = PINS_POR_SEMANA, hoje=None) -> list[dict]:
    """Uma linha por categoria, das mais vendidas pra menos. Se o catálogo tiver
    menos categorias que `quantidade`, sai só o que tem - repetir categoria na mesma
    semana é o padrão de conteúdo duplicado que o Pinterest rebaixa."""
    hoje = hoje or timezone.localdate()
    chave = hoje.strftime("%Y%m%d")
    categorias = [
        categoria for categoria in ofertas_services.categorias_mais_vendidas(quantidade * 2)
        if categoria["categoria_id"] and categoria["categoria_nome"]
    ][:quantidade]

    linhas = []
    for categoria, horario in zip(categorias, _horarios(hoje, len(categorias))):
        categoria_id, nome = categoria["categoria_id"], categoria["categoria_nome"]
        linhas.append({
            "Title": _titulo(nome),
            "Media URL": url_imagem_pin(categoria_id, chave),
            "Pinterest board": settings.PINTEREST_NOME_BOARD.format(categoria=nome),
            "Thumbnail": "",
            "Description": _descricao(nome),
            "Link": url_destino(categoria_id, nome),
            "Publish date": horario.strftime("%Y-%m-%dT%H:%M:%S"),
            "Keywords": _palavras_chave(nome),
        })
    return linhas


def gerar_csv(linhas: list[dict]) -> str:
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=COLUNAS_CSV)
    escritor.writeheader()
    escritor.writerows(linhas)
    return saida.getvalue()
