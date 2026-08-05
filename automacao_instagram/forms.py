from django import forms

from .models import AutomacaoComentario, ContaInstagramConectada


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
