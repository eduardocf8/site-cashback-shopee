from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from .comunicacoes import FILTROS, enviar_comunicacao, obter_destinatarios
from .models import ComunicacaoEmail, ConfiguracaoIndicacao, Indicacao, PushSubscription, User
from .push import enviar_push


class UserAdmin(BaseUserAdmin):
    # CPF é obrigatório e único no model (accounts.models.User) - sem incluir aqui
    # também na tela de criação, ela salva com cpf="" e o segundo usuário criado
    # pelo Admin esbarra na restrição de unicidade (erro 500 genérico).
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Dados adicionais", {"fields": ("cpf",)}),)
    fieldsets = BaseUserAdmin.fieldsets + (("Dados adicionais", {"fields": ("cpf", "codigo_indicacao")}),)
    list_display = ("username", "email", "cpf", "codigo_indicacao", "is_staff")
    readonly_fields = ("codigo_indicacao",)

    def get_urls(self):
        urls = [
            path(
                "comunicacoes/",
                self.admin_site.admin_view(self.comunicacao_view),
                name="accounts_comunicacao",
            ),
            path(
                "comunicacoes/contar/",
                self.admin_site.admin_view(self.comunicacao_contar_view),
                name="accounts_comunicacao_contar",
            ),
        ]
        return urls + super().get_urls()

    def comunicacao_contar_view(self, request):
        filtro = request.GET.get("filtro", "todos")
        total = obter_destinatarios(filtro).count()
        return JsonResponse({"total": total})

    def comunicacao_view(self, request):
        if request.method == "POST":
            assunto = request.POST.get("assunto", "").strip()
            corpo = request.POST.get("corpo", "").strip()
            filtro = request.POST.get("filtro", "todos")

            if not assunto or not corpo:
                messages.error(request, "Preencha o assunto e o corpo do e-mail.")
            else:
                comunicacao = enviar_comunicacao(
                    assunto=assunto, corpo=corpo, filtro=filtro, enviado_por=request.user
                )
                if comunicacao.total_destinatarios == 0:
                    messages.warning(request, "Nenhum destinatário encontrado pra esse filtro - nada foi enviado.")
                elif comunicacao.total_enviados < comunicacao.total_destinatarios:
                    messages.warning(
                        request,
                        f"Enviado pra {comunicacao.total_enviados} de {comunicacao.total_destinatarios} "
                        "destinatário(s) - alguns lotes falharam, confira os logs do servidor.",
                    )
                else:
                    messages.success(
                        request, f"E-mail enviado com sucesso pra {comunicacao.total_enviados} destinatário(s)."
                    )
                return redirect("admin:accounts_comunicacao")

        contexto = {
            **self.admin_site.each_context(request),
            "title": "Enviar comunicação por e-mail",
            "filtros": FILTROS,
            "historico": ComunicacaoEmail.objects.select_related("enviado_por")[:20],
        }
        return TemplateResponse(request, "admin/comunicacao_email.html", contexto)


@admin.register(ComunicacaoEmail)
class ComunicacaoEmailAdmin(admin.ModelAdmin):
    # Histórico só - a criação acontece pela tela de envio (UserAdmin.comunicacao_view),
    # nunca por aqui, então não faz sentido permitir adicionar/editar direto no admin.
    list_display = ("assunto", "filtro", "total_destinatarios", "total_enviados", "enviado_por", "enviado_em")
    list_filter = ("filtro",)
    search_fields = ("assunto", "corpo")
    readonly_fields = [f.name for f in ComunicacaoEmail._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Indicacao)
class IndicacaoAdmin(admin.ModelAdmin):
    list_display = ("indicador", "indicado", "pedido_bonus_indicado", "pedido_bonus_indicador", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("indicador__username", "indicado__username")
    autocomplete_fields = ("indicador", "indicado")


@admin.register(ConfiguracaoIndicacao)
class ConfiguracaoIndicacaoAdmin(admin.ModelAdmin):
    # Linha única (pk=1, criada pela migração 0006) - só dá pra editar o campo "ativa",
    # não criar outra linha nem apagar a que existe.
    list_display = ("ativa",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "criado_em")
    search_fields = ("usuario__username",)
    autocomplete_fields = ("usuario",)
    actions = ["mandar_notificacao_de_teste"]

    @admin.action(description="Mandar notificação de teste")
    def mandar_notificacao_de_teste(self, request, queryset):
        usuarios = {inscricao.usuario for inscricao in queryset}
        total_enviado = sum(
            enviar_push(
                usuario,
                "Notificação de teste",
                "Se você recebeu isso, as notificações da cash-b estão funcionando!",
                url="/dashboard/",
            )
            for usuario in usuarios
        )
        if total_enviado:
            self.message_user(request, f"Notificação de teste enviada com sucesso ({total_enviado}).")
        else:
            self.message_user(
                request,
                "Não saiu nenhuma notificação - o envio falhou no servidor. Procure por "
                '"Falha ao enviar push" nos logs do Render pra ver o erro exato.',
                level=messages.WARNING,
            )


admin.site.register(User, UserAdmin)
