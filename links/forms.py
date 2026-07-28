from urllib.parse import urlparse

from django import forms


class LinkProdutoForm(forms.Form):
    url_produto = forms.URLField(
        label="Link do produto na Shopee",
        widget=forms.URLInput(attrs={"placeholder": "https://shopee.com.br/produto-exemplo-i.123.456"}),
    )

    def clean_url_produto(self):
        url = self.cleaned_data["url_produto"]
        host = urlparse(url).netloc.lower()
        if "shopee." not in host:
            raise forms.ValidationError("Informe um link de um produto da Shopee.")
        return url
