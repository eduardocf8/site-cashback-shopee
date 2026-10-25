from django.conf import settings
from django.contrib import admin

from .models import MetaMensal, RegraSubId, RelatorioEmail, SincronizacaoResultados, VendaItem


@admin.register(SincronizacaoResultados)
class SincronizacaoResultadosAdmin(admin.ModelAdmin):
    list_display = ("conta", "pedido_em", "iniciada_em", "concluida_em", "cobertura_inicio", "tem_erro")
    search_fields = ("conta__email",)
    readonly_fields = ("conta", "pedido_em", "iniciada_em", "concluida_em", "erro", "cobertura_inicio")
    actions = ["pedir_atualizacao"]

    @admin.display(boolean=True, description="Erro")
    def tem_erro(self, obj):
        return bool(obj.erro)

    @admin.action(description="Buscar os números na Shopee de novo")
    def pedir_atualizacao(self, request, queryset):
        from django.utils import timezone

        queryset.update(pedido_em=timezone.now())


@admin.register(MetaMensal)
class MetaMensalAdmin(admin.ModelAdmin):
    list_display = ("conta", "ano", "mes")
    list_filter = ("ano", "mes")
    search_fields = ("conta__email",)


@admin.register(RegraSubId)
class RegraSubIdAdmin(admin.ModelAdmin):
    list_display = ("conta", "operador", "texto", "nome")
    search_fields = ("conta__email", "texto", "nome")


@admin.register(VendaItem)
class VendaItemAdmin(admin.ModelAdmin):
    list_display = ("comprado_em", "conta", "nome", "quantidade", "comissao", "situacao", "sub_id")
    list_filter = ("situacao",)
    search_fields = ("conta__email", "nome", "pedido_id")
    list_select_related = ("conta",)
    readonly_fields = [f.name for f in VendaItem._meta.fields]


@admin.register(RelatorioEmail)
class RelatorioEmailAdmin(admin.ModelAdmin):
    list_display = ("conta", "ativo", "ultimo_envio_dia", "ultimo_erro")
    list_filter = ("ativo",)
    search_fields = ("conta__email",)


# --- E-mails de dicas e sugestões ---------------------------------------------------

from django.contrib import messages  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.urls import path  # noqa: E402

from .models import Sugestao, TextoEmailDica  # noqa: E402

AJUDA_DO_FORMATO = (
    "Formato: parágrafos separados por linha em branco · **negrito** · linha começando com ↳ vira item · "
    "parágrafo começando com \"Dica:\" ou \"Minha dica:\" vira a caixinha · {nome} = primeiro nome · {imagem} = o print · "
    "{botao} = o botão amarelo · {numeros} = os números da pessoa (dia 21) · [texto](destino) vira link "
    "(destinos: planos, automacao, campanhas, mensagens, alerta, resultados, radar, conversor, site, carrosseis, notas, "
    "configuracoes, sugestoes, inicio ou https://...) · linha começando com [bot], [premium], [site], [carrosséis], "
    "[carrosséis premium], [notas], [api] ou [emissor] só aparece para quem tem; [sem ...] para quem não tem."
)


@admin.register(TextoEmailDica)
class TextoEmailDicaAdmin(admin.ModelAdmin):
    """Os e-mails de dicas dos novos assinantes, com prévia e envio de teste (painel/emails_valor.py)."""

    list_display = ("dia", "assunto", "ativo", "atualizado_em")
    list_editable = ("ativo",)
    fields = ("dia", "assunto", "texto", "texto_sem", "ativo")
    readonly_fields = ("dia",)
    change_form_template = "admin/painel/textoemaildica/change_form.html"
    ordering = ("id",)  # na ordem da sequência (criados assim na migração)

    @admin.display(description="Dia")
    def dia(self, obj):
        from .emails_valor import SEQUENCIA

        return next((f"Dia {d}" for c, d in SEQUENCIA if c == obj.chave), "")

    def has_add_permission(self, request):
        return False  # a sequência é fixa; edite os textos

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for campo in ("texto", "texto_sem"):
            if campo in form.base_fields:
                form.base_fields[campo].help_text = AJUDA_DO_FORMATO
                form.base_fields[campo].widget.attrs.update({"rows": 22, "style": "width:100%;font-family:monospace"})
        return form

    def get_urls(self):
        return [
            path("<int:pk>/previa/", self.admin_site.admin_view(self.previa), name="painel_textoemaildica_previa"),
        ] + super().get_urls()

    def previa(self, request, pk):
        """Prévia (ou envio de teste) do que está no formulário, mesmo antes de salvar."""
        from django.utils import timezone

        from licencas.models import ContaAppfiliado

        from . import emails_valor

        if request.method != "POST" or not self.has_change_permission(request):
            return HttpResponse(status=405)
        salvo = TextoEmailDica.objects.get(pk=pk)
        texto = TextoEmailDica(chave=salvo.chave, assunto=request.POST.get("assunto", salvo.assunto),
                               texto=request.POST.get("texto", salvo.texto), texto_sem=request.POST.get("texto_sem", salvo.texto_sem))
        variante = request.POST.get("variante", "com")
        liberados = ["whatsapp", "site", "carrosseis"] if variante == "com" else []
        exemplo = ContaAppfiliado(email="exemplo@appfiliado.com.br", nome="Ana Lima", shopee_validado_em=timezone.now())
        if request.POST.get("enviar_teste"):
            destino = request.user.email or settings.APPFILIADO_EMAIL_SUPORTE
            if not destino:
                return HttpResponse("Seu usuário do admin não tem e-mail. Cadastre um e tente de novo.")
            emails_valor.enviar(exemplo, salvo.chave, para=[destino], liberados=liberados, texto=texto)
            return HttpResponse(f"<p style='font-family:sans-serif'>Teste enviado para <strong>{destino}</strong> "
                                f"({'tem o módulo' if variante == 'com' else 'não tem o módulo'}). Pode fechar esta aba.</p>")
        _, _, html = emails_valor.montar(exemplo, salvo.chave, liberados=liberados, texto=texto)
        return HttpResponse(html)


@admin.register(Sugestao)
class SugestaoAdmin(admin.ModelAdmin):
    """Sugestões dos afiliados. Marque "Feita" e a pessoa recebe um e-mail avisando."""

    list_display = ("descricao_curta", "tipo", "ferramenta", "importancia", "conta", "situacao", "criada_em")
    list_editable = ("situacao",)
    list_filter = ("situacao", "tipo", "ferramenta", "importancia")
    search_fields = ("descricao", "beneficio", "conta__email")
    readonly_fields = ("conta", "tipo", "ferramenta", "descricao", "beneficio", "como_hoje", "importancia",
                       "pode_contatar", "criada_em", "avisada_em")
    fields = ("situacao", "anotacoes", "conta", "tipo", "ferramenta", "descricao", "beneficio", "como_hoje", "importancia",
              "pode_contatar", "criada_em", "avisada_em")

    @admin.display(description="Sugestão")
    def descricao_curta(self, obj):
        return obj.descricao[:90]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        from .sugestoes import avisar_que_ficou_pronta

        super().save_model(request, obj, form, change)
        if obj.situacao == Sugestao.FEITA and avisar_que_ficou_pronta(obj):
            messages.info(request, f"{obj.conta.email} recebeu o aviso de que a sugestão ficou pronta.")
