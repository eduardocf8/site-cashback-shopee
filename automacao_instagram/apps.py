from django.apps import AppConfig


class AutomacaoInstagramConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "automacao_instagram"

    def ready(self):
        from . import padrao_story

        padrao_story.conectar()
