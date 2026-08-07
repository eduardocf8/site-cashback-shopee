from urllib.parse import urlparse

from django import forms

# shopee.com.br: domínio padrão de produto. shp.ee: domínio oficial de link curto da
# Shopee (gerado por "Compartilhar > Copiar link" no app), com subdomínios por país
# (ex: br.shp.ee) - por isso comparamos com endswith, não só "in".
DOMINIOS_SHOPEE_VALIDOS = ("shopee.com.br", "shp.ee")


class LinkProdutoForm(forms.Form):
    url_produto = forms.URLField(
        label="Link do produto na Shopee",
        widget=forms.URLInput(attrs={"placeholder": "https://shopee.com.br/produto-exemplo-i.123.456"}),
    )

    def clean_url_produto(self):
        url = self.cleaned_data["url_produto"]
        host = urlparse(url).netloc.lower()
        if not any(host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_SHOPEE_VALIDOS):
            raise forms.ValidationError("Informe um link de um produto da Shopee.")
        return url
