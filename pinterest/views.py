from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone

from ofertas.services import carregar_categorias_nivel1

from . import services
from .imagem import gerar_imagem_pin_categoria

PASTA_PINS = Path(settings.MEDIA_ROOT) / "pinterest"


def imagem_pin(request, categoria_id, chave, assinatura):
    """Gerada no primeiro pedido (normalmente o do próprio Pinterest, na importação) e
    guardada em disco dali em diante. Gerar as 14 artes na hora de baixar a planilha
    passaria do timeout do gunicorn - cada uma baixa 4 fotos da Shopee."""
    if not services.assinatura_valida(categoria_id, chave, assinatura):
        raise Http404
    nome_categoria = carregar_categorias_nivel1().get(categoria_id)
    if not nome_categoria:
        raise Http404

    caminho = PASTA_PINS / f"{categoria_id}-{chave}.jpg"
    if not caminho.exists():
        ofertas = services.escolher_fotos(categoria_id, chave)
        if not ofertas:
            # Categoria sumiu do catálogo desde que a planilha foi gerada. Sem foto
            # nenhuma o Pin seria só um título sobre quadrados vazios - melhor o
            # Pinterest recusar a linha do que publicar isso.
            raise Http404
        PASTA_PINS.mkdir(parents=True, exist_ok=True)
        gerar_imagem_pin_categoria(nome_categoria, ofertas).save(caminho, "JPEG", quality=90)
    return FileResponse(caminho.open("rb"), content_type="image/jpeg")


@staff_member_required
def planilha_semana(request):
    linhas = services.montar_linhas()
    resposta = HttpResponse(services.gerar_csv(linhas), content_type="text/csv; charset=utf-8")
    nome = f"pins-cash-b-{timezone.localdate():%Y-%m-%d}.csv"
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return resposta
