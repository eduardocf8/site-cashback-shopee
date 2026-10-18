from django import forms
from django.contrib.auth.password_validation import validate_password


class EntrarForm(forms.Form):
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class EsqueciSenhaForm(forms.Form):
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))


class NovaSenhaForm(forms.Form):
    senha = forms.CharField(
        label="Nova senha", min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Pelo menos 8 caracteres, sem ser só números.",
    )
    confirmacao = forms.CharField(label="Repita a senha", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean(self):
        dados = super().clean()
        senha, confirmacao = dados.get("senha"), dados.get("confirmacao")
        if senha and confirmacao and senha != confirmacao:
            self.add_error("confirmacao", "As duas senhas não são iguais.")
        if senha:
            try:
                validate_password(senha)
            except forms.ValidationError as erro:
                self.add_error("senha", erro)
        return dados


class TrocarSenhaForm(NovaSenhaForm):
    senha_atual = forms.CharField(label="Senha atual", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    field_order = ["senha_atual", "senha", "confirmacao"]

    def __init__(self, *args, conta=None, **kwargs):
        self.conta = conta
        super().__init__(*args, **kwargs)

    def clean_senha_atual(self):
        valor = self.cleaned_data["senha_atual"]
        if not self.conta.confere_senha(valor):
            raise forms.ValidationError("Senha atual incorreta.")
        return valor


class ShopeeForm(forms.Form):
    app_id = forms.CharField(label="AppID", max_length=64, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    secret = forms.CharField(
        label="Secret", max_length=200, required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
        help_text="Deixe em branco pra manter o que já está salvo.",
    )
