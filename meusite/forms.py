import io
import re

from django import forms

from bot_whatsapp.models import ConfiguracaoOfertas

from . import cores
from .models import CORES, ENDERECOS_RESERVADOS, REDES, BotaoSite, SiteAfiliado

OUTRA_COR = "outra"
PADRAO_ENDERECO = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")


class SiteForm(forms.ModelForm):
    categorias = forms.MultipleChoiceField(label="Categorias", required=False, widget=forms.CheckboxSelectMultiple)
    ordenacao = forms.ChoiceField(label="Ordem", choices=ConfiguracaoOfertas.ORDENACOES)
    # Uma das cores prontas ou "outra" (aí vale a do seletor de cor ao lado).
    cor = forms.ChoiceField(label="Cor do site", choices=CORES + [(OUTRA_COR, "Outra cor")], widget=forms.RadioSelect)
    cor_outra = forms.CharField(label="Outra cor", required=False, max_length=7,
                                widget=forms.TextInput(attrs={"type": "color"}))

    class Meta:
        model = SiteAfiliado
        fields = [
            "endereco", "publicado", "nome", "frase", "cor", "layout", "mostrar_conversor", "conversor_titulo",
            "conversor_texto", "conversor_botao", "sub_id", "sub_id_vitrine",
            "vitrine", "vitrine_formato", "busca_tipo", "palavra_chave", "loja", "categorias", "ordenacao", "links_manuais",
        ]
        labels = {
            "endereco": "Endereço", "publicado": "Site no ar", "nome": "Nome", "frase": "Frase curta",
            "cor": "Cor do site", "layout": "Estilo do site", "mostrar_conversor": "Mostrar o conversor de links no site",
            "sub_id": "Sub ID das vendas pelo conversor", "sub_id_vitrine": "Sub ID das vendas pela vitrine", "vitrine": "O que mostrar", "vitrine_formato": "Como mostrar as ofertas", "busca_tipo": "Buscar",
            "palavra_chave": "Palavra-chave", "loja": "Link da loja", "links_manuais": "Links dos produtos",
            "conversor_titulo": "Título", "conversor_texto": "Texto", "conversor_botao": "Texto do botão",
        }
        help_texts = {
            "endereco": "Só letras minúsculas, números e hífen (3 a 40). É o link da sua bio.",
            "sub_id": "Assim as vendas do conversor aparecem separadas em Resultados. Só letras e números.",
            "sub_id_vitrine": "Para ver em Resultados as vendas da vitrine separadas das vendas do conversor. "
                              "Em branco, usa o mesmo Sub ID do conversor.",
            "links_manuais": "Cole o link de cada produto da Shopee, um por linha, na ordem em que devem aparecer "
                             "(até 60). Depois de salvar, dá para corrigir a categoria de cada um na lista de produtos.",
            "frase": "Aparece embaixo do nome. Ex: As melhores ofertas da Shopee todo dia.",
            "conversor_botao": "Em branco, fica o texto padrão (aparece apagadinho no campo).",
        }
        widgets = {
            "layout": forms.RadioSelect, "vitrine": forms.RadioSelect, "busca_tipo": forms.RadioSelect,
            "vitrine_formato": forms.RadioSelect,
            "links_manuais": forms.Textarea(attrs={"rows": 5, "placeholder": "https://s.shopee.com.br/..."}),
            "endereco": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false", "autocapitalize": "none"}),
            "conversor_titulo": forms.TextInput(attrs={"placeholder": SiteAfiliado.TITULO_PADRAO}),
            "conversor_texto": forms.Textarea(attrs={"rows": 3, "placeholder": SiteAfiliado.TEXTO_PADRAO}),
            "conversor_botao": forms.TextInput(attrs={"placeholder": SiteAfiliado.BOTAO_PADRAO}),
        }

    def __init__(self, *args, tem_bot=True, regras=None, **kwargs):
        from bot_whatsapp.categorias import opcoes_categoria
        from licencas import planos

        super().__init__(*args, **kwargs)
        self.regras = regras or {**planos.SITE[True], "premium": True}  # o que o plano da conta libera
        self.fields["categorias"].choices = opcoes_categoria()
        self.fields["endereco"].required = True
        self.fields["vitrine_formato"].required = False
        self.fields["layout"].required = False
        sub_id = self.instance.sub_id or "site"
        self.fields["sub_id_vitrine"].widget.attrs["placeholder"] = f"igual ao do conversor ({sub_id})"
        for nome in self.CAMPOS_COM_EMOJI:
            if nome in self.fields:
                self.fields[nome].widget.attrs["data-emoji"] = ""
        cor_atual = self.instance.cor or SiteAfiliado._meta.get_field("cor").default
        pronta = cor_atual.upper() in {c for c, _ in CORES}
        self.initial["cor"] = cor_atual.upper() if pronta else OUTRA_COR
        self.initial["cor_outra"] = cor_atual
        escolhas = list(SiteAfiliado.FONTES_VITRINE)
        if not tem_bot:  # sem o bot de WhatsApp, a vitrine "do bot" não teria o que mostrar
            escolhas = [e for e in escolhas if e[0] != SiteAfiliado.VITRINE_BOT]
        self.fields["vitrine"].choices = escolhas
        exemplos = {"whatsapp": "Link do grupo ou número com DDD", "telegram": "@seucanal ou link"}
        for rede, nome, _ in REDES:
            self.fields[f"rede_{rede}"] = forms.CharField(
                label=nome, required=False, max_length=300,
                initial=(self.instance.redes or {}).get(rede, ""),
                widget=forms.TextInput(attrs={"placeholder": exemplos.get(rede, "@seuperfil ou link"), "autocomplete": "off"}),
            )

    CAMPOS_COM_EMOJI = ("nome", "frase", "conversor_titulo", "conversor_texto", "conversor_botao")

    def campos_das_redes(self):
        return [self[f"rede_{rede}"] for rede, _, _ in REDES]

    @staticmethod
    def link_da_rede(rede: str, modelo: str, valor: str) -> str:
        """Aceita o link ou só o @ (WhatsApp: link ou número com DDD)."""
        valor = valor.strip()
        if not valor:
            return ""
        if re.match(r"^(https?://|[\w-]+\.[\w.-]+/)", valor, re.I):
            url = valor if re.match(r"^https?://", valor, re.I) else "https://" + valor
            forms.URLField().clean(url)
            return url
        if rede == "whatsapp":
            numero = re.sub(r"\D", "", valor)
            if len(numero) < 10:
                raise forms.ValidationError("Use o link do grupo ou o número com DDD.")
            return f"https://wa.me/{numero if numero.startswith('55') else '55' + numero}"
        usuario = valor.lstrip("@").strip()
        if not re.match(r"^[\w.-]{1,60}$", usuario):
            raise forms.ValidationError("Use o @ do perfil ou o link.")
        return modelo.format(usuario)

    def clean_cor(self):
        cor = self.cleaned_data.get("cor")
        if cor != OUTRA_COR:
            return cor
        outra = (self.data.get(self.add_prefix("cor_outra")) or "").strip()
        if not cores.valida(outra):
            raise forms.ValidationError("Escolha a outra cor no seletor.")
        return outra.upper()

    def clean_layout(self):
        return self.cleaned_data.get("layout") or self.instance.layout or SiteAfiliado.LAYOUT_COLORIDO

    def clean_vitrine_formato(self):
        return self.cleaned_data.get("vitrine_formato") or self.instance.vitrine_formato or SiteAfiliado.FORMATO_LISTA

    def clean_endereco(self):
        endereco = (self.cleaned_data.get("endereco") or "").strip().lower()
        if not PADRAO_ENDERECO.match(endereco) or "--" in endereco:
            raise forms.ValidationError("Use de 3 a 40 letras minúsculas, números ou hífen (sem acento nem espaço).")
        if endereco in ENDERECOS_RESERVADOS:
            raise forms.ValidationError("Esse endereço é reservado. Escolha outro.")
        if SiteAfiliado.objects.filter(endereco=endereco).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Esse endereço já está em uso. Escolha outro.")
        return endereco

    def clean_sub_id_vitrine(self):
        return self._sub_id_valido("sub_id_vitrine")

    def clean_sub_id(self):
        return self._sub_id_valido("sub_id")

    def _sub_id_valido(self, campo):
        from bot_whatsapp.shopee_ofertas import SubIdInvalido, validar_sub_ids

        sub_id = (self.cleaned_data.get(campo) or "").strip()
        try:
            validar_sub_ids([sub_id] if sub_id else [])
        except SubIdInvalido as erro:
            raise forms.ValidationError(str(erro))
        return sub_id

    def clean(self):
        from bot_whatsapp.shopee_ofertas import extrair_id_da_loja

        dados = super().clean()
        redes = {}
        for rede, _, modelo in REDES:
            try:
                link = self.link_da_rede(rede, modelo, dados.get(f"rede_{rede}", ""))
            except forms.ValidationError as erro:
                self.add_error(f"rede_{rede}", erro.messages[0] if erro.messages[0] != "Enter a valid URL." else "Link inválido.")
                continue
            if link:
                redes[rede] = link
        self.instance.redes = redes
        if dados.get("vitrine") == SiteAfiliado.VITRINE_BUSCA:
            tipo = dados.get("busca_tipo")
            if tipo == SiteAfiliado.BUSCA_PALAVRA and not (dados.get("palavra_chave") or "").strip():
                self.add_error("palavra_chave", "Informe a palavra-chave.")
            if tipo == SiteAfiliado.BUSCA_LOJA and not extrair_id_da_loja(dados.get("loja", "")):
                self.add_error("loja", "Não achei a loja nesse link. Cole o link da página da loja na Shopee.")
            if tipo == SiteAfiliado.BUSCA_CATEGORIA and not dados.get("categorias"):
                self.add_error("categorias", "Escolha pelo menos uma categoria.")
        if dados.get("vitrine") == SiteAfiliado.VITRINE_MANUAL and not self.regras["produtos_escolhidos"]:
            self.add_error("vitrine", "A vitrine com os produtos que você escolher é do plano Premium.")
        elif dados.get("vitrine") == SiteAfiliado.VITRINE_MANUAL and not (dados.get("links_manuais") or "").strip():
            self.add_error("links_manuais", "Cole pelo menos um link de produto.")
        return dados


