from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User
from .validators import validar_celular, validar_cpf, validar_nome_completo


def _campo_nome_completo():
    return forms.CharField(
        required=True, label="Nome completo", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Como está no seu documento", "autocomplete": "name"}),
    )


def _campo_celular():
    return forms.CharField(
        required=False, label="Celular com DDD (opcional)", max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "(11) 98765-4321", "autocomplete": "tel", "inputmode": "tel"}),
    )


class RegistroForm(UserCreationForm):
    nome_completo = _campo_nome_completo()
    email = forms.EmailField(required=True, label="E-mail")
    celular = _campo_celular()
    cpf = forms.CharField(
        required=True,
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )

    class Meta:
        model = User
        fields = ("nome_completo", "username", "email", "celular", "cpf", "password1", "password2")

    def clean_nome_completo(self):
        return validar_nome_completo(self.cleaned_data["nome_completo"])

    def clean_celular(self):
        celular = self.cleaned_data.get("celular", "")
        return validar_celular(celular) if celular.strip() else ""

    def clean_cpf(self):
        cpf = validar_cpf(self.cleaned_data["cpf"])
        if User.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este CPF.")
        return cpf

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email


class EditarPerfilForm(forms.ModelForm):
    nome_completo = _campo_nome_completo()
    celular = _campo_celular()
    cpf = forms.CharField(
        required=True,
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )

    class Meta:
        model = User
        fields = ("nome_completo", "username", "email", "celular", "cpf", "aceita_email_marketing")

    def clean_nome_completo(self):
        return validar_nome_completo(self.cleaned_data["nome_completo"])

    def clean_celular(self):
        celular = self.cleaned_data.get("celular", "")
        return validar_celular(celular) if celular.strip() else ""

    def clean_cpf(self):
        cpf = validar_cpf(self.cleaned_data["cpf"])
        if User.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este CPF.")
        return cpf

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma conta cadastrada com este e-mail.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Esse nome de usuário já está em uso.")
        return username


class ChavePixForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("tipo_chave_pix", "chave_pix")
        labels = {"tipo_chave_pix": "Tipo da chave Pix", "chave_pix": "Chave Pix"}
        widgets = {
            "chave_pix": forms.TextInput(attrs={"placeholder": "Cole aqui sua chave Pix"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Contas antigas não têm nome completo, e ele é comparado com o titular da
        # chave (accounts/verificacao_pix.py) - pede aqui, junto com a chave.
        if not self.instance.nome_completo:
            self.fields["nome_completo"] = _campo_nome_completo()
            self.order_fields(["nome_completo", "tipo_chave_pix", "chave_pix"])

    def clean_nome_completo(self):
        return validar_nome_completo(self.cleaned_data["nome_completo"])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("chave_pix") and not cleaned.get("tipo_chave_pix"):
            raise forms.ValidationError("Selecione o tipo da chave Pix.")
        return cleaned

    def save(self, commit=True):
        if "nome_completo" in self.cleaned_data:
            self.instance.nome_completo = self.cleaned_data["nome_completo"]
        return super().save(commit=commit)
