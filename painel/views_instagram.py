"""Instagram no painel: a conexão da conta (vale para o Estúdio Instagram e para as Automações), as
Automações do Instagram (módulo próprio: Standard responde comentários; Premium também stories e
DMs) e a publicação dos posts do Estúdio.

Até o lançamento (settings.APPFILIADO_LANCAMENTO_INSTAGRAM), só para a conta com a chave de teste
ligada; as outras recebem 404. As regras ficam em instagram_painel/ (conexao.py, webhook.py e publicar.py)."""

import json
import re
import secrets
import unicodedata

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from anuncios import servico as servico_anuncios
from anuncios.models import ConexaoMeta
from estudio.models import PostInstagram
from instagram_painel import api, conexao
from instagram_painel import publicar as P
from instagram_painel.models import AnuncioVisto, Automacao, ContaInstagram, Disparo, ImagemPublicacao, Publicacao
from instagram_painel.webhook import conferir_os_antigos, ligadas, na_fila, palavras, respondidas_no_mes, valendo
from licencas import planos as planos_do_app

from . import conversor
from . import modulos as mod
from .views import _contexto
from .views_estudio import SLUG, _beta, exige

SLUG_AUTOMACOES = "automacoes_instagram"
_automacoes = exige(SLUG_AUTOMACOES)
_conexao = exige(SLUG_AUTOMACOES, SLUG)  # conectar o Instagram: serve a quem tem qualquer um dos dois
SESSAO_STATE = "instagram_state"
SESSAO_JANELA = "instagram_janela"  # o login abriu numa janela à parte: a volta fecha a janela
MAX_AUTOMACOES = 500  # trava de segurança; o Premium não tem limite de automações ligadas


def _retorno_url() -> str:
    # Tem de ser igual ao cadastrado no app da Meta: monta pelo endereço fixo do painel.
    return settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_instagram_retorno")


def _ig(conta) -> ContaInstagram | None:
    return ContaInstagram.objects.filter(conta=conta).first()


def _ig_id(conta) -> str:
    ig = _ig(conta)
    return ig.ig_id if ig else ""


def _tem_automacoes(conta) -> bool:
    return mod.estado(mod.POR_SLUG[SLUG_AUTOMACOES], conta.modulos_liberados()) == "liberado"


def _pagina_da_conexao(conta) -> str:
    """Onde fica o cartão do Instagram conectado: nas Automações ou, só com o Estúdio, nas Publicações."""
    return reverse("painel_estudio_automacoes" if _tem_automacoes(conta) else "painel_estudio_publicacoes")


MOSTRAR_PALAVRAS = 4  # no cartão da lista; o resto vira "+2"


def _quando(a: Automacao) -> str:
    """O gatilho e onde ele vale, numa frase curta para o cartão da lista."""
    if a.gatilho == Automacao.DIRETO:
        return "Mandou DM com a palavra"
    if a.gatilho == Automacao.STORY:
        return "Respondeu o anúncio" if a.e_anuncio else "Respondeu este story" if a.midia_id else "Respondeu qualquer story"
    return "Comentou no anúncio" if a.e_anuncio else "Comentou neste post" if a.midia_id else "Comentou em qualquer post"