class BotaoForm(forms.ModelForm):
    url = forms.CharField(label="Link", max_length=500)

    class Meta:
        model = BotaoSite
        fields = ["texto", "url", "destaque"]
        labels = {"texto": "Texto do botão", "destaque": "Em destaque (na cor do site)"}
        widgets = {"texto": forms.TextInput(attrs={"placeholder": "💬 Entrar no grupo de ofertas"})}

    def clean_url(self):
        url = (self.cleaned_data.get("url") or "").strip()
        if url and not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        try:
            forms.URLField().clean(url)
        except forms.ValidationError:
            raise forms.ValidationError("Link inválido. Ex: https://chat.whatsapp.com/...")
        return url


class FotoForm(forms.Form):
    foto = forms.ImageField(label="Foto")

    TAMANHO = 320
    MAXIMO_MB = 5

    def clean_foto(self):
        from PIL import Image, ImageOps

        arquivo = self.cleaned_data["foto"]
        if arquivo.size > self.MAXIMO_MB * 1024 * 1024:
            raise forms.ValidationError(f"A foto pode ter até {self.MAXIMO_MB} MB.")
        imagem = ImageOps.exif_transpose(Image.open(arquivo)).convert("RGB")
        imagem = ImageOps.fit(imagem, (self.TAMANHO, self.TAMANHO), Image.LANCZOS)
        saida = io.BytesIO()
        imagem.save(saida, "JPEG", quality=85, optimize=True)
        return saida.getvalue()
