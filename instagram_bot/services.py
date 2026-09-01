import io
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from PIL import Image

from ofertas import services as ofertas_services
from ofertas.models import Oferta

from . import aprovacao, conteudo, instagram_client
from .models import RegistroPublicacao
from .templates_imagem import (
    CORES,
    gerar_imagem_conta,
    gerar_imagem_numero_com_produto,
    gerar_imagem_oferta_carrossel,
    gerar_imagem_oferta_story,
    gerar_imagem_passos,
    gerar_imagem_texto_simples,
)

logger = logging.getLogger(__name__)

PASTA_MEDIA_BOT = Path(settings.MEDIA_ROOT) / "instagram"

# Stories de oferta: em vez de 1 story só com 3 ofertas juntas, posta várias vezes ao
# dia (ver /tarefas/postar-story-oferta/ e o cron dedicado) 1 story com 1 oferta só,
# até completar esse número - assim o perfil não fica "bombardeado" de oferta de uma
# vez, mas também não some do ar o resto do dia (a conta não é só sobre ofertas).
NUMERO_STORIES_OFERTAS_POR_DIA = 5

# A Shopee tende a devolver sempre os mesmos best-sellers de um dia pro outro (a
# sincronização é um "retrato" diário, sem histórico - ver ofertas/services.py,
# sincronizar_ofertas), então sem um intervalo mínimo entre repetições o mesmo produto
# aparecia quase todo dia. 7 dias = não repete a mesma oferta na mesma semana.
DIAS_SEM_REPETIR_OFERTA = 7


def _url_publica_da_midia(nome_arquivo: str, request) -> str:
    """Sempre usa o endereço direto do Render (onrender.com) quando disponível, nunca
    o domínio customizado (ex: cash-b.com) - se houver Cloudflare ou outro proxy/CDN
    na frente do domínio customizado, o rastreador da Meta pode não conseguir buscar
    a imagem por ali (bot fight mode etc.), mesmo funcionando normal num navegador."""
    caminho = f"{settings.MEDIA_URL}instagram/{nome_arquivo}"
    if settings.RENDER_EXTERNAL_HOSTNAME:
        return f"https://{settings.RENDER_EXTERNAL_HOSTNAME}{caminho}"
    return request.build_absolute_uri(caminho)


def _salvar_e_montar_url(imagem, request) -> str:
    # JPEG, não PNG: a Instagram Graph API só aceita JPEG pra publicar imagem
    # (PNG gera o erro genérico "Only photo or video can be accepted as media type").
    PASTA_MEDIA_BOT.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    caminho = PASTA_MEDIA_BOT / nome_arquivo
    imagem.save(caminho, "JPEG", quality=90)
    return _url_publica_da_midia(nome_arquivo, request)


def _bytes_jpeg(imagem) -> bytes:
    buffer = io.BytesIO()
    imagem.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _salvar_e_montar_urls(imagens, request) -> list[str]:
    return [_salvar_e_montar_url(imagem, request) for imagem in imagens]


def _ja_processado_hoje(data, conteudo_tipo: str) -> bool:
    """True se já existe um registro de hoje pra esse tipo de conteúdo que não seja
    um erro transitório - ou seja, já foi simulado, já está aguardando aprovação, já
    foi publicado ou já foi rejeitado. Só erro não bloqueia, pra permitir nova
    tentativa na próxima execução da tarefa diária."""
    return (
        RegistroPublicacao.objects.filter(data=data, conteudo_tipo=conteudo_tipo)
        .exclude(status=RegistroPublicacao.STATUS_ERRO)
        .exists()
    )


def _registrar(
    data, tipo, conteudo_tipo, legenda, imagem_url, simulacao, sucesso, status, erro="", imagem_urls=""
):
    return RegistroPublicacao.objects.create(
        data=data,
        tipo=tipo,
        conteudo_tipo=conteudo_tipo,
        legenda=legenda,
        imagem_url=imagem_url,
        imagem_urls=imagem_urls,
        modo_simulacao=simulacao,
        status=status,
        sucesso=sucesso,
        erro=erro,
    )


