from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("registrar/", views.registrar, name="registrar"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("chave-pix/", views.editar_chave_pix, name="editar_chave_pix"),
    path("chave-pix/excluir/", views.excluir_chave_pix, name="excluir_chave_pix"),
    path("editar-perfil/", views.editar_perfil, name="editar_perfil"),
    path("verificar-email/<str:token>/", views.verificar_email, name="verificar_email"),
    path("reenviar-verificacao/", views.reenviar_verificacao, name="reenviar_verificacao"),
    path(
        "trocar-senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/senha_trocar.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "trocar-senha/concluido/",
        auth_views.PasswordChangeDoneView.as_view(template_name="accounts/senha_trocar_concluido.html"),
        name="password_change_done",
    ),
    path(
        "esqueci-senha/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/senha_resetar.html",
            email_template_name="accounts/email_senha_resetar.txt",
            subject_template_name="accounts/email_senha_resetar_assunto.txt",
        ),
        name="password_reset",
    ),
    path(
        "esqueci-senha/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/senha_resetar_enviado.html"),
        name="password_reset_done",
    ),
    path(
        "resetar-senha/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="accounts/senha_resetar_confirmar.html"),
        name="password_reset_confirm",
    ),
    path(
        "resetar-senha/concluido/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/senha_resetar_concluido.html"),
        name="password_reset_complete",
    ),
]