@_automacoes
def automacoes(request, conta):
    plano, ig = planos_do_app.automacoes(conta), _ig(conta)
    ig_id = ig.ig_id if ig else ""
    valem = set(valendo(conta, ig_id, plano).values_list("pk", flat=True))
    lista = []
    for a in Automacao.objects.filter(conta=conta):
        total = a.disparos.count()
        outra = bool(a.ig_id and a.ig_id != ig_id)
        fora = (f"Parada: é do @{a.ig_username}, que não está conectado." if outra
                else "Parada: responder stories e DMs é do plano Premium." if a.gatilho not in plano["gatilhos"]
                else f"Parada: no Standard valem só as {plano['ativas']} ligadas mais recentes." if a.ativa and a.pk not in valem else "")
        todas = [p.upper() for p in palavras(a)]
        lista.append({"a": a, "total": total, "dms": a.disparos.filter(dm_ok=True).count(), "outra_conta": outra,
                      "palavras": todas[:MOSTRAR_PALAVRAS], "mais_palavras": max(0, len(todas) - MOSTRAR_PALAVRAS),
                      "quando": _quando(a), "fora_do_plano": fora})
    lista.sort(key=lambda item: item["outra_conta"])  # as do Instagram conectado primeiro
    return render(request, "painel/estudio_automacoes.html", _contexto(
        request, SLUG_AUTOMACOES, ig=_ig(conta), plano=plano, lista=lista, respondidas=respondidas_no_mes(conta),
        ligadas=ligadas(conta, ig_id).count(),
        fila=na_fila(conta), configurado=bool(api.app_id() and api.app_secret()),
    ))


@_conexao
def conectar(request, conta):
    if not (api.app_id() and api.app_secret()):
        messages.error(request, "A conexão com o Instagram ainda não está configurada.")
        return redirect(_pagina_da_conexao(conta))
    state = secrets.token_urlsafe(24)
    request.session[SESSAO_STATE] = state
    # "1": volta para a página do cartão do Instagram; "ficar": só fecha a janela (o editor confere sozinho).
    janela = request.GET.get("janela")
    request.session[SESSAO_JANELA] = janela if janela in ("1", "ficar") else ""
    return redirect(api.url_de_autorizacao(_retorno_url(), state))


def _voltar(request, conta):
    """Fim do login: na janela à parte, avisa a página do Appfiliado e fecha; senão, volta para ela."""
    janela = request.session.pop(SESSAO_JANELA, "")
    if janela:
        return render(request, "painel/instagram_retorno.html",
                      {"destino": _pagina_da_conexao(conta), "ficar": janela == "ficar"})
    return redirect(_pagina_da_conexao(conta))


@_conexao
def retorno(request, conta):
    state = request.session.pop(SESSAO_STATE, None)
    if request.GET.get("error"):
        messages.info(request, "A conexão com o Instagram foi cancelada.")
        return _voltar(request, conta)
    if not state or not secrets.compare_digest(state, request.GET.get("state", "")) or not request.GET.get("code"):
        messages.error(request, "Não deu para confirmar a conexão. Tente conectar de novo.")
        return _voltar(request, conta)
    codigo = request.GET["code"].split("#")[0]
    try:
        ig = conexao.conectar(conta, codigo, _retorno_url())
    except conexao.ErroConexao as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Instagram @{ig.username} conectado.")
    return _voltar(request, conta)


@require_POST
@_conexao
def desconectar(request, conta):
    conexao.desconectar(conta)
    messages.info(request, "Instagram desconectado. As automações e as publicações agendadas ficam paradas até conectar de novo.")
    voltar = request.POST.get("voltar", "")
    if voltar and url_has_allowed_host_and_scheme(voltar, allowed_hosts=None) and voltar.startswith("/"):
        return redirect(voltar)
    return redirect(_pagina_da_conexao(conta))


@_automacoes
def midias(request, conta):
    """Posts, stories no ar ou anúncios (de onde já chegou resposta) do Instagram conectado, para escolher na automação."""
    ig = _ig(conta)
    if not ig:
        return JsonResponse({"erro": "Conecte o seu Instagram primeiro."}, status=400)
    if request.GET.get("tipo") == "anuncio":
        return JsonResponse(_lista_de_anuncios(conta, ig, request.GET.get("gatilho", "")))
    try:
        itens = api.stories_no_ar(ig.token) if request.GET.get("tipo") == "story" else api.posts_recentes(ig.token)
    except api.ErroInstagram as erro:
        return JsonResponse({"erro": f"O Instagram não respondeu ({erro})."}, status=502)
    return JsonResponse({"itens": [{
        "id": m.get("id"), "link": m.get("permalink", ""), "legenda": (m.get("caption") or "")[:120],
        "imagem": m.get("thumbnail_url") or m.get("media_url") or "", "data": m.get("timestamp", ""),
    } for m in itens]})


