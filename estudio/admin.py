import base64
import binascii
import json
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from PIL import Image

from . import ia
from .marcas import CAMPOS_TEXTO, FORMATOS, LIMITES_LISTA, MARCAS
from .models import ImagemEstudio, ProjetoAppfiliado, ProjetoCashb

MAX_SLIDES = 10
MAX_MINIATURA = 600 * 1024
MAX_IMAGEM = 12 * 1024 * 1024


def _largura_print(nome):
    try:
        with Image.open(Path(settings.BASE_DIR) / "landing" / "static" / "landing" / "prints" / f"{nome}-m.webp") as im:
            return im.width
    except OSError:
        return 840


def _modelos(marca):
    caminho = Path(__file__).parent / "modelos" / f"{marca}.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else []


class _EstudioAdmin(admin.ModelAdmin):
    marca = ""
    list_display = ("ver_miniatura", "nome", "formato", "qtd_slides", "atualizado_em")
    list_display_links = ("ver_miniatura", "nome")
    list_filter = ("formato",)
    search_fields = ("nome", "legenda")
    actions = ["duplicar"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(marca=self.marca)

    @admin.display(description="")
    def ver_miniatura(self, obj):
        if obj.miniatura:
            return format_html('<img src="{}" style="width:72px;border-radius:6px;display:block">', obj.miniatura.url)
        return "—"

    @admin.display(description="Slides")
    def qtd_slides(self, obj):
        return len(obj.slides or [])

    @admin.action(description="Duplicar os posts selecionados")
    def duplicar(self, request, queryset):
        for p in queryset:
            self.model.objects.create(marca=self.marca, formato=p.formato, nome=f"{p.nome} (cópia)"[:120],
                                      slides=p.slides, legenda=p.legenda, criado_por=request.user)
        self.message_user(request, "Cópia criada.", messages.SUCCESS)

    # --- editor ----------------------------------------------------------------------------
    def _nome_url(self, sufixo):
        return f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_{sufixo}"

    def get_urls(self):
        v = self.admin_site.admin_view
        return [
            path("api/salvar/", v(require_POST(self.api_salvar)), name=self._nome_url("salvar")[6:]),
            path("api/ia/", v(require_POST(self.api_ia)), name=self._nome_url("ia")[6:]),
            path("api/imagens/", v(self.api_imagens), name=self._nome_url("imagens")[6:]),
        ] + super().get_urls()

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        m = MARCAS[self.marca]
        projeto = {"id": None, "nome": "Novo post", "formato": m["formato_padrao"], "slides": [], "legenda": ""}
        return self._editor(request, projeto)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if not self.has_change_permission(request):
            raise PermissionDenied
        p = get_object_or_404(self.get_queryset(request), pk=object_id)
        projeto = {"id": p.pk, "nome": p.nome, "formato": p.formato, "slides": p.slides, "legenda": p.legenda}
        return self._editor(request, projeto)

    def _editor(self, request, projeto):
        m = MARCAS[self.marca]
        config = {
            "marca": self.marca, "nome": m["nome"],
            "formatos": {k: {"nome": n, "w": w, "h": h} for k, (n, w, h) in FORMATOS.items()},
            "tipos": {k: {"nome": n, "campos": c} for k, (n, c) in m["tipos"].items()},
            "cores": m["cores"], "artes": m["artes"], "tons": m["tons"], "icones": m["icones"],
            "prints": {p: {"url": static(f"landing/prints/{p}-m.webp"), "w": _largura_print(p)} for p in m["prints"]},
            "fontes": {"dm500": static("estudio/fontes/dmsans-500.ttf"), "dm800": static("estudio/fontes/dmsans-800.ttf"),
                       "familjen": static("fonts/familjen-grotesk.woff2"), "mono": static("fonts/jetbrains-mono.woff2")},
            "urls": {"salvar": reverse(self._nome_url("salvar")), "ia": reverse(self._nome_url("ia")),
                     "imagens": reverse(self._nome_url("imagens")), "lista": reverse(self._nome_url("changelist")),
                     "editar": reverse(self._nome_url("change"), args=[0])},
            "ia_ligada": bool(settings.ANTHROPIC_API_KEY),
            "campos_texto": {k: list(v) for k, v in CAMPOS_TEXTO.items()}, "limites": LIMITES_LISTA,
            "max_slides": MAX_SLIDES,
        }
        contexto = {**self.admin_site.each_context(request), "title": f"Estúdio de posts · {m['nome']}",
                    "opts": self.model._meta, "is_nav_sidebar_enabled": False, "config": config, "projeto": projeto, "modelos": _modelos(self.marca)}
        return TemplateResponse(request, "admin/estudio/editor.html", contexto)

    # --- API do editor ------------------------------------------------------------------------
    def _corpo(self, request):
        try:
            return json.loads(request.body or b"{}")
        except ValueError:
            return {}

    def api_salvar(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        d = self._corpo(request)
        formato = d.get("formato") if d.get("formato") in FORMATOS else MARCAS[self.marca]["formato_padrao"]
        slides = [x for x in (ia.limpar_slide(self.marca, s) for s in (d.get("slides") or [])[:MAX_SLIDES]) if x]
        if d.get("id"):
            p = get_object_or_404(self.get_queryset(request), pk=d["id"])
        else:
            p = self.model(marca=self.marca, criado_por=request.user)
        p.nome = (str(d.get("nome") or "").strip() or "Sem nome")[:120]
        p.formato, p.slides, p.legenda = formato, slides, str(d.get("legenda") or "")[:2200]
        miniatura = str(d.get("miniatura") or "")
        if miniatura.startswith("data:image/jpeg;base64,"):
            try:
                dados = base64.b64decode(miniatura.split(",", 1)[1], validate=True)
            except (binascii.Error, ValueError):
                dados = b""
            if 0 < len(dados) <= MAX_MINIATURA and dados[:3] == b"\xff\xd8\xff":
                if p.miniatura:
                    p.miniatura.delete(save=False)
                p.miniatura.save(f"post-{self.marca}.jpg", ContentFile(dados), save=False)
        p.save()
        return JsonResponse({"id": p.pk, "url": reverse(self._nome_url("change"), args=[p.pk]), "slides": slides})

    def api_ia(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        d = self._corpo(request)
        atual = {"slides": d.get("slides") or [], "legenda": d.get("legenda") or ""} if d.get("ajustar") else None
        try:
            post = ia.gerar(self.marca, d.get("formato") or MARCAS[self.marca]["formato_padrao"], d.get("pedido") or "", atual)
        except ia.ErroIA as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(post)

    def api_imagens(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            arquivo = request.FILES.get("arquivo")
            if not arquivo:
                return JsonResponse({"erro": "Escolha uma imagem."}, status=400)
            if arquivo.size > MAX_IMAGEM:
                return JsonResponse({"erro": "A imagem passa de 12 MB."}, status=400)
            try:
                with Image.open(arquivo) as im:
                    formato = im.format
                    im.verify()
            except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
                formato = None
            if formato not in ("JPEG", "PNG", "WEBP"):
                return JsonResponse({"erro": "Esse arquivo não é uma imagem válida (use JPG, PNG ou WebP)."}, status=400)
            arquivo.seek(0)
            ImagemEstudio.objects.create(marca=self.marca, arquivo=arquivo, nome=arquivo.name[:120])
        imagens = ImagemEstudio.objects.filter(marca=self.marca)[:60]
        return JsonResponse({"imagens": [{"id": i.pk, "url": i.arquivo.url, "nome": i.nome} for i in imagens]})


@admin.register(ProjetoAppfiliado)
class ProjetoAppfiliadoAdmin(_EstudioAdmin):
    marca = "appfiliado"


@admin.register(ProjetoCashb)
class ProjetoCashbAdmin(_EstudioAdmin):
    marca = "cashb"

# ImagemEstudio não tem tela própria no admin: as imagens são enviadas e escolhidas dentro do editor.