def _publicar_ou_simular(
    imagem, legenda, tipo, conteudo_tipo, data, request, story: bool, posicao=None
) -> RegistroPublicacao:
    """posicao é (qual, total) e só chega até o e-mail de aprovação - ver
    aprovacao.enviar_email_aprovacao. Nos outros caminhos (simulação, publicação direta)
    ela é ignorada, porque não existe e-mail para ordenar."""
    if not settings.INSTAGRAM_BOT_ATIVO:
        return _simular(imagem, legenda, tipo, conteudo_tipo, data, request)
    if settings.INSTAGRAM_REQUER_APROVACAO:
        return _aguardar_aprovacao(imagem, legenda, tipo, conteudo_tipo, data, request, posicao)
    return _publicar_direto(imagem, legenda, tipo, conteudo_tipo, data, request, story)


def _simular(imagem, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_url = _salvar_e_montar_url(imagem, request)
    logger.info(
        "[instagram_bot] modo simulação (INSTAGRAM_BOT_ATIVO=False) - geraria %s/%s: %s",
        tipo, conteudo_tipo, imagem_url,
    )
    return _registrar(
        data, tipo, conteudo_tipo, legenda, imagem_url,
        simulacao=True, sucesso=True, status=RegistroPublicacao.STATUS_SIMULADO,
    )


def _publicar_direto(imagem, legenda, tipo, conteudo_tipo, data, request, story: bool) -> RegistroPublicacao:
    imagem_url = ""
    try:
        imagem_url = _salvar_e_montar_url(imagem, request)
        media_id = instagram_client.publicar_imagem(imagem_url, legenda=legenda, story=story)
        registro = _registrar(
            data, tipo, conteudo_tipo, legenda, imagem_url,
            simulacao=False, sucesso=True, status=RegistroPublicacao.STATUS_PUBLICADO,
        )
        registro.instagram_media_id = media_id
        registro.save(update_fields=["instagram_media_id"])
        return registro
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar %s/%s", tipo, conteudo_tipo)
        return _registrar(
            data, tipo, conteudo_tipo, legenda, imagem_url,
            simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_ERRO, erro=str(erro),
        )


def _aguardar_aprovacao(imagem, legenda, tipo, conteudo_tipo, data, request, posicao=None) -> RegistroPublicacao:
    imagem_url = _salvar_e_montar_url(imagem, request)
    registro = _registrar(
        data, tipo, conteudo_tipo, legenda, imagem_url,
        simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_PENDENTE_APROVACAO,
    )
    try:
        aprovacao.enviar_email_aprovacao(registro, [_bytes_jpeg(imagem)], request, posicao=posicao)
    except Exception:
        logger.exception("[instagram_bot] falha ao enviar e-mail de aprovação (registro %s)", registro.pk)
    return registro


def _publicar_ou_simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    if not settings.INSTAGRAM_BOT_ATIVO:
        return _simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)
    if settings.INSTAGRAM_REQUER_APROVACAO:
        return _aguardar_aprovacao_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)
    return _publicar_direto_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request)


def _simular_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = _salvar_e_montar_urls(imagens, request)
    logger.info(
        "[instagram_bot] modo simulação (INSTAGRAM_BOT_ATIVO=False) - geraria carrossel %s/%s com %s imagens",
        tipo, conteudo_tipo, len(imagem_urls),
    )
    return _registrar(
        data, tipo, conteudo_tipo, legenda, "",
        simulacao=True, sucesso=True, status=RegistroPublicacao.STATUS_SIMULADO,
        imagem_urls="\n".join(imagem_urls),
    )


