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