def _anuncio_na_lista(v: AnuncioVisto) -> dict:
    """Um item da opção "Um anúncio". A resposta a um anúncio de reels que também roda nos stories chega só
    como resposta a um story que não é do perfil (sem o ID do anúncio), igual à resposta a um story seu que
    já saiu do ar: a hora da última resposta ajuda a achar o anúncio (responda de outra conta e veja qual
    item subiu para o topo)."""
    comentario = v.origem == AnuncioVisto.COMENTARIO
    nome = v.titulo or ("Anúncio " + v.anuncio_id if v.anuncio_id else "Anúncio sem legenda" if comentario else "Story que não está no seu perfil")
    respostas = f"{v.respostas} " + ("comentário" if comentario else "resposta") + ("s" if v.respostas != 1 else "")
    quando = timezone.localtime(v.ultima_em)
    dia = "hoje" if quando.date() == timezone.localdate() else quando.strftime("%d/%m")
    ultima = f"última {dia} às {quando:%H:%M}" + (f": \"{v.ultimo_texto[:40]}\"" if v.ultimo_texto else "")
    return {"id": v.chave, "link": "", "legenda": nome[:120], "imagem": v.imagem, "data": v.ultima_em.isoformat(),
            "detalhe": f"{respostas} · {ultima}"}


def _lista_de_anuncios(conta, ig, gatilho: str) -> dict:
    """A opção "Um anúncio": os anúncios de onde já chegou comentário (ou resposta a story) e, com a conta de
    anúncios conectada (Campanhas da Meta), os anúncios dela, com o nome e a foto, antes de qualquer comentário.

    Nos comentários, o anúncio da Meta é a mídia dele no Instagram (post:<effective_instagram_media_id>). Nas
    respostas a story, a Meta só dá nome ao item quando o story respondido é essa mesma mídia."""
    origem = AnuncioVisto.COMENTARIO if gatilho == Automacao.COMENTARIO else AnuncioVisto.MENSAGEM
    # os antigos (sem foto, ou com a foto já vencida) são conferidos de novo no Instagram, poucos por vez;
    # os que forem stories do perfil saem da lista
    conferir_os_antigos(ig, list(AnuncioVisto.objects.filter(ig_id=ig.ig_id, origem=origem, do_perfil=False)[:60]))
    vistos = list(AnuncioVisto.objects.filter(ig_id=ig.ig_id, origem=origem, do_perfil=False)[:60])
    da_meta, erro = servico_anuncios.anuncios_com_instagram(conta)
    por_midia = {a["midia_id"]: a for a in da_meta}
    itens = []
    for v in vistos:
        item, anuncio = _anuncio_na_lista(v), por_midia.get(v.post_id if origem == AnuncioVisto.COMENTARIO else v.story_id)
        if anuncio:
            item["legenda"] = anuncio["nome"] or item["legenda"]
            item["imagem"] = item["imagem"] or anuncio["imagem"]
            item["detalhe"] = f"{_situacao(anuncio)} · {item['detalhe']}"
        itens.append(item)
    if origem == AnuncioVisto.COMENTARIO:  # os da Meta que ainda não tiveram comentário
        ja = {v.post_id for v in vistos}
        itens += [{"id": f"post:{a['midia_id']}", "link": a["link"], "legenda": a["nome"] or "Anúncio sem nome", "imagem": a["imagem"],
                   "data": "", "detalhe": f"{_situacao(a)} · nenhum comentário ainda"} for a in da_meta if a["midia_id"] not in ja]
    conectada = ConexaoMeta.objects.filter(conta=conta).exists()
    return {"itens": itens, "meta": {
        "conectada": conectada, "erro": erro,
        "pode_conectar": not conectada and servico_anuncios.liberado(conta),
        "url": reverse("painel_campanhas_meta") if servico_anuncios.liberado(conta) else "",
    }}