def _publicar_direto_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = []
    try:
        imagem_urls = _salvar_e_montar_urls(imagens, request)
        media_id = instagram_client.publicar_carrossel(imagem_urls, legenda=legenda)
        registro = _registrar(
            data, tipo, conteudo_tipo, legenda, "",
            simulacao=False, sucesso=True, status=RegistroPublicacao.STATUS_PUBLICADO,
            imagem_urls="\n".join(imagem_urls),
        )
        registro.instagram_media_id = media_id
        registro.save(update_fields=["instagram_media_id"])
        return registro
    except Exception as erro:
        logger.exception("[instagram_bot] falha ao publicar carrossel %s/%s", tipo, conteudo_tipo)
        return _registrar(
            data, tipo, conteudo_tipo, legenda, "",
            simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_ERRO, erro=str(erro),
            imagem_urls="\n".join(imagem_urls),
        )


def _aguardar_aprovacao_carrossel(imagens, legenda, tipo, conteudo_tipo, data, request) -> RegistroPublicacao:
    imagem_urls = _salvar_e_montar_urls(imagens, request)
    registro = _registrar(
        data, tipo, conteudo_tipo, legenda, "",
        simulacao=False, sucesso=False, status=RegistroPublicacao.STATUS_PENDENTE_APROVACAO,
        imagem_urls="\n".join(imagem_urls),
    )
    try:
        aprovacao.enviar_email_aprovacao(registro, [_bytes_jpeg(imagem) for imagem in imagens], request)
    except Exception:
        logger.exception("[instagram_bot] falha ao enviar e-mail de aprovação (registro %s)", registro.pk)
    return registro


def _escolher_oferta_do_momento(data) -> Oferta | None:
    """1 categoria (nível 1) por story, entre as NUMERO_STORIES_OFERTAS_POR_DIA
    categorias mais vendidas - nunca repete categoria já usada hoje, nem produto (por
    nome) já usado nos últimos DIAS_SEM_REPETIR_OFERTA dias. Retorna None quando já
    bateu o número de stories do dia ou não sobra oferta disponível nas categorias
    candidatas."""
    ja_hoje = RegistroPublicacao.objects.filter(
        data=data, conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
    ).exclude(status=RegistroPublicacao.STATUS_ERRO)

    if ja_hoje.count() >= NUMERO_STORIES_OFERTAS_POR_DIA:
        return None

    # Categoria só não repete no mesmo dia (categorias são poucas - se valesse pra
    # semana inteira, esgotava as candidatas logo no 2º dia). Produto não repete numa
    # janela maior, é o que evita a mesma oferta voltando quase todo dia.
    categorias_usadas = set(
        ja_hoje.exclude(oferta_categoria_id__isnull=True).values_list("oferta_categoria_id", flat=True)
    )
    ja_na_semana = RegistroPublicacao.objects.filter(
        data__gte=data - timedelta(days=DIAS_SEM_REPETIR_OFERTA),
        data__lte=data,
        conteudo_tipo=RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
    ).exclude(status=RegistroPublicacao.STATUS_ERRO)
    nomes_usados = {
        ofertas_services.normalizar_nome_produto(nome)
        for nome in ja_na_semana.exclude(oferta_nome="").values_list("oferta_nome", flat=True)
    }

    categorias_candidatas = [
        categoria["categoria_id"]
        for categoria in ofertas_services.categorias_mais_vendidas(NUMERO_STORIES_OFERTAS_POR_DIA)
        if categoria["categoria_id"] not in categorias_usadas
    ]

    for categoria_id in categorias_candidatas:
        for oferta in Oferta.objects.filter(categoria_id=categoria_id):
            if ofertas_services.normalizar_nome_produto(oferta.nome) not in nomes_usados:
                return oferta
    return None


