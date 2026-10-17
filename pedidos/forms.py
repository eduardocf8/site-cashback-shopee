from django import forms


class ReclamacaoPedidoForm(forms.Form):
    order_id = forms.CharField(
        label="Nº do pedido na Shopee",
        max_length=64,
        help_text="No app da Shopee: Eu > Minhas compras > abra o pedido > Nº do pedido.",
        widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Ex.: 241016ABCD1234"}),
    )
    data_compra = forms.DateField(label="Data da compra", widget=forms.DateInput(attrs={"type": "date"}))
    produto = forms.CharField(
        label="Qual produto você comprou?",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: fone de ouvido bluetooth"}),
    )
