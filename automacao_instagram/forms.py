from django import forms

from .models import AutomacaoComentario, AutomacaoStory, ContaInstagramConectada


class ContaInstagramForm(forms.ModelForm):
    class Meta:
        model = ContaInstagramConectada
        fields = ("nome_exibicao", "instagram_business_account_id", "access_token")
        labels = {
            "nome_exibicao": "Nome de exibição",
            "instagram_business_account_id": "ID da conta comercial do Instagram",
            "access_token": "Access token",
        }
        widgets = {
            "access_token": forms.PasswordInput(render_value=True),
        }


class AutomacaoComentarioForm(forms.ModelForm):
    """A escolha do post (instagram_media_id) acontece antes desse form, na etapa
    de seleção (ver views.automacao_nova) - aqui só o resto dos dados da regra."""

    class Meta:
        model = AutomacaoComentario
        fields = (
            "nome", "palavras_chave",
            "responder_comentario", "texto_resposta",
            "enviar_dm", "texto_dm",
            "ativa",
        )
        labels = {
            "nome": "Nome da automação",
            "palavras_chave": "Palavras-chave (uma por linha)",
            "responder_comentario": "Responder o comentário publicamente",
            "texto_resposta": "Texto da resposta pública",
            "enviar_dm": "Enviar mensagem direta (DM)",
            "texto_dm": "Texto da DM",
            "ativa": "Automação ativa",
        }
        widgets = {
            "palavras_chave": forms.Textarea(attrs={"rows": 4, "placeholder": "quero\nmanda\nenvia"}),
            "texto_resposta": forms.Textarea(attrs={"rows": 3}),
            "texto_dm": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("responder_comentario") and not cleaned.get("enviar_dm"):
            raise forms.ValidationError("Marque pelo menos uma ação: responder o comentário e/ou enviar DM.")
        if cleaned.get("responder_comentario") and not cleaned.get("texto_resposta"):
            self.add_error("texto_resposta", "Preencha o texto da resposta pública.")
        if cleaned.get("enviar_dm") and not cleaned.get("texto_dm"):
            self.add_error("texto_dm", "Preencha o texto da DM.")
        return cleaned


class AutomacaoStoryForm(forms.ModelForm):
    """A escolha do story (instagram_story_media_id) acontece antes desse form, na
    etapa de seleção (ver views._automacao_nova_story) - aqui só o resto dos dados da
    regra. Se o story escolhido não tem link de produto detectado, a view valida (não
    dá pra saber isso aqui dentro do form)."""

    class Meta:
        model = AutomacaoStory
        fields = ("nome", "modo_resposta", "texto_personalizado", "ativa")
        labels = {
            "nome": "Nome da automação",
            "modo_resposta": "O que enviar por DM pra quem responder",
            "texto_personalizado": "Mensagem personalizada",
            "ativa": "Automação ativa",
        }
        widgets = {
            "modo_resposta": forms.RadioSelect,
            "texto_personalizado": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("modo_resposta") == AutomacaoStory.MODO_PERSONALIZADA and not cleaned.get("texto_personalizado"):
            self.add_error("texto_personalizado", "Preencha o texto da mensagem.")
        return cleaned


class ProcessarComentarioManualForm(forms.Form):
    """Reprocessa um comentário que o worker não pegou sozinho (ex: perdido por
    alguma falha temporária) - o ID e o texto precisam ser conferidos manualmente
    (na própria página do post, ou no código-fonte/rede do navegador)."""

    instagram_comment_id = forms.CharField(label="ID do comentário")
    texto_comentario = forms.CharField(label="Texto do comentário", widget=forms.Textarea(attrs={"rows": 2}))
    autor_username = forms.CharField(label="Usuário de quem comentou", required=False)
