from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MaxValueValidator, MinValueValidator

from bot_whatsapp.models import AlertaPreco, CampanhaBot, ConfiguracaoOfertas


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
    texto = forms.CharField(label="Texto", max_length=120, required=False,
                            widget=forms.TextInput(attrs={"placeholder": "ex: grupo"}))
    nome = forms.CharField(label="Mostrar como", max_length=60, widget=forms.TextInput(attrs={"placeholder": "ex: Grupos de WhatsApp"}))

    def __init__(self, *args, **kwargs):
        from .models import RegraSubId

        super().__init__(*args, **kwargs)
        self.fields["operador"].choices = RegraSubId.OPERADORES

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean(self):
        from .models import RegraSubId

        dados = super().clean()
        if dados.get("operador") == RegraSubId.SEM:
            dados["texto"] = ""  # "está vazio" não usa texto
        elif not (dados.get("texto") or "").strip():
            self.add_error("texto", "Informe o texto.")
        else:
            dados["texto"] = dados["texto"].strip()
        return dados


DIAS_DA_SEMANA = [(0, "Seg"), (1, "Ter"), (2, "Qua"), (3, "Qui"), (4, "Sex"), (5, "Sáb"), (6, "Dom")]


ATTRS_HORA = {
    "type": "text", "inputmode": "numeric", "maxlength": "5", "placeholder": "07:00",
    "pattern": "([01]?[0-9]|2[0-3]):[0-5][0-9]", "title": "Hora no formato 24 h, ex: 07:00 ou 22:30",
    "autocomplete": "off", "data-hora": "",
}


def _salvos_primeiro(nomes: dict, salvos) -> list[tuple[str, str]]:
    """Os grupos/canais já salvos no topo da lista (fica fácil ver e desmarcar), depois
    os outros; cada parte em ordem alfabética. Usa o que está salvo, não o que está
    marcado na tela, para a lista não pular enquanto a pessoa marca."""
    marcados = {g.get("jid") for g in salvos or []}
    return sorted(nomes.items(), key=lambda item: (item[0] not in marcados, item[1].lower()))


def _marcar_divisa(linhas: list[dict], salvos) -> list[dict]:
    """Marca a primeira linha depois dos salvos (a tela põe uma linha separando)."""
    marcados = {g.get("jid") for g in salvos or []}
    for i, linha in enumerate(linhas):
        linha["divisa"] = bool(marcados) and i > 0 and linha["opcao"].data["value"] not in marcados and (
            linhas[i - 1]["opcao"].data["value"] in marcados
        )
    return linhas