def _publicar_story_de_oferta(oferta: Oferta, data, request) -> RegistroPublicacao:
    """Gera a arte e publica (ou simula/aguarda aprovação) o story de UMA oferta já
    escolhida - reaproveitado tanto pela escolha automática quanto pela manual
    (publicar_story_oferta_especifica)."""
    imagem = gerar_imagem_oferta_story(oferta)
    nome_exibido = oferta.nome_curto or oferta.nome
    legenda = f"{nome_exibido} — cashback garantido na cash-b. Link na bio pra ver essa e outras ofertas. 🛍️💸"

    registro = _publicar_ou_simular(
        imagem, legenda, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_OFERTA_DIARIA,
        data, request, story=True,
    )
    registro.oferta_categoria_id = oferta.categoria_id
    registro.oferta_item_id = oferta.item_id
    registro.oferta_nome = oferta.nome
    registro.save(update_fields=["oferta_categoria_id", "oferta_item_id", "oferta_nome"])
    return registro


def publicar_story_oferta_do_momento(data, request) -> RegistroPublicacao | None:
    """Chamado várias vezes ao dia (não é a tarefa diária única) - posta no máximo 1
    story de oferta por chamada. Ver NUMERO_STORIES_OFERTAS_POR_DIA."""
    if data.weekday() not in conteudo.DIAS_COM_STORIES_DE_OFERTA:
        return None

    oferta = _escolher_oferta_do_momento(data)
    if not oferta:
        return None

    return _publicar_story_de_oferta(oferta, data, request)


def publicar_story_oferta_especifica(url_produto: str, request) -> RegistroPublicacao:
    """Posta um story pra UM produto escolhido na mão (fora do calendário automático) -
    ver ofertas/services.py, buscar_oferta_por_link. Chamado pelo management command
    postar_oferta_especifica (rodado pelo Shell do Render). De propósito usa o mesmo
    CONTEUDO_OFERTA_DIARIA dos stories automáticos: conta pro limite diário
    (NUMERO_STORIES_OFERTAS_POR_DIA) e entra na janela de DIAS_SEM_REPETIR_OFERTA dias -
    mantém o cuidado de não "bombardear" o perfil de oferta, mesmo pra posts manuais."""
    oferta = ofertas_services.buscar_oferta_por_link(url_produto)
    return _publicar_story_de_oferta(oferta, timezone.localdate(), request)


def publicar_story_oferta_curada(oferta_curada, request) -> RegistroPublicacao:
    """Posta um story pra uma oferta cadastrada à mão no admin (OfertaManual ou
    OfertaDestaqueManual - ver ofertas/models.py, _OfertaCuradaBase) - botão "Criar
    story" em ofertas/admin.py. Ao contrário de publicar_story_oferta_especifica, não
    busca dado nenhum na Shopee: usa exatamente o que foi digitado no admin (preço,
    desconto, comissão), pra bater com o que já está publicado no site pra essa mesma
    oferta. Mesmo CONTEUDO_OFERTA_DIARIA das outras formas de publicar story de oferta -
    mesmo motivo (ver publicar_story_oferta_especifica)."""
    return _publicar_story_de_oferta(oferta_curada, timezone.localdate(), request)


def publicar_story_dica(data, request) -> RegistroPublicacao:
    texto = conteudo.escolher_dica(data)
    imagem = gerar_imagem_texto_simples(
        texto, bg=CORES["highlight"], cor_texto=CORES["ink"], tamanho=(1080, 1920),
    )
    return _publicar_ou_simular(
        imagem, texto, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_DICA,
        data, request, story=True,
    )


def publicar_story_lembrete(data, request) -> RegistroPublicacao:
    texto = conteudo.escolher_lembrete(data)
    imagem = gerar_imagem_texto_simples(
        texto, bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"], tamanho=(1080, 1920),
    )
    return _publicar_ou_simular(
        imagem, texto, RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_LEMBRETE,
        data, request, story=True,
    )


