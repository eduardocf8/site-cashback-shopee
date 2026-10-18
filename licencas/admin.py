from django import forms
from django.contrib import admin, messages

from .models import MODULOS, Assinatura, ContaAppfiliado, EventoWebhookZouti, ProdutoZouti, modulos_de_texto
from .services import enviar_email_chave

NOMES_MODULOS = dict(MODULOS)


class CampoModulos(forms.MultipleChoiceField):
    """Mostra os módulos como caixinhas e guarda como texto "whatsapp,site"."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(choices=MODULOS, widget=forms.CheckboxSelectMultiple, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, str):
            return modulos_de_texto(value)
        return value

    def clean(self, value):
        return ",".join(super().clean(value))


class ProdutoZoutiForm(forms.ModelForm):
    modulos = CampoModulos(label="Módulos que este produto libera")

    class Meta:
        model = ProdutoZouti
        fields = "__all__"


@admin.register(ProdutoZouti)
class ProdutoZoutiAdmin(admin.ModelAdmin):
    form = ProdutoZoutiForm
    list_display = ("nome", "zouti_product_id", "modulos_legiveis")
    search_fields = ("nome", "zouti_product_id")

    @admin.display(description="Módulos")
    def modulos_legiveis(self, obj):
        return ", ".join(NOMES_MODULOS[m] for m in obj.lista_modulos()) or "-"


class AssinaturaInline(admin.TabularInline):
    model = Assinatura
    extra = 0
    can_delete = False
    fields = ("zouti_subscription_id", "plano", "status", "motivo", "proxima_cobranca", "acesso_ate", "zouti_product_ids")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ContaAppfiliadoForm(forms.ModelForm):
    modulos_cortesia = CampoModulos(label="Módulos de cortesia")

    class Meta:
        model = ContaAppfiliado
        fields = "__all__"


@admin.register(ContaAppfiliado)
class ContaAppfiliadoAdmin(admin.ModelAdmin):
    form = ContaAppfiliadoForm
    list_display = ("email", "nome", "chave", "modulos_agora", "criada_em")
    search_fields = ("email", "nome", "chave", "assinaturas__zouti_subscription_id")
    readonly_fields = (
        "chave", "chave_enviada_em", "modulos_agora", "tem_senha_painel", "ultimo_login",
        "shopee_app_id", "shopee_validado_em", "criada_em", "atualizada_em",
    )
    fields = (
        "email", "nome", "chave", "chave_enviada_em", "modulos_agora",
        "modulos_cortesia", "cortesia_ate",
        "tem_senha_painel", "ultimo_login", "shopee_app_id", "shopee_validado_em",
        "criada_em", "atualizada_em",
    )
    inlines = [AssinaturaInline]
    actions = ["reenviar_chave", "enviar_link_senha", "mostrar_link_senha"]

    @admin.display(description="Senha do painel criada?", boolean=True)
    def tem_senha_painel(self, obj):
        return obj.tem_senha

    @admin.action(description="Enviar link para criar/trocar a senha do painel")
    def enviar_link_senha(self, request, queryset):
        from painel.emails import enviar_email_recuperar_senha

        falharam = [conta.email for conta in queryset if not enviar_email_recuperar_senha(conta)]
        enviados = queryset.count() - len(falharam)
        if enviados:
            self.message_user(request, f"Link enviado para {enviados} conta(s).")
        if falharam:
            self.message_user(
                request,
                f"Não consegui enviar para: {', '.join(falharam)}. O motivo aparece nos logs do Render "
                "(\"falha ao enviar e-mail de senha\"). Use \"Mostrar link para criar a senha\" "
                "para pegar o link sem e-mail.",
                messages.ERROR,
            )

    @admin.action(description="Mostrar link para criar a senha do painel (sem e-mail)")
    def mostrar_link_senha(self, request, queryset):
        """Para suporte (ou quando o e-mail não chega): mostra o link aqui mesmo, para
        abrir ou mandar para a pessoa por outro canal. Vale por 3 dias e uma vez só."""
        from django.utils.html import format_html

        from painel.emails import link_definir_senha

        if queryset.count() != 1:
            self.message_user(request, "Selecione uma conta só.", messages.WARNING)
            return
        conta = queryset.get()
        link = link_definir_senha(conta)
        self.message_user(
            request,
            format_html(
                'Link para {} criar a senha (vale por 3 dias e uma vez só): <a href="{}">{}</a>',
                conta.email, link, link,
            ),
        )

    @admin.display(description="Módulos liberados agora")
    def modulos_agora(self, obj):
        if not obj.pk:
            return "-"
        return ", ".join(NOMES_MODULOS[m] for m in obj.modulos_liberados()) or "Nenhum"

    @admin.action(description="Reenviar a chave por e-mail")
    def reenviar_chave(self, request, queryset):
        enviados = sum(1 for conta in queryset if enviar_email_chave(conta.pk))
        falhas = queryset.count() - enviados
        self.message_user(request, f"Chave reenviada para {enviados} conta(s).")
        if falhas:
            self.message_user(request, f"{falhas} envio(s) falharam - veja os logs.", level=messages.WARNING)


@admin.register(EventoWebhookZouti)
class EventoWebhookZoutiAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_evento", "email", "assinatura_valida", "processado_com_sucesso", "resultado", "recebido_em",
    )
    list_filter = ("assinatura_valida", "processado_com_sucesso", "tipo_evento")
    search_fields = ("email", "zouti_event_id", "zouti_object_id", "corpo_bruto")
    readonly_fields = [f.name for f in EventoWebhookZouti._meta.fields]

    def has_add_permission(self, request):
        return False