def _situacao(anuncio: dict) -> str:
    return "Ativo" if anuncio["situacao"] == "ACTIVE" else "Pausado" if "PAUSED" in anuncio["situacao"] else "Anúncio"


def anuncio_escolhido(midia_id: str) -> bool:
    """A automação está presa a um anúncio (e não a um post ou story do perfil)."""
    return midia_id.startswith(("ad:", "post:", "story:"))


def anuncio_cabe(gatilho: str, midia_id: str) -> bool:
    """No comentário, só a mídia comentada (post:); na resposta a story, qualquer jeito de achar o anúncio."""
    if gatilho == Automacao.COMENTARIO:
        return midia_id.startswith("post:")
    return gatilho == Automacao.STORY


class AutomacaoForm(forms.ModelForm):
    class Meta:
        model = Automacao
        fields = ["nome", "gatilho", "midia_id", "midia_link", "midia_imagem", "midia_legenda", "palavras",
                  "responder_comentario", "respostas", "enviar_dm", "texto_dm", "link", "botoes", "texto_botao", "sub_id", "ativa"]
        widgets = {f: forms.HiddenInput for f in ("midia_id", "midia_link", "midia_imagem", "midia_legenda", "botoes")}

    def __init__(self, *args, conta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.conta = conta
        self.plano = planos_do_app.automacoes(conta) if conta else planos_do_app.AUTOMACOES[True]
        self.gatilhos = self.plano["gatilhos"]
        self.antes = (self.instance.link, self.instance.sub_id, self.instance.ativa) if self.instance.pk else ("", "", False)
        self.extras_antes = list(self.instance.botoes_extras or []) if self.instance.pk else []
        self.fields["botoes"].required = False  # fora do Premium o contador vem travado (não é enviado)
        self._extras = None

    def extras_na_tela(self) -> list[dict]:
        """O 2º e o 3º botão como aparecem no formulário (o que a pessoa mandou, ou o que está salvo)."""
        if self.is_bound:
            return [{"texto": self.data.get(f"texto_botao_{n}", ""), "link": self.data.get(f"link_botao_{n}", "")} for n in (2, 3)]
        return [{"texto": "", "link": "", **(self.extras_antes[i] if i < len(self.extras_antes) else {})} for i in range(2)]

    def quantos_botoes(self) -> int:
        """O número no contador: fora do Premium, 0 (o link vai no texto)."""
        if not self.plano["botao"]:
            return 0
        if self.is_bound:  # sem o contador no envio: 1 botão se tem link
            valor = self.data.get("botoes", 1 if (self.data.get("link") or "").strip() else 0)
        else:
            valor = self.initial.get("botoes", self.instance.botoes)
        try:
            return max(0, min(Automacao.MAXIMO_BOTOES, int(valor)))
        except (TypeError, ValueError):
            return 1

    def _ler_botoes(self, d) -> None:
        """Premium: quantos botões (0 a 3) e o texto e o link de cada um. O 1º abre o link principal."""
        quantos = self.quantos_botoes()
        d["botoes"] = quantos
        if quantos >= 1:
            d["texto_botao"] = (d.get("texto_botao") or "").strip() or "Ver produto"
            if not d.get("link") and "link" not in self.errors:
                self.add_error("link", "Coloque o link do botão 1 (ou deixe 0 botões: aí a DM vai sem link).")
        validar = URLValidator(schemes=["http", "https"])
        self._extras = []
        for numero in (2, 3):
            texto = " ".join(str(self.data.get(f"texto_botao_{numero}") or "").split())
            link = str(self.data.get(f"link_botao_{numero}") or "").strip()
            if quantos >= numero:
                if not texto:
                    self.add_error("botoes", f"Botão {numero}: escreva o texto.")
                elif len(texto) > 20:
                    self.add_error("botoes", f"Botão {numero}: o texto vai até 20 caracteres.")
                try:
                    validar(link)
                except forms.ValidationError:
                    self.add_error("botoes", f"Botão {numero}: coloque um link completo, começando com https://")
            self._extras.append({"texto": texto[:20], "link": link[:600], "link_afiliado": ""})

    def clean_sub_id(self):
        sub_id = (self.cleaned_data.get("sub_id") or "").strip()
        if sub_id and not re.fullmatch(r"[A-Za-z0-9]{1,50}", sub_id):
            raise forms.ValidationError("O Sub ID só pode ter letras e números (sem espaço, hífen ou acento).")
        return sub_id

    def clean(self):
        d = super().clean()
        if self.plano["botao"]:
            self._ler_botoes(d)
        else:  # fica o que estava (no Standard, o link vai no texto)
            d["botoes"] = self.instance.botoes if self.instance.pk else 1
        if not self.plano["sub_id"]:
            d["sub_id"] = self.instance.sub_id
        if self.plano["ativas"] and d.get("ativa") and not self.antes[2]:
            outras = ligadas(self.conta, _ig_id(self.conta)).exclude(pk=self.instance.pk).count()
            if outras >= self.plano["ativas"]:
                self.add_error("ativa", f"No plano Standard ficam até {self.plano['ativas']} automações ligadas ao mesmo tempo. "
                                        "Pause outra ou salve esta desligada. No Premium não há limite.")
        gatilho = d.get("gatilho")
        if gatilho and gatilho not in self.gatilhos:
            self.add_error("gatilho", "Responder stories e DMs é do plano Premium das Automações.")
        if gatilho == Automacao.DIRETO and not (d.get("palavras") or "").strip():
            self.add_error("palavras", "Para DM, escolha pelo menos uma palavra (senão a automação responderia toda DM).")
        if gatilho != Automacao.COMENTARIO:
            d["responder_comentario"] = False
        if not d.get("responder_comentario") and not d.get("enviar_dm"):
            raise forms.ValidationError("Escolha pelo menos uma resposta: a do comentário ou a DM.")
        if d.get("responder_comentario") and not (d.get("respostas") or "").strip():
            self.add_error("respostas", "Escreva pelo menos uma resposta para o comentário.")
        if d.get("enviar_dm") and not (d.get("texto_dm") or "").strip():
            self.add_error("texto_dm", "Escreva o texto da DM.")
        if gatilho == Automacao.STORY and (colado := re.sub(r"\D", "", str(self.data.get("anuncio_colado") or ""))):
            if len(colado) < 6:
                self.add_error(None, "O ID do anúncio tem só números e é bem comprido (copie do Gerenciador de Anúncios).")
            else:  # o ID do anúncio colado à mão vale mais que um escolhido na lista
                visto = AnuncioVisto.objects.filter(ig_id=_ig_id(self.conta), chave=f"ad:{colado}").first()
                d["midia_id"], d["midia_link"] = f"ad:{colado}"[:64], ""
                d["midia_imagem"] = visto.imagem if visto else ""
                d["midia_legenda"] = (visto.titulo if visto and visto.titulo else f"Anúncio {colado}")[:190]
        if anuncio_escolhido(d.get("midia_id") or "") and not anuncio_cabe(gatilho, d.get("midia_id") or ""):
            d["midia_id"] = d["midia_link"] = d["midia_imagem"] = d["midia_legenda"] = ""
        for campo in ("midia_link", "midia_imagem"):
            if d.get(campo) and not str(d[campo]).startswith("https://"):
                d[campo] = ""
        if not self.errors:
            self._link_com_sub_id(d)
        return d

    def _link_com_sub_id(self, d):
        """Premium: gera o link de afiliado de novo com o Sub ID da automação, no link principal e no de cada
        botão (só quando o link ou o Sub ID mudam). Link de fora da Shopee vai como está."""
        sub_id = d.get("sub_id") or ""
        self.instance.link_afiliado = self._com_sub_id(d.get("link") or "", sub_id, self.antes[0], self.instance.link_afiliado)
        if self._extras is None:
            return
        for i, extra in enumerate(self._extras):
            if i + 2 > d.get("botoes", 0):
                continue  # botão que não vai: guarda o texto e o link, gera o link quando voltar
            antes = self.extras_antes[i] if i < len(self.extras_antes) else {}
            extra["link_afiliado"] = self._com_sub_id(extra["link"], sub_id, antes.get("link", ""), antes.get("link_afiliado", ""))
        self.instance.botoes_extras = self._extras

    def _com_sub_id(self, link: str, sub_id: str, link_antes: str, afiliado_antes: str) -> str:
        if not sub_id or not link or not conversor.tem_link_da_shopee(link):
            return ""
        if (link, sub_id) == (link_antes, self.antes[1]) and afiliado_antes:
            return afiliado_antes
        try:
            feito = conversor.converter(self.conta, link, conversor.MODO_LINKS, sub_id, ferramenta="instagram")
        except conversor.ErroConversor as erro:
            self.add_error("sub_id", f"Não consegui gerar o link com esse Sub ID: {erro}")
            return ""
        return feito["texto"].splitlines()[0]


def _sub_id_sugerido(nome: str) -> str:
    """"Garrafa térmica (QUERO)" -> "garrafatermica"."""
    sem_acento = unicodedata.normalize("NFD", nome or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower().split("(")[0])[:30]


def _form_contexto(request, conta, form, automacao=None):
    plano = planos_do_app.automacoes(conta)
    gatilhos = [{"valor": v, "nome": n, "livre": v in plano["gatilhos"]} for v, n in Automacao.GATILHOS]
    return _contexto(request, SLUG_AUTOMACOES, form=form, automacao=automacao, ig=_ig(conta), gatilhos=gatilhos, plano=plano,
                     disparos=automacao.disparos.all()[:8] if automacao else [])  # o resto fica no Histórico


@_automacoes
def automacao_nova(request, conta):
    if request.method == "POST":
        form = AutomacaoForm(request.POST, conta=conta)
        ig = _ig(conta)
        if not ig:
            form.add_error(None, "Conecte o seu Instagram antes de criar a automação.")
        elif Automacao.objects.filter(conta=conta).count() >= MAX_AUTOMACOES:
            form.add_error(None, f"Você chegou a {MAX_AUTOMACOES} automações. Exclua alguma para criar outra.")
        elif form.is_valid():
            a = form.save(commit=False)
            a.conta, a.ig_id, a.ig_username = conta, ig.ig_id, ig.username
            post = PostInstagram.objects.filter(conta=conta, pk=request.POST.get("post") or 0).first()
            a.post_estudio = post
            a.save()
            messages.success(request, f"Automação \"{a.nome}\" criada.")
            return redirect("painel_estudio_automacoes")
    else:
        inicial = {"gatilho": Automacao.COMENTARIO, "palavras": "QUERO", "ativa": True,
                   "respostas": "Te mandei na DM! 📩\nEnviei o link na sua DM 😉\nCorre na DM que já te mandei!",
                   "texto_dm": "Oi! Aqui está o link que você pediu:"}
        post = PostInstagram.objects.filter(conta=conta, pk=request.GET.get("post") or 0).first()
        if post:
            inicial.update(nome=post.nome[:100], link=(post.produto or {}).get("link", ""))
            if (post.produto or {}).get("nome"):
                inicial["texto_dm"] = f"Oi! Aqui está o link do {post.produto['nome'][:80]}:"
            if planos_do_app.automacoes(conta)["sub_id"]:
                inicial["sub_id"] = _sub_id_sugerido(post.nome)
        plano = planos_do_app.automacoes(conta)
        if plano["ativas"] and ligadas(conta, _ig_id(conta)).count() >= plano["ativas"]:
            inicial["ativa"] = False  # Standard com todas as vagas ocupadas: nasce desligada
        form = AutomacaoForm(initial=inicial, conta=conta)
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form) | {
        "post_id": request.GET.get("post") or request.POST.get("post") or ""})