class ConfiguracaoOfertasForm(forms.ModelForm):
    """Ofertas automáticas (bot_whatsapp.ConfiguracaoOfertas). Preços e avaliação
    entram como texto para aceitar "39,90"."""

    categorias = forms.MultipleChoiceField(label="Categorias", required=False, widget=forms.CheckboxSelectMultiple)
    grupos = forms.MultipleChoiceField(label="Grupos e canais que recebem as ofertas", required=False,
                                       widget=forms.CheckboxSelectMultiple)
    origens = forms.MultipleChoiceField(label="Copiar as ofertas destes grupos e canais", required=False,
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
            "modo", "origens", "tipo_busca", "palavra_chave", "loja", "categorias", "ordenacao",
            "comissao_minima", "desconto_minimo", "preco_minimo", "preco_maximo", "vendas_minimas",
            "avaliacao_minima", "cupom", "sub_ids", "grupos", "intervalo_minutos", "horario_inicio",
            "horario_fim", "dias_semana", "limite_diario", "repetir_apos_dias", "formato_envio", "ia_ativa", "ia_tipo", "simulacao",
        ]
        labels = {
            "modo": "De onde vêm as ofertas", "tipo_busca": "Buscar", "palavra_chave": "Palavra-chave", "loja": "Link da loja",
            "ordenacao": "Ordem", "comissao_minima": "Comissão mínima (%)", "desconto_minimo": "Desconto mínimo (%)",
            "vendas_minimas": "Vendas mínimas", "cupom": "Cupom (opcional)", "sub_ids": "Sub IDs padrão (opcional)",
            "intervalo_minutos": "Uma oferta a cada (minutos)", "horario_inicio": "Das", "horario_fim": "Até",
            "limite_diario": "Máximo de ofertas por dia (em branco = sem limite)",
            "repetir_apos_dias": "Não repetir o mesmo produto no mesmo grupo por (dias)",
        }
        help_texts = {
            "loja": "Cole o link da loja na Shopee (ou de um produto dela).",
            "sub_ids": "Valem para todos os grupos que não têm um Sub ID próprio (logo abaixo, na lista de "
                       "grupos). Até 5, separados por vírgula, só letras e números. Ex: grupos, whatsapp",
            "cupom": "Aparece em todas as ofertas como “Cupom: …”.",
            "limite_diario": "", "repetir_apos_dias": "", "dias_semana": "",
            "intervalo_minutos": "Copiando de grupos: 0 = repassa assim que chegar.",
        }
        widgets = {
            "modo": forms.RadioSelect,
            "tipo_busca": forms.RadioSelect,
            "ia_tipo": forms.RadioSelect,
            "formato_envio": forms.RadioSelect,
            # Texto "HH:MM" (sempre 24 h): o campo de hora do navegador mostra AM/PM em
            # computadores configurados em inglês.
            "horario_inicio": forms.TimeInput(attrs=ATTRS_HORA, format="%H:%M"),
            "horario_fim": forms.TimeInput(attrs=ATTRS_HORA, format="%H:%M"),
        }

    def __init__(self, *args, grupos_disponiveis=None, regras=None, **kwargs):
        from bot_whatsapp import ia
        from bot_whatsapp.categorias import opcoes_categoria
        from licencas import planos

        super().__init__(*args, **kwargs)
        self.regras = regras or {**planos.BOT[True], "premium": True}  # o que o plano da conta libera
        self.ia_disponivel = ia.disponivel()
        self.fields["ia_tipo"].required = False
        self.fields["formato_envio"].required = False
        if not self.ia_disponivel or not self.regras["ia"]:  # sem a chave do Appfiliado ou fora do plano
            self.fields["ia_ativa"].disabled = True
            self.fields["ia_tipo"].disabled = True
        self.fields["categorias"].choices = opcoes_categoria()
        # Destinos: grupos e canais onde o número posta (+ os já escolhidos, caso tenham
        # sumido da lista). Origens: qualquer grupo ou canal que o número participa/segue.
        todos = [g for g in (grupos_disponiveis or []) if g.get("jid")]
        disponiveis = {g["jid"]: g.get("nome", g["jid"]) for g in todos if g.get("pode_postar", True)}
        for g in self.instance.grupos or []:
            disponiveis.setdefault(g.get("jid"), g.get("nome", ""))
        self.nomes_dos_grupos = disponiveis
        self.fields["grupos"].choices = _salvos_primeiro(disponiveis, self.instance.grupos)
        self.initial["grupos"] = [g.get("jid") for g in self.instance.grupos or []]
        origens = {g["jid"]: g.get("nome", g["jid"]) for g in todos}
        for g in self.instance.origens or []:
            origens.setdefault(g.get("jid"), g.get("nome", ""))
        self.nomes_das_origens = origens
        self.fields["origens"].choices = _salvos_primeiro(origens, self.instance.origens)
        self.initial["origens"] = [g.get("jid") for g in self.instance.origens or []]
        for campo in ("preco_minimo", "preco_maximo", "avaliacao_minima"):
            valor = getattr(self.instance, campo)
            self.initial[campo] = "" if valor is None else f"{valor}".replace(".", ",")
        # Filtros e limite opcionais: em branco = não filtrar / sem limite (guarda 0).
        for campo in self.OPCIONAIS_ZERO:
            self.fields[campo].required = False
            if not getattr(self.instance, campo):
                self.initial[campo] = ""
        for campo, (minimo, maximo) in {
            "intervalo_minutos": (0, 240), "comissao_minima": (0, 100), "desconto_minimo": (0, 100),
            "limite_diario": (0, 1000), "repetir_apos_dias": (1, 90),
        }.items():
            self.fields[campo].min_value = minimo
            self.fields[campo].max_value = maximo
            self.fields[campo].validators += [MinValueValidator(minimo), MaxValueValidator(maximo)]
            self.fields[campo].widget.attrs.update({"min": minimo, "max": maximo})
        if self.regras["copiar"]:
            self.fields["intervalo_minutos"].help_text = (
                f"Na busca da Shopee, mínimo de {self.regras['intervalo_minimo']} minutos. "
                "Copiando de grupos: 0 = repassa assim que chegar.")
        else:
            self.fields["intervalo_minutos"].help_text = f"No seu plano, mínimo de {self.regras['intervalo_minimo']} minutos."
            self.fields["intervalo_minutos"].widget.attrs["min"] = self.regras["intervalo_minimo"]

    OPCIONAIS_ZERO = ("comissao_minima", "desconto_minimo", "vendas_minimas", "limite_diario")

    def clean_formato_envio(self):
        return self.cleaned_data.get("formato_envio") or self.instance.formato_envio or ConfiguracaoOfertas.FORMATO_FOTO

    def clean_ia_tipo(self):
        return self.cleaned_data.get("ia_tipo") or self.instance.ia_tipo or ConfiguracaoOfertas.IA_CONTEXTUAL

    def clean_comissao_minima(self):
        return self.cleaned_data.get("comissao_minima") or 0

    def clean_desconto_minimo(self):
        return self.cleaned_data.get("desconto_minimo") or 0

    def clean_vendas_minimas(self):
        return self.cleaned_data.get("vendas_minimas") or 0

    def clean_limite_diario(self):
        return self.cleaned_data.get("limite_diario") or 0

    def _numero(self, campo, minimo=None, maximo=None):
        from painel.telas import ler_numero_br

        texto = self.cleaned_data.get(campo, "")
        if not str(texto).strip():
            return None
        valor = ler_numero_br(texto)
        if valor is None or (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
            raise forms.ValidationError("Número inválido.")
        if not valor:
            return None  # 0 = sem filtro; fica em branco na tela
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
        return _marcar_divisa([
            {
                "opcao": opcao,
                "sub_id": self._sub_id_digitado(opcao.data["value"]),
                "canal": str(opcao.data["value"]).endswith("@newsletter"),
            }
            for opcao in self["grupos"]
        ], self.instance.grupos)

    def clean_grupos(self):
        return [{"jid": jid, "nome": self.nomes_dos_grupos.get(jid, "")} for jid in self.cleaned_data.get("grupos", [])]

    def clean_origens(self):
        return [{"jid": jid, "nome": self.nomes_das_origens.get(jid, "")} for jid in self.cleaned_data.get("origens", [])]

    @property
    def linhas_das_origens(self) -> list[dict]:
        return _marcar_divisa(
            [{"opcao": opcao, "canal": str(opcao.data["value"]).endswith("@newsletter")} for opcao in self["origens"]],
            self.instance.origens,
        )

    def clean(self):
        from bot_whatsapp.shopee_ofertas import extrair_id_da_loja

        dados = super().clean()
        regras = self.regras
        if dados.get("modo") == ConfiguracaoOfertas.MODO_COPIAR and not regras["copiar"]:
            self.add_error("modo", "Copiar ofertas de outros grupos e canais é do plano Premium.")
        if len(dados.get("grupos") or []) > regras["grupos"]:
            self.add_error("grupos", f"No seu plano dá para escolher até {regras['grupos']} grupos e canais.")
        if not regras["ia"]:
            dados["ia_ativa"] = False  # a revisão com IA é do Premium
        if (dados.get("modo") != ConfiguracaoOfertas.MODO_COPIAR and dados.get("intervalo_minutos")
                and dados["intervalo_minutos"] < regras["intervalo_minimo"]):
            self.add_error("intervalo_minutos", f"No seu plano o intervalo mínimo é de {regras['intervalo_minimo']} minutos.")
        if dados.get("modo") == ConfiguracaoOfertas.MODO_COPIAR:
            if not dados.get("origens"):
                self.add_error("origens", "Escolha pelo menos um grupo ou canal para copiar.")
            repetidos = {o["jid"] for o in dados.get("origens") or []} & {g["jid"] for g in dados.get("grupos") or []}
            if repetidos:
                nomes = ", ".join(sorted(self.nomes_das_origens.get(j, j) for j in repetidos))
                self.add_error("origens", f"Um grupo não pode ser origem e destino ao mesmo tempo: {nomes}.")
        else:
            tipo = dados.get("tipo_busca")
            if tipo == "palavra_chave" and not (dados.get("palavra_chave") or "").strip():
                self.add_error("palavra_chave", "Informe a palavra-chave.")
            if tipo == "loja" and not extrair_id_da_loja(dados.get("loja", "")):
                self.add_error("loja", "Não achei a loja nesse link. Cole o link da página da loja na Shopee.")
            if tipo == "categoria" and not dados.get("categorias"):
                self.add_error("categorias", "Escolha pelo menos uma categoria.")
            if dados.get("intervalo_minutos") == 0:
                self.add_error("intervalo_minutos", "Na busca da Shopee o intervalo mínimo é 1 minuto.")
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


class RelatorioEmailForm(forms.ModelForm):
    class Meta:
        from .models import RelatorioEmail

        model = RelatorioEmail
        fields = ["ativo", "hora", "emails_extras"]
        widgets = {"emails_extras": forms.TextInput(attrs={"placeholder": "socio@exemplo.com, outro@exemplo.com"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hora"].required = False

    def clean_hora(self):
        # Sem o campo (página aberta antes dele existir), fica o horário que já estava.
        hora = self.cleaned_data.get("hora")
        return self.instance.hora if hora in (None, "") else hora

    def clean_emails_extras(self):
        from django.core.validators import validate_email

        from .relatorio import MAXIMO_EXTRAS

        emails = [e.strip().lower() for e in self.cleaned_data.get("emails_extras", "").replace(";", ",").split(",") if e.strip()]
        if len(emails) > MAXIMO_EXTRAS:
            raise forms.ValidationError(f"Dá para colocar até {MAXIMO_EXTRAS} e-mails extras.")
        for email in emails:
            try:
                validate_email(email)
            except forms.ValidationError:
                raise forms.ValidationError(f"E-mail inválido: {email}")
        return ", ".join(dict.fromkeys(emails))


class CampanhaBotForm(forms.ModelForm):
    """Modo campanha do bot. Em branco = usa o valor da Automação."""

    datas_ligadas = forms.MultipleChoiceField(label="Datas", required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = CampanhaBot
        fields = [
            "datas_ligadas", "intervalo_minutos", "limite_diario", "horario_inicio", "horario_fim",
            "palavra_chave", "comissao_minima", "desconto_minimo",
            "mensagem_ativa", "frase_abertura", "cupom", "pagina_ativa", "titulo_pagina", "texto_pagina", "link_campanha",
            "link_campanha_a_cada",
        ]
        labels = {
            "intervalo_minutos": "Uma oferta a cada (minutos)", "limite_diario": "Máximo de ofertas no dia",
            "horario_inicio": "Das", "horario_fim": "Até", "palavra_chave": "Palavra-chave da campanha",
            "comissao_minima": "Comissão mínima (%)", "desconto_minimo": "Desconto mínimo (%)",
            "frase_abertura": "Frase de abertura", "cupom": "Cupom da campanha",
            "link_campanha": "Link da página da campanha na Shopee", "link_campanha_a_cada": "Enviar a cada",
            "titulo_pagina": "Título", "texto_pagina": "Texto antes do link",
        }
        help_texts = {
            "palavra_chave": "Ex: fone bluetooth. Em branco, o bot busca como na Automação.",
            "frase_abertura": "Vai no começo de cada oferta. Ex: 🔥 11.11 na Shopee",
            "cupom": "Aparece nas ofertas como “Cupom: …”, no lugar do cupom da Automação. Vai também na mensagem da página.",
            "titulo_pagina": "Opcional. Vai no começo da mensagem. Ex: 🔥 11.11 CHEGOU!",
            "texto_pagina": "Em branco, vai “🛍️ 11.11: todas as ofertas num lugar só”.",
            "link_campanha": "Cole o link da página da campanha. O bot troca pelo seu link de afiliado.",
        }
        widgets = {
            "horario_inicio": forms.TimeInput(attrs={**ATTRS_HORA, "placeholder": "00:00"}, format="%H:%M"),
            "horario_fim": forms.TimeInput(attrs={**ATTRS_HORA, "placeholder": "23:59"}, format="%H:%M"),
            "frase_abertura": forms.TextInput(attrs={"placeholder": "🔥 11.11 na Shopee", "data-emoji": ""}),
            "cupom": forms.TextInput(attrs={"placeholder": "Ex: SHOPEE1111", "data-emoji": ""}),
            "link_campanha": forms.URLInput(attrs={"placeholder": "https://shopee.com.br/m/11-11"}),
            "titulo_pagina": forms.TextInput(attrs={"placeholder": "🔥 11.11 CHEGOU!", "data-emoji": ""}),
            "texto_pagina": forms.TextInput(attrs={"placeholder": "🛍️ Todas as ofertas do 11.11 aqui", "data-emoji": ""}),
        }

    def __init__(self, *args, datas=(), regras=None, **kwargs):
        from licencas import planos

        super().__init__(*args, **kwargs)
        self.regras = regras or {**planos.BOT[True], "premium": True}
        self.fields["datas_ligadas"].choices = [(d["chave"], d["nome"]) for d in datas if not d["propria"]]
        self.initial["datas_ligadas"] = list(self.instance.datas_ligadas or [])
        minimo = self.regras["intervalo_minimo"]
        self.fields["intervalo_minutos"].help_text = f"No seu plano, mínimo de {minimo} minutos. Em branco = o da Automação."
        self.fields["limite_diario"].help_text = "Em branco = o da Automação."
        for campo, (menor, maior) in {"intervalo_minutos": (minimo, 240), "limite_diario": (1, 1000),
                                      "comissao_minima": (0, 100), "desconto_minimo": (0, 100),
                                      "link_campanha_a_cada": (3, 100)}.items():
            self.fields[campo].validators += [MinValueValidator(menor), MaxValueValidator(maior)]
            self.fields[campo].widget.attrs.update({"min": menor, "max": maior})
        for campo in ("comissao_minima", "desconto_minimo"):
            self.fields[campo].widget.attrs["placeholder"] = "Como na Automação"

    def clean_datas_ligadas(self):
        # Guarda também as chaves que não aparecem na lista agora (datas fora dos próximos 12 meses).
        visiveis = {c for c, _ in self.fields["datas_ligadas"].choices}
        fora = [c for c in self.instance.datas_ligadas or [] if c not in visiveis]
        return fora + list(self.cleaned_data.get("datas_ligadas") or [])

    def clean_link_campanha(self):
        from ofertas.services import eh_host_da_shopee

        link = (self.cleaned_data.get("link_campanha") or "").strip()
        if link and not eh_host_da_shopee(link):
            raise forms.ValidationError("Cole um link da Shopee (shopee.com.br).")
        return link

    def clean(self):
        dados = super().clean()
        if dados.get("pagina_ativa") and not dados.get("link_campanha") and "link_campanha" not in self.errors:
            self.add_error("link_campanha", "Cole o link da página da campanha para enviar a mensagem.")
        if dados.get("horario_inicio") is None:
            dados["horario_inicio"] = self.instance.horario_inicio
        if dados.get("horario_fim") is None:
            dados["horario_fim"] = self.instance.horario_fim
        if dados["horario_inicio"] >= dados["horario_fim"]:
            self.add_error("horario_fim", "O horário final precisa ser depois do inicial.")
        return dados


class AlertaPrecoForm(forms.ModelForm):
    """Alerta de preço: de quanto em quanto tempo conferir, a queda mínima e onde avisar."""

    grupos = forms.MultipleChoiceField(label="Grupos e canais", required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = AlertaPreco
        fields = ["intervalo_minutos", "queda_minima", "avisar_email", "enviar_grupos", "grupos", "modelo_mensagem"]
        labels = {"intervalo_minutos": "Conferir os preços a cada", "queda_minima": "Avisar quando cair pelo menos (%)",
                  "modelo_mensagem": "Mensagem"}
        widgets = {"modelo_mensagem": forms.Textarea(attrs={"rows": 9, "data-emoji": ""})}

    def __init__(self, *args, grupos_disponiveis=(), regras=None, **kwargs):
        from licencas import planos

        super().__init__(*args, **kwargs)
        self.regras = regras or {**planos.BOT[True], "premium": True}
        minimo = self.regras["alerta_intervalo_minimo"]
        self.fields["intervalo_minutos"].choices = [(v, n) for v, n in AlertaPreco.INTERVALOS if v >= minimo]
        self.fields["intervalo_minutos"].widget = forms.Select(choices=self.fields["intervalo_minutos"].choices)
        self.fields["queda_minima"].validators += [MinValueValidator(1), MaxValueValidator(90)]
        self.fields["queda_minima"].widget.attrs.update({"min": 1, "max": 90})
        disponiveis = {g["jid"]: g.get("nome", g["jid"]) for g in grupos_disponiveis if g.get("jid") and g.get("pode_postar", True)}
        for g in self.instance.grupos or []:
            disponiveis.setdefault(g.get("jid"), g.get("nome", ""))
        self.nomes_dos_grupos = disponiveis
        self.fields["grupos"].choices = list(disponiveis.items())
        self.initial["grupos"] = [g.get("jid") for g in self.instance.grupos or []]

    def clean_intervalo_minutos(self):
        valor = self.cleaned_data["intervalo_minutos"]
        if valor < self.regras["alerta_intervalo_minimo"]:
            raise forms.ValidationError("Esse intervalo não está no seu plano.")
        return valor

    def clean_grupos(self):
        jids = self.cleaned_data.get("grupos") or []
        if len(jids) > self.regras["grupos"]:
            raise forms.ValidationError(f"No seu plano dá para escolher até {self.regras['grupos']} grupos e canais.")
        return [{"jid": j, "nome": self.nomes_dos_grupos.get(j, "")} for j in jids]

    def clean(self):
        dados = super().clean()
        if dados.get("enviar_grupos") and not dados.get("grupos") and "grupos" not in self.errors:
            self.add_error("grupos", "Escolha pelo menos um grupo para postar os alertas.")
        return dados
