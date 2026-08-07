from django import forms


class ContatoForm(forms.Form):
    nome = forms.CharField(label="Seu nome", max_length=120)
    email = forms.EmailField(label="Seu e-mail")
    assunto = forms.CharField(label="Assunto", max_length=150)
    mensagem = forms.CharField(label="Mensagem", widget=forms.Textarea(attrs={"rows": 6}))

    # Honeypot: campo escondido que só um robô preencheria.
    campo_extra = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_campo_extra(self):
        valor = self.cleaned_data.get("campo_extra")
        if valor:
            raise forms.ValidationError("Erro de validação.")
        return valor