def publicar_post_institucional(data, request) -> RegistroPublicacao:
    post = conteudo.escolher_post_institucional(data)
    if post["estilo"] == "brand":
        imagem = gerar_imagem_texto_simples(
            post["texto"], bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"],
        )
    else:
        imagem = gerar_imagem_texto_simples(post["texto"], bg=CORES["highlight"], cor_texto=CORES["ink"])
    return _publicar_ou_simular(
        imagem, post["legenda"], RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_INSTITUCIONAL,
        data, request, story=False,
    )


def publicar_post_ofertas_semana(data, request) -> RegistroPublicacao | None:
    """Carrossel com uma capa + 8 ofertas (uma por slide) - carrossel tende a gerar mais
    salvamentos que um post único, o que ajuda o alcance pra quem ainda não segue."""
    ofertas = ofertas_services.selecionar_top_ofertas_sem_duplicar(8)
    if not ofertas:
        logger.warning("[instagram_bot] sem ofertas sincronizadas, pulando post semanal")
        return None
    # Sem emoji aqui: as fontes da marca não têm esses glifos, e o Pillow simplesmente
    # some com o caractere sem erro nenhum - o emoji fica só na legenda (o Instagram
    # renderiza a legenda com a fonte dele, aí sim com suporte a emoji).
    capa = gerar_imagem_texto_simples(
        "Top da semana na cash-b", bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"],
    )
    slides = [
        gerar_imagem_oferta_carrossel(oferta, indice, len(ofertas))
        for indice, oferta in enumerate(ofertas, start=1)
    ]
    legenda = (
        "As ofertas em destaque essa semana na cash-b — cashback garantido em cada uma. "
        "Link na bio pra ver todas. 🔥\n#cashback #shopee #ofertas"
    )
    return _publicar_ou_simular_carrossel(
        [capa, *slides], legenda, RegistroPublicacao.TIPO_FEED, RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA,
        data, request,
    )


def publicar_combo_de_stories(data, request) -> list[RegistroPublicacao]:
    """Publica a sequência do dia: capa, a melhor oferta em % (com a conta em R$ dela),
    a melhor oferta em R$, e por fim como achar as duas na vitrine.

    É o único despachante que devolve mais de um registro - os cinco stories são um
    conteúdo só, e é por isso que _ja_processado_hoje continua bloqueando o dia inteiro
    com um único conteudo_tipo: ou o combo sai completo, ou não sai.

    Devolve lista vazia quando não há catálogo, pra não publicar um story anunciando
    "0%" de cashback (ver conteudo.combo_de_stories_do_dia)."""
    combo = conteudo.combo_de_stories_do_dia()
    if not combo:
        return []

    construtores = {
        "capa": lambda s: gerar_imagem_texto_simples(
            s["titulo"], bg=CORES["brand"], cor_texto=CORES["paper"], cor_acento=CORES["highlight"],
            tamanho=(1080, 1920),
        ),
        "numero_com_produto": lambda s: gerar_imagem_numero_com_produto(
            s["numero"], s["rotulo"], s["apoio"], s["imagem_url"],
            legenda_produto=s["legenda_produto"],
        ),
        "conta": lambda s: gerar_imagem_conta(
            s["titulo"], s["linhas"], s["destaque"], s["rodape"], tamanho=(1080, 1920),
        ),
        "passos": lambda s: gerar_imagem_passos(
            s["titulo"], s["passos"], s["rodape"], link_bio=s.get("link_bio", False),
        ),
    }

    registros = []
    for indice, story in enumerate(combo, start=1):
        imagem = construtores[story["formato"]](story)
        registros.append(_publicar_ou_simular(
            imagem, story.get("apoio") or story["titulo"],
            RegistroPublicacao.TIPO_STORY, RegistroPublicacao.CONTEUDO_COMBO_DIARIO,
            data, request, story=True, posicao=(indice, len(combo)),
        ))
    return registros