@_automacoes
def automacao(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    form = AutomacaoForm(request.POST or None, instance=a, conta=conta)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Automação \"{a.nome}\" salva.")
        return redirect("painel_estudio_automacoes")
    return render(request, "painel/estudio_automacao.html", _form_contexto(request, conta, form, a))


@require_POST
@_automacoes
def automacao_ligar(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    limite = planos_do_app.automacoes(conta)["ativas"]
    if not a.ativa and limite and ligadas(conta, _ig_id(conta)).count() >= limite:
        messages.error(request, f"No plano Standard ficam até {limite} automações ligadas ao mesmo tempo. "
                                "Pause outra para ligar esta. No Premium não há limite.")
    else:
        a.ativa = not a.ativa
        a.save(update_fields=["ativa", "atualizada_em"])
    if request.POST.get("voltar") == "lista":
        return redirect("painel_estudio_automacoes")
    return redirect("painel_estudio_automacao", pk=a.pk)


@require_POST
@_automacoes
def automacao_excluir(request, conta, pk):
    a = get_object_or_404(Automacao, pk=pk, conta=conta)
    a.delete()
    messages.info(request, f"Automação \"{a.nome}\" excluída.")
    return redirect("painel_estudio_automacoes")


@_automacoes
def historico(request, conta):
    """Todas as respostas das automações, das mais novas para as mais antigas."""
    automacoes_ = Automacao.objects.filter(conta=conta).order_by("nome")
    disparos = Disparo.objects.filter(automacao__conta=conta).select_related("automacao")
    escolhida = automacoes_.filter(pk=request.GET.get("automacao") or 0).first()
    if escolhida:
        disparos = disparos.filter(automacao=escolhida)
    pagina = Paginator(disparos, 50).get_page(request.GET.get("pagina"))
    return render(request, "painel/estudio_historico.html", _contexto(
        request, SLUG_AUTOMACOES, pagina=pagina, automacoes=automacoes_, escolhida=escolhida,
        ig=_ig(conta), plano=planos_do_app.automacoes(conta),
        total=disparos.count(), dms=disparos.filter(dm_ok=True).count(), respostas=disparos.filter(resposta_ok=True).count(),
    ))


# --- publicar no Instagram (todos os planos) -----------------------------------------------------

def _publicacao_json(p: Publicacao) -> dict:
    return {"id": p.pk, "tipo": p.get_tipo_display(), "estado": p.estado, "estado_nome": p.get_estado_display(),
            "quando": timezone.localtime(p.publicada_em or p.agendada_para).strftime("%d/%m/%Y %H:%M"),
            "link": p.permalink, "erro": p.erro, "agora": p.agora, "conta": f"@{p.ig_username}" if p.ig_username else "",
            "cancelar": reverse("painel_estudio_publicacao_cancelar", args=[p.pk]) if p.estado == Publicacao.PENDENTE else "",
            "tentar": reverse("painel_estudio_publicacao_tentar", args=[p.pk]) if p.estado == Publicacao.ERRO else ""}


@_beta
def publicar(request, conta, pk):
    """GET: a conta conectada e as publicações deste post. POST: as imagens (JPEG) e quando publicar."""
    post = get_object_or_404(PostInstagram, pk=pk, conta=conta)
    if request.method == "POST":
        try:
            quando = None if request.POST.get("quando") != "agendar" else P.quando_de(request.POST.get("data", ""))
            arquivos = [request.FILES[k] for k in sorted(request.FILES, key=lambda k: int(k.split("_")[-1]) if k.split("_")[-1].isdigit() else 99)
                        if k.startswith("imagem_")]
            pub = P.agendar(post, arquivos, quando)
        except P.ErroPublicacao as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        msg = ("Enviado! O post sai no seu Instagram em instantes." if quando is None
               else f"Agendado para {timezone.localtime(quando).strftime('%d/%m/%Y às %H:%M')}.")
        return JsonResponse({"ok": True, "mensagem": msg, "publicacao": _publicacao_json(pub)})
    ig = _ig(conta)
    return JsonResponse({
        "ig": {"username": ig.username, "foto": ig.foto} if ig else None,
        "conectar": reverse("painel_instagram_conectar") + "?janela=ficar" if api.app_id() and api.app_secret() else "",
        "tipo": P.tipo_do_post(post),
        "publicacoes": [_publicacao_json(p) for p in Publicacao.objects.filter(post=post).exclude(estado=Publicacao.CANCELADA)[:10]],
    })


@_beta
def publicacoes(request, conta):
    """Publicações agendadas e as mais recentes, de todos os posts."""
    agendadas = Publicacao.objects.filter(conta=conta, estado__in=[Publicacao.PENDENTE, Publicacao.PUBLICANDO]).order_by("agendada_para")
    feitas = Publicacao.objects.filter(conta=conta, estado__in=[Publicacao.PUBLICADA, Publicacao.ERRO]).order_by("-agendada_para")
    pagina = Paginator(feitas, 30).get_page(request.GET.get("pagina"))
    return render(request, "painel/estudio_publicacoes.html", _contexto(
        request, SLUG, agendadas=agendadas, pagina=pagina, ig=_ig(conta), configurado=bool(api.app_id() and api.app_secret())))


@require_POST
@_beta
def publicacao_cancelar(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    if P.cancelar(pub):
        msg = "Publicação cancelada."
    else:
        msg = "Essa publicação já saiu ou está saindo agora."
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"mensagem": msg})
    messages.info(request, msg)
    return redirect("painel_estudio_publicacoes")


