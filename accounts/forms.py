from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User
from .validators import validar_cpf


class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail")
    cpf = forms.CharField(
        required=True,
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "cpf", "password1", "password2")

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
    cpf = forms.CharField(
        required=True,
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "cpf")

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
        labels = {"tipo_chave_pix": "Tipo da chave PIX", "chave_pix": "Chave PIX"}
        widgets = {
            "chave_pix": forms.TextInput(attrs={"placeholder": "Cole aqui sua chave PIX"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("chave_pix") and not cleaned.get("tipo_chave_pix"):
            raise forms.ValidationError("Selecione o tipo da chave PIX.")
        return cleaned
