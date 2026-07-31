from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("registrar/", views.registrar, name="registrar"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("chave-pix/", views.editar_chave_pix, name="editar_chave_pix"),
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
