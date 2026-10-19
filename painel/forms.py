from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MaxValueValidator, MinValueValidator

from bot_whatsapp.models import ConfiguracaoOfertas


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
        help_text="Deixe em branco para manter o que já está salvo.",
    )


class RegraSubIdForm(forms.Form):
    operador = forms.ChoiceField(label="Se o Sub ID", choices=[])
    texto = forms.CharField(label="Texto", max_length=120, widget=forms.TextInput(attrs={"placeholder": "ex: grupo"}))
    nome = forms.CharField(label="Mostrar como", max_length=60, widget=forms.TextInput(attrs={"placeholder": "ex: Grupos de WhatsApp"}))

    def __init__(self, *args, **kwargs):
        from .models import RegraSubId

        super().__init__(*args, **kwargs)
        self.fields["operador"].choices = RegraSubId.OPERADORES

    def clean_texto(self):
        texto = self.cleaned_data["texto"].strip()
        if not texto:
            raise forms.ValidationError("Informe o texto.")
        return texto

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()


DIAS_DA_SEMANA = [(0, "Seg"), (1, "Ter"), (2, "Qua"), (3, "Qui"), (4, "Sex"), (5, "Sáb"), (6, "Dom")]


class ConfiguracaoOfertasForm(forms.ModelForm):
    """Ofertas automáticas (bot_whatsapp.ConfiguracaoOfertas). Preços e avaliação
    entram como texto para aceitar "39,90"."""

    categorias = forms.MultipleChoiceField(label="Categorias", required=False, widget=forms.CheckboxSelectMultiple)
    grupos = forms.MultipleChoiceField(label="Grupos e canais que recebem as ofertas", required=False,
                                       widget=forms.CheckboxSelectMultiple)
    dias_semana = forms.TypedMultipleChoiceField(
        label="Dias", choices=DIAS_DA_SEMANA, coerce=int, required=False, widget=forms.CheckboxSelectMultiple,
    )
    preco_minimo = forms.CharField(label="Preço mínimo (R$)", required=False)
    preco_maximo = forms.CharField(label="Preço máximo (R$)", required=False)
    avaliacao_minima = forms.CharField(label="Avaliação mínima (0 a 5)", required=False)

    class Meta:
        model = ConfiguracaoOfertas
        fields = [
            "tipo_busca", "palavra_chave", "loja", "categorias", "ordenacao",
            "comissao_minima", "desconto_minimo", "preco_minimo", "preco_maximo", "vendas_minimas",
            "avaliacao_minima", "cupom", "sub_ids", "grupos", "intervalo_minutos", "horario_inicio",
            "horario_fim", "dias_semana", "limite_diario", "repetir_apos_dias",
        ]
        labels = {
            "tipo_busca": "Buscar", "palavra_chave": "Palavra-chave", "loja": "Link da loja",
            "ordenacao": "Ordem", "comissao_minima": "Comissão mínima (%)", "desconto_minimo": "Desconto mínimo (%)",
            "vendas_minimas": "Vendas mínimas", "cupom": "Cupom (opcional)", "sub_ids": "Sub IDs padrão (opcional)",
            "intervalo_minutos": "Uma oferta a cada (minutos)", "horario_inicio": "Das", "horario_fim": "Até",
            "limite_diario": "Máximo de ofertas por dia (0 = sem limite)",
            "repetir_apos_dias": "Não repetir o mesmo produto no mesmo grupo por (dias)",
        }
        help_texts = {
            "loja": "Cole o link da loja na Shopee (ou de um produto dela).",
            "sub_ids": "Valem para todos os grupos que não têm um Sub ID próprio (logo abaixo, na lista de "
                       "grupos). Até 5, separados por vírgula, só letras e números. Ex: grupos, whatsapp",
            "cupom": "Aparece em todas as ofertas como “Cupom: …”.",
            "limite_diario": "", "repetir_apos_dias": "", "dias_semana": "",
        }
        widgets = {
            "tipo_busca": forms.RadioSelect,
            "horario_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "horario_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, grupos_disponiveis=None, **kwargs):
        from bot_whatsapp.categorias import opcoes_categoria

        super().__init__(*args, **kwargs)
        self.fields["categorias"].choices = opcoes_categoria()
        # Grupos do WhatsApp conectado + os já escolhidos (caso tenham sumido da lista).
        disponiveis = {g["jid"]: g.get("nome", g["jid"]) for g in (grupos_disponiveis or []) if g.get("jid")}
        for g in self.instance.grupos or []:
            disponiveis.setdefault(g.get("jid"), g.get("nome", ""))
        self.nomes_dos_grupos = disponiveis
        self.fields["grupos"].choices = sorted(disponiveis.items(), key=lambda item: item[1].lower())
        self.initial["grupos"] = [g.get("jid") for g in self.instance.grupos or []]
        for campo in ("preco_minimo", "preco_maximo", "avaliacao_minima"):
            valor = getattr(self.instance, campo)
            self.initial[campo] = "" if valor is None else f"{valor}".replace(".", ",")
        for campo, (minimo, maximo) in {
            "intervalo_minutos": (1, 240), "comissao_minima": (0, 100), "desconto_minimo": (0, 100),
            "limite_diario": (0, 1000), "repetir_apos_dias": (1, 90),
        }.items():
            self.fields[campo].min_value = minimo
            self.fields[campo].max_value = maximo
            self.fields[campo].validators += [MinValueValidator(minimo), MaxValueValidator(maximo)]
            self.fields[campo].widget.attrs.update({"min": minimo, "max": maximo})

    def _numero(self, campo, minimo=None, maximo=None):
        from painel.telas import ler_numero_br

        texto = self.cleaned_data.get(campo, "")
        if not str(texto).strip():
            return None
        valor = ler_numero_br(texto)
        if valor is None or (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
            raise forms.ValidationError("Número inválido.")
        return Decimal(str(round(valor, 2)))

    def clean_preco_minimo(self):
        return self._numero("preco_minimo", 0)

    def clean_preco_maximo(self):
        return self._numero("preco_maximo", 0)

    def clean_avaliacao_minima(self):
        return self._numero("avaliacao_minima", 0, 5)

    def clean_sub_ids(self):
        from bot_whatsapp.shopee_ofertas import SubIdInvalido, validar_sub_ids

        sub_ids = [s.strip() for s in self.cleaned_data.get("sub_ids", "").split(",") if s.strip()]
        try:
            validar_sub_ids(sub_ids)
        except SubIdInvalido as erro:
            raise forms.ValidationError(str(erro))
        return ", ".join(sub_ids)

    def _sub_id_digitado(self, jid: str) -> str:
        if self.is_bound:
            return str(self.data.get(f"subid_{jid}", "")).strip()
        return (self.instance.sub_ids_por_grupo or {}).get(jid, "")

    @property
    def linhas_dos_grupos(self) -> list[dict]:
        """Cada grupo da lista com o campo de Sub ID próprio dele."""
        return [
            {
                "opcao": opcao,
                "sub_id": self._sub_id_digitado(opcao.data["value"]),
                "canal": str(opcao.data["value"]).endswith("@newsletter"),
            }
            for opcao in self["grupos"]
        ]

    def clean_grupos(self):
        return [{"jid": jid, "nome": self.nomes_dos_grupos.get(jid, "")} for jid in self.cleaned_data.get("grupos", [])]

    def clean(self):
        from bot_whatsapp.shopee_ofertas import extrair_id_da_loja

        dados = super().clean()
        tipo = dados.get("tipo_busca")
        if tipo == "palavra_chave" and not (dados.get("palavra_chave") or "").strip():
            self.add_error("palavra_chave", "Informe a palavra-chave.")
        if tipo == "loja" and not extrair_id_da_loja(dados.get("loja", "")):
            self.add_error("loja", "Não achei a loja nesse link. Cole o link da página da loja na Shopee.")
        if tipo == "categoria" and not dados.get("categorias"):
            self.add_error("categorias", "Escolha pelo menos uma categoria.")
        minimo, maximo = dados.get("preco_minimo"), dados.get("preco_maximo")
        if minimo is not None and maximo is not None and minimo > maximo:
            self.add_error("preco_maximo", "O preço máximo é menor que o mínimo.")
        if not dados.get("dias_semana"):
            self.add_error("dias_semana", "Escolha pelo menos um dia.")
        self._limpar_sub_ids_por_grupo(dados)
        return dados

    def _limpar_sub_ids_por_grupo(self, dados):
        from bot_whatsapp.shopee_ofertas import SubIdInvalido, validar_sub_ids

        por_grupo = dict(self.instance.sub_ids_por_grupo or {})
        for jid, nome in self.nomes_dos_grupos.items():
            sub_ids = [s.strip() for s in self._sub_id_digitado(jid).split(",") if s.strip()]
            try:
                validar_sub_ids(sub_ids)
            except SubIdInvalido as erro:
                self.add_error("grupos", f"Sub ID de “{nome}”: {erro}")
                continue
            if sub_ids:
                por_grupo[jid] = ", ".join(sub_ids)
            else:
                por_grupo.pop(jid, None)
        self.instance.sub_ids_por_grupo = por_grupo