@require_POST
@_beta
def publicacao_tentar(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    msg = ("Vamos tentar de novo. O post sai em instantes." if P.tentar_de_novo(pub)
           else "Não dá para tentar de novo essa publicação. Publique outra vez pelo editor.")
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"mensagem": msg})
    messages.info(request, msg)
    return redirect("painel_estudio_publicacoes")


@_beta
def publicacao_miniatura(request, conta, pk):
    pub = get_object_or_404(Publicacao, pk=pk, conta=conta)
    if not pub.miniatura:
        raise Http404
    resposta = HttpResponse(bytes(pub.miniatura), content_type="image/jpeg")
    resposta["Cache-Control"] = "private, max-age=86400"
    return resposta


def midia_publica(request, token):
    """A imagem que a Meta baixa para publicar. Sem login: o token secreto é a chave, e só vale
    enquanto a publicação não saiu."""
    if len(token) > 64:
        raise Http404
    imagem = (ImagemPublicacao.objects.filter(token=token, publicacao__estado__in=[Publicacao.PENDENTE, Publicacao.PUBLICANDO])
              .only("dados").first())
    if not imagem:
        raise Http404
    resposta = HttpResponse(bytes(imagem.dados), content_type="image/jpeg")
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


# --- avisos da Meta (sem login: quem chama é a Meta, a segurança é a assinatura) ------------------

@csrf_exempt
@require_POST
def desautorizar(request):
    """A pessoa tirou o Appfiliado do Instagram dela: apaga a conexão."""
    dados = conexao.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    conexao.apagar_por_usuario(str(dados.get("user_id") or ""))
    return HttpResponse("ok")


@csrf_exempt
@require_POST
def apagar_dados(request):
    """Pedido de exclusão de dados (exigido pela Meta): apaga e devolve onde acompanhar."""
    dados = conexao.ler_signed_request(request.POST.get("signed_request", ""))
    if not dados:
        return HttpResponse(status=400)
    conexao.apagar_por_usuario(str(dados.get("user_id") or ""))
    codigo = secrets.token_hex(8)
    url = settings.APPFILIADO_PAINEL_URL.rstrip("/") + reverse("painel_instagram_dados_apagados", args=[codigo])
    return HttpResponse(json.dumps({"url": url, "confirmation_code": codigo}), content_type="application/json")


def dados_apagados(request, codigo):
    if not codigo.isalnum() or len(codigo) > 32:
        raise Http404
    return HttpResponse(f"Pedido {codigo}: os dados do Instagram ligados a esta conta foram apagados do Appfiliado.",
                        content_type="text/plain; charset=utf-8")