DESPACHANTES = {
    RegistroPublicacao.CONTEUDO_DICA: publicar_story_dica,
    RegistroPublicacao.CONTEUDO_LEMBRETE: publicar_story_lembrete,
    RegistroPublicacao.CONTEUDO_INSTITUCIONAL: publicar_post_institucional,
    RegistroPublicacao.CONTEUDO_OFERTAS_SEMANA: publicar_post_ofertas_semana,
    RegistroPublicacao.CONTEUDO_COMBO_DIARIO: publicar_combo_de_stories,
}


def executar_publicacoes_do_dia(request) -> list[dict]:
    """Chamado a partir da tarefa diária (ver cashback_shopee/views.py). Decide o que
    precisa ser publicado hoje conforme o calendário e publica (ou simula, se
    INSTAGRAM_BOT_ATIVO=False)."""
    hoje = timezone.localdate()
    resultados = []

    for tipo in conteudo.tipo_de_conteudo_do_dia(hoje):
        if _ja_processado_hoje(hoje, tipo):
            continue
        despachante = DESPACHANTES[tipo]
        # o combo diário devolve os 5 stories de uma vez; os outros, um registro só
        retorno = despachante(hoje, request)
        registros = retorno if isinstance(retorno, list) else [retorno] if retorno else []
        for registro in registros:
            resultados.append({
                "conteudo_tipo": registro.conteudo_tipo,
                "status": registro.status,
                "simulado": registro.modo_simulacao,
            })

    return resultados


def _reconverter_para_jpeg(url: str, request) -> str:
    """Se a URL já for .jpg (gerada depois da correção do formato), não mexe. Senão
    (arte antiga, salva em PNG antes da correção), lê o arquivo do disco e reconverte.

    Importante: lê do disco em vez de baixar a própria URL pública via HTTP - com só
    1 worker do gunicorn, a requisição feita de dentro de uma requisição em andamento
    fica esperando o próprio processo (que está ocupado) responder, e nunca sai do
    lugar (timeout)."""
    if url.lower().endswith((".jpg", ".jpeg")):
        return url
    nome_arquivo = url.rsplit("/", 1)[-1]
    imagem = Image.open(PASTA_MEDIA_BOT / nome_arquivo).convert("RGB")
    return _salvar_e_montar_url(imagem, request)


def tentar_publicar_de_novo(registro: RegistroPublicacao, request) -> None:
    """Reprocessa um registro que falhou (ex: erro 500 "Only photo or video can be
    accepted" por causa da arte antiga em PNG) - converte a(s) imagem(ns) pra JPEG e
    tenta publicar de novo. Chamado pela ação "Tentar publicar de novo" no Admin.

    Salva a URL já convertida ANTES de chamar a API (não só depois de dar certo) -
    assim, se falhar de novo, dá pra ver no Admin exatamente qual URL foi tentada
    (pra testar ela mesma no Depurador de Compartilhamento da Meta, por exemplo)."""
    if registro.imagem_urls:
        urls_convertidas = [_reconverter_para_jpeg(url, request) for url in registro.imagem_urls.splitlines()]
        registro.imagem_urls = "\n".join(urls_convertidas)
        registro.save(update_fields=["imagem_urls"])
        media_id = instagram_client.publicar_carrossel(urls_convertidas, legenda=registro.legenda)
    else:
        url_convertida = _reconverter_para_jpeg(registro.imagem_url, request)
        registro.imagem_url = url_convertida
        registro.save(update_fields=["imagem_url"])
        story = registro.tipo == RegistroPublicacao.TIPO_STORY
        media_id = instagram_client.publicar_imagem(url_convertida, legenda=registro.legenda, story=story)

    registro.status = RegistroPublicacao.STATUS_PUBLICADO
    registro.sucesso = True
    registro.erro = ""
    registro.instagram_media_id = media_id
    registro.save(update_fields=["status", "sucesso", "erro", "instagram_media_id", "imagem_url", "imagem_urls"])
